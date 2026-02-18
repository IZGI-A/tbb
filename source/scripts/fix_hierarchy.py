"""Migration: rebuild main_statement hierarchy in financial_statements.

Infers hierarchy from numbering conventions and rewrites main_statement
using a ClickHouse INSERT INTO ... SELECT with a multiIf expression.

Previous runs covered sections 1-5, 7-8 (Arabic+Roman numbering).
This run covers dipnot sections (letter-based numbering).

Usage:
    docker compose exec fastapi python -m scripts.fix_hierarchy
"""

import re
import logging

from clickhouse_driver import Client
from config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# --- Already migrated (Arabic+Roman) — kept for reference / re-runs ---
ROOTS = ()

_ROMAN = {
    1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII",
    8: "VIII", 9: "IX", 10: "X", 11: "XI", 12: "XII", 13: "XIII",
    14: "XIV", 15: "XV", 16: "XVI", 17: "XVII", 18: "XVIII",
    19: "XIX", 20: "XX", 21: "XXI", 22: "XXII", 23: "XXIII",
    24: "XXIV", 25: "XXV",
}

_ARABIC_PREFIX_RE = re.compile(r"^(\d+(?:\.\d+)*)")


def _find_roman_item(first_num: int, items: list[str]) -> str | None:
    roman = _ROMAN.get(first_num)
    if not roman:
        return None
    for item in items:
        if item.startswith(f"{roman}.") or item.startswith(f"{roman} "):
            return item
    return None


def _find_item_by_prefix(prefix: str, items: list[str]) -> str | None:
    for item in items:
        if item.startswith(prefix + " "):
            return item
        if item.startswith(prefix + "."):
            rest = item[len(prefix) + 1:]
            if rest and not rest[0].isdigit():
                return item
    return None


def _esc(s: str) -> str:
    """Escape single quotes for ClickHouse SQL strings."""
    return s.replace("\\", "\\\\").replace("'", "\\'")


def build_changes(ch: Client) -> list[tuple[str, str, str]]:
    """Build list of (root, child_statement, new_main_statement) — Arabic+Roman sections."""
    changes: list[tuple[str, str, str]] = []

    for root in ROOTS:
        rows = ch.execute(
            "SELECT DISTINCT child_statement FROM tbb.financial_statements FINAL "
            "WHERE main_statement = %(root)s ORDER BY child_statement",
            {"root": root},
        )
        items = [r[0] for r in rows if r[0]]

        for child in items:
            m = _ARABIC_PREFIX_RE.match(child)
            if not m:
                continue

            num_str = m.group(1).rstrip(".")
            parts = num_str.split(".")
            path = [root]

            first_num = int(parts[0])
            roman_item = _find_roman_item(first_num, items)
            if roman_item:
                path.append(roman_item)

            for depth in range(1, len(parts) - 1):
                intermediate_prefix = ".".join(parts[: depth + 1])
                found = _find_item_by_prefix(intermediate_prefix, items)
                if found:
                    path.append(found)

            new_main = " > ".join(path)
            if new_main != root:
                changes.append((root, child, new_main))

    return changes


# --- Dipnot sections (letter-based numbering) ---

DIPNOT_ROOTS = (
    "1. MALİ BÜNYE İLE İLGİLİ DİPNOTLAR",
    "2. AKTİFLERLE İLGİLİ DİPNOTLAR",
    "3. PASİFLERLE İLGİLİ DİPNOTLAR",
    "4. NAZIM HESAPLARLA İLGİLİ DİPNOTLAR",
    "5. GELİR TABLOSU İLE İLGİLİ DİPNOTLAR",
    "6. RİSK GRUBUNA AİT DİPNOTLAR",
    "9. DİPNOTLAR",
)

# Matches: "2. f.10 iv)", "2.a.3.i)", "RİSK-1. c.1)", "2. ğ.3)" etc.
_DIPNOT_RE = re.compile(
    r"^(RİSK-\d+|\d+)"       # group 1: prefix ("2" or "RİSK-1")
    r"[.\s]+"                  # separator
    r"([a-zçğıöşü])"          # group 2: letter
    r"(?:"
        r"[.\s]+(\d+)"        # group 3: optional sub-number
        r"(?:[.\s]+([ivx]+))?" # group 4: optional roman sub-sub
    r")?"
    r"\)",                     # closing paren
)


def build_dipnot_changes(ch: Client) -> list[tuple[str, str, str]]:
    """Build hierarchy changes for dipnot sections (letter-based numbering).

    Pattern examples:
      "2. a) ..."         → stays at root (letter only, no sub-number)
      "2. f.1) ..."       → root > 2.f
      "2. f.10 i) ..."    → root > 2.f > 2.f.10
      "2.a.3.ii) ..."     → root > 2.a > 2.a.3
      "RİSK-1. c.1) ..." → root > RİSK-1.c
    """
    changes: list[tuple[str, str, str]] = []

    for root in DIPNOT_ROOTS:
        rows = ch.execute(
            "SELECT DISTINCT child_statement FROM tbb.financial_statements FINAL "
            "WHERE main_statement = %(root)s ORDER BY child_statement",
            {"root": root},
        )
        items = [r[0] for r in rows if r[0]]

        for child in items:
            m = _DIPNOT_RE.match(child)
            if not m:
                continue

            prefix = m.group(1)
            letter = m.group(2)
            sub = m.group(3)
            subsub = m.group(4)

            path = [root]

            if sub:
                # Has sub-number → letter group is intermediate
                path.append(f"{prefix}.{letter}")

                if subsub:
                    # Has roman sub-sub → sub-number is also intermediate
                    path.append(f"{prefix}.{letter}.{sub}")

            new_main = " > ".join(path)
            if new_main != root:
                changes.append((root, child, new_main))

    return changes


def build_multiif_expr(changes: list[tuple[str, str, str]]) -> str:
    """Build a ClickHouse multiIf expression for main_statement transformation."""
    if not changes:
        return "main_statement"

    conditions = []
    for root, child, new_main in changes:
        cond = (
            f"main_statement = '{_esc(root)}' "
            f"AND child_statement = '{_esc(child)}'"
        )
        conditions.append(f"    {cond}, '{_esc(new_main)}'")

    return "multiIf(\n" + ",\n".join(conditions) + ",\n    main_statement\n)"


def migrate(ch: Client) -> None:
    """Apply hierarchy changes using temp table + swap."""

    initial_count = ch.execute("SELECT count() FROM tbb.financial_statements FINAL")[0][0]
    logger.info("Initial row count: %d", initial_count)

    logger.info("Building hierarchy mapping...")
    changes = build_changes(ch)
    dipnot_changes = build_dipnot_changes(ch)
    changes.extend(dipnot_changes)
    logger.info(
        "Found %d changes (%d Arabic+Roman, %d dipnot)",
        len(changes), len(changes) - len(dipnot_changes), len(dipnot_changes),
    )

    for root, child, new_main in changes[:15]:
        logger.info("  %s | %s → %s", child, root, new_main)
    if len(changes) > 15:
        logger.info("  ... and %d more", len(changes) - 15)

    if not changes:
        logger.info("No changes needed.")
        return

    multiif = build_multiif_expr(changes)

    # Create temp table with same structure
    logger.info("Creating temp table...")
    ch.execute("DROP TABLE IF EXISTS tbb.financial_statements_tmp")
    ch.execute("CREATE TABLE tbb.financial_statements_tmp AS tbb.financial_statements")

    # Insert transformed data
    logger.info("Inserting transformed data into temp table...")
    insert_query = f"""
        INSERT INTO tbb.financial_statements_tmp
        SELECT
            accounting_system,
            {multiif} AS main_statement,
            child_statement,
            bank_name,
            year_id,
            month_id,
            amount_tc,
            amount_fc,
            amount_total,
            crawl_timestamp
        FROM tbb.financial_statements FINAL
    """
    ch.execute(insert_query)

    tmp_count = ch.execute("SELECT count() FROM tbb.financial_statements_tmp FINAL")[0][0]
    logger.info("Temp table row count: %d", tmp_count)

    if tmp_count == 0:
        logger.error("Temp table is empty! Aborting.")
        ch.execute("DROP TABLE tbb.financial_statements_tmp")
        return

    # Swap tables
    logger.info("Swapping tables...")
    ch.execute(
        "EXCHANGE TABLES tbb.financial_statements AND tbb.financial_statements_tmp"
    )

    # Drop old table (now named _tmp)
    ch.execute("DROP TABLE tbb.financial_statements_tmp")

    # Optimize
    logger.info("Optimizing table...")
    ch.execute("OPTIMIZE TABLE tbb.financial_statements FINAL")

    # Verify
    final_count = ch.execute("SELECT count() FROM tbb.financial_statements FINAL")[0][0]
    logger.info("Done. Row count: %d → %d", initial_count, final_count)

    # Show sample hierarchical rows
    sample = ch.execute(
        "SELECT DISTINCT main_statement, child_statement "
        "FROM tbb.financial_statements FINAL "
        "WHERE main_statement LIKE '%%DİPNOT%%>%%' OR main_statement LIKE '%%RİSK%%>%%' "
        "ORDER BY main_statement LIMIT 20"
    )
    logger.info("Sample dipnot hierarchical rows:")
    for s in sample:
        logger.info("  main: %s | child: %s", s[0], s[1])


def main():
    ch = Client(
        host=settings.CLICKHOUSE_HOST,
        port=settings.CLICKHOUSE_PORT,
        database=settings.CLICKHOUSE_DB,
        user=settings.CLICKHOUSE_USER,
        password=settings.CLICKHOUSE_PASSWORD,
    )
    migrate(ch)


if __name__ == "__main__":
    main()

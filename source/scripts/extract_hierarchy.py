"""Map flat main_statements to their TBB hierarchy paths and migrate.

Uses the TBB public API (no Selenium needed) to fetch the full item hierarchy,
then matches flat main_statements by their child_statements to disambiguate
items that appear at multiple hierarchy locations.

Usage:
    docker compose exec airflow-scheduler python /opt/airflow/source/scripts/extract_hierarchy.py
"""

import json
import logging
import os
import re
import sys

import requests
from clickhouse_driver import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Regex to strip item IDs like "(16330)" from names
_ITEM_ID_RE = re.compile(r"\(\d+\)\s*$")
_ITEM_ID_FALLBACK_RE = re.compile(r"\b(\d{4,})\)\s*$")

TBB_API_URL = "https://verisistemi.tbb.org.tr/api/router"

# Known DB section roots (used to determine path start)
KNOWN_SECTIONS = {
    "1. VARLIKLAR", "2. YÜKÜMLÜLÜKLER", "3. NAZIM HESAPLAR",
    "4. GELİR-GİDER TABLOSU",
    "5. ÖZKAYNAKLARDA MUHASEBELEŞTİRİLEN GELİR GİDER KALEMLERİ",
    "6. ÖZKAYNAK DEĞİŞİM TABLOSU", "7. NAKİT AKIŞ TABLOSU",
    "8. KAR DAĞITIM TABLOSU", "9. DİPNOTLAR",
}
KNOWN_DIPNOTS = {
    "1. MALİ BÜNYE İLE İLGİLİ DİPNOTLAR",
    "2. AKTİFLERLE İLGİLİ DİPNOTLAR",
    "3. PASİFLERLE İLGİLİ DİPNOTLAR",
    "4. NAZIM HESAPLARLA İLGİLİ DİPNOTLAR",
    "5. GELİR TABLOSU İLE İLGİLİ DİPNOTLAR",
    "6. RİSK GRUBUNA AİT DİPNOTLAR",
}
ALL_KNOWN = KNOWN_SECTIONS | KNOWN_DIPNOTS


def _clean(name: str) -> str:
    """Clean item name: remove trailing IDs, whitespace."""
    name = _ITEM_ID_RE.sub("", name)
    name = _ITEM_ID_FALLBACK_RE.sub("", name)
    return name.strip()


def _esc(s: str) -> str:
    """Escape single quotes for ClickHouse SQL strings."""
    return s.replace("\\", "\\\\").replace("'", "\\'")


def fetch_tbb_hierarchy() -> list[dict]:
    """Fetch all mali tablolar items from TBB API."""
    logger.info("Fetching TBB hierarchy from API...")
    resp = requests.post(
        TBB_API_URL,
        json={"route": "maliTablolarAll"},
        headers={
            "Content-Type": "application/json",
            "token": "asd",
            "role": "1",
            "LANG": "tr",
        },
        verify=False,
        timeout=120,
    )
    resp.raise_for_status()
    items = resp.json()
    logger.info("Fetched %d items from TBB API", len(items))
    return items


def build_hierarchy_path(item: dict, lookup: dict[int, dict]) -> str:
    """Walk UST_UK chain to build full hierarchy path for an item.

    Returns path from the deepest known DB section down to the item itself.
    """
    name = _clean(item.get("TR_ADI", ""))

    # Walk up ancestors
    ancestors = []
    cur = item.get("UST_UK")
    visited = set()
    while cur and cur in lookup and cur not in visited:
        visited.add(cur)
        parent = lookup[cur]
        ancestors.append(_clean(parent.get("TR_ADI", "")))
        cur = parent.get("UST_UK")

    # Reverse to get top-down order
    ancestors.reverse()

    # Find deepest known section to start the path from
    start_idx = 0
    for i, anc in enumerate(ancestors):
        if anc in ALL_KNOWN:
            start_idx = i

    path_parts = ancestors[start_idx:] + [name]
    return " > ".join(path_parts)


def match_flat_statements(
    ch: Client,
    tbb_items: list[dict],
) -> dict[str, str]:
    """Match flat main_statements to their hierarchy paths.

    Uses child_statement overlap to disambiguate items appearing
    at multiple hierarchy locations.
    """
    # Build lookup and children map
    lookup = {item["UNIQUE_KEY"]: item for item in tbb_items if item.get("UNIQUE_KEY")}
    children_map: dict[int, set[str]] = {}
    for item in tbb_items:
        ust = item.get("UST_UK")
        if ust:
            child_name = _clean(item.get("TR_ADI", ""))
            if child_name:
                children_map.setdefault(ust, set()).add(child_name)

    # Get flat main_statements from DB
    rows = ch.execute("""
        SELECT DISTINCT main_statement
        FROM tbb.financial_statements FINAL
        WHERE main_statement NOT LIKE '%>%'
        ORDER BY main_statement
    """)
    flat_mains = {r[0] for r in rows if r[0]}
    logger.info("Found %d flat main_statements in DB", len(flat_mains))

    # Exclude known section roots — they are already correct
    flat_mains -= ALL_KNOWN
    logger.info("After excluding known sections: %d flat main_statements", len(flat_mains))

    # Build name → list of (unique_key, path) for TFRS9-SOLO items
    solo_root = "TFRS9-SOLO"
    name_to_candidates: dict[str, list[tuple[int, str]]] = {}
    for item in tbb_items:
        if solo_root not in item.get("ROOT_TR_ADI", ""):
            continue
        name = _clean(item.get("TR_ADI", ""))
        if name not in flat_mains:
            continue

        path = build_hierarchy_path(item, lookup)
        name_to_candidates.setdefault(name, []).append(
            (item["UNIQUE_KEY"], path)
        )

    logger.info(
        "Found %d flat names in TBB hierarchy (%d unique, %d ambiguous)",
        len(name_to_candidates),
        sum(1 for v in name_to_candidates.values() if len(v) == 1),
        sum(1 for v in name_to_candidates.values() if len(v) > 1),
    )

    # Match each flat main_statement to its correct path
    mapping: dict[str, str] = {}
    unmatched = []

    for flat_main in sorted(flat_mains):
        candidates = name_to_candidates.get(flat_main, [])
        if not candidates:
            unmatched.append(flat_main)
            continue

        if len(candidates) == 1:
            # Unique match
            _, path = candidates[0]
            if path != flat_main:
                mapping[flat_main] = path
            continue

        # Ambiguous: use child_statement matching
        child_rows = ch.execute(
            "SELECT DISTINCT child_statement FROM tbb.financial_statements FINAL "
            "WHERE main_statement = %(ms)s",
            {"ms": flat_main},
        )
        db_children = {r[0] for r in child_rows if r[0]}

        best_uk, best_path, best_overlap = None, None, -1
        for uk, path in candidates:
            tbb_children = children_map.get(uk, set())
            overlap = len(db_children & tbb_children)
            if overlap > best_overlap:
                best_uk, best_path, best_overlap = uk, path, overlap

        if best_path and best_path != flat_main:
            mapping[flat_main] = best_path

    logger.info("Matched %d flat main_statements to hierarchy paths", len(mapping))
    if unmatched:
        logger.info("Unmatched: %d items", len(unmatched))
        for u in unmatched[:10]:
            logger.info("  %s", u)

    return mapping


def migrate(ch: Client, mapping: dict[str, str]) -> None:
    """Apply hierarchy changes using a mapping table + LEFT JOIN.

    Uses a temporary mapping table instead of a giant multiIf expression,
    which would exceed ClickHouse memory limits with 400+ long conditions.
    """
    if not mapping:
        logger.info("No changes to apply.")
        return

    initial_count = ch.execute(
        "SELECT count() FROM tbb.financial_statements FINAL"
    )[0][0]
    logger.info("Initial row count: %d", initial_count)

    # Show sample changes
    for old, new in list(mapping.items())[:15]:
        logger.info("  %s → %s", old, new)
    if len(mapping) > 15:
        logger.info("  ... and %d more", len(mapping) - 15)

    # Create mapping table
    logger.info("Creating mapping table with %d entries...", len(mapping))
    ch.execute("DROP TABLE IF EXISTS tbb._hierarchy_map")
    ch.execute("""
        CREATE TABLE tbb._hierarchy_map (
            old_main String,
            new_main String
        ) ENGINE = MergeTree() ORDER BY old_main
    """)
    ch.execute(
        "INSERT INTO tbb._hierarchy_map (old_main, new_main) VALUES",
        [{"old_main": old, "new_main": new} for old, new in mapping.items()],
    )
    map_count = ch.execute("SELECT count() FROM tbb._hierarchy_map")[0][0]
    logger.info("Mapping table has %d rows", map_count)

    # Create temp table with same structure
    logger.info("Creating temp table...")
    ch.execute("DROP TABLE IF EXISTS tbb.financial_statements_tmp")
    ch.execute("CREATE TABLE tbb.financial_statements_tmp AS tbb.financial_statements")

    # Insert transformed data using LEFT JOIN
    logger.info("Inserting transformed data (JOIN approach)...")
    ch.execute("""
        INSERT INTO tbb.financial_statements_tmp
        SELECT
            f.accounting_system,
            if(m.new_main != '', m.new_main, f.main_statement) AS main_statement,
            f.child_statement,
            f.bank_name,
            f.year_id,
            f.month_id,
            f.amount_tc,
            f.amount_fc,
            f.amount_total,
            f.crawl_timestamp
        FROM (SELECT * FROM tbb.financial_statements FINAL) AS f
        LEFT JOIN tbb._hierarchy_map AS m
            ON f.main_statement = m.old_main
    """)

    tmp_count = ch.execute(
        "SELECT count() FROM tbb.financial_statements_tmp FINAL"
    )[0][0]
    logger.info("Temp table row count: %d", tmp_count)

    if tmp_count == 0:
        logger.error("Temp table is empty! Aborting.")
        ch.execute("DROP TABLE tbb.financial_statements_tmp")
        ch.execute("DROP TABLE tbb._hierarchy_map")
        return

    # Swap tables
    logger.info("Swapping tables...")
    ch.execute(
        "EXCHANGE TABLES tbb.financial_statements AND tbb.financial_statements_tmp"
    )
    ch.execute("DROP TABLE tbb.financial_statements_tmp")
    ch.execute("DROP TABLE tbb._hierarchy_map")

    # Optimize
    logger.info("Optimizing table...")
    ch.execute("OPTIMIZE TABLE tbb.financial_statements FINAL")

    # Verify
    final_count = ch.execute(
        "SELECT count() FROM tbb.financial_statements FINAL"
    )[0][0]
    logger.info("Done. Row count: %d → %d", initial_count, final_count)

    # Show remaining flat main_statements
    remaining = ch.execute("""
        SELECT DISTINCT main_statement
        FROM tbb.financial_statements FINAL
        WHERE main_statement NOT LIKE '%>%'
        ORDER BY main_statement
    """)
    remaining_flat = [r[0] for r in remaining if r[0]]
    logger.info("Remaining flat main_statements: %d", len(remaining_flat))
    for r in remaining_flat[:20]:
        logger.info("  %s", r)


def main():
    ch = Client(
        host=settings.CLICKHOUSE_HOST,
        port=settings.CLICKHOUSE_PORT,
        database=settings.CLICKHOUSE_DB,
        user=settings.CLICKHOUSE_USER,
        password=settings.CLICKHOUSE_PASSWORD,
    )

    # Step 1: Fetch hierarchy from TBB API
    tbb_items = fetch_tbb_hierarchy()

    # Step 2: Build mapping
    mapping = match_flat_statements(ch, tbb_items)

    # Step 3: Save mapping for reference
    os.makedirs("/tmp/tbb_staging", exist_ok=True)
    out_path = "/tmp/tbb_staging/hierarchy_mapping.json"
    with open(out_path, "w") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    logger.info("Saved mapping to %s (%d entries)", out_path, len(mapping))

    # Step 4: Apply migration
    migrate(ch, mapping)


if __name__ == "__main__":
    main()

"""Fix missing hierarchy paths in financial_statements.

Some items appear at multiple hierarchy locations in TBB (e.g., under both
"Cari Dönem" and "Önceki Dönem"). The initial migration picked only ONE path.
This script reassigns child_statements to their correct parent paths.

Usage:
    docker compose exec airflow-scheduler python /opt/airflow/source/scripts/fix_missing_paths.py
"""

import json
import logging
import os
import re
import sys
from collections import defaultdict

import requests
from clickhouse_driver import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_ITEM_ID_RE = re.compile(r"\(\d+\)\s*$")
_ITEM_ID_FALLBACK_RE = re.compile(r"\b(\d{4,})\)\s*$")

TBB_API_URL = "https://verisistemi.tbb.org.tr/api/router"

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
    name = _ITEM_ID_RE.sub("", name)
    name = _ITEM_ID_FALLBACK_RE.sub("", name)
    return name.strip()


def fetch_tbb_hierarchy() -> list[dict]:
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


def build_path(item: dict, lookup: dict[int, dict]) -> str:
    name = _clean(item.get("TR_ADI", ""))
    ancestors = []
    cur = item.get("UST_UK")
    visited = set()
    while cur and cur in lookup and cur not in visited:
        visited.add(cur)
        parent = lookup[cur]
        ancestors.append(_clean(parent.get("TR_ADI", "")))
        cur = parent.get("UST_UK")
    ancestors.reverse()
    start_idx = 0
    for i, anc in enumerate(ancestors):
        if anc in ALL_KNOWN:
            start_idx = i
    path_parts = ancestors[start_idx:] + [name]
    return " > ".join(path_parts)


def find_reassign_pairs(ch: Client, tbb_items: list[dict]) -> list[tuple[str, str, str]]:
    """Find (old_main, child_statement, new_main) pairs to reassign."""
    lookup = {item["UNIQUE_KEY"]: item for item in tbb_items if item.get("UNIQUE_KEY")}

    # Build children_map: parent_uk -> set of child names
    children_map: dict[int, set[str]] = defaultdict(set)
    for item in tbb_items:
        ust = item.get("UST_UK")
        if ust:
            child_name = _clean(item.get("TR_ADI", ""))
            if child_name:
                children_map[ust].add(child_name)

    # Get all main_statements with '>' from DB
    rows = ch.execute("""
        SELECT DISTINCT main_statement
        FROM tbb.financial_statements FINAL
        WHERE main_statement LIKE '%>%'
        ORDER BY main_statement
    """)
    db_mains_with_path = {r[0] for r in rows if r[0]}
    logger.info("DB main_statements with path: %d", len(db_mains_with_path))

    # Get leaf items from paths
    leaf_names = set()
    for ms in db_mains_with_path:
        leaf = ms.split(" > ")[-1]
        leaf_names.add(leaf)
    logger.info("Unique leaf names in paths: %d", len(leaf_names))

    # For each leaf name, find ALL valid TBB paths (TFRS9-SOLO only)
    solo_root = "TFRS9-SOLO"
    name_to_all_paths: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for item in tbb_items:
        if solo_root not in item.get("ROOT_TR_ADI", ""):
            continue
        name = _clean(item.get("TR_ADI", ""))
        if name not in leaf_names:
            continue
        path = build_path(item, lookup)
        name_to_all_paths[name].append((item["UNIQUE_KEY"], path))

    # Find items with existing path in DB but missing other valid paths
    items_with_missing = []
    for name, candidates in name_to_all_paths.items():
        existing = set()
        for uk, path in candidates:
            if path in db_mains_with_path:
                existing.add(path)

        missing = set()
        for uk, path in candidates:
            if path not in existing and path != name:
                missing.add(path)

        if existing and missing:
            items_with_missing.append((name, existing, missing, candidates))

    logger.info("Items with missing paths: %d", len(items_with_missing))
    total_missing = sum(len(m) for _, _, m, _ in items_with_missing)
    logger.info("Total missing paths: %d", total_missing)

    # For each missing path, find child_statements to reassign
    reassign_pairs = []

    for name, existing_paths, missing_paths_set, candidates in items_with_missing:
        # Build path -> TBB children mapping
        path_to_children: dict[str, set[str]] = {}
        for uk, path in candidates:
            tbb_children = children_map.get(uk, set())
            if tbb_children:
                path_to_children[path] = tbb_children

        # Check each existing path's DB children
        for existing_path in existing_paths:
            child_rows = ch.execute(
                "SELECT DISTINCT child_statement FROM tbb.financial_statements FINAL "
                "WHERE main_statement = %(ms)s",
                {"ms": existing_path},
            )
            db_children = {r[0] for r in child_rows if r[0]}

            for missing_path in missing_paths_set:
                expected_children = path_to_children.get(missing_path, set())
                if not expected_children:
                    continue

                existing_expected = path_to_children.get(existing_path, set())
                # Children in DB that belong to missing_path but NOT to existing_path
                truly_wrong = (db_children & expected_children) - existing_expected

                for child in truly_wrong:
                    reassign_pairs.append((existing_path, child, missing_path))

    logger.info("Reassignable pairs: %d", len(reassign_pairs))
    return reassign_pairs


def migrate(ch: Client, pairs: list[tuple[str, str, str]]) -> None:
    """Apply reassignment using mapping table + LEFT JOIN on (main_statement, child_statement)."""
    if not pairs:
        logger.info("No changes to apply.")
        return

    initial_count = ch.execute("SELECT count() FROM tbb.financial_statements FINAL")[0][0]
    logger.info("Initial row count: %d", initial_count)

    # Show sample changes
    for old, child, new in pairs[:15]:
        logger.info("  %s | %s -> %s", child, old, new)
    if len(pairs) > 15:
        logger.info("  ... and %d more", len(pairs) - 15)

    # Create mapping table
    logger.info("Creating mapping table with %d entries...", len(pairs))
    ch.execute("DROP TABLE IF EXISTS tbb._path_fix_map")
    ch.execute("""
        CREATE TABLE tbb._path_fix_map (
            old_main String,
            child_stmt String,
            new_main String
        ) ENGINE = MergeTree() ORDER BY (old_main, child_stmt)
    """)
    ch.execute(
        "INSERT INTO tbb._path_fix_map (old_main, child_stmt, new_main) VALUES",
        [{"old_main": old, "child_stmt": child, "new_main": new} for old, child, new in pairs],
    )
    map_count = ch.execute("SELECT count() FROM tbb._path_fix_map")[0][0]
    logger.info("Mapping table has %d rows", map_count)

    # Create temp table
    logger.info("Creating temp table...")
    ch.execute("DROP TABLE IF EXISTS tbb.financial_statements_tmp")
    ch.execute("CREATE TABLE tbb.financial_statements_tmp AS tbb.financial_statements")

    # Insert transformed data using LEFT JOIN on both main_statement AND child_statement
    logger.info("Inserting transformed data (JOIN on main+child)...")
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
        LEFT JOIN tbb._path_fix_map AS m
            ON f.main_statement = m.old_main AND f.child_statement = m.child_stmt
    """)

    tmp_count = ch.execute("SELECT count() FROM tbb.financial_statements_tmp FINAL")[0][0]
    logger.info("Temp table row count: %d", tmp_count)

    if tmp_count == 0:
        logger.error("Temp table is empty! Aborting.")
        ch.execute("DROP TABLE tbb.financial_statements_tmp")
        ch.execute("DROP TABLE tbb._path_fix_map")
        return

    # Swap tables
    logger.info("Swapping tables...")
    ch.execute("EXCHANGE TABLES tbb.financial_statements AND tbb.financial_statements_tmp")
    ch.execute("DROP TABLE tbb.financial_statements_tmp")
    ch.execute("DROP TABLE tbb._path_fix_map")

    # Optimize
    logger.info("Optimizing table...")
    ch.execute("OPTIMIZE TABLE tbb.financial_statements FINAL")

    # Verify
    final_count = ch.execute("SELECT count() FROM tbb.financial_statements FINAL")[0][0]
    logger.info("Done. Row count: %d -> %d", initial_count, final_count)


def main():
    ch = Client(
        host=settings.CLICKHOUSE_HOST,
        port=settings.CLICKHOUSE_PORT,
        database=settings.CLICKHOUSE_DB,
        user=settings.CLICKHOUSE_USER,
        password=settings.CLICKHOUSE_PASSWORD,
    )

    # Step 1: Fetch hierarchy
    tbb_items = fetch_tbb_hierarchy()

    # Step 2: Find reassignment pairs
    pairs = find_reassign_pairs(ch, tbb_items)

    # Step 3: Save for reference
    os.makedirs("/tmp/tbb_staging", exist_ok=True)
    out_path = "/tmp/tbb_staging/reassign_pairs.json"
    with open(out_path, "w") as f:
        json.dump(pairs, f, ensure_ascii=False, indent=2)
    logger.info("Saved %d pairs to %s", len(pairs), out_path)

    # Step 4: Apply migration
    migrate(ch, pairs)

    # Step 5: Show example for user's reported item
    rows = ch.execute("""
        SELECT DISTINCT main_statement
        FROM tbb.financial_statements FINAL
        WHERE main_statement LIKE '%Türev Finansal Araçlardan Alacaklar%'
        ORDER BY main_statement
    """)
    logger.info("Paths containing 'Türev Finansal Araçlardan Alacaklar':")
    for r in rows:
        logger.info("  %s", r[0])


if __name__ == "__main__":
    main()

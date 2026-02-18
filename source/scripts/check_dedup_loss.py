"""Check how many hierarchy paths are lost due to ReplacingMergeTree deduplication.

Items where Cari/Önceki Dönem share identical child_statements lose one
context's data when main_statement was flat.
"""

import re
import sys
import os
from collections import defaultdict

import requests
from clickhouse_driver import Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

_ITEM_ID_RE = re.compile(r"\(\d+\)\s*$")
_ITEM_ID_FALLBACK_RE = re.compile(r"\b(\d{4,})\)\s*$")

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


def _clean(name):
    name = _ITEM_ID_RE.sub("", name)
    name = _ITEM_ID_FALLBACK_RE.sub("", name)
    return name.strip()


def main():
    ch = Client(
        host=settings.CLICKHOUSE_HOST,
        port=settings.CLICKHOUSE_PORT,
        database=settings.CLICKHOUSE_DB,
        user=settings.CLICKHOUSE_USER,
        password=settings.CLICKHOUSE_PASSWORD,
    )

    resp = requests.post(
        "https://verisistemi.tbb.org.tr/api/router",
        json={"route": "maliTablolarAll"},
        headers={"Content-Type": "application/json", "token": "asd", "role": "1", "LANG": "tr"},
        verify=False,
        timeout=120,
    )
    tbb_items = resp.json()
    print(f"Fetched {len(tbb_items)} TBB items")

    lookup = {item["UNIQUE_KEY"]: item for item in tbb_items if item.get("UNIQUE_KEY")}
    children_map = defaultdict(set)
    for item in tbb_items:
        ust = item.get("UST_UK")
        if ust:
            children_map[ust].add(_clean(item.get("TR_ADI", "")))

    def build_path(item):
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

    # Get DB state
    rows = ch.execute("""
        SELECT DISTINCT main_statement
        FROM tbb.financial_statements FINAL
        WHERE main_statement LIKE '%>%'
        ORDER BY main_statement
    """)
    db_mains_with_path = {r[0] for r in rows if r[0]}
    print(f"DB main_statements with path: {len(db_mains_with_path)}")

    leaf_names = set()
    for ms in db_mains_with_path:
        leaf = ms.split(" > ")[-1]
        leaf_names.add(leaf)

    solo_root = "TFRS9-SOLO"
    name_to_all_paths = defaultdict(list)
    for item in tbb_items:
        if solo_root not in item.get("ROOT_TR_ADI", ""):
            continue
        name = _clean(item.get("TR_ADI", ""))
        if name not in leaf_names:
            continue
        path = build_path(item)
        name_to_all_paths[name].append((item["UNIQUE_KEY"], path))

    # Find items with dedup-lost paths
    dedup_lost = []
    for name, candidates in name_to_all_paths.items():
        existing = set()
        missing = set()
        for uk, path in candidates:
            if path in db_mains_with_path:
                existing.add((uk, path))
            elif path != name:
                missing.add((uk, path))

        if not existing or not missing:
            continue

        for miss_uk, miss_path in missing:
            miss_children = children_map.get(miss_uk, set())
            for exist_uk, exist_path in existing:
                exist_children = children_map.get(exist_uk, set())
                if miss_children and miss_children == exist_children:
                    dedup_lost.append({
                        "name": name,
                        "missing_path": miss_path,
                        "existing_path": exist_path,
                        "shared_children": len(miss_children),
                    })
                    break

    print(f"\nItems with data lost due to deduplication: {len(dedup_lost)}")
    print()
    for item in dedup_lost[:30]:
        print(f'{item["name"]}:')
        print(f'  EXISTS:  {item["existing_path"]}')
        print(f'  MISSING: {item["missing_path"]}')
        print(f'  Shared children: {item["shared_children"]}')
        print()
    if len(dedup_lost) > 30:
        print(f"... and {len(dedup_lost) - 30} more")

    # Also check: still-missing paths where children DON'T match (not dedup issue)
    other_missing = []
    for name, candidates in name_to_all_paths.items():
        existing = set()
        missing = set()
        for uk, path in candidates:
            if path in db_mains_with_path:
                existing.add((uk, path))
            elif path != name:
                missing.add((uk, path))

        if not existing or not missing:
            continue

        for miss_uk, miss_path in missing:
            miss_children = children_map.get(miss_uk, set())
            is_dedup = False
            for exist_uk, exist_path in existing:
                exist_children = children_map.get(exist_uk, set())
                if miss_children and miss_children == exist_children:
                    is_dedup = True
                    break
            if not is_dedup:
                other_missing.append({
                    "name": name,
                    "missing_path": miss_path,
                    "children": len(miss_children),
                })

    print(f"\nOther still-missing paths (not dedup): {len(other_missing)}")
    for item in other_missing[:10]:
        print(f'  {item["name"]}: {item["missing_path"]} ({item["children"]} children)')


if __name__ == "__main__":
    main()

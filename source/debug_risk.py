"""Debug: explore risk center reports and categories on TBB site."""
import sys, json, time
sys.path.insert(0, "/opt/airflow/source")

from scrapers.base import TBBScraper

scraper = TBBScraper()
try:
    scraper.navigate("index.php?/tbb/report_rm")
    time.sleep(5)
    scraper.dismiss_tour()
    time.sleep(2)

    # 1. Get all report names from raporAdiList
    result = scraper.execute_js("""
        var items = document.querySelectorAll('#raporAdiList .dx-item');
        var out = [];
        for (var i = 0; i < items.length; i++) {
            out.push({idx: i, text: items[i].textContent.trim()});
        }
        return JSON.stringify(out);
    """)
    if result:
        reports = json.loads(result) if isinstance(result, str) else result
        print(f"Total reports: {len(reports)}")
        for r in reports:
            print(f"  [{r['idx']}] {r['text']}")

    # 2. For each report, click it and get categories
    print("\n=== CATEGORIES PER REPORT ===")
    for r in reports:
        idx = r['idx']
        scraper.execute_js(f"""
            var items = document.querySelectorAll('#raporAdiList .dx-item');
            if (items.length > {idx}) items[{idx}].click();
        """)
        time.sleep(2)

        cats = scraper.execute_js("""
            try {
                var tv = $('#kategorilerList').dxTreeView('instance');
                var nodes = tv.getNodes();
                var out = [];
                function walk(arr, depth) {
                    for (var i = 0; i < arr.length; i++) {
                        var n = arr[i];
                        var d = n.itemData || {};
                        out.push({text: d.TR_ADI || d.text || n.text || '', depth: depth});
                        if (n.children && n.children.length) walk(n.children, depth + 1);
                    }
                }
                walk(nodes, 0);
                return JSON.stringify(out);
            } catch(e) {
                return '[]';
            }
        """)
        if cats:
            categories = json.loads(cats) if isinstance(cats, str) else cats
            print(f"\n[{idx}] {r['text']}: {len(categories)} categories")
            for c in categories[:10]:
                indent = "  " * (c['depth'] + 1)
                print(f"{indent}{c['text']}")
            if len(categories) > 10:
                print(f"    ... ({len(categories) - 10} more)")

    # 3. Get available periods
    years = scraper.execute_js("""
        var list = $('#yillarList').dxList('instance');
        var items = list.option('items');
        if (!items) return '[]';
        var out = [];
        for (var i = 0; i < Math.min(10, items.length); i++) {
            out.push(items[i]);
        }
        return JSON.stringify(out);
    """)
    if years:
        periods = json.loads(years) if isinstance(years, str) else years
        print(f"\nPeriods (first 10): {len(periods)}")
        for p in periods:
            print(f"  {p}")

finally:
    scraper.close()

import studio_cob as studio, json

p = studio.proj()
out = open('probe_roberts_chart.txt', 'w')
def w(s): out.write(s+'\n'); out.flush()

for c in p.listCharts(quiet=True):
    d = c if isinstance(c, dict) else json.loads(str(c).replace("'", '"')) if False else None

charts = list(p.listCharts(quiet=True))
target = [c for c in charts if 'Roberts' in str(c.get('title',''))]
for c in target:
    w(f"TITLE: {c.get('title')}")
    w(f"ID: {c.get('id')}")
    w(f"DESC: {c.get('description')}")
    snap = c.get('snapshot', {})
    schema = snap.get('data', {}).get('table', {}).get('schema', [])
    rows = snap.get('data', {}).get('table', {}).get('rows', [])
    w(f"COLS: {[s.get('name') for s in schema]}")
    w(f"N ROWS: {len(rows)}")
    w(f"SAMPLE ROWS: {json.dumps(rows[:5], default=str)[:3000]}")
    # try to get the underlying SQL
    for key in ('request','query','sql','customsql','definition'):
        if key in c:
            w(f"{key.upper()}: {str(c[key])[:2000]}")
    w('---full dict keys---')
    w(str(list(c.keys())))
    w('=====')
w('DONE')
out.close()

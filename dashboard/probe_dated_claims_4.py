"""Register + profile candidate CarlQryRun tables: does the recovery $ column actually have values, and over what date range?"""
import sys, json, time, ast, studio_cob as studio
from machinify.openapi import DataResourceFormatFactory
out = open('probe_dated_claims_4.txt', 'a')
def w(s): print(s); out.write(s + '\n'); out.flush()
p = studio.proj()
have = set()
for r in p.listResources(quiet=True):
    s = str(r)
    try:
        dd = ast.literal_eval(s[:s.index(", 'format'")] + '}'); have.add(dd.get('identifier'))
    except Exception: pass
def reg(ident):
    if ident in have: w(f'exists {ident}'); return True
    try:
        r = p.createResource(name=f'CarlQryRun.{ident}', sourceid='S001ii', identifier=ident,
                             data_resource_format=DataResourceFormatFactory(format='jdbc.0'),
                             description='Registered 2026-09-16 - dated COB recovery search', quiet=True, timeout=300)
        dd = ast.literal_eval(str(r)); w(f'created {ident} cols={[c["name"] for c in dd["format"]["schema"]]}'); return True
    except Exception as e:
        w(f'register ERR {ident}: {str(e)[-300:]}'); return False
def q(tag, sql, timeout=900):
    t = time.time()
    try:
        d = studio.q(sql, timeout=timeout, retries=1)
        w(f'>> {tag} ({time.time()-t:.0f}s) rows={len(d)}'); w('   ' + json.dumps(d.to_dict('records'), default=str)[:4000]); return d
    except Exception as e:
        w(f'ERR {tag} ({time.time()-t:.0f}s): {str(e)[-400:]}'); return None

targets = sys.argv[1:]
for t in targets:
    if reg(t):
        q(f'sample {t}', f"SELECT * FROM `CarlQryRun.{t}` LIMIT 3")
w('DONE'); out.close()

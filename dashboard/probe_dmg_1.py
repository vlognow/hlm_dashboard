"""Register + sample DMGMining candidates (source S001ij). Usage: python3 probe_dmg_1.py <ident> ..."""
import sys, json, time, ast, studio_cob as studio
from machinify.openapi import DataResourceFormatFactory
out = open('probe_dmg_1.txt', 'a')
def w(s): print(s); out.write(s + '\n'); out.flush()
p = studio.proj()
have = set()
for r in p.listResources(quiet=True):
    s = str(r)
    try:
        dd = ast.literal_eval(s[:s.index(", 'format'")] + '}')
        if dd.get('sourceId') == 'S001ij': have.add(dd.get('identifier'))
    except Exception: pass
def reg(ident):
    if ident in have: w(f'exists {ident}'); return True
    try:
        r = p.createResource(name=f'DMGMining.{ident}', sourceid='S001ij', identifier=ident,
                             data_resource_format=DataResourceFormatFactory(format='jdbc.0'),
                             description='Registered 2026-09-16 - dated COB/Rx recovery search', quiet=True, timeout=600)
        dd = ast.literal_eval(str(r)); w(f'created {ident} cols={[c["name"] for c in dd["format"]["schema"]]}'); return True
    except Exception as e:
        w(f'register ERR {ident}: {str(e)[-300:]}'); return False
def q(tag, sql, timeout=1500):
    t = time.time()
    try:
        d = studio.q(sql, timeout=timeout, retries=1)
        w(f'>> {tag} ({time.time()-t:.0f}s) rows={len(d)}'); w('   ' + json.dumps(d.to_dict('records'), default=str)[:3500]); return d
    except Exception as e:
        w(f'ERR {tag} ({time.time()-t:.0f}s): {str(e)[-400:]}'); return None
for t in sys.argv[1:]:
    if reg(t):
        q(f'sample {t}', f"SELECT * FROM `DMGMining.{t}` LIMIT 3")
        q(f'count {t}', f"SELECT COUNT(*) n FROM `DMGMining.{t}`")
w('DONE'); out.close()

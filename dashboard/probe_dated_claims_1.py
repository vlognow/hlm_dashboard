"""Step 1: register catalog views on both COB SQL sources + sample the S3 claim imports."""
import studio_cob as studio, json, time, ast
from machinify.openapi import DataResourceFormatFactory

out = open('probe_dated_claims_1.txt', 'a')
def w(s): print(s); out.write(s + '\n'); out.flush()
def q(tag, sql, timeout=900):
    t = time.time()
    try:
        d = studio.q(sql, timeout=timeout, retries=1)
        w(f'>> {tag} ({time.time()-t:.0f}s) rows={len(d)} cols={list(d.columns)[:40]}')
        w('   ' + json.dumps(d.to_dict('records'), default=str)[:5000])
        return d
    except Exception as e:
        w(f'ERR {tag} ({time.time()-t:.0f}s): {str(e)[-600:]}')
        return None

p = studio.proj()
have = set()
for r in p.listResources(quiet=True):
    s = str(r)
    try:
        dd = ast.literal_eval(s[:s.index(", 'format'")] + '}')
        have.add((dd.get('sourceId'), dd.get('identifier')))
    except Exception:
        pass

def reg(src, db, ident):
    name = f'{db}.{ident}'
    if (src, ident) in have:
        w(f'exists {name}'); return
    try:
        r = p.createResource(name=name, sourceid=src, identifier=ident,
                             data_resource_format=DataResourceFormatFactory(format='jdbc.0'),
                             description='Registered 2026-09-16 - RPS exec dashboard dated-claims search',
                             quiet=True, timeout=300)
        dd = ast.literal_eval(str(r))
        w(f'created {name} cols={[c["name"] for c in dd["format"]["schema"]][:60]}')
    except Exception as e:
        w(f'register ERR {name}: {str(e)[-500:]}')

# DMGMining (192.168.251.18) - never explored
reg('S001ij', 'DMGMining', 'information_schema.tables')
reg('S001ij', 'DMGMining', 'information_schema.columns')
# CarlQryRun - add column-level catalog
reg('S001ii', 'CarlQryRun', 'information_schema.columns')

# S3 imports that look like claims
q('claim-summaries sample', "SELECT * FROM `claim-summaries` LIMIT 5")
q('cob_overlap_history sample', "SELECT * FROM `cob_overlap_history` LIMIT 5")

w('DONE')
out.close()

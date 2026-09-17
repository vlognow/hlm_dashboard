import studio_cob as studio, json, time, ast
from machinify.openapi import DataResourceFormatFactory

out = open('probe_finals.txt', 'a')
def w(s): out.write(s+'\n'); out.flush()
def q(tag, sql, timeout=600):
    t=time.time()
    try:
        d = studio.q(sql, timeout=timeout, retries=1)
        w(f'>> {tag} ({time.time()-t:.0f}s) rows={len(d)} cols={list(d.columns)}')
        w('   ' + json.dumps(d.to_dict('records'), default=str)[:2500])
        return d
    except Exception as e:
        w(f'ERR {tag} ({time.time()-t:.0f}s): {str(e)[-400:]}')
        return None

p = studio.proj()
have = {}
for r in p.listResources(quiet=True):
    s = str(r)
    try:
        dd = ast.literal_eval(s[:s.index(", 'format'")] + '}')
        have[(dd.get('sourceId'), dd.get('identifier'))] = dd.get('name')
    except Exception:
        pass

SRC = 'S001ii'
targets = ['dbo.qryAetnaHMOPincCommFinal', 'dbo.qryAetnaHRPPincCommFinal',
           'dbo.qryAetnaRCEDraftIssueMCFinal', 'dbo.qryAetnaHMOPINOCommercialFinal',
           'dbo.qryAetnaHRPPINOCommercialFinal', 'dbo.qryAetnaHMOPincMCFinal',
           'dbo.qryAetnaHRPPincMCFinal']
for ident in targets:
    name = f'CarlQryRun.{ident}'
    if (SRC, ident) in have:
        w(f'exists {name}')
        continue
    try:
        r = p.createResource(name=name, sourceid=SRC, identifier=ident,
                              data_resource_format=DataResourceFormatFactory(format='jdbc.0'),
                              description='Registered 2026-09-15 for RPS exec dashboard real-data search',
                              quiet=True)
        dd = ast.literal_eval(str(r))
        cols = [c['name'] for c in dd['format']['schema']]
        w(f'created {name} n_cols={len(cols)}')
        # flag likely $ / date columns without dumping full PHI-laden schema
        dollarish = [c for c in cols if any(k in c.lower() for k in ('amt','amount','paid','overpay','recover','received'))]
        dateish = [c for c in cols if any(k in c.lower() for k in ('date',))]
        w(f'   $-like cols: {dollarish}')
        w(f'   date-like cols: {dateish}')
    except Exception as e:
        w(f'register ERR {name}: {str(e)[-400:]}')

w('DONE')
out.close()

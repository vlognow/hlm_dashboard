import studio_cob as studio, json, time, ast
from machinify.openapi import DataResourceFormatFactory

out = open('probe_mining_db.txt', 'a')
def w(s): out.write(s+'\n'); out.flush()
def q(tag, sql, timeout=600):
    t=time.time()
    try:
        d = studio.q(sql, timeout=timeout, retries=1)
        w(f'>> {tag} ({time.time()-t:.0f}s) rows={len(d)}')
        w('   ' + json.dumps(d.to_dict('records'), default=str)[:3000])
        return d
    except Exception as e:
        w(f'ERR {tag} ({time.time()-t:.0f}s): {str(e)[-500:]}')
        return None

p = studio.proj()
try:
    r = p.createResource(name='MachinifyMining.information_schema.tables', sourceid='S001ii',
                          identifier='MachinifyMining.information_schema.tables',
                          data_resource_format=DataResourceFormatFactory(format='jdbc.0'),
                          description='probe for sibling DB access', quiet=True)
    dd = ast.literal_eval(str(r))
    w(f'created MachinifyMining.information_schema.tables cols={[c["name"] for c in dd["format"]["schema"]]}')
except Exception as e:
    w(f'register ERR: {str(e)[-500:]}')

q('MachinifyMining tables (identified_overlaps)', """
SELECT TABLE_SCHEMA, TABLE_NAME FROM `MachinifyMining.information_schema.tables`
WHERE lower(TABLE_NAME) RLIKE 'identified_overlaps' ORDER BY TABLE_NAME DESC LIMIT 20
""")
w('DONE')
out.close()

import studio_cob as studio, json, time

out = open('probe_ctpa.txt', 'a')
def w(s): out.write(s+'\n'); out.flush()
def q(tag, sql, timeout=900):
    t=time.time()
    try:
        d = studio.q(sql, timeout=timeout, retries=1)
        w(f'>> {tag} ({time.time()-t:.0f}s) rows={len(d)} cols={list(d.columns)}')
        w('   ' + json.dumps(d.to_dict('records'), default=str)[:2500])
        return d
    except Exception as e:
        w(f'ERR {tag} ({time.time()-t:.0f}s): {str(e)[-500:]}')
        return None

# search table names for CTPA / TotalPayAmount / any very recently created objects
q('name search CTPA/TotalPay', """
SELECT TABLE_SCHEMA, TABLE_NAME FROM `CarlQryRun.information_schema.tables`
WHERE lower(TABLE_NAME) RLIKE 'ctpa|totalpay|total_pay'
ORDER BY 1,2 LIMIT 100
""")
w('DONE')
out.close()

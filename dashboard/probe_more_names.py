import studio_cob as studio, json, time

out = open('probe_more_names.txt', 'a')
def w(s): out.write(s+'\n'); out.flush()
def q(tag, sql, timeout=600):
    t=time.time()
    try:
        d = studio.q(sql, timeout=timeout, retries=1)
        w(f'>> {tag} ({time.time()-t:.0f}s) rows={len(d)}')
        w('   ' + json.dumps(d.to_dict('records'), default=str)[:6000])
        return d
    except Exception as e:
        w(f'ERR {tag} ({time.time()-t:.0f}s): {str(e)[-500:]}')
        return None

q('Repaid/Stage/PincRepaid variants', """
SELECT TABLE_SCHEMA, TABLE_NAME FROM `CarlQryRun.information_schema.tables`
WHERE lower(TABLE_NAME) RLIKE 'repaid|pincrepaid|overpaymentreceived|recoveredamt|amountrecovered'
ORDER BY 1,2 LIMIT 200
""")
q('qry* tables (adhoc extracts, often finalized $ outputs)', """
SELECT TABLE_SCHEMA, TABLE_NAME FROM `CarlQryRun.information_schema.tables`
WHERE TABLE_NAME LIKE 'qry%' ORDER BY 1,2 LIMIT 300
""")
w('DONE')
out.close()

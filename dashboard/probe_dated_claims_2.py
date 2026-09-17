"""Step 2: column-level catalog search. Usage: python3 probe_dated_claims_2.py <DB>  (DMGMining | CarlQryRun)"""
import sys, studio_cob as studio, json, time

DB = sys.argv[1]
out = open(f'probe_dated_claims_2_{DB}.txt', 'a')
def w(s): print(s); out.write(s + '\n'); out.flush()
def q(tag, sql, timeout=1500):
    t = time.time()
    try:
        d = studio.q(sql, timeout=timeout, retries=1)
        w(f'>> {tag} ({time.time()-t:.0f}s) rows={len(d)}')
        w('   ' + json.dumps(d.to_dict('records'), default=str)[:12000])
        return d
    except Exception as e:
        w(f'ERR {tag} ({time.time()-t:.0f}s): {str(e)[-700:]}')
        return None

COLS = f'`{DB}.information_schema.columns`'
TABS = f'`{DB}.information_schema.tables`'

q('schemas + table counts', f"""
SELECT TABLE_SCHEMA, TABLE_TYPE, COUNT(*) n FROM {TABS} GROUP BY TABLE_SCHEMA, TABLE_TYPE ORDER BY n DESC LIMIT 100
""")

# tables with BOTH a date-typed column and a money-ish column; rank by recovery-flavoured names
q('tables with date + money columns (ranked)', f"""
WITH c AS (
  SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, lower(DATA_TYPE) dt, lower(COLUMN_NAME) cn FROM {COLS}
),
agg AS (
  SELECT TABLE_SCHEMA, TABLE_NAME,
    SUM(CASE WHEN dt IN ('date','datetime','datetime2','smalldatetime') THEN 1 ELSE 0 END) n_date_typed,
    SUM(CASE WHEN dt IN ('money','smallmoney','decimal','numeric','float','real') THEN 1 ELSE 0 END) n_money_typed,
    SUM(CASE WHEN cn RLIKE 'recover|repaid|refund|remit|received|posted|collect|check' THEN 1 ELSE 0 END) n_recovery_named,
    SUM(CASE WHEN cn RLIKE 'paid|allow|bill|charge|amt|amount' THEN 1 ELSE 0 END) n_paid_named,
    SUM(CASE WHEN cn RLIKE 'claim' THEN 1 ELSE 0 END) n_claim_named,
    COUNT(*) n_cols,
    concat_ws(', ', collect_list(CASE WHEN dt IN ('date','datetime','datetime2','smalldatetime') THEN COLUMN_NAME END)) date_cols,
    concat_ws(', ', collect_list(CASE WHEN cn RLIKE 'recover|repaid|refund|remit|received|posted|collect|check|paid|amt|amount' THEN COLUMN_NAME END)) money_cols
  FROM c GROUP BY TABLE_SCHEMA, TABLE_NAME
)
SELECT * FROM agg
WHERE n_date_typed > 0 AND (n_money_typed > 0 OR n_paid_named > 0 OR n_recovery_named > 0)
ORDER BY n_recovery_named DESC, n_claim_named DESC, n_money_typed DESC
LIMIT 400
""")

# any column at all whose NAME says recovery/repaid/refund + a date sibling in the same table
q('recovery-named columns list', f"""
SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE FROM {COLS}
WHERE lower(COLUMN_NAME) RLIKE 'recover|repaid|refund|remit|receiveddate|paiddate|postdate|posteddate|checkdate|checkamt|checkamount'
ORDER BY TABLE_SCHEMA, TABLE_NAME LIMIT 1500
""")

w('DONE')
out.close()

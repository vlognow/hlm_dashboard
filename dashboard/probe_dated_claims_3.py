"""Save full catalog-search results to CSV (the .txt probes truncate at 12k chars)."""
import sys, studio_cob as studio, time
DB = sys.argv[1]
COLS = f'`{DB}.information_schema.columns`'
t = time.time()
ranked = studio.q(f"""
WITH c AS (SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, lower(DATA_TYPE) dt, lower(COLUMN_NAME) cn FROM {COLS}),
agg AS (
  SELECT TABLE_SCHEMA, TABLE_NAME,
    SUM(CASE WHEN dt IN ('date','datetime','datetime2','smalldatetime') THEN 1 ELSE 0 END) n_date_typed,
    SUM(CASE WHEN dt IN ('money','smallmoney','decimal','numeric','float','real') THEN 1 ELSE 0 END) n_money_typed,
    SUM(CASE WHEN cn RLIKE 'recover|repaid|refund|remit|received|posted|collect|check' THEN 1 ELSE 0 END) n_recovery_named,
    SUM(CASE WHEN cn RLIKE 'claim' THEN 1 ELSE 0 END) n_claim_named,
    COUNT(*) n_cols,
    concat_ws(', ', collect_list(CASE WHEN dt IN ('date','datetime','datetime2','smalldatetime') OR cn RLIKE 'date|_dt$' THEN COLUMN_NAME END)) date_cols,
    concat_ws(', ', collect_list(CASE WHEN cn RLIKE 'recover|repaid|refund|remit|received|posted|collect|check|paid|amt|amount' THEN COLUMN_NAME END)) money_cols
  FROM c GROUP BY TABLE_SCHEMA, TABLE_NAME)
SELECT * FROM agg WHERE n_date_typed > 0 OR date_cols <> ''
ORDER BY n_recovery_named DESC, n_claim_named DESC, n_money_typed DESC LIMIT 4000
""", timeout=1500, retries=1)
ranked.to_csv(f'catalog_ranked_{DB}.csv', index=False)
print(f'{DB}: ranked rows={len(ranked)} ({time.time()-t:.0f}s)')

import json, time, studio_cob as studio
out = open('probe_dmg_6.txt', 'a')
def w(s): print(s); out.write(s + '\n'); out.flush()
def q(tag, sql, csv=None, timeout=1500):
    t = time.time()
    try:
        d = studio.q(sql, timeout=timeout, retries=1)
        if csv: d.to_csv(csv, index=False)
        w(f'>> {tag} ({time.time()-t:.0f}s) rows={len(d)}'); w('   ' + json.dumps(d.to_dict('records'), default=str)[:3000]); return d
    except Exception as e:
        w(f'ERR {tag} ({time.time()-t:.0f}s): {str(e)[-400:]}'); return None
T='`DMGMining.dbo.PostedRecoveryTrendingData`'
q('PRT month x type (since 2025-07)', f"""SELECT date_format(Date,'yyyy-MM') ym, InvestigationType, SUM(Recovery) recovered, COUNT(*) n
  FROM {T} WHERE Date >= '2025-07-01' GROUP BY 1,2 ORDER BY 1,2""", csv='dmg_PRT_month_type.csv')
q('PRT month x client (since 2025-07)', f"""SELECT date_format(Date,'yyyy-MM') ym, Client, SUM(Recovery) recovered, COUNT(*) n
  FROM {T} WHERE Date >= '2025-07-01' GROUP BY 1,2 ORDER BY 1,2""", csv='dmg_PRT_month_client.csv')
q('PRT daily last 120d', f"""SELECT CAST(Date AS date) d, SUM(Recovery) recovered, COUNT(*) n FROM {T}
  WHERE Date >= date_sub(current_date(), 120) GROUP BY 1 ORDER BY 1""", csv='dmg_PRT_daily_120d.csv')
q('PRT negatives check', f"SELECT SUM(CASE WHEN Recovery < 0 THEN 1 ELSE 0 END) n_neg, SUM(CASE WHEN Recovery < 0 THEN Recovery ELSE 0 END) neg_amt, MAX(Date) max_d FROM {T}")
w('DONE'); out.close()

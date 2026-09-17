import json, time, studio_cob as studio
out = open('probe_dmg_5a.txt', 'a')
def w(s): print(s); out.write(s + '\n'); out.flush()
def q(tag, sql, csv=None, timeout=1500):
    t = time.time()
    try:
        d = studio.q(sql, timeout=timeout, retries=1)
        if csv: d.to_csv(csv, index=False)
        w(f'>> {tag} ({time.time()-t:.0f}s) rows={len(d)}'); w('   ' + json.dumps(d.to_dict('records'), default=str)[:6000]); return d
    except Exception as e:
        w(f'ERR {tag} ({time.time()-t:.0f}s): {str(e)[-400:]}'); return None
q('AetnaSBR_Report full', "SELECT * FROM `DMGMining.dbo.AetnaSBR_Report` ORDER BY Year, Month, Breakout, ProgramBreakout", csv='dmg_AetnaSBR_Report.csv')
q('AetnaSBR by month total', "SELECT Year, Month, ProgramBreakout, SUM(Recovered) recovered, COUNT(*) n FROM `DMGMining.dbo.AetnaSBR_Report` GROUP BY 1,2,3 ORDER BY 1,2,3", csv='dmg_AetnaSBR_monthly.csv')
T='`DMGMining.dbo.PostedRecoveryTrendingData`'
q('PRT overall', f"SELECT COUNT(*) n, SUM(Recovery) total, MIN(Date) min_d, MAX(Date) max_d, COUNT(DISTINCT Client) n_clients FROM {T}")
q('PRT by month', f"SELECT date_format(Date,'yyyy-MM') ym, COUNT(*) n, SUM(Recovery) recovered FROM {T} GROUP BY 1 ORDER BY 1", csv='dmg_PRT_monthly.csv')
q('PRT by bucket/type', f"SELECT ReportBucket, InvestigationType, COUNT(*) n, SUM(Recovery) recovered FROM {T} GROUP BY 1,2 ORDER BY recovered DESC LIMIT 40", csv='dmg_PRT_bucket_type.csv')
q('PRT by client', f"SELECT Client, COUNT(*) n, SUM(Recovery) recovered, MIN(Date) min_d, MAX(Date) max_d FROM {T} GROUP BY 1 ORDER BY recovered DESC LIMIT 60", csv='dmg_PRT_client.csv')
q('PRT by month x bucket', f"SELECT date_format(Date,'yyyy-MM') ym, ReportBucket, SUM(Recovery) recovered FROM {T} GROUP BY 1,2 ORDER BY 1,2", csv='dmg_PRT_month_bucket.csv')
T='`DMGMining.dbo.CrossDivisionRecap_Claims_AllClients`'
q('CrossDivision fill + by month', f"""SELECT date_format(RecoveryDate,'yyyy-MM') ym, COUNT(*) n, SUM(RecoveredTotal) recovered, SUM(InvoicedTotal) invoiced
  FROM {T} WHERE RecoveryDate IS NOT NULL GROUP BY 1 ORDER BY 1""", csv='dmg_CrossDivision_monthly.csv')
q('CEMRxFinance by year', "SELECT year(DtPaid) y, COUNT(*) n, SUM(Recovered) recovered FROM `DMGMining.dbo.CEMRxFinance` GROUP BY 1 ORDER BY 1")
w('DONE'); out.close()

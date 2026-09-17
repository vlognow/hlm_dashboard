import json, time, studio_cob as studio
out = open('probe_dmg_5b.txt', 'a')
def w(s): print(s); out.write(s + '\n'); out.flush()
def q(tag, sql, csv=None, timeout=1500):
    t = time.time()
    try:
        d = studio.q(sql, timeout=timeout, retries=1)
        if csv: d.to_csv(csv, index=False)
        w(f'>> {tag} ({time.time()-t:.0f}s) rows={len(d)}'); w('   ' + json.dumps(d.to_dict('records'), default=str)[:5000]); return d
    except Exception as e:
        w(f'ERR {tag} ({time.time()-t:.0f}s): {str(e)[-400:]}'); return None
q('RxDirects by posting month', """SELECT date_format(PostingDate,'yyyy-MM') ym, COUNT(*) n, SUM(Recovered) recovered, SUM(Writeoff) writeoff
  FROM `DMGMining.dbo.RxDirectsResults` WHERE PostingDate IS NOT NULL GROUP BY 1 ORDER BY 1""", csv='dmg_RxDirects_monthly.csv')
q('RxDirects by client/type', """SELECT clientName, InvestigationType, COUNT(*) n, SUM(Recovered) recovered, MIN(PostingDate) min_d, MAX(PostingDate) max_d
  FROM `DMGMining.dbo.RxDirectsResults` GROUP BY 1,2 ORDER BY recovered DESC LIMIT 40""", csv='dmg_RxDirects_client_type.csv')
q('EvernorthCBA$ by paid month', """SELECT date_format(DtPaid,'yyyy-MM') ym, COUNT(*) n, SUM(Recovered) recovered, SUM(AmtBilled) billed
  FROM `DMGMining.dbo.EvernorthCBAInvestigationsDollars` WHERE DtPaid IS NOT NULL GROUP BY 1 ORDER BY 1""", csv='dmg_EvernorthCBA_monthly.csv')
q('CBAReportData by month', """SELECT date_format(`date`,'yyyy-MM') ym, SUM(PostedRecovery) posted, SUM(SubmittedRecovery) submitted, SUM(Invoiced) invoiced, SUM(Investigations) investigations
  FROM `DMGMining.evernorth.CBAReportData` GROUP BY 1 ORDER BY 1""", csv='dmg_CBAReportData_monthly.csv')
q('CBAReportData by type', """SELECT InvestigationType, SUM(PostedRecovery) posted, SUM(Invoiced) invoiced FROM `DMGMining.evernorth.CBAReportData` GROUP BY 1 ORDER BY posted DESC LIMIT 20""")
q('UHC passfile fill + by recovered month', """SELECT date_format(RECOVERED_DATE,'yyyy-MM') ym, COUNT(*) n, SUM(TOTAL_RECOVERED_AMOUNT) total_recovered, SUM(AMOUNT_RECOVERED_REPORTING) recovered_reporting
  FROM `DMGMining.dbo.UnitedRxPFMTPassFile` WHERE RECOVERED_DATE IS NOT NULL GROUP BY 1 ORDER BY 1""", csv='dmg_UHC_monthly.csv')
w('DONE'); out.close()

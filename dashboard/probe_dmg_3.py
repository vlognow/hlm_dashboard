import json, time, studio_cob as studio
out = open('probe_dmg_3.txt', 'a')
def w(s): print(s); out.write(s + '\n'); out.flush()
def q(tag, sql, timeout=1500):
    t = time.time()
    try:
        d = studio.q(sql, timeout=timeout, retries=1)
        w(f'>> {tag} ({time.time()-t:.0f}s) rows={len(d)}'); w('   ' + json.dumps(d.to_dict('records'), default=str)[:7000]); return d
    except Exception as e:
        w(f'ERR {tag} ({time.time()-t:.0f}s): {str(e)[-400:]}'); return None
T = '`DMGMining.dbo.EvernorthClaimRemit`'
q('Evernorth overall', f"""SELECT COUNT(*) n, COUNT(DISTINCT CLAIM_NBR) n_claims, COUNT(DISTINCT pkInvestigation) n_inv,
  SUM(GROSS_RECOVERY_AMT) gross, SUM(SERVICE_FEE_AMT) fee, SUM(NET_REFUND_AMT) net, SUM(PAID_AMT) paid,
  MIN(RECOVERY_DTE) min_rec, MAX(RECOVERY_DTE) max_rec, MIN(REQUEST_DTE) min_req, MAX(REQUEST_DTE) max_req,
  SUM(CASE WHEN RECOVERY_DTE IS NULL THEN 1 ELSE 0 END) n_null_recdate FROM {T}""")
q('Evernorth by recovery month', f"""SELECT date_format(RECOVERY_DTE,'yyyy-MM') ym, COUNT(*) n, SUM(GROSS_RECOVERY_AMT) gross, SUM(NET_REFUND_AMT) net
  FROM {T} WHERE RECOVERY_DTE IS NOT NULL GROUP BY 1 ORDER BY 1""")
q('Evernorth by type/reason/receivedby/status', f"""SELECT RECOVERY_TYPE_CDE, RECOVERY_REASON_CDE, RECOVERY_RECEIVED_BY, ReportStatus, COUNT(*) n, SUM(GROSS_RECOVERY_AMT) gross
  FROM {T} GROUP BY 1,2,3,4 ORDER BY n DESC LIMIT 30""")
q('Evernorth by client (REIMB_LOC_NME)', f"""SELECT REIMB_LOC_NME, COUNT(*) n, SUM(GROSS_RECOVERY_AMT) gross FROM {T} GROUP BY 1 ORDER BY gross DESC LIMIT 25""")
w('DONE'); out.close()

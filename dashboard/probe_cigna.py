import studio_cob as studio, json, time

out = open('probe_cigna.txt', 'a')
def w(s): out.write(s+'\n'); out.flush()
def q(tag, sql, timeout=600):
    t=time.time()
    try:
        d = studio.q(sql, timeout=timeout, retries=1)
        w(f'>> {tag} ({time.time()-t:.0f}s) rows={len(d)} cols={list(d.columns)}')
        w('   ' + json.dumps(d.to_dict('records'), default=str)[:5000])
        return d
    except Exception as e:
        w(f'ERR {tag} ({time.time()-t:.0f}s): {str(e)[-500:]}')
        return None

T = '`CarlQryRun.dbo.qryCignaProClaimsPincRepaidStage5`'
q('row/date coverage', f"""
SELECT COUNT(*) n,
       MIN(PayDate) min_pay, MAX(PayDate) max_pay,
       MIN(ReceivedDate) min_rcv, MAX(ReceivedDate) max_rcv,
       MIN(ProcessingDate) min_proc, MAX(ProcessingDate) max_proc,
       SUM(OverpaymentReceivedAmount) total_amt,
       SUM(CASE WHEN OverpaymentReceivedAmount > 0 THEN 1 ELSE 0 END) n_with_amt,
       COUNT(DISTINCT InvestigationID) n_investigations,
       COUNT(DISTINCT AuditClientCode) n_clients
FROM {T}
""")
q('by OverpaymentReceivedIndicator', f"""
SELECT OverpaymentReceivedIndicator, COUNT(*) n, SUM(OverpaymentReceivedAmount) amt
FROM {T} GROUP BY OverpaymentReceivedIndicator
""")
q('by AuditCategory/AuditClientCode', f"""
SELECT AuditClientCode, AuditCategory, AuditType, COUNT(*) n, SUM(OverpaymentReceivedAmount) amt
FROM {T} GROUP BY AuditClientCode, AuditCategory, AuditType ORDER BY amt DESC LIMIT 30
""")
q('monthly by PayDate', f"""
SELECT date_format(from_unixtime(PayDate),'yyyy-MM') ym, COUNT(*) n, SUM(OverpaymentReceivedAmount) amt
FROM {T} WHERE PayDate IS NOT NULL GROUP BY date_format(from_unixtime(PayDate),'yyyy-MM') ORDER BY ym
""")
q('monthly by ReceivedDate', f"""
SELECT date_format(from_unixtime(ReceivedDate),'yyyy-MM') ym, COUNT(*) n, SUM(OverpaymentReceivedAmount) amt
FROM {T} WHERE ReceivedDate IS NOT NULL GROUP BY date_format(from_unixtime(ReceivedDate),'yyyy-MM') ORDER BY ym
""")
w('DONE')
out.close()

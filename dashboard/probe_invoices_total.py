import studio_cob as studio, json, time

out = open('probe_invoices_total.txt', 'a')
def w(s): out.write(s+'\n'); out.flush()
def q(tag, sql, timeout=900):
    t=time.time()
    try:
        d = studio.q(sql, timeout=timeout, retries=1)
        w(f'>> {tag} ({time.time()-t:.0f}s) rows={len(d)}')
        w('   ' + json.dumps(d.to_dict('records'), default=str)[:2000])
        return d
    except Exception as e:
        w(f'ERR {tag} ({time.time()-t:.0f}s): {str(e)[-400:]}')
        return None

q('InvestigationInvoices total', """
SELECT COUNT(*) n, SUM(InvoiceRecorded) total, AVG(InvoiceRecorded) avg,
       SUM(CASE WHEN InvoiceRecorded > 0 THEN 1 ELSE 0 END) n_positive,
       SUM(CASE WHEN InvoiceRecorded > 0 THEN InvoiceRecorded ELSE 0 END) total_positive
FROM `CarlQryRun.overlap_detection.InvestigationInvoices`
""")
w('DONE')
out.close()

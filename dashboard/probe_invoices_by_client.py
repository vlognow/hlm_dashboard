import studio_cob as studio, json, time

out = open('probe_invoices_by_client.txt', 'a')
def w(s): out.write(s+'\n'); out.flush()
def q(tag, sql, timeout=1200):
    t=time.time()
    try:
        d = studio.q(sql, timeout=timeout, retries=1)
        w(f'>> {tag} ({time.time()-t:.0f}s) rows={len(d)}')
        w('   ' + json.dumps(d.to_dict('records'), default=str)[:6000])
        return d
    except Exception as e:
        w(f'ERR {tag} ({time.time()-t:.0f}s): {str(e)[-500:]}')
        return None

q('invoiced $ by client (real, PHI-free)', """
SELECT c.ClientCode, COUNT(DISTINCT i.InvestigationID) n_investigations,
       SUM(i.InvoiceRecorded) total_invoiced
FROM `CarlQryRun.overlap_detection.InvestigationInvoices` i
JOIN (
    SELECT InvestigationID, MAX(ClientCode) AS ClientCode
    FROM `CarlQryRun.overlap_detection.CEMOverlapsAndSmartIIResults`
    WHERE InvestigationID IS NOT NULL
    GROUP BY InvestigationID
) c ON c.InvestigationID = i.InvestigationID
GROUP BY c.ClientCode
ORDER BY total_invoiced DESC
LIMIT 40
""")
w('DONE')
out.close()

import studio_cob as studio, json, time

out = open('probe_finals_agg.txt', 'a')
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

tables = ['qryAetnaHMOPincCommFinal', 'qryAetnaHRPPincCommFinal', 'qryAetnaRCEDraftIssueMCFinal',
          'qryAetnaHMOPINOCommercialFinal', 'qryAetnaHRPPINOCommercialFinal',
          'qryAetnaHMOPincMCFinal', 'qryAetnaHRPPincMCFinal']
for t in tables:
    T = f'`CarlQryRun.dbo.{t}`'
    q(f'coverage {t}', f"""
    SELECT COUNT(*) n,
           SUM(CASE WHEN OverpaymentReceivedAmount IS NOT NULL THEN 1 ELSE 0 END) n_with_amt,
           SUM(OverpaymentReceivedAmount) total_amt,
           MIN(PayDate) min_pay, MAX(PayDate) max_pay,
           MIN(ReceivedDate) min_rcv, MAX(ReceivedDate) max_rcv
    FROM {T}
    """)
w('DONE')
out.close()

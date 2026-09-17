import json, time, studio_cob as studio
out = open('probe_dated_claims_5.txt', 'a')
def w(s): print(s); out.write(s + '\n'); out.flush()
def q(tag, sql, timeout=1200):
    t = time.time()
    try:
        d = studio.q(sql, timeout=timeout, retries=1)
        w(f'>> {tag} ({time.time()-t:.0f}s) rows={len(d)}'); w('   ' + json.dumps(d.to_dict('records'), default=str)[:6000]); return d
    except Exception as e:
        w(f'ERR {tag} ({time.time()-t:.0f}s): {str(e)[-500:]}'); return None
T = '`CarlQryRun.dbo.CenteneRetraction`'
q('CenteneRetraction overall', f"""
SELECT COUNT(*) n_rows,
  SUM(CASE WHEN TRIM(`Recovery Amount`) <> '' THEN 1 ELSE 0 END) n_recovery_filled,
  SUM(CASE WHEN TRIM(`Check Number`) <> '' THEN 1 ELSE 0 END) n_check_filled,
  SUM(TRY_CAST(REPLACE(REPLACE(`Recovery Amount`,'$',''),',','') AS DOUBLE)) sum_recovery,
  SUM(`Mining Cache Line Amount`) sum_mining_line_amt,
  COUNT(DISTINCT `Claim Number - Medical`) n_claims, COUNT(DISTINCT InvoiceID) n_invoices,
  MIN(TO_DATE(`Date Letter Sent`,'MM-dd-yyyy')) min_letter, MAX(TO_DATE(`Date Letter Sent`,'MM-dd-yyyy')) max_letter,
  MIN(TO_DATE(PayDate,'MM-dd-yyyy')) min_pay, MAX(TO_DATE(PayDate,'MM-dd-yyyy')) max_pay
FROM {T}
""")
q('CenteneRetraction by letter month', f"""
SELECT date_format(TO_DATE(`Date Letter Sent`,'MM-dd-yyyy'),'yyyy-MM') ym, COUNT(*) n_lines,
  COUNT(DISTINCT InvoiceID) n_invoices, SUM(`Mining Cache Line Amount`) line_amt,
  SUM(TRY_CAST(REPLACE(REPLACE(`Recovery Amount`,'$',''),',','') AS DOUBLE)) recovery_amt
FROM {T} GROUP BY 1 ORDER BY 1
""")
q('CenteneRetraction distinct Recovery or Direct Pay values', f"SELECT `Recovery or Direct Pay` v, COUNT(*) n FROM {T} GROUP BY 1 ORDER BY 2 DESC LIMIT 20")
q('CenteneRetraction by program', f"SELECT `Program (COBM/COBC/OVRP/LTC/CBAL)` prog, `Business Unit` bu, COUNT(*) n, SUM(`Mining Cache Line Amount`) amt FROM {T} GROUP BY 1,2 ORDER BY 4 DESC LIMIT 30")
w('DONE'); out.close()

import studio_cob as studio, json, time

out = open('probe_cob_real.txt', 'a')
def w(s): out.write(s+'\n'); out.flush()
def q(tag, sql, timeout=600):
    t=time.time()
    try:
        d = studio.q(sql, timeout=timeout, retries=1)
        w(f'>> {tag} ({time.time()-t:.0f}s) rows={len(d)} cols={list(d.columns)}')
        w('   ' + json.dumps(d.to_dict('records'), default=str)[:3000])
        return d
    except Exception as e:
        w(f'ERR {tag} ({time.time()-t:.0f}s): {str(e)[-500:]}')
        return None

# Broader name search across the full dbo schema (7135 tables) for anything $-and-date shaped
q('broad recovery-ish names', """
SELECT TABLE_SCHEMA, TABLE_NAME FROM `CarlQryRun.information_schema.tables`
WHERE lower(TABLE_NAME) RLIKE 'overpaid|overpayment|repaid|refund|remit|collect|recap|posted|checkamt|paidamt'
ORDER BY 1,2 LIMIT 400
""")

for t in ['dbo.tblAetnaRxOverpayments', 'dbo.qryCignaProClaimsPincRepaidStage5',
          'dbo.CAQHOverlapScoringOverpaymentresults', 'dbo.CAQHOverlapScoringOverpaymentresultsNewBusRules',
          'dbo.CAQHOverlapScoringOverpaymentresultsOriginalBusRules', 'dbo.RxValidationSocres_MonthlyScorecard']:
    q(f'schema {t}', f"SELECT * FROM `CarlQryRun.{t}` LIMIT 3")

w('DONE')
out.close()

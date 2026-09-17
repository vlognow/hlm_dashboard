"""Pull medical COB posted recoveries from ACT.dbo.Remit (DivisionId IS NULL = Payment Integrity / Audit book)
and save CSVs for the exec page. Net of adjustments/reversals (negative remits kept). Each query joins only what it needs."""
import act_conn, pandas as pd, time
FROM = "DATEADD(MONTH,-27,DATEFROMPARTS(YEAR(GETDATE()),MONTH(GETDATE()),1))"
W = f"WHERE r.DivisionId IS NULL AND r.AddDate >= {FROM}"
ALLOC = """OUTER APPLY (SELECT TOP 1 ClaimID FROM dbo.RemitPendingClaim WITH (NOLOCK) WHERE RemitID = r.ID) rp
OUTER APPLY (SELECT TOP 1 t.ClaimID FROM dbo.RemitTransaction x WITH (NOLOCK) JOIN dbo.[Transaction] t WITH (NOLOCK) ON t.ID = x.TransactionID WHERE x.RemitID = r.ID AND rp.ClaimID IS NULL) rx
CROSS APPLY (SELECT COALESCE(rp.ClaimID, rx.ClaimID) AS ClaimID) rpc"""
q = act_conn.q
t = time.time()
monthly = q(f"""SELECT FORMAT(r.AddDate,'yyyy-MM') ym, COUNT_BIG(*) n_remits, SUM(r.AppliedAmt) applied,
  SUM(CASE WHEN r.AppliedAmt<0 THEN r.AppliedAmt ELSE 0 END) reversals,
  SUM(CASE WHEN r.TransactionTypeID=10 THEN r.AppliedAmt ELSE 0 END) completed_recovery
FROM dbo.Remit r WITH (NOLOCK) {W} GROUP BY FORMAT(r.AddDate,'yyyy-MM') ORDER BY ym""")
claims = q(f"""SELECT FORMAT(r.AddDate,'yyyy-MM') ym, COUNT_BIG(DISTINCT rpc.ClaimID) n_claims
FROM dbo.Remit r WITH (NOLOCK) JOIN dbo.RemitPendingClaim rpc WITH (NOLOCK) ON rpc.RemitID = r.ID {W} GROUP BY FORMAT(r.AddDate,'yyyy-MM')""")
monthly = monthly.merge(claims, on='ym', how='left'); monthly.to_csv('cob_act_monthly.csv', index=False)
print(f'monthly {time.time()-t:.0f}s'); print(monthly.tail(14).to_string())
t = time.time()
cat = q(f"""SELECT FORMAT(r.AddDate,'yyyy-MM') ym,
  ISNULL(cob.AuditCategory, CASE WHEN rpc.ClaimID IS NULL THEN '(no claim allocation)' ELSE '(uncategorised)' END) category,
  COUNT_BIG(*) n_remits, SUM(r.AppliedAmt) applied
FROM dbo.Remit r WITH (NOLOCK) {ALLOC}
LEFT JOIN dbo.Claim c WITH (NOLOCK) ON c.ID = rpc.ClaimID LEFT JOIN dbo.COB cob WITH (NOLOCK) ON cob.ID = c.COBID
{W} GROUP BY FORMAT(r.AddDate,'yyyy-MM'), ISNULL(cob.AuditCategory, CASE WHEN rpc.ClaimID IS NULL THEN '(no claim allocation)' ELSE '(uncategorised)' END)""")
cat.to_csv('cob_act_month_category.csv', index=False); print(f'category {time.time()-t:.0f}s rows={len(cat)}')
t = time.time()
cli = q(f"""SELECT FORMAT(r.AddDate,'yyyy-MM') ym, ISNULL(c.ParentClientCode,'(no claim allocation)') parent, COUNT_BIG(*) n_remits, SUM(r.AppliedAmt) applied
FROM dbo.Remit r WITH (NOLOCK) {ALLOC} LEFT JOIN dbo.Claim c WITH (NOLOCK) ON c.ID = rpc.ClaimID
{W} GROUP BY FORMAT(r.AddDate,'yyyy-MM'), ISNULL(c.ParentClientCode,'(no claim allocation)')""")
cli.to_csv('cob_act_month_client.csv', index=False); print(f'client {time.time()-t:.0f}s rows={len(cli)}')
t = time.time()
typ = q(f"""SELECT FORMAT(r.AddDate,'yyyy-MM') ym, tt.Name txn_type, rt.Name recovery_type, COUNT_BIG(*) n_remits, SUM(r.AppliedAmt) applied
FROM dbo.Remit r WITH (NOLOCK) LEFT JOIN dbo.TransactionType tt ON tt.ID = r.TransactionTypeID LEFT JOIN dbo.RecoveryType rt ON rt.ID = r.RecoveryTypeID
{W} GROUP BY FORMAT(r.AddDate,'yyyy-MM'), tt.Name, rt.Name""")
typ.to_csv('cob_act_month_type.csv', index=False)
daily = q("SELECT CAST(r.AddDate AS date) d, COUNT_BIG(*) n, SUM(r.AppliedAmt) applied FROM dbo.Remit r WITH (NOLOCK) WHERE r.DivisionId IS NULL AND r.AddDate >= DATEADD(DAY,-120,CAST(GETDATE() AS date)) GROUP BY CAST(r.AddDate AS date) ORDER BY d")
daily.to_csv('cob_act_daily_120d.csv', index=False); print(f'type+daily {time.time()-t:.0f}s')
print(cat[cat.ym=='2026-08'].sort_values('applied', ascending=False).to_string()); print(cli[cli.ym=='2026-08'].sort_values('applied', ascending=False).head(12).to_string())

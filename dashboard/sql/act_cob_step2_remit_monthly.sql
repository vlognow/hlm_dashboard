/* =====================================================================
   RPS $ Recovered dashboard -- COB (Medical) posted recoveries from ACT
   Step 2b: monthly $ from dbo.Remit (the posted-remittance event table)
   ---------------------------------------------------------------------
   SERVER/DB : TRGACAP3, ACT.  Read-only, aggregate-only (no member rows).
   HOW TO RUN: SSMS, Results To Text (Ctrl+T), Execute, save as
               act_cob_step2_remit_monthly_output.txt (git-ignored).
   Or:  sqlcmd -S TRGACAP3 -d ACT -E -t 1200 -W -w 300 -i act_cob_step2_remit_monthly.sql -o act_cob_step2_remit_monthly_output.txt
   WHY dbo.Remit: discovery (step 1) showed Remit is the only table with a
   DivisionId, an add date, gross/applied/fee amounts, recovery type and
   method. RemitPendingClaim allocates each remit to claims; RemitCheck ->
   Check carries the physical check; RemitTransaction -> Transaction is the
   per-claim ledger. vwRemitInfo is the app's own denormalised view of it.
   Division lookup in ACT: 1 Audit (Payment Integrity), 2 Subro, 3 Pharmacy,
   4 CPS. John Marcsik: COB medical = Division 2 (named "Subro" in ACT).
   R6/R7 confirm that by client code and audit category.
   ===================================================================== */
USE ACT; SET NOCOUNT ON; SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;

PRINT '=== R1. Remit: count and $ by DivisionId (all time) ===';
SELECT r.DivisionId, d.Name AS division, COUNT_BIG(*) n, MIN(r.AddDate) first_dt, MAX(r.AddDate) last_dt,
       SUM(r.ARDAmount) ard, SUM(r.AuditorAmount) auditor, SUM(r.AppliedAmt) applied, SUM(r.FeeValue) fee
FROM dbo.Remit r WITH (NOLOCK) LEFT JOIN dbo.Division d ON d.ID = r.DivisionId
GROUP BY r.DivisionId, d.Name ORDER BY r.DivisionId;

PRINT '=== R2. Remit: monthly by AddDate x DivisionId, last 26 months ===';
SELECT r.DivisionId, FORMAT(r.AddDate,'yyyy-MM') ym, COUNT_BIG(*) n, COUNT_BIG(DISTINCT r.InvestigationId) n_inv,
       SUM(r.ARDAmount) ard, SUM(r.AuditorAmount) auditor, SUM(r.AppliedAmt) applied, SUM(r.FeeValue) fee, SUM(r.SecondaryFeeValue) fee2
FROM dbo.Remit r WITH (NOLOCK)
WHERE r.AddDate >= DATEADD(MONTH,-26,DATEFROMPARTS(YEAR(GETDATE()),MONTH(GETDATE()),1))
GROUP BY r.DivisionId, FORMAT(r.AddDate,'yyyy-MM') ORDER BY r.DivisionId, ym;

PRINT '=== R3. Remit Division 2, last 12 months: by TransactionType x RecoveryType ===';
SELECT r.TransactionTypeID, tt.Name tt_name, r.RecoveryTypeID, rt.Name rt_name, COUNT_BIG(*) n,
       SUM(r.AppliedAmt) applied, SUM(r.ARDAmount) ard, SUM(r.AuditorAmount) auditor, SUM(r.FeeValue) fee
FROM dbo.Remit r WITH (NOLOCK)
LEFT JOIN dbo.TransactionType tt ON tt.ID = r.TransactionTypeID
LEFT JOIN dbo.RecoveryType rt ON rt.ID = r.RecoveryTypeID
WHERE r.DivisionId = 2 AND r.AddDate >= DATEADD(MONTH,-12,DATEFROMPARTS(YEAR(GETDATE()),MONTH(GETDATE()),1))
GROUP BY r.TransactionTypeID, tt.Name, r.RecoveryTypeID, rt.Name ORDER BY applied DESC;

PRINT '=== R4. Remit Division 2, last 12 months: by RemitterType / RecoverySource / RecoveryMethod ===';
SELECT r.RemitterType, r.RecoverySource, rm.Name method, COUNT_BIG(*) n, SUM(r.AppliedAmt) applied, SUM(r.ARDAmount) ard
FROM dbo.Remit r WITH (NOLOCK) LEFT JOIN ruin.RecoveryMethod rm ON rm.RecoveryMethodId = r.RecoveryMethodId
WHERE r.DivisionId = 2 AND r.AddDate >= DATEADD(MONTH,-12,DATEFROMPARTS(YEAR(GETDATE()),MONTH(GETDATE()),1))
GROUP BY r.RemitterType, r.RecoverySource, rm.Name ORDER BY applied DESC;

PRINT '=== R5. RemitPendingClaim: claim-allocated Recovery $ by month x division, last 26 months (should track R2 applied) ===';
SELECT r.DivisionId, FORMAT(r.AddDate,'yyyy-MM') ym, COUNT_BIG(*) n_alloc, COUNT_BIG(DISTINCT rpc.ClaimID) n_claims,
       SUM(rpc.Recovery) recovery, SUM(rpc.WriteOff) writeoff, SUM(rpc.CoinDed) coinded
FROM dbo.Remit r WITH (NOLOCK) JOIN dbo.RemitPendingClaim rpc WITH (NOLOCK) ON rpc.RemitID = r.ID
WHERE r.AddDate >= DATEADD(MONTH,-26,DATEFROMPARTS(YEAR(GETDATE()),MONTH(GETDATE()),1))
GROUP BY r.DivisionId, FORMAT(r.AddDate,'yyyy-MM') ORDER BY r.DivisionId, ym;

PRINT '=== R6. Remit Division 2, last 12 months: top 25 client codes by applied $ (codes only, no member data) ===';
SELECT TOP 25 cl.Code AS client_code, cl.ParentCode, c.ParentClientCode, COUNT_BIG(DISTINCT r.ID) n_remits, SUM(r.AppliedAmt) applied
FROM dbo.Remit r WITH (NOLOCK)
OUTER APPLY (SELECT TOP 1 ClaimID FROM dbo.RemitPendingClaim WITH (NOLOCK) WHERE RemitID = r.ID) rpc
LEFT JOIN dbo.Claim c WITH (NOLOCK) ON c.ID = rpc.ClaimID
LEFT JOIN dbo.Client cl WITH (NOLOCK) ON cl.ID = c.ClientID
WHERE r.DivisionId = 2 AND r.AddDate >= DATEADD(MONTH,-12,DATEFROMPARTS(YEAR(GETDATE()),MONTH(GETDATE()),1))
GROUP BY cl.Code, cl.ParentCode, c.ParentClientCode ORDER BY applied DESC;

PRINT '=== R7. Remit Division 2, last 12 months: COB.AuditCategory (program-line candidate for the L2 split) ===';
SELECT cob.AuditCategory, COUNT_BIG(DISTINCT r.ID) n_remits, SUM(r.AppliedAmt) applied
FROM dbo.Remit r WITH (NOLOCK)
OUTER APPLY (SELECT TOP 1 ClaimID FROM dbo.RemitPendingClaim WITH (NOLOCK) WHERE RemitID = r.ID) rpc
LEFT JOIN dbo.Claim c WITH (NOLOCK) ON c.ID = rpc.ClaimID
LEFT JOIN dbo.COB cob WITH (NOLOCK) ON cob.ID = c.COBID
WHERE r.DivisionId = 2 AND r.AddDate >= DATEADD(MONTH,-12,DATEFROMPARTS(YEAR(GETDATE()),MONTH(GETDATE()),1))
GROUP BY cob.AuditCategory ORDER BY applied DESC;

PRINT '=== R8. Remit Division 2: daily $ last 120 days (batch-day shape, for the L30/P30 caveat) ===';
SELECT CAST(r.AddDate AS date) d, COUNT_BIG(*) n, SUM(r.AppliedAmt) applied, SUM(r.ARDAmount) ard
FROM dbo.Remit r WITH (NOLOCK)
WHERE r.DivisionId = 2 AND r.AddDate >= DATEADD(DAY,-120,CAST(GETDATE() AS date))
GROUP BY CAST(r.AddDate AS date) ORDER BY d;
PRINT '=== DONE ===';

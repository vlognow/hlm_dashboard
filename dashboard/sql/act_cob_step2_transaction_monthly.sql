/* =====================================================================
   RPS $ Recovered dashboard -- COB (Medical) from ACT
   Step 2c: per-claim ledger (dbo.Transaction) + status history, Division 2
   ---------------------------------------------------------------------
   SERVER/DB : TRGACAP3, ACT.  Read-only, aggregate-only.  HEAVY: Transaction
   has 241M rows and ClaimStatusHistory 547M; expect 5-20 minutes.
   HOW TO RUN: as step 2b; save as act_cob_step2_transaction_monthly_output.txt.
   PURPOSE   : cross-check Remit (step 2b) against the claim ledger, and
               confirm Division 2 is the COB medical book.
   TransactionType ids of interest: 6 Posted, 10 Completed Recovery, 19 Invoice,
   4 Write Off, 11 Adj-Provider, 12 Adj-Client, 15 Adjustment, 18 Internal Posted.
   ===================================================================== */
USE ACT; SET NOCOUNT ON; SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;
DECLARE @from datetime = DATEADD(MONTH,-26,DATEFROMPARTS(YEAR(GETDATE()),MONTH(GETDATE()),1));

PRINT '=== T1. Claim count by DivisionID (which division is the medical COB book?) ===';
SELECT c.DivisionID, d.Name, COUNT_BIG(*) n_claims, MIN(c.PaidDate) min_paid, MAX(c.PaidDate) max_paid
FROM dbo.Claim c WITH (NOLOCK) LEFT JOIN dbo.Division d ON d.ID = c.DivisionID
GROUP BY c.DivisionID, d.Name ORDER BY c.DivisionID;

PRINT '=== T2. Top 15 ParentClientCode per division (client codes only) ===';
SELECT * FROM (
  SELECT c.DivisionID, c.ParentClientCode, COUNT_BIG(*) n,
         ROW_NUMBER() OVER (PARTITION BY c.DivisionID ORDER BY COUNT_BIG(*) DESC) rn
  FROM dbo.Claim c WITH (NOLOCK) GROUP BY c.DivisionID, c.ParentClientCode) x
WHERE rn <= 15 ORDER BY DivisionID, rn;

PRINT '=== T3. COB.AuditCategory by DivisionID ===';
SELECT DivisionID, AuditCategory, COUNT_BIG(*) n FROM dbo.COB WITH (NOLOCK)
GROUP BY DivisionID, AuditCategory ORDER BY DivisionID, n DESC;

PRINT '=== T4. Transaction ledger, Division 2 claims: monthly $ by TransactionType, last 26 months ===';
SELECT FORMAT(t.[Date],'yyyy-MM') ym, tt.ID tt_id, tt.Name tt_name, COUNT_BIG(*) n, COUNT_BIG(DISTINCT t.ClaimID) n_claims, SUM(t.Amount) amount
FROM dbo.[Transaction] t WITH (NOLOCK)
JOIN dbo.TransactionTypeReason ttr WITH (NOLOCK) ON ttr.ID = t.TransactionTypeReasonID
JOIN dbo.TransactionType tt WITH (NOLOCK) ON tt.ID = ttr.TransactionTypeID
JOIN dbo.Claim c WITH (NOLOCK) ON c.ID = t.ClaimID
WHERE t.[Date] >= @from AND c.DivisionID = 2
GROUP BY FORMAT(t.[Date],'yyyy-MM'), tt.ID, tt.Name ORDER BY ym, amount DESC;

PRINT '=== T5. Transaction ledger, Division 2, Posted (6) + Completed Recovery (10): monthly by RecoveryType ===';
SELECT FORMAT(t.[Date],'yyyy-MM') ym, tt.Name tt_name, rt.Name rt_name, COUNT_BIG(*) n, SUM(t.Amount) amount
FROM dbo.[Transaction] t WITH (NOLOCK)
JOIN dbo.TransactionTypeReason ttr WITH (NOLOCK) ON ttr.ID = t.TransactionTypeReasonID
JOIN dbo.TransactionType tt WITH (NOLOCK) ON tt.ID = ttr.TransactionTypeID
LEFT JOIN dbo.RecoveryType rt WITH (NOLOCK) ON rt.ID = t.RecoveryTypeID
JOIN dbo.Claim c WITH (NOLOCK) ON c.ID = t.ClaimID
WHERE t.[Date] >= @from AND c.DivisionID = 2 AND tt.ID IN (6,10)
GROUP BY FORMAT(t.[Date],'yyyy-MM'), tt.Name, rt.Name ORDER BY ym, amount DESC;

PRINT '=== T6. Reconciliation: Remit.AppliedAmt vs Transaction Posted, Division 2, by month ===';
;WITH r AS (
  SELECT FORMAT(AddDate,'yyyy-MM') ym, SUM(AppliedAmt) remit_applied, SUM(ARDAmount) remit_ard
  FROM dbo.Remit WITH (NOLOCK) WHERE DivisionId = 2 AND AddDate >= @from GROUP BY FORMAT(AddDate,'yyyy-MM')),
t AS (
  SELECT FORMAT(t.[Date],'yyyy-MM') ym, SUM(t.Amount) txn_posted
  FROM dbo.[Transaction] t WITH (NOLOCK)
  JOIN dbo.TransactionTypeReason ttr WITH (NOLOCK) ON ttr.ID = t.TransactionTypeReasonID
  JOIN dbo.Claim c WITH (NOLOCK) ON c.ID = t.ClaimID
  WHERE t.[Date] >= @from AND c.DivisionID = 2 AND ttr.TransactionTypeID = 6
  GROUP BY FORMAT(t.[Date],'yyyy-MM'))
SELECT COALESCE(r.ym,t.ym) ym, r.remit_applied, r.remit_ard, t.txn_posted, r.remit_applied - t.txn_posted diff
FROM r FULL OUTER JOIN t ON t.ym = r.ym ORDER BY ym;

PRINT '=== T7. Claim status history, Division 2: monthly claims reaching recovery-ish statuses, last 26 months ===';
SELECT FORMAT(h.[Date],'yyyy-MM') ym, ss.Name status, COUNT_BIG(DISTINCT h.ClaimID) n_claims
FROM dbo.ClaimStatusHistory h WITH (NOLOCK)
JOIN dbo.Status s WITH (NOLOCK) ON s.ID = h.StatusID
JOIN dbo.StatusSecondary ss WITH (NOLOCK) ON ss.ID = s.StatusSecondaryID
JOIN dbo.Claim c WITH (NOLOCK) ON c.ID = h.ClaimID
WHERE h.[Date] >= @from AND c.DivisionID = 2
  AND ss.Name IN ('Cash Recovery','Direct','Fully Recovered','Partial Recovery','Fee Billed','Fee Received','Retraction Complete','Check Received')
GROUP BY FORMAT(h.[Date],'yyyy-MM'), ss.Name ORDER BY ym, status;
PRINT '=== DONE ===';

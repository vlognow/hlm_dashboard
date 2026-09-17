/* Step 2d: characterise Remit rows with DivisionId NULL (candidate medical COB book) vs Division 2.
   TRGACAP3 / ACT, read-only, aggregate-only. */
USE ACT; SET NOCOUNT ON; SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;
DECLARE @from datetime = DATEADD(MONTH,-12,DATEFROMPARTS(YEAR(GETDATE()),MONTH(GETDATE()),1));

PRINT '=== N0. Remit columns ===';
SELECT ORDINAL_POSITION, COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='Remit' ORDER BY ORDINAL_POSITION;

PRINT '=== N1. Division lookup ===';
SELECT * FROM dbo.Division;

PRINT '=== N2. NULL-division remits, last 12 months: Claim.DivisionID of the allocated claims ===';
SELECT c.DivisionID claim_division, d.Name, COUNT_BIG(DISTINCT r.ID) n_remits, SUM(r.AppliedAmt) applied, SUM(r.ARDAmount) ard, SUM(r.AuditorAmount) auditor
FROM dbo.Remit r WITH (NOLOCK)
OUTER APPLY (SELECT TOP 1 ClaimID FROM dbo.RemitPendingClaim WITH (NOLOCK) WHERE RemitID = r.ID) rpc
LEFT JOIN dbo.Claim c WITH (NOLOCK) ON c.ID = rpc.ClaimID
LEFT JOIN dbo.Division d ON d.ID = c.DivisionID
WHERE r.DivisionId IS NULL AND r.AddDate >= @from
GROUP BY c.DivisionID, d.Name ORDER BY applied DESC;

PRINT '=== N3. NULL-division remits, last 12 months: top 30 parent client codes ===';
SELECT TOP 30 c.ParentClientCode, cl.Code client_code, COUNT_BIG(DISTINCT r.ID) n_remits, SUM(r.AppliedAmt) applied, SUM(r.ARDAmount) ard, SUM(r.AuditorAmount) auditor
FROM dbo.Remit r WITH (NOLOCK)
OUTER APPLY (SELECT TOP 1 ClaimID FROM dbo.RemitPendingClaim WITH (NOLOCK) WHERE RemitID = r.ID) rpc
LEFT JOIN dbo.Claim c WITH (NOLOCK) ON c.ID = rpc.ClaimID
LEFT JOIN dbo.Client cl WITH (NOLOCK) ON cl.ID = c.ClientID
WHERE r.DivisionId IS NULL AND r.AddDate >= @from
GROUP BY c.ParentClientCode, cl.Code ORDER BY applied DESC;

PRINT '=== N4. NULL-division remits, last 12 months: TransactionType x RecoveryType ===';
SELECT r.TransactionTypeID, tt.Name tt_name, r.RecoveryTypeID, rt.Name rt_name, COUNT_BIG(*) n, SUM(r.AppliedAmt) applied, SUM(r.ARDAmount) ard, SUM(r.AuditorAmount) auditor
FROM dbo.Remit r WITH (NOLOCK) LEFT JOIN dbo.TransactionType tt ON tt.ID=r.TransactionTypeID LEFT JOIN dbo.RecoveryType rt ON rt.ID=r.RecoveryTypeID
WHERE r.DivisionId IS NULL AND r.AddDate >= @from GROUP BY r.TransactionTypeID, tt.Name, r.RecoveryTypeID, rt.Name ORDER BY applied DESC;

PRINT '=== N5. NULL-division remits, last 12 months: RemitterType x RecoverySource ===';
SELECT r.RemitterType, r.RecoverySource, COUNT_BIG(*) n, SUM(r.AppliedAmt) applied FROM dbo.Remit r WITH (NOLOCK)
WHERE r.DivisionId IS NULL AND r.AddDate >= @from GROUP BY r.RemitterType, r.RecoverySource ORDER BY applied DESC;

PRINT '=== N6. NULL-division remits, last 12 months: COB.AuditCategory ===';
SELECT cob.AuditCategory, COUNT_BIG(DISTINCT r.ID) n_remits, SUM(r.AppliedAmt) applied
FROM dbo.Remit r WITH (NOLOCK)
OUTER APPLY (SELECT TOP 1 ClaimID FROM dbo.RemitPendingClaim WITH (NOLOCK) WHERE RemitID = r.ID) rpc
LEFT JOIN dbo.Claim c WITH (NOLOCK) ON c.ID = rpc.ClaimID LEFT JOIN dbo.COB cob WITH (NOLOCK) ON cob.ID = c.COBID
WHERE r.DivisionId IS NULL AND r.AddDate >= @from GROUP BY cob.AuditCategory ORDER BY applied DESC;

PRINT '=== N7. Division 2 remits, last 12 months: Claim.DivisionID + top parent client codes (is it Subro?) ===';
SELECT TOP 30 c.DivisionID claim_division, c.ParentClientCode, COUNT_BIG(DISTINCT r.ID) n_remits, SUM(r.AppliedAmt) applied
FROM dbo.Remit r WITH (NOLOCK)
OUTER APPLY (SELECT TOP 1 ClaimID FROM dbo.RemitPendingClaim WITH (NOLOCK) WHERE RemitID = r.ID) rpc
LEFT JOIN dbo.Claim c WITH (NOLOCK) ON c.ID = rpc.ClaimID
WHERE r.DivisionId = 2 AND r.AddDate >= @from GROUP BY c.DivisionID, c.ParentClientCode ORDER BY applied DESC;

PRINT '=== N8. NULL-division: does ARD + Auditor = Applied? and how many remits have no claim allocation ===';
SELECT COUNT_BIG(*) n, SUM(r.AppliedAmt) applied, SUM(ISNULL(r.ARDAmount,0) + ISNULL(r.AuditorAmount,0)) ard_plus_auditor,
       SUM(CASE WHEN rpc.RemitID IS NULL THEN 1 ELSE 0 END) n_unallocated
FROM dbo.Remit r WITH (NOLOCK)
LEFT JOIN (SELECT DISTINCT RemitID FROM dbo.RemitPendingClaim WITH (NOLOCK)) rpc ON rpc.RemitID = r.ID
WHERE r.DivisionId IS NULL AND r.AddDate >= @from;

PRINT '=== N9. Monthly, last 26 months, NULL-division: applied + count of distinct remits with ARD vs Auditor ===';
SELECT FORMAT(r.AddDate,'yyyy-MM') ym, COUNT_BIG(*) n, SUM(r.AppliedAmt) applied, SUM(r.ARDAmount) ard, SUM(r.AuditorAmount) auditor,
       SUM(CASE WHEN r.AppliedAmt < 0 THEN r.AppliedAmt END) negatives
FROM dbo.Remit r WITH (NOLOCK) WHERE r.DivisionId IS NULL AND r.AddDate >= DATEADD(MONTH,-26,DATEFROMPARTS(YEAR(GETDATE()),MONTH(GETDATE()),1))
GROUP BY FORMAT(r.AddDate,'yyyy-MM') ORDER BY ym;
PRINT '=== DONE ===';

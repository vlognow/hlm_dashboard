/* Step 2a: metadata only -- column definitions + small lookup tables. No claim/member/dollar rows. */
USE ACT; SET NOCOUNT ON; SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;
PRINT '=== columns: Transaction, TransactionHistory, Check, TransactionFees, Disbursement, RecoveryPayType, RecoveryType, TransactionType, RecoveryMethod, Division ===';
SELECT TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION, COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME IN ('Transaction','TransactionHistory','Check','TransactionFees','Disbursement','RecoveryPayType','RecoveryType','TransactionType','RecoveryMethod','Division')
ORDER BY TABLE_NAME, ORDINAL_POSITION;
PRINT '=== view columns: vwRemitInfo, vwTransactionInfo, vTransactionDetail, vClaimTransactionSummary ===';
SELECT TABLE_NAME, ORDINAL_POSITION, COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME IN ('vwRemitInfo','vwTransactionInfo','vTransactionDetail','vClaimTransactionSummary') ORDER BY TABLE_NAME, ORDINAL_POSITION;
PRINT '=== lookup: TransactionType ==='; SELECT * FROM dbo.TransactionType ORDER BY 1;
PRINT '=== lookup: RecoveryType ==='; SELECT * FROM dbo.RecoveryType ORDER BY 1;
PRINT '=== lookup: ruin.RecoveryMethod ==='; SELECT * FROM ruin.RecoveryMethod ORDER BY 1;
PRINT '=== lookup: RecoveryPayType ==='; IF OBJECT_ID('dbo.RecoveryPayType') IS NOT NULL EXEC('SELECT * FROM dbo.RecoveryPayType ORDER BY 1') ELSE PRINT 'none';
PRINT '=== lookup: DivisionStatusLookup ==='; SELECT * FROM dbo.DivisionStatusLookup ORDER BY 1;
PRINT '=== view definition: vwRemitInfo ==='; SELECT OBJECT_DEFINITION(OBJECT_ID('dbo.vwRemitInfo'));
PRINT '=== view definition: vTransactionDetail ==='; SELECT OBJECT_DEFINITION(OBJECT_ID('dbo.vTransactionDetail'));

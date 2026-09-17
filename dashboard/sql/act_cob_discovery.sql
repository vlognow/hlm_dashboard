/* =====================================================================
   RPS $ Recovered dashboard -- COB (Medical) dated recoveries from ACT
   Step 1: schema discovery + first-cut monthly numbers
   ---------------------------------------------------------------------
   DATABASE : ACT
   SERVER   : TRGACAP3 (192.168.251.12). A second copy is on 192.168.251.18.
              Prod alias per the COBE PRD: SQLUserShared.
   HOW TO RUN: SSMS -> connect to the server -> set database to ACT
               (or leave the USE line below) -> Query > Results To > Text
               (Ctrl+T) so all result sets land in one output -> Execute
               -> save the output as act_discovery_output.txt and send it back.
   Read-only. Every section is guarded so a missing object skips instead
   of aborting the script.
   ===================================================================== */
USE ACT;
SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;

PRINT '=== A1. Server / database / row counts of every user table ===';
SELECT @@SERVERNAME AS server_name, DB_NAME() AS db_name, GETDATE() AS run_at;

SELECT s.name AS schema_name, t.name AS table_name,
       SUM(p.rows) AS row_count
FROM sys.tables t
JOIN sys.schemas s ON s.schema_id = t.schema_id
JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0,1)
GROUP BY s.name, t.name
ORDER BY SUM(p.rows) DESC;

PRINT '=== A2. Views ===';
SELECT s.name AS schema_name, v.name AS view_name
FROM sys.views v JOIN sys.schemas s ON s.schema_id = v.schema_id
ORDER BY s.name, v.name;

PRINT '=== A3. Columns that look like division / invoice / recovery / posting / payment / remit ===';
SELECT c.TABLE_SCHEMA, c.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE
FROM INFORMATION_SCHEMA.COLUMNS c
WHERE c.COLUMN_NAME LIKE '%Division%'
   OR c.COLUMN_NAME LIKE '%Invoice%'
   OR c.COLUMN_NAME LIKE '%Recover%'
   OR c.COLUMN_NAME LIKE '%Post%'
   OR c.COLUMN_NAME LIKE '%Payment%'
   OR c.COLUMN_NAME LIKE '%Paid%'
   OR c.COLUMN_NAME LIKE '%Remit%'
   OR c.COLUMN_NAME LIKE '%Check%'
   OR c.COLUMN_NAME LIKE '%Deposit%'
   OR c.COLUMN_NAME LIKE '%Fee%'
ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION;

PRINT '=== A4. Tables that have BOTH a date/datetime column AND a money/decimal column (candidate ledgers) ===';
SELECT c.TABLE_SCHEMA, c.TABLE_NAME,
       SUM(CASE WHEN c.DATA_TYPE IN ('date','datetime','datetime2','smalldatetime') THEN 1 ELSE 0 END) AS n_date_cols,
       SUM(CASE WHEN c.DATA_TYPE IN ('money','smallmoney','decimal','numeric','float') THEN 1 ELSE 0 END) AS n_amount_cols,
       STRING_AGG(CASE WHEN c.DATA_TYPE IN ('date','datetime','datetime2','smalldatetime') THEN c.COLUMN_NAME END, ', ') AS date_cols,
       STRING_AGG(CASE WHEN c.DATA_TYPE IN ('money','smallmoney','decimal','numeric','float') THEN c.COLUMN_NAME END, ', ') AS amount_cols
FROM INFORMATION_SCHEMA.COLUMNS c
JOIN sys.tables t ON t.name = c.TABLE_NAME AND SCHEMA_NAME(t.schema_id) = c.TABLE_SCHEMA
GROUP BY c.TABLE_SCHEMA, c.TABLE_NAME
HAVING SUM(CASE WHEN c.DATA_TYPE IN ('date','datetime','datetime2','smalldatetime') THEN 1 ELSE 0 END) > 0
   AND SUM(CASE WHEN c.DATA_TYPE IN ('money','smallmoney','decimal','numeric','float') THEN 1 ELSE 0 END) > 0
ORDER BY n_amount_cols DESC, n_date_cols DESC;

PRINT '=== A5. Full column list for the tables we already know exist (claim, Client, COB, COBContent) plus anything named Division/Invoice ===';
SELECT c.TABLE_SCHEMA, c.TABLE_NAME, c.ORDINAL_POSITION, c.COLUMN_NAME, c.DATA_TYPE
FROM INFORMATION_SCHEMA.COLUMNS c
WHERE c.TABLE_NAME IN ('claim','Client','COB','COBContent','vwClaimStatusHistory','vStatusFull','Status','ClaimStatusHistory')
   OR c.TABLE_NAME LIKE '%Division%'
   OR c.TABLE_NAME LIKE '%Invoice%'
   OR c.TABLE_NAME LIKE '%Recover%'
   OR c.TABLE_NAME LIKE '%Payment%'
   OR c.TABLE_NAME LIKE '%Remit%'
ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION;

PRINT '=== B1. Division lookup (John: COB = Division ID 2) ===';
IF OBJECT_ID('dbo.Division') IS NOT NULL
    EXEC('SELECT TOP 50 * FROM dbo.Division ORDER BY 1');
ELSE
    PRINT 'no dbo.Division table -- see A3/A5 for where DivisionID lives';

PRINT '=== B2. Status taxonomy (vStatusFull) ===';
IF OBJECT_ID('dbo.vStatusFull') IS NOT NULL
    EXEC('SELECT * FROM dbo.vStatusFull ORDER BY 1');
ELSE
    PRINT 'no dbo.vStatusFull';

PRINT '=== B3. Client table: how many clients per division ===';
IF OBJECT_ID('dbo.Client') IS NOT NULL AND COL_LENGTH('dbo.Client','DivisionID') IS NOT NULL
    EXEC('SELECT DivisionID, COUNT(*) AS n_clients, MIN(Code) AS example_code FROM dbo.Client GROUP BY DivisionID ORDER BY DivisionID');
ELSE
    PRINT 'dbo.Client has no DivisionID column (or no Client table) -- check A3 for the division column';

PRINT '=== B4. claim table: 5 sample rows and date range ===';
IF OBJECT_ID('dbo.claim') IS NOT NULL
BEGIN
    EXEC('SELECT TOP 5 * FROM dbo.claim ORDER BY ID DESC');
    EXEC('SELECT COUNT_BIG(*) AS n_claims, MIN(StartDateOfService) AS min_dos, MAX(StartDateOfService) AS max_dos FROM dbo.claim');
END

PRINT '=== B5. Claim status history: which statuses exist and their date range (this is where Fee Billed / recovery dates should be) ===';
IF OBJECT_ID('dbo.vwClaimStatusHistory') IS NOT NULL
    EXEC('SELECT [Status], COUNT_BIG(*) AS n, MIN(StatusDate) AS first_dt, MAX(StatusDate) AS last_dt
          FROM dbo.vwClaimStatusHistory GROUP BY [Status] ORDER BY n DESC');
ELSE
    PRINT 'no dbo.vwClaimStatusHistory';

PRINT '=== B6. For every candidate ledger table from A4 with an Invoice/Recover/Paid/Post date: monthly $ for the last 24 months (auto-generated) ===';
/* Builds, for each table that has a date column named like Invoice/Recover/Paid/Post/Remit/Check
   and an amount column, a monthly sum for the last 24 months. Read-only; skips tables > 200M rows. */
DECLARE @sql NVARCHAR(MAX) = N'';
;WITH d AS (
    SELECT c.TABLE_SCHEMA, c.TABLE_NAME, c.COLUMN_NAME AS date_col,
           ROW_NUMBER() OVER (PARTITION BY c.TABLE_SCHEMA, c.TABLE_NAME ORDER BY
               CASE WHEN c.COLUMN_NAME LIKE '%Recover%' THEN 1 WHEN c.COLUMN_NAME LIKE '%Post%' THEN 2
                    WHEN c.COLUMN_NAME LIKE '%Paid%' THEN 3 WHEN c.COLUMN_NAME LIKE '%Remit%' THEN 4
                    WHEN c.COLUMN_NAME LIKE '%Check%' THEN 5 WHEN c.COLUMN_NAME LIKE '%Invoice%' THEN 6 ELSE 9 END) AS rn
    FROM INFORMATION_SCHEMA.COLUMNS c
    WHERE c.DATA_TYPE IN ('date','datetime','datetime2','smalldatetime')
      AND (c.COLUMN_NAME LIKE '%Recover%' OR c.COLUMN_NAME LIKE '%Post%' OR c.COLUMN_NAME LIKE '%Paid%'
           OR c.COLUMN_NAME LIKE '%Remit%' OR c.COLUMN_NAME LIKE '%Check%' OR c.COLUMN_NAME LIKE '%Invoice%')
), a AS (
    SELECT c.TABLE_SCHEMA, c.TABLE_NAME, c.COLUMN_NAME AS amt_col,
           ROW_NUMBER() OVER (PARTITION BY c.TABLE_SCHEMA, c.TABLE_NAME ORDER BY
               CASE WHEN c.COLUMN_NAME LIKE '%Recover%' THEN 1 WHEN c.COLUMN_NAME LIKE '%Paid%' THEN 2
                    WHEN c.COLUMN_NAME LIKE '%Amount%' THEN 3 WHEN c.COLUMN_NAME LIKE '%Amt%' THEN 4 ELSE 9 END) AS rn
    FROM INFORMATION_SCHEMA.COLUMNS c
    WHERE c.DATA_TYPE IN ('money','smallmoney','decimal','numeric','float')
), sz AS (
    SELECT SCHEMA_NAME(t.schema_id) AS TABLE_SCHEMA, t.name AS TABLE_NAME, SUM(p.rows) AS row_count
    FROM sys.tables t JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0,1)
    GROUP BY t.schema_id, t.name
)
SELECT @sql = @sql + N'
PRINT ''--- ' + d.TABLE_SCHEMA + '.' + d.TABLE_NAME + ' by month of ' + d.date_col + ' summing ' + a.amt_col + ' (rows=' + CAST(sz.row_count AS NVARCHAR(20)) + ') ---'';
BEGIN TRY
SELECT ''' + d.TABLE_SCHEMA + '.' + d.TABLE_NAME + ''' AS tbl, ''' + d.date_col + ''' AS date_col, ''' + a.amt_col + ''' AS amt_col,
       FORMAT(' + QUOTENAME(d.date_col) + ', ''yyyy-MM'') AS ym, COUNT_BIG(*) AS n_rows, SUM(CAST(' + QUOTENAME(a.amt_col) + ' AS DECIMAL(18,2))) AS total_amt
FROM ' + QUOTENAME(d.TABLE_SCHEMA) + '.' + QUOTENAME(d.TABLE_NAME) + ' WITH (NOLOCK)
WHERE ' + QUOTENAME(d.date_col) + ' >= DATEADD(MONTH, -24, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
GROUP BY FORMAT(' + QUOTENAME(d.date_col) + ', ''yyyy-MM'') ORDER BY ym;
END TRY BEGIN CATCH PRINT ''  skipped: '' + ERROR_MESSAGE(); END CATCH;'
FROM d JOIN a ON a.TABLE_SCHEMA = d.TABLE_SCHEMA AND a.TABLE_NAME = d.TABLE_NAME AND a.rn = 1
JOIN sz ON sz.TABLE_SCHEMA = d.TABLE_SCHEMA AND sz.TABLE_NAME = d.TABLE_NAME
WHERE d.rn = 1 AND sz.row_count BETWEEN 1 AND 200000000;
IF @sql = N'' PRINT 'no candidate ledger tables found by column naming -- fall back to B5 status history';
ELSE EXEC sp_executesql @sql;

PRINT '=== B7. First-cut COB monthly from claim status history, Division 2, if the columns line up ===';
/* Assumes: dbo.claim (ID, ClientID), dbo.Client (ID, DivisionID), dbo.vwClaimStatusHistory (ClaimID, Status, StatusDate).
   Counts claims reaching each status per month for Division 2. Dollars are added in step 2 once B3-B6 show the amount column. */
IF OBJECT_ID('dbo.claim') IS NOT NULL AND OBJECT_ID('dbo.Client') IS NOT NULL AND OBJECT_ID('dbo.vwClaimStatusHistory') IS NOT NULL
   AND COL_LENGTH('dbo.Client','DivisionID') IS NOT NULL
BEGIN
    BEGIN TRY
    EXEC('SELECT hs.[Status], FORMAT(hs.StatusDate, ''yyyy-MM'') AS ym, COUNT_BIG(DISTINCT hs.ClaimID) AS n_claims
          FROM dbo.vwClaimStatusHistory hs WITH (NOLOCK)
          JOIN dbo.claim c WITH (NOLOCK) ON c.ID = hs.ClaimID
          JOIN dbo.Client ct WITH (NOLOCK) ON ct.ID = c.ClientID
          WHERE ct.DivisionID = 2
            AND hs.StatusDate >= DATEADD(MONTH, -24, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
          GROUP BY hs.[Status], FORMAT(hs.StatusDate, ''yyyy-MM'')
          ORDER BY hs.[Status], ym');
    END TRY BEGIN CATCH PRINT '  B7 skipped: ' + ERROR_MESSAGE(); END CATCH;
END
ELSE PRINT 'B7 skipped: claim / Client.DivisionID / vwClaimStatusHistory not all present -- will rewrite from A5 output';

PRINT '=== DONE ===';

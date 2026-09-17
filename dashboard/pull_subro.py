import studio, json, time
import pandas as pd

t0 = time.time()

# A) daily total, Subrogation only (~300 business days, well under the 5000-row cap)
sqlA = """
SELECT CAST(RecoveryDate AS date) AS RecoveryDate,
       SUM(GrossRecovery) AS GrossRecovery, COUNT(DISTINCT File_key) AS Files
FROM `SubroReports.rpt.RecoveriesbyLOBTableau`
WHERE IsPostedRecovery = true AND Division = 'S'
  AND RecoveryDate >= date_sub(current_date(), 430)
GROUP BY CAST(RecoveryDate AS date)
"""
dA = studio.q(sqlA, timeout=1800, retries=1)
dA.to_parquet('data/subro_daily_total.parquet', index=False)
print('A rows', len(dA), f'{time.time()-t0:.0f}s')

# B) daily x team, last 60 days only (for unit small-multiples / daily-by-unit chart)
sqlB = """
SELECT CAST(RecoveryDate AS date) AS RecoveryDate, Team,
       SUM(GrossRecovery) AS GrossRecovery, COUNT(DISTINCT File_key) AS Files
FROM `SubroReports.rpt.RecoveriesbyLOBTableau`
WHERE IsPostedRecovery = true AND Division = 'S'
  AND RecoveryDate >= date_sub(current_date(), 60)
GROUP BY CAST(RecoveryDate AS date), Team
"""
dB = studio.q(sqlB, timeout=1800, retries=1)
dB.to_parquet('data/subro_daily_team_60d.parquet', index=False)
print('B rows', len(dB), f'{time.time()-t0:.0f}s')

# C) monthly total, last 14 months (for the 12-month trend page)
sqlC = """
SELECT date_format(RecoveryDate,'yyyy-MM') AS YearMonth,
       SUM(GrossRecovery) AS GrossRecovery, COUNT(DISTINCT File_key) AS Files
FROM `SubroReports.rpt.RecoveriesbyLOBTableau`
WHERE IsPostedRecovery = true AND Division = 'S'
  AND RecoveryDate >= add_months(current_date(), -14)
GROUP BY date_format(RecoveryDate,'yyyy-MM')
"""
dC = studio.q(sqlC, timeout=1800, retries=1)
dC.to_parquet('data/subro_monthly_total.parquet', index=False)
print('C rows', len(dC), f'{time.time()-t0:.0f}s')

# D) monthly x team, last 14 months (for unit-level monthly trend on drill page)
sqlD = """
SELECT date_format(RecoveryDate,'yyyy-MM') AS YearMonth, Team,
       SUM(GrossRecovery) AS GrossRecovery, COUNT(DISTINCT File_key) AS Files
FROM `SubroReports.rpt.RecoveriesbyLOBTableau`
WHERE IsPostedRecovery = true AND Division = 'S'
  AND RecoveryDate >= add_months(current_date(), -14)
GROUP BY date_format(RecoveryDate,'yyyy-MM'), Team
"""
dD = studio.q(sqlD, timeout=1800, retries=1)
dD.to_parquet('data/subro_monthly_team.parquet', index=False)
print('D rows', len(dD), f'{time.time()-t0:.0f}s')

# E) top files by $ recovered in the last 60 days (ORDER BY + LIMIT so truncation can't drop big ones)
sqlE = """
SELECT File_key, ContractualClientCode, Parent_Name, Parent_Code, clnt_name, clnt_code, Team, LOB,
       SUM(GrossRecovery) AS GrossRecovery, MAX(RecoveryDate) AS LastRecoveryDate
FROM `SubroReports.rpt.RecoveriesbyLOBTableau`
WHERE IsPostedRecovery = true AND Division = 'S'
  AND RecoveryDate >= date_sub(current_date(), 60)
GROUP BY File_key, ContractualClientCode, Parent_Name, Parent_Code, clnt_name, clnt_code, Team, LOB
ORDER BY GrossRecovery DESC
LIMIT 500
"""
dE = studio.q(sqlE, timeout=1800, retries=1)
dE.to_parquet('data/subro_top_files_60d.parquet', index=False)
print('E rows', len(dE), f'{time.time()-t0:.0f}s')

print('DONE')

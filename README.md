# RPS $ Recovered — Executive Dashboard (HLM)

Working repo for the RPS high-level "$ recovered" dashboard across Subrogation, COB (medical) and Pharmacy programs.

## Where to update

**Notion note (the deliverable, update this):**
https://app.notion.com/p/machinify/RPS-Recovered-Proposal-for-RPS-High-Level-Dashbaord-Analytics-Monitoring-3dc5356b3971812fb847cec6bee99566

Companion Notion pages in the same "HLM Dashboard" space: *RPS $ Recovered — Design & Build Plan* and *RPS Dashboard — Real Data Visual (Mockup)*.

## Current state (2026-09-17)

| Pillar | Status | Source |
|---|---|---|
| Subrogation | Monthly posted $ done, through Sep 2026 | `SubroReports.rpt.RecoveriesbyLOBTableau` (TRGDMGREP1, Studio project 0010z) |
| Pharmacy programs | Monthly posted $ done | `DMGMining.dbo.PostedRecoveryTrendingData` (192.168.251.18, Studio project 0012k) |
| COB (medical) | **Monthly posted $ done (2026-09-17).** Aug 2026 $8.63M, T12 $124.71M. Source is `ACT.dbo.Remit` with `DivisionId IS NULL` (Payment Integrity book). `DivisionId = 2` turned out to be Subrogation at the submitted stage and is NOT used (see `DECISIONS.md`). | `ACT.dbo.Remit` on TRGACAP3, pulled by `dashboard/pull_cob_act.py` via direct pymssql. |

## COB: what the ACT discovery found (2026-09-16)

Full output (PHI sample rows redacted) is in `dashboard/sql/act_discovery_output.txt` (git-ignored, local only). Summary:

**ACT is the audit/COB claim and remittance system**, 521 tables. The recovery ledger is a small cluster of `dbo` tables:

| Table | Rows | Role |
|---|---|---|
| `Remit` | 2.8 M | **One row per posted remittance.** `AddDate` (posting date), `DivisionId`, `ARDAmount`, `AuditorAmount`, `AppliedAmt`, `FeeValue`, `SecondaryFeeValue`, `RecoveryTypeID` (Cash / Direct / Retraction / Check / EFT / Card / Adjustment…), `TransactionTypeID`, `RecoveryMethodId`, `InvestigationId`, `RecoverySource`, `RemitterType`, `IsDisputed`. This is the `FactRecovery` source for COB. |
| `RemitPendingClaim` | 1.35 M | Allocation of a remit to claims: `RemitID`, `ClaimID`, `Recovery`, `WriteOff`, `CoinDed`. |
| `RemitCheck` → `Check` | 1.9 M / 2.0 M | Physical check: `CheckNumber`, `Date`, `Amount`, `DisbursementAmount`. |
| `RemitTransaction` → `Transaction` | 65 M / 241 M | Per-claim ledger: `ClaimID`, `Date`, `Amount`, `TransactionTypeReasonID` → `TransactionType` (6 Posted, 10 Completed Recovery, 19 Invoice, 4 Write Off, 11/12 Adj-Provider/Client, 15 Adjustment, 18 Internal Posted), `RecoveryTypeID`, `StatusID`. |
| `Claim` | 101.5 M | Claim line: `DivisionID`, `ClientID`, `ParentClientCode`, `InvestigationID`, `COBID`, `InvoiceID`, `ChargedAmount`, `ClientPaidAmount`, `OverPaidAmount`, `PaidDate`, DOS. Carries member PHI — aggregate only. |
| `COB` | 15.8 M | The COB case (other-coverage record): `DivisionID`, primacy dates, group, `AuditCategory` (candidate L2 program line). |
| `ClaimStatusHistory` / `vwClaimStatusHistory` | 547 M | Status timeline. Recovery statuses: Cash Recovery, Direct, Partial Recovery, Fully Recovered, Fee Billed, Fee Received, Retraction Complete, Check Received. |
| `vwRemitInfo`, `vTransactionDetail`, `vClaimTransactionSummary` | views | The app's own denormalised reporting views (definitions saved in `act_cob_step2_metadata_output.txt`). |

**Division lookup** (`dbo.Division`): 1 Audit / "Payment Integrity", 2 **Subro**, 3 Pharmacy, 4 CPS. John Marcsik said COB = Division 2, and the Division 2 claim rows carry the COB overpayment pattern (ClientPaidAmount / OverPaidAmount, parents HRP, CIG). `vTransactionDetail` explicitly *excludes* Division "Subro", so ACT's own reporting treats Division 2 as a separate book. Treat "Division 2 = COB medical" as John's statement to be confirmed by R6/R7/T1–T3 (client codes and audit categories), not as settled.

Things that looked like ledgers but are not: `dbo.Claim.PaidDate` is the *client's* original paid date, not a recovery; `dwAudit.tblInvoiceSummary` and `rpt.HitDetail` returned no rows for the last 24 months; `ClientFee` is a fee-schedule table.

## Status 2026-09-17 and next steps

Done: overall RPS total (Aug 2026 $124.43M, +3.9% MoM, T12 $1,350.14M) with stacked chart, COB monthly series, COB by audit category and by client, all on the Notion note. Outputs: `dashboard/cob_act_*.csv`, `dashboard/rps_total_monthly.csv`, `dashboard/exec_chart_cob_*.png`, `dashboard/exec_chart_rps_total_monthly.png`.

Open items:
1. `dashboard/sql/act_cob_step2_transaction_monthly.sql` (ledger cross-check, heavy) was started 2026-09-17 in the background; if `sql/act_cob_step2_transaction_monthly_output.txt` is still 89 bytes it did not finish. Rerun with `python dashboard/run_act_discovery.py dashboard/sql/act_cob_step2_transaction_monthly.sql` off-hours. Its T6 reconciles `Remit.AppliedAmt` to `Transaction` type 6 Posted; note T1-T7 filter on Division 2, which we now know is Subro, so change them to `c.DivisionID = 1` before rerunning.
2. Confirm with Josh Roberts (DMG) / COB Ops that `Remit.AppliedAmt`, NULL division, is what finance recognises as posted COB recovery, and that the Jun 2026 process change (remits now linked through `RemitTransaction` instead of `RemitPendingClaim`) is expected.
3. Reconcile the Pharmacy series against Kyle Schmidt's Power BI dashboards.
4. Design doc §2 COB rows: replace the Division 2 assumption with the NULL-division finding (done in summary rows; draft SQL block still says `DivisionId = 2`).

## Layout

- `RPS_Recovered_Exec_Dashboard_Design.md` — full design doc (sources, model, pipeline, owners, blockers).
- `RPS_Dashboard_Real_Data_Visual.md` — mockup narrative with real numbers.
- `dashboard/` — Studio query helpers (`studio.py` for 0010z lives in `~/subro/thresholding/analysis/`, `studio_cob.py` here for 0012k), probe scripts, pulled CSVs, generated charts (`exec_chart_*.png`), Streamlit app (`app.py`).
- `DECISIONS.md` — decision log (why NULL-division = COB, why Division 2 is excluded, totals rule).
- `dashboard/pull_cob_act.py`, `generate_cob_charts.py`, `generate_rps_total_chart.py` — COB pull and the COB / overall charts.
- `dashboard/sql/` — SQL to run directly on the SQL Servers:
  - `act_cob_discovery.sql` — step 1, schema discovery (done 2026-09-16).
  - `act_cob_step2_metadata.sql` — column definitions, lookups, view definitions (done).
  - `act_cob_step2_remit_monthly.sql` — step 2b, monthly posted $ from `Remit` (run 2026-09-17).
  - `act_cob_step2d_null_division.sql` — step 2d, proves NULL division = COB and Division 2 = Subro (run 2026-09-17).
  - `act_cob_step2_transaction_monthly.sql` — step 2c, ledger cross-check (started, see open items).
  - `*output*.txt` — query outputs, git-ignored because they can contain PHI.
- `dashboard/catalog_ranked_*.csv` — column catalogs of CarlQryRun and DMGMining ranked by date/money column counts.

## Direct SQL access from JupyterHub (preferred for ACT / SmartII / RXP)

Verified 2026-09-17: JupyterHub reaches the Rawlings SQL Servers directly on port 1433, so Studio is not required.

- Credentials: `~/sql_access.txt` (outside the repo, chmod 600, never commit). Domain login `TRGLLC\<user>`.
- Driver: `pip install --user pymssql` (already installed for jovyan).
- Helper: `dashboard/act_conn.py`

```python
import sys; sys.path.insert(0, '/home/jovyan/HLM dashboard/dashboard')
import act_conn
df = act_conn.q("SELECT TOP 5 * FROM sys.tables")                      # ACT on TRGACAP3 (192.168.251.12)
df = act_conn.q("SELECT ...", db='SmartII')                             # same server, other DB
df = act_conn.q("SELECT ...", db='DMGMining', host=act_conn.HOSTS['PIDCOB'])   # 192.168.251.18
```

Plain T-SQL (TOP, three-part names, cross-database joins all work). Use `WITH (NOLOCK)` on big tables.
The ACT discovery script can be run as `python dashboard/run_act_discovery.py` (writes `dashboard/sql/act_discovery_output.txt`).

## Studio access notes (fallback)

Studio custom SQL is Spark-SQL flavoured: backtick-quote registered names, `LIMIT` not `TOP`, queries take minutes. Registering a table = `proj.createResource(name, sourceid, identifier, jdbc.0)`; identifiers must be two-part (`schema.table`) inside the source's own database. Source ids: 0010z — S000ei Subro_SRS, S000eq SubroReports, S000ej SubroIntelligence, S000eh RawlingsCommon; 0012k — S001ii CarlQryRun, S001ij DMGMining.

ACT is **not** in Studio. It is reachable directly: `sqlcmd -S TRGACAP3 -d ACT -E` (Windows integrated auth, same as the subro-ai-extractor PowerShell scripts use for TRGDMGREP1). Use `-W -w 300` for readable text output, or `-y 0 -w 65535` when pulling view definitions. A second copy of ACT is on 192.168.251.18; prod alias per the COBE PRD is `SQLUserShared`.

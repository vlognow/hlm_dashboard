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
| COB (medical) | **Blocked: no dated source reachable from Studio.** John Marcsik says the dates live in **ACT, Division ID = 2** (claim-line invoice/recovery dates). ACT exists on TRGACAP3 (192.168.251.12) and 192.168.251.18 but Studio sources are bound to CarlQryRun / DMGMining only. | Run `dashboard/sql/act_cob_discovery.sql` against database **ACT** with SSMS; paste the output back, then write the monthly aggregation and restate the overall RPS total at the top of the Notion note. |

## Next step for whoever picks this up

1. Run `dashboard/sql/act_cob_discovery.sql` on server TRGACAP3, database `ACT` (SSMS, Results to Text). It is read-only and every section is guarded.
2. From the output, identify the posted-recovery table/columns for Division 2 and write the monthly sum (last 12 complete months, plus trailing-12 and vs-prior-month).
3. Update the Notion note: replace the "COB (Medical) — Source Status" section with the monthly series, fill the COB column of the By Pillar table, and restate "Total Posted Recoveries" as Subro + Pharmacy + COB.

## Layout

- `RPS_Recovered_Exec_Dashboard_Design.md` — full design doc (sources, model, pipeline, owners, blockers).
- `RPS_Dashboard_Real_Data_Visual.md` — mockup narrative with real numbers.
- `dashboard/` — Studio query helpers (`studio.py` for 0010z lives in `~/subro/thresholding/analysis/`, `studio_cob.py` here for 0012k), probe scripts, pulled CSVs, generated charts (`exec_chart_*.png`), Streamlit app (`app.py`).
- `dashboard/sql/` — SQL to run directly on the SQL Servers (starts with the ACT discovery script).
- `dashboard/catalog_ranked_*.csv` — column catalogs of CarlQryRun and DMGMining ranked by date/money column counts.

## Access notes

Studio custom SQL is Spark-SQL flavoured: backtick-quote registered names, `LIMIT` not `TOP`, queries take minutes. Registering a table = `proj.createResource(name, sourceid, identifier, jdbc.0)`; identifiers must be two-part (`schema.table`) inside the source's own database. Source ids: 0010z — S000ei Subro_SRS, S000eq SubroReports, S000ej SubroIntelligence, S000eh RawlingsCommon; 0012k — S001ii CarlQryRun, S001ij DMGMining.

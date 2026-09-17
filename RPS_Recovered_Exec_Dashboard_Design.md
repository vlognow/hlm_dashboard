# RPS "$ Recovered" Executive Dashboard — Design & Build Plan

**Author:** Sidd Sampath (Data Science) · **Date:** 2026-09-14 · **Status:** Draft v1 for review
**Audience:** whoever builds the .pbix (Part 1) and whoever stands up the daily pipeline (Part 2)
**Scope:** one Power BI report, three pillars (Subrogation, COB, Pharma), refreshed daily, exec-facing.

> **How this was produced.** Every design choice below is tied to what I could actually see today:
> the live SQL Server catalog behind the Subro reporting layer (queried through Machinify Studio project
> 0010z, which fronts TRGDMGREP1), the COB working tables Josh Roberts' Data Mining team has staged
> (Studio project 0012k, which fronts the `CarlQryRun` database on TRGACAP3), Notion system documentation
> for Pharmacy (RXP / RxTra), and Slack history for the Power BI environment. Where I could not reach a
> system (SmartII, RXP, RxTra, ACT directly), I say so and list what to request.

---

## 0. Executive summary (one screen)

| Item | Decision / finding |
|---|---|
| Headline metric | **Gross $ posted as recovered in the trailing 30 days**, vs the prior 30 days. "Recovered" = a posted recovery/remittance transaction, dated by its posting date. Not lien amount, not invoiced amount, not settlement amount (those are leading indicators and appear on drill-down only). |
| Pillar → L2 | Subro → **LRU / RCU / SRU** (recovery unit). COB → **program line** (default; alternatives below). Pharma → **solution line** (Pharmacy COB / Retro Term / Part D Compliance / High Cost Drugs) (default; alternatives below). |
| Source of truth, Subro | `SubroReports.rpt.RecoveriesbyLOBTableau` (one row per file × recovery date, already carrying Team, LOB, Division and a posted/submitted flag; refreshed nightly ~04:00 ET; reconciles to the ledger within 1 %) for $, with `rpt.SubroDataWarehouseRecovery` (55.8 M-row posted-recovery ledger) as the audit fallback, joined to `rpt.SubroFile` for file attributes. `SubroReports.rp.SubroFile` does **not** exist; the object John shared is `rpt.SubroFile`, and "RPT.subro in ODS" is the same table (the Subro ODS team owns the `rpt` schema). |
| Source of truth, COB | **`ACT.dbo.Remit` on TRGACAP3** (one row per posted remittance: `AddDate`, `DivisionId`, `AppliedAmt` / `ARDAmount` / `AuditorAmount`, `FeeValue`, `RecoveryTypeID`, `RecoveryMethodId`, `InvestigationId`), allocated to claims by `RemitPendingClaim` and mirrored in the per-claim `Transaction` ledger (`TransactionType` 6 = Posted). Located by the ACT schema discovery on 2026-09-16 (see `hlm_dashboard/README.md`); dollar aggregates not yet pulled. SmartII (`tblInvestigation`, `tblAudit`) and Josh Roberts' staged `CarlQryRun.overlap_detection.*` tables remain the source for investigation attributes and invoiced $. COB = ACT Division 2 per John Marcsik (ACT labels that division "Subro"; confirm with the step 2 client-code/audit-category queries). |
| Source of truth, Pharma | `RXP.dbo.tblInvoice` / `tblInvoiceClaim` (billing) and `RxTra.dbo.tblRemitDetailTransaction` (append-only A/R ledger; a posting row = a recovery). Both on SQL alias `SQLUserRx`. Not yet directly profiled; documented from the Pharmacy team's Notion source-read. |
| Model | One fact (`FactRecovery`, transaction grain, union of three pillars) + `DimDate` + `DimPillarUnit` + `DimClient` + `DimCase`. Import mode, one daily refresh. |
| Pipeline | Per-pillar SQL job on the pillar's own server (Pattern 1) writes a thin daily fact table; a Python consolidator on **PC210344** (Pattern 2, Task Scheduler) unions the three into one reporting schema; Power BI refreshes from that one schema through the existing on-prem data gateway. |
| Power BI estate | Machinify already has a **central, IT-owned Power BI Service tenant** with an approval workflow for workspaces, an on-prem data gateway run by the DBA team, and **F64 Fabric capacity** in the l-Rawlings tenant. This should not be a personal workspace. Recommend a dedicated workspace on the F64 capacity so execs view without Pro licenses. |
| Posting seasonality (measured) | Subro recoveries post on business days only, and one month-end batch day carries 23–35 % of the month (Jun 30: $21.8M, Jul 15: $20.8M, Aug 31: $28.9M). A rolling 30-day Δ% therefore swung from **+6.7 % to −23.8 %** across four anchor days in Aug–Sep 2026 with no change in performance. The headline keeps the requested L30-vs-P30, but the page must also show the calendar-month view and the daily chart carries a 7-day rolling line — see §1.1. |
| Biggest blockers | (1) COB recovery-posting source located (`ACT.dbo.Remit`) but the monthly $ still has to be pulled and Division 2 = COB confirmed; (2) read access to SmartII/RXP/RxTra (or a DMG-produced extract) for COB/Pharma; (3) an agreed cross-pillar client master; (4) DBA/ADO lead time for three scheduled jobs; (5) workspace + gateway data-source requests through Freshservice. |

---

# PART 1 — DASHBOARD DESIGN

## 1.1 Metric definitions (lock these first)

| Term | Definition | Why |
|---|---|---|
| **Recovered $** | Sum of gross recovery amounts on posted recovery transactions whose **recovery/posting date** falls in the window. Gross = before Machinify's contingency fee. | It is the only concept that exists in all three pillars as a dated transaction. Subro stores it on `SubroDataWarehouseRecovery.GrossRecovery` / `RecoveryDate`; Pharma on RxTra remittance postings; COB on the SmartII/ACT posting record. |
| **Last 30 days (L30)** | `RecoveryDate` in `[Today-30, Today-1]`. "Today" = the refresh date. Excludes today because postings for the current day are incomplete at a 6 AM refresh. | Stable, reproducible number for execs. |
| **Prior 30 days (P30)** | `RecoveryDate` in `[Today-60, Today-31]`. | Like-for-like comparison. |
| **Δ%** | `(L30 − P30) / P30`. Show ▲ green / ▼ red, with the arrow driven by sign, not by a threshold. | |
| **% of total** | Pillar L30 ÷ all-pillar L30. | |
| **File / case count** | `DISTINCTCOUNT` of the case key (Subro `file_key`, COB `InvestigationID`, Pharma `InvestigationId`) that had ≥1 posting in the window. | "Files recovered", not "files open". |
| **Net $** (drill-down only) | Gross − fee (`TRC_Fee` in Subro; fee columns in RxTra/SmartII postings). | Execs asked for $ recovered; net is available for finance readers on drill-down but not on the landing page. |

Reversals/negative postings are kept in the fact table with negative amounts, so the sums are net of reversals automatically. (Subro `recovery_collect` has `rec_col_type_id`; reversals appear as negative `gross_amt` rows — confirm with Subro ODS.)

**Batch-posting caveat (measured on `rpt.SubroDataWarehouseRecovery`, Jun–Sep 2026).** Subro postings land only on business days, in a typical range of $0.4M–$5M per day, with one batch day per month (client remittance runs) of $16M–$29M. Trailing-30-day totals therefore depend on how many batch days fall inside each window:

| Anchor (data-through) date | L30 | P30 | Δ% |
|---|---|---|---|
| 2026-09-10 | $97.3M | $91.2M | **+6.7 %** |
| 2026-09-03 | $95.1M | $92.6M | +2.6 % |
| 2026-08-27 | $82.0M | $97.1M | −15.5 % |
| 2026-08-20 | $83.7M | $109.9M | **−23.8 %** |
| 2026-09-14 (calendar days incl. weekend, ledger as of Sep 14) | $65.2M · 15,148 files | $82.5M | −21.0 % |

Same business, three weeks apart, a 30-point swing. The same 30-day window also contained 4,959 negative ledger rows (−$0.96M), so reversals are real and must stay in the sum. Design response: (1) keep L30 vs P30 as the headline because that is what was asked for, but show the calendar-month figures (Jul $90.7M, Aug $96.5M) as a second reference label on the headline card so the reader can see the stable number; (2) add a 7-day rolling average line to every daily chart; (3) footnote the number of business days and batch days in each window (`DimDate[IsHoliday]` plus a `IsBatchDay` flag derived as "day > 3× trailing-20-day median"); (4) offer leadership a **month-to-date vs same point last month** alternative headline and let them choose before build (open question 11). COB and Pharma likely have the same shape (payer batch P2P remittances); verify once their sources are reachable.

## 1.2 Hierarchy and the L2 breakdowns

### Pillar accent colors (one per pillar, everything else neutral gray)

| Pillar | Accent | Use |
|---|---|---|
| Subrogation | `#1F5AA6` (blue) | pillar card border, its bars/lines, drill-through header |
| COB | `#0F8B6E` (teal-green) | same |
| Pharma | `#B4571C` (burnt orange) | same |
| Neutral | text `#1F2933`, secondary `#6B7280`, gridlines `#E5E7EB`, background `#FFFFFF`, ▲ `#178A5A`, ▼ `#C0392B` | |

### Subrogation L2 — LRU / RCU / SRU (defined)

Two ways to assign a recovery to a unit exist in the estate. Pick one and document it:

| Option | Logic | Evidence | Verdict |
|---|---|---|---|
| **A. Team of the analyst credited with the recovery (recommended)** | `rpt.RecoveriesbyLOBTableau.Team` (or recovery → `Subro_SRS.dbo.fversion` → `rep_maint.team`); map team 41/42 → SRU, 45 → RCU, else → LRU. ODS's own `rpt.SubrogationRecoveryPerformanceDashboard` carries a `Recovery Unit` column with values **SRU, RCU, LRU, SrLRU** (plus role codes ATL, TL, TOM, TA and NULL rows) — reuse its derivation. | In the last 30 days `RecoveriesbyLOBTableau` shows posted $ by team 45 ($3.4M, RCU) and 42 ($1.1M, SRU) alongside teams 1–20 ($0.4M–$5.7M each, the LRU teams); this matches the 41/42/45 mapping used in the LRU threshold work and ODS's dashboard table. `rpt.TeamPod` maps a *different* team range (68–97) to LOB pods (Self Funded, Fully Insured, Medicare, Medicaid, FEP, WC), so a team→unit crosswalk must come from ODS, not be inferred. | Use ODS's `Recovery Unit` derivation. Show **LRU = LRU + SrLRU** on the exec card with SrLRU as a sub-split on drill-down (validate). |
| B. Inventory-score band at distribution | `DistributionScoring.subro.InventorySupply.InventoryScore`: −299.9..−200 = SRU, −399.9..−300 = RCU, ≥50,000 & claims ≥$400 = LRU, "Subro Senior Analyst" model = LRU-SR (query shared by Jason Gibson in #ask-subro-ods-data-products, 2026-08-27). | Distribution-time assignment; files migrate between units after lien refresh, so it drifts from who actually recovered. | Keep as an attribute on `DimCase` for "unit at distribution", not for the L2 split. |

**Assumption to validate with Subro ODS (Jennefer Murphy / Dan Stephens):** unit = team of the rep on the file version current at `RecoveryDate`; Global/WC teams are excluded from the three units and shown as "Other" in a footnote row. Workers' Comp files (`SubroFile.WorkComp = 1`) are excluded from the Subrogation pillar unless leadership wants WC counted — flag.

### COB L2 — three candidates, one default

What the COB data can actually support today (from Josh Roberts' staged tables, SmartII structure, and the COB product docs):

| Candidate | Supportable today? | Source field(s) | Notes |
|---|---|---|---|
| **1. Program / recovery line (recommended default)** — Commercial COB (post-pay), Medicaid TPL reclamation, Medicare/MSP, Provider aged recoveries (RPR), Medicare Rx reclamation, Dental reclamation | **Yes** | SmartII `tblAudit` (ClientCode, audit/program) and `tblInvestigation` investigation type; `aCentricReports.rpt.DistributedInventory.RegisteredSystemId`; Tory Johnson's list of what COB performs (Slack, 2026-08-31). | This is how the business already describes COB and how finance invoices. Default. |
| 2. Cost avoidance vs post-payment recovery | **No, not as $.** | COB today is pay-and-chase; cost avoidance (pre-pay / COB Update File to the plan) is not posted as a dollar transaction anywhere we found. The RPS Analytics Blueprint proposes `cob_cost_avoided_amount` but it is not built. | Show as a future toggle; do not promise a number. If leadership insists, the only near-term proxy is "claims redirected" counts from the pre-pay pilot (Kaiser/Centene), which is a count, not $. |
| 3. Payer segment (Commercial / Medicare / Medicaid) or client | **Yes** | `tblAudit.ClientCode` → client LOB via the same lookup Subro uses (`SubroReports.dbo.LOBByChildCode_FinanceUpdate`) or SmartII plan type. | Use as the L3 slicer and top-client table rather than the L2 split; overlaps heavily with candidate 1. |

Default: **program line**, with client as the L3 table. Validate with Josh Roberts (DMG) and COB Ops (Jared / Stefan / Ryan per the RPS Domain KB) that the SmartII investigation-type list collapses cleanly into 4–6 lines.

### Pharma L2 — three candidates, one default

| Candidate | Supportable today? | Source field(s) | Notes |
|---|---|---|---|
| **1. Solution line (recommended default)** — Pharmacy COB · Retro Term · Part D Compliance · High Cost Drugs | **Yes** | RXP investigation type (`tblInvestigation` → investigation type / `tblClient.IsCompliancePDE`), as used in the Pharmacy Overview revenue split ($36M / $4.6M / $9.4M / $2.2M in 2025). | Matches how Pharmacy leadership already reports. Default. |
| 2. Recovery channel — PBM batch P2P · portal · USPS letter · member reimbursement · pharmacy rebill | **Yes, with caveats** | RxTra remittance/OPR (`tblRemittance.RemittanceTypeId`, OPR file method) and Retro Term recovery source (member / pharmacy rebill / other payer) per the standard "Monthly Retro Term Recovery Report". | Method is well captured for Retro Term; for Pharmacy COB the P2P vs portal distinction lives in OPR file assembly and may need a lookup. Good L3 attribute. |
| 3. Drug class | **Not recommended** | NDC is on `RXP.dbo.tblClaim`; there is no drug-class reference joined to recoveries, and postings are at invoice/claim level, not drug level. | Would need an NDC→therapeutic class reference and claim-level allocation. Low exec value; skip. |

Default: **solution line**, with recovery channel and top PBM/payer as L3.

### L3 detail (what sits under each L2 bucket)

| Pillar | L3 table grain | Columns |
|---|---|---|
| Subro | One row per **file** with a posting in the window (top 25 by $) | File key · Client (FinanceReportingClient) · Parent (DIGClientParent) · Unit · Team/Pod · Lien $ · Recovered $ (window) · Recovered $ (life) · Last recovery date · File status |
| COB | One row per **investigation** (top 25) and a second table one row per **payer/client** | Investigation ID · Client code · Program line · Other insurer/payer · Invoiced $ · Recovered $ (window) · Last posting date · Status |
| Pharma | One row per **investigation/invoice** (top 25) and one row per **PBM/payer** | Investigation ID · Client · Solution line · PBM/OI carrier · Invoiced $ · Recovered $ (window) · Recovery method · Last posting date |

Claim-line grain is available in all three systems but is deliberately kept out of the exec report (PHI exposure, size). If claim-level is needed, add a separate ops report on the same dataset with RLS.

## 1.3 Page 1 — Executive landing

**Purpose:** answer "how much did we recover in the last 30 days, is it up or down, and where did it come from" in under 10 seconds.

**Canvas:** 1280×720 (16:9), white background, 24 px outer margin, 16 px gutters. No page-level slicers except the pillar-scoped date info in the header.

*Numbers in the wireframes are illustrative layout values only. For scale: measured Subro alone was ≈ $97M for the 30 days ending 2026-09-10; COB and Pharma have not been measured yet.*

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│  RPS RECOVERIES                                   Data through: Sep 13, 2026   ⟳ 06:15 ET │  header band (56px)
├──────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│   TOTAL RECOVERED · LAST 30 DAYS                                                         │
│   $ 48.2M                     ▲ 6.4%  vs prior 30 days ($45.3M)                          │  K1 headline card (full width, 150px)
│   Aug 14 – Sep 13, 2026       ▁▂▃▂▄▅▄▆▅▇ (daily sparkline, gray)                          │
│                                                                                          │
├────────────────────────────┬────────────────────────────┬────────────────────────────────┤
│ ▍SUBROGATION               │ ▍COB                       │ ▍PHARMA                        │
│  $ 31.9M        66%        │  $ 10.8M        22%        │  $ 5.5M         11%            │  P1 P2 P3 pillar cards (220px)
│  ▲ 4.1% vs prior 30d       │  ▲ 12.0% vs prior 30d      │  ▼ 3.2% vs prior 30d           │
│  2,184 files               │  611 investigations        │  1,302 investigations          │
│  ────────────── (share bar) │  ────────────── (share bar)│  ────────────── (share bar)    │
│  [ Drill into Subro › ]    │  [ Drill into COB › ]      │  [ Drill into Pharma › ]       │
├────────────────────────────┴────────────────────────────┴────────────────────────────────┤
│  DAILY RECOVERED, LAST 30 DAYS (stacked by pillar)                                       │
│  $3M ┤        ▂▃  ▄        ▅▆   ▃                                                       │  V1 stacked column (200px)
│  $2M ┤  ▂▃▄▅▆▇█▇▆▅▆▇█▇▆▅▄▆▇█▇▆▅▆▇▆▅▄▃▂                                                   │
│  $1M ┤▁▂                                                                                 │
│      └──────────────────────────────────────────────────────────  Aug 14 ……… Sep 13      │
│                                                    [ Daily trend › ]   [ Monthly trend › ]│
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

**Visuals, field wells, behaviors**

| ID | Visual | Fields / measures | Format & behavior |
|---|---|---|---|
| H | Header: text box + 2 cards | `[Data Through Date]`, `[Last Refresh]` | 12 pt gray. `Last Refresh` from a 1-row `RefreshLog` table loaded in the same refresh. |
| K1 | **Card (new card visual)** with reference labels | Value `[Recovered L30]`; reference label 1 `[Δ% vs P30]` with `[Δ Arrow]` glyph; reference label 2 `[Recovered P30]`; reference label 3 `[Recovered Last Complete Month]` labelled with the month name (the stable number, see §1.1); subtitle `[L30 Window Label]` plus `[Window Business Days Label]` ("22 business days · 1 batch day"); sparkline on `[Recovered Daily]` by `DimDate[Date]` filtered to L30 | 40 pt value, `$#,0.0,,M`. Arrow color by `[Δ Color]` conditional format. Sparkline gray, no axis. |
| P1–P3 | **Card visuals** (one per pillar), wrapped in a rectangle with a 4 px left accent bar in the pillar color | Value `[Recovered L30]` filtered by `DimPillarUnit[Pillar]`; `[Share of Total L30]`; `[Δ% vs P30]` + arrow; `[Cases L30]` with label "files" (Subro) / "investigations" (COB, Pharma) from `DimPillarUnit[CaseNoun]`; share bar = 100 % stacked bar, single row, value `[Share of Total L30]`, no axis | Pillar filter is a **visual-level filter**, not a slicer, so the page stays slicer-free. |
| B1–B3 | **Buttons** "Drill into … ›" | Action = Drill through → page 2 with the pillar's `DimPillarUnit[Pillar]` value carried | Also allow right-click drill-through on the pillar cards. Button fill = pillar accent, white text. |
| V1 | **Stacked column + line chart** | X `DimDate[Date]` (L30), columns `[Recovered]` by legend `DimPillarUnit[Pillar]`, line `[Recovered 7d Rolling Avg]` | Colors = pillar accents; rolling line dark gray, 1.5 px. No data labels. Y axis `$#,0.0,,M`. Weekends/holidays shown as gaps (category axis on `DimDate[Date]` filtered to business days) so the eye is not drawn to zero bars. Tooltip: date, pillar $, total $, 7-day avg. Clicking a column cross-filters P1–P3 to that day (Interactions: cards filter, buttons none). |
| B4–B5 | Buttons "Daily trend ›" / "Monthly trend ›" | Page navigation → page 3, plus bookmark `BM_Daily` / `BM_Monthly` | |

**Interactions:** V1 → P1–P3 filter; P1–P3 → V1 highlight; nothing filters K1 (edit interactions: none) so the headline never changes on a click.

**Empty/late data rule:** if `MAX(FactRecovery[RecoveryDate]) < Today-2`, the header shows a yellow "Data delayed" pill (`[Data Freshness Flag]` measure). Execs should never read a stale number as current.

## 1.4 Page 2 — Pillar drill-down (one reusable drillthrough page)

**Purpose:** one page, filtered by whichever pillar was clicked, showing L2 unit cards and L3 detail.

**Drillthrough field:** `DimPillarUnit[Pillar]` (keep "Keep all filters" ON so a clicked day on page 1 also carries). Add the built-in back button.

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ ‹ Back    ▍SUBROGATION · RECOVERED LAST 30 DAYS                Aug 14 – Sep 13, 2026     │  header (pillar name + accent from selected pillar)
│           $31.9M   ▲ 4.1% vs prior 30d ($30.6M)   ·  2,184 files  ·  66% of RPS total   │  K2 summary strip
├────────────────────────────┬────────────────────────────┬────────────────────────────────┤
│  LRU                       │  RCU                       │  SRU                           │
│  $ 22.4M    70%            │  $ 6.1M     19%            │  $ 3.4M     11%                │  U1..Un L2 unit cards (auto-generated
│  ▲ 5.0%     512 files      │  ▼ 1.8%     640 files      │  ▲ 9.9%   1,032 files          │  from DimPillarUnit[Unit] – small multiples)
├────────────────────────────┴────────────────────────────┴────────────────────────────────┤
│  Slicers:  [Unit ▾]  [Client / Parent ▾]  [LOB ▾]         Sort: Recovered $ ▾            │  S1..S3 (dropdown slicers, single row)
├──────────────────────────────────────────────────────────────────────────────────────────┤
│  TOP FILES BY $ RECOVERED (LAST 30 DAYS)                                                 │
│  File     Client            Parent      Unit  Team  Lien $    Recovered $  Life $  Last  │  T1 detail table (top 25, scroll)
│  1720…    Centene AZ        Centene     LRU   ba4   $412,000  $ 388,500   $388,500 09/11│
│  1698…    Aetna HRP         Aetna       LRU   jg20  $260,110  $ 201,000   $201,000 09/09│
│  …                                                                                       │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│  RECOVERED BY UNIT, DAILY (L30)   ▁▂▃▄▅▆▇ (small clustered bars, gray with unit accent)  │  V2 (optional, 120px)
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

**Visuals, field wells, behaviors**

| ID | Visual | Fields / measures | Behavior |
|---|---|---|---|
| K2 | Card + 3 small cards in a strip | `[Recovered L30]`, `[Δ% vs P30]`, `[Recovered P30]`, `[Cases L30]`, `[Share of Total L30]` | Header text = `[Selected Pillar Name]` (`SELECTEDVALUE(DimPillarUnit[Pillar])`), accent from `[Pillar Accent Hex]` via conditional formatting on the rectangle. |
| U1..Un | **Small multiples** card row: a single card visual with small multiples by `DimPillarUnit[Unit]` | `[Recovered L30]`, `[Share of Pillar L30]`, `[Δ% vs P30]`, `[Cases L30]` | Renders 3 cards for Subro (LRU/RCU/SRU), 4–6 for COB (program lines), 4 for Pharma (solution lines) without page changes. Sort by `DimPillarUnit[UnitSortOrder]`. Clicking a unit card filters T1 and V2. |
| S1–S3 | Dropdown slicers | `DimPillarUnit[Unit]`, `DimClient[ParentName]` (hierarchy Parent → Client), `DimClient[LOB]` | Single-select off. Sync **not** enabled across pages (page 3 gets its own copy so the trend page starts clean). |
| T1 | **Table** | `DimCase[CaseId]`, `DimClient[ClientName]`, `DimClient[ParentName]`, `DimPillarUnit[Unit]`, `DimCase[Team]`, `DimCase[LeadingAmount]` (Lien $ / Invoiced $), `[Recovered L30]`, `[Recovered Lifetime]`, `[Last Recovery Date]`, `DimCase[Status]` | Top-N filter: Top 25 by `[Recovered L30]`. Column labels come from `DimPillarUnit` (`CaseNoun`, `LeadingAmountLabel`) so "Lien $" reads "Invoiced $" on COB/Pharma. Conditional data bars on `[Recovered L30]` in pillar accent. Right-click a row → drill-through to the ops detail report (out of scope here) or "Copy case ID". |
| V2 | Clustered column (optional) | X `DimDate[Date]`, Y `[Recovered]`, legend `DimPillarUnit[Unit]` | Gray palette with pillar accent for the largest unit. Can be removed if the page feels busy. |
| T2 (COB/Pharma only) | Second table, visible via `[Show Payer Table]` = 1 | `DimCase[CounterpartyName]` (other insurer / PBM), `[Recovered L30]`, `[Cases L30]` | Hidden for Subro via a page-level visibility bookmark on the drill-through pillar. |

**Why one page and not three:** everything pillar-specific is a *label* or a *color*, both derivable from `DimPillarUnit`. That keeps the .pbix to three pages and guarantees the three pillars are compared with identical math.

## 1.5 Page 3 — Trend

**Purpose:** daily view (last 30 days) or monthly view (last 12 complete months), same filter context, one toggle.

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ ‹ Back   RECOVERY TREND                              [ Daily · 30d ] [ Monthly · 12m ]   │  header + toggle buttons (bookmarks)
│ Slicers: [Pillar ▾ (All)]  [Unit ▾]  [Parent/Client ▾]  [LOB ▾]     ☐ Show prior period  │  S4..S7 + toggle
├──────────────────────────────────────────────────────────────────────────────────────────┤
│  $ RECOVERED PER DAY (stacked by pillar)          — or —  $ RECOVERED PER MONTH          │
│  $3M ┤     ▂▃▄  ▅▆▅   ▄▅▆▇█                          $60M┤ ▇▇▆▇▇█▇█▇▇▇▇ ─ 12-mo line     │  V3 daily stacked column / V4 monthly
│  $2M ┤ ▂▃▄▅▆▇▆▅▄▅▆▇▆▅▄▆▇▆▅▄▃▂                        $40M┤                              │  column + line (prior-year line dotted)
│  $1M ┤▁▂                                             $20M┤                              │
│      └───────────────────────────── Aug 14 … Sep 13      └────────── Oct'25 … Sep'26     │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│  Period    Subro     COB     Pharma    Total    Δ vs prior   Files   Investigations       │  T3 matrix (daily rows or monthly rows)
│  Sep 13    $1.2M   $0.4M    $0.2M    $1.8M      ▲ 3%       …                            │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

**Mechanics**

| ID | Visual | Fields / measures | Behavior |
|---|---|---|---|
| B6/B7 | Toggle buttons | Bookmarks `BM_Daily` (shows V3 + T3-daily, hides V4 + T3-monthly) and `BM_Monthly` (inverse). Bookmarks capture **display only** (uncheck "Data"), so slicer state carries across the toggle. | Selected state styled with pillar-neutral dark fill. |
| S4–S7 | Slicers | `DimPillarUnit[Pillar]`, `DimPillarUnit[Unit]`, `DimClient[ParentName]`, `DimClient[LOB]` | When arriving from page 2 via a button with "Keep all filters", the pillar and unit are pre-set. |
| V3 | Stacked column | X `DimDate[Date]` filtered `[Is L30] = 1`, Y `[Recovered]`, legend `Pillar` | Optional dotted line `[Recovered P30 Aligned]` (same day-offset in the prior window) when "Show prior period" is on. |
| V4 | Column + line | X `DimDate[YearMonth]` filtered `[Is Last 12 Complete Months] = 1`, columns `[Recovered]` by `Pillar`, line `[Recovered Same Month Prior Year]` (dotted gray) | Monthly numbers use **complete** calendar months; the current partial month is excluded and noted in the subtitle. |
| T3 | Matrix | Rows `DimDate[Date]` or `DimDate[YearMonth]`; columns `Pillar`; values `[Recovered]`, `[Δ% vs Prior Period]`, `[Cases]` | Two matrices swapped by the bookmark. Totals row on. |

**Filter context carry-through:** all measures use `DimDate` as the only date table and `FactRecovery[RecoveryDate]` as the only relationship to it, so any slicer on page 3 changes both the chart and the matrix identically.

## 1.6 Measures (DAX) the builder needs

```DAX
-- Anchors
Data Through Date = MAX ( FactRecovery[RecoveryDate] )
Anchor Date       = [Data Through Date]                       -- refresh-driven; do not use TODAY()
L30 Start         = [Anchor Date] - 29
P30 Start         = [Anchor Date] - 59
P30 End           = [Anchor Date] - 30

-- Core
Recovered = SUM ( FactRecovery[GrossAmount] )
Recovered L30 = CALCULATE ( [Recovered], DATESBETWEEN ( DimDate[Date], [L30 Start], [Anchor Date] ) )
Recovered P30 = CALCULATE ( [Recovered], DATESBETWEEN ( DimDate[Date], [P30 Start], [P30 End] ) )
Δ% vs P30 = DIVIDE ( [Recovered L30] - [Recovered P30], [Recovered P30] )
Δ Arrow = SWITCH ( TRUE (), ISBLANK ( [Δ% vs P30] ), "", [Δ% vs P30] >= 0, "▲", "▼" )
Δ Color = IF ( [Δ% vs P30] >= 0, "#178A5A", "#C0392B" )
Cases L30 = CALCULATE ( DISTINCTCOUNT ( FactRecovery[CaseKey] ), DATESBETWEEN ( DimDate[Date], [L30 Start], [Anchor Date] ) )
Share of Total L30 = DIVIDE ( [Recovered L30], CALCULATE ( [Recovered L30], REMOVEFILTERS ( DimPillarUnit ) ) )
Share of Pillar L30 = DIVIDE ( [Recovered L30], CALCULATE ( [Recovered L30], REMOVEFILTERS ( DimPillarUnit[Unit] ) ) )
Recovered Lifetime = CALCULATE ( [Recovered], REMOVEFILTERS ( DimDate ) )
Last Recovery Date = CALCULATE ( MAX ( FactRecovery[RecoveryDate] ), REMOVEFILTERS ( DimDate ) )
Net Recovered L30 = CALCULATE ( SUM ( FactRecovery[NetAmount] ), DATESBETWEEN ( DimDate[Date], [L30 Start], [Anchor Date] ) )

-- Stable references and seasonality helpers
Recovered Last Complete Month = VAR m = EOMONTH ( [Anchor Date], -1 ) RETURN CALCULATE ( [Recovered], DATESBETWEEN ( DimDate[Date], EOMONTH ( m, -1 ) + 1, m ) )
Recovered 7d Rolling Avg = AVERAGEX ( DATESINPERIOD ( DimDate[Date], MAX ( DimDate[Date] ), -7, DAY ), [Recovered] )
Window Business Days = CALCULATE ( COUNTROWS ( FILTER ( DimDate, DimDate[IsHoliday] = FALSE () && WEEKDAY ( DimDate[Date], 2 ) <= 5 ) ), DATESBETWEEN ( DimDate[Date], [L30 Start], [Anchor Date] ) )
Trailing 20d Median Daily = MEDIANX ( FILTER ( DATESINPERIOD ( DimDate[Date], [Anchor Date], -28, DAY ), [Recovered] > 0 ), [Recovered] )
Window Batch Days = CALCULATE ( COUNTROWS ( FILTER ( VALUES ( DimDate[Date] ), [Recovered] > 3 * [Trailing 20d Median Daily] ) ), DATESBETWEEN ( DimDate[Date], [L30 Start], [Anchor Date] ) )
Window Business Days Label = [Window Business Days] & " business days · " & [Window Batch Days] & " batch day(s)"
MTD Recovered = CALCULATE ( [Recovered], DATESBETWEEN ( DimDate[Date], EOMONTH ( [Anchor Date], -1 ) + 1, [Anchor Date] ) )
MTD Recovered Same Point Last Month = CALCULATE ( [Recovered], DATESBETWEEN ( DimDate[Date], EOMONTH ( [Anchor Date], -2 ) + 1, EDATE ( [Anchor Date], -1 ) ) )

-- Trend helpers
Is L30 = IF ( MAX ( DimDate[Date] ) >= [L30 Start] && MAX ( DimDate[Date] ) <= [Anchor Date], 1, 0 )
Is Last 12 Complete Months = VAR m = EOMONTH ( [Anchor Date], -1 ) RETURN IF ( MAX ( DimDate[Date] ) <= m && MAX ( DimDate[Date] ) > EDATE ( m, -12 ), 1, 0 )
Recovered Same Month Prior Year = CALCULATE ( [Recovered], SAMEPERIODLASTYEAR ( DimDate[Date] ) )
Recovered P30 Aligned = CALCULATE ( [Recovered], DATEADD ( DimDate[Date], -30, DAY ) )

-- Labels
L30 Window Label = FORMAT ( [L30 Start], "mmm d" ) & " – " & FORMAT ( [Anchor Date], "mmm d, yyyy" )
Selected Pillar Name = SELECTEDVALUE ( DimPillarUnit[Pillar], "All pillars" )
Pillar Accent Hex = SELECTEDVALUE ( DimPillarUnit[AccentHex], "#1F2933" )
Data Freshness Flag = IF ( [Data Through Date] < TODAY () - 2, "Data delayed", BLANK () )
```

Formatting: all currency `$#,0.0,,M` on cards and axes, `$#,0` in tables; percentages `0.0%`.

## 1.7 Visual hygiene rules for the builder

- Three pages only; no hidden "helper" pages except tooltip pages.
- One font (Segoe UI), three sizes (40 / 16 / 11 pt). Titles sentence case.
- No borders on visuals; whitespace and the pillar accent bar do the grouping.
- No pie/donut charts; share is shown as a number plus a thin share bar.
- Tooltips: a single report-page tooltip (`TT_Recovery`) showing $, Δ%, cases for the hovered slice.
- Row-level security: none on the exec report (aggregates only). PHI never appears: no member names, no claim numbers. Case IDs are internal keys.

---

# PART 2 — DATA SOURCES & DAILY IMPLEMENTATION

## 2.1 What I found (reconciliations that change the design)

### `SubroReports.rp.SubroFile` vs `RPT.subro in ODS`

| Claim | Finding |
|---|---|
| "`SubroReports.rp.SubroFile` was shared as a source" | There is no `rp` schema in `SubroReports`. The `information_schema` of `SubroReports` (3,433 objects) has schemas `dbo` (2,270), `rpt` (252), `subrofile` (48), `tmp`, `Ops`, `analytics`, `log`, … The object is **`SubroReports.rpt.SubroFile`** (a physical BASE TABLE, not a view). John's DM used `rp` as shorthand. |
| "`RPT.subro` in ODS with lien amount, gross recovery, file status, all files created" | **Same object.** "ODS" here is the *Subro ODS team* (Subrogation Operations & Data Strategy; Data Products under Jennefer Murphy, Enterprise Reporting under Dan Stephens), not a database named ODS. There is no `ODS` database on TRGDMGREP1 (129 databases listed; none named ODS). The `rpt` schema is theirs. |
| Where it physically lives | `SubroReports` database on **TRGDMGREP1** (192.168.251.19, the DMG reporting replica that Studio 0010z fronts). John's Slack queries also run it on **trgsubrodmg3**; treat TRGDMGREP1 as the read replica and confirm the primary with the DBAs. |
| How it is built / refreshed | It is assembled by an ODS ETL from `Subro_SRS` (staging tables `subrofile.SubroFileClassification`, `subrofile.SubroFileResolvedDate`, `subrofile.SubroFileISOSub`, `subrofile.SubroFileLetterSent`, …). **Measured from `log.SubroFileRefresh`:** one run per day, capture point 00:30 ET, completing between ~02:00 and ~04:30 ET (one late finish at 09:33 on Sep 4; 3,173 runs logged; Sep 5–7 Labor Day weekend skipped). Last run completed 2026-09-13 02:13. John notes "a small lag, maybe a week" for some derived columns. |
| Grain | One row per **file_key**, cumulative. Columns of interest: `GrossRecovery`, `FirstRecoveryDate`, `LatestRecoveryDate`, `ClosedRecoveryDate`, `LienAmount`, `DistributionLienAmount`, `file_stat`, `file_type`, `Classification`, `SBRCategory`, `SourceType`, `WorkComp`, `FinanceReportingClient`, `DIGClientParent`, `clnt_code/clnt_name`, `parent_code/parent_name`, `load_key`. |
| Size | ~156 M rows across 39 `file_stat` values. Only **2.92 M are `C$` (closed with recovery, $10.17 B lifetime gross)** and 0.94 M `OP`. The bulk (`NM` 56.9 M, `CO` 40.6 M, `CU` 12.6 M, …) are mining-stage candidates that never became worked files. Any query must filter status; never import this table whole. |
| Fit for the headline | **Not by itself.** `GrossRecovery` is a lifetime total per file and `LatestRecoveryDate` is only the most recent posting, so "$ recovered in the last 30 days" cannot be reconstructed from it (a file that recovered $10k in July and $1k yesterday would show $11k against yesterday). Use the transaction table below; use `SubroFile` for attributes. |

### The Subro transaction-grain recovery source

`SubroReports.rpt.SubroDataWarehouseRecovery` — columns `RecoveryDate, GrossRecovery, TRC_Fee, file_key, clnt_id, line_no, rec_collect_id`. One row per posted recovery line (a recovery is split across claim lines, so ~20 rows per file-recovery is normal). **Measured 2026-09-14:** 55.8 M rows, `RecoveryDate` from 2003-01-03 to **2026-09-10** (data through the prior Thursday on a Monday morning, i.e. a 1–2 business-day lag), $10.45 B gross and $2.10 B `TRC_Fee` lifetime (fee ≈ 20 %), 2.79 M distinct files — which matches the 2.92 M `C$` files in `SubroFile` closely enough to confirm this is the posted-recovery ledger behind `GrossRecovery`. Recent calendar months: Jul 2026 $90.7 M, Aug 2026 $96.5 M. `rec_collect_id` keys back to the SRS source `Subro_SRS.dbo.recovery_collect` (`rec_collect_id, recovery_id, rec_claim_id, file_key, line_no, rec_col_type_id, gross_amt, fee_amt, d_entered, entered_by`) and `Subro_SRS.dbo.recovery` (`recovery_id, file_key, file_ver, fee_pct, tot_rec_amt, rec_type_id, rec_pay_type_id, rec_source_id, remitter_type_id, d_added, checkamount, financestamp, …`). ODS already derives several reporting tables from it:

| ODS table | Grain | Useful for |
|---|---|---|
| `rpt.RecoveriesbyLOBTableau` | file × recovery date, with `LOB, ContractualClientCode, Parent, clnt, Team, Rep, UserFullName, Division, GrossRecovery, SubmittedRecovery, IsPostedRecovery, UpdateDate` | **Use this as the Subro fact.** Measured: 2.61 M rows from 2018-01-04 through **2026-09-14**, `UpdateDate` max 2026-09-13 04:04 (nightly refresh ~04:00 ET). `IsPostedRecovery = true` rows carry `GrossRecovery`; `false` rows are submitted-not-posted with $0 gross. Last-30-day posted $ by LOB: Self Funded $29.4M, Fully Insured $20.4M, Medicare $12.2M, FEP $2.8M, Medicaid $1.2M (≈$66M), which reconciles to the $65.2M ledger figure. `Division` = S (Subro) / W (Workers' Comp) gives the WC exclusion for free. |
| `rpt.TableauRecoveriesBySourceRemitter` | recovery line with `Remitter, OpenFileSourceType, RecoveryAmount, rec_collect_id` | Remitter (auto carrier / attorney / member) for L3 "source of recovery". |
| `rpt.SubroSettlementsRecoveries` | file × `SubmittedDate, SubmittedDollars` | "Submitted" (check received, not yet posted) — a leading indicator, not the headline. |
| `rpt.GlobalRCURecoveries` | `ReportMonth, recovery_id, file_key, SubmittedDate, Team, FileOwner, SubmittedDollars, LastRefreshed` | Confirms ODS already reports by unit (RCU). |
| `rpt.SubrogationRecoveryPerformanceDashboard` | `Report Date × Recovery Unit × LOB × Pod × Client × Team × Analyst` with Invoiced/Negotiating/Settled/Submitted $ and counts | ODS's own unit-level dashboard feed; reuse its `Recovery Unit` logic. |
| `rpt.MonthlyKPIReport`, `rpt.MonthlySummary`, `rpt.ClientValueMetricsMonthly` | monthly by client/LOB with `PostedRecoveries`, `SubmittedRecoveries`, `TotalPostedAmount`, `HitRate` | Monthly reconciliation targets for page 3. |
| `rpt.DimDate` | calendar with holidays, fiscal-free | Reuse as the model's date dimension. |
| `rpt.TeamPod`, `rpt.AnalystPodTeamRole` | Team → Pod; analyst → team/pod/role with dates | Unit mapping. |
| `rpt.FinanceClientCodeLookup`, `rpt.MapPlanAndFundingToLOB`, `dbo.LOBByChildCode_FinanceUpdate` | client → finance client/parent; plan+funding → LOB | `DimClient`. |
| `rpt.LargeDollarFileTracking_PBI` | large-dollar file tracker | Evidence ODS already feeds **Power BI** (the `_PBI` suffix). |

Legacy `rpt.Tableau*` tables show Rawlings used Tableau historically; no live Tableau Server surfaced in 2025–26 Slack. Treat Tableau as retired for RPS and confirm with Dan Stephens. Subro ODS's production reporting today is **SSRS** (report server `subrossrs/Reports_SUBRO`, e.g. `RptOperationsWeeklyReportV2.1`) plus SSRS email subscriptions, with Power BI used for newer items such as the large-dollar tracker; the RPS Domain KB describes this as "SSRS and manual stored procedures, ad-hoc Excel for one-offs."

### COB — where Josh Roberts' reports actually live

Josh Roberts is **Data Mining (DMG) for COB** (John Marcsik, Slack DM 2026-07-30). His team's reporting runs as **SQL Agent jobs on TRGACAP3** (job steps bulk-load `.sql` files from `\\trgrd2\sqlqueries\QueryLogic\SQL\...` and run as `TRGLLC\sqla_ACAP3`), and his working outputs are materialized in the **`CarlQryRun`** database on TRGACAP3 (192.168.251.12). Studio project **0012k** already has a JDBC source to `CarlQryRun` (user `COBOverLapPilot`) with these registered tables:

| Table (schema `overlap_detection`) | What it is (from names/usage in #cob-overlap-detection) | Profiling status |
|---|---|---|
| `CEMOverlapsAndSmartIIResults` | One row per CEM overlap (`OverlapKey`) joined to its SmartII outcome. ~95 columns; the ones that matter here: `ClientCode`, `OtherClientCode`, `OverlapSource` (`CAQH` / `Production`), `InsertDate`, `CompletionDateTime`, `CEMResultStatus` (e.g. "Distributed", "OI Primary: No Claims to Load", "DistributableButExpired"), `AuditID`, `InvestigationID`, `InvestigationStatus` (e.g. "Overpayment", "Clsd CP No Overpay"), `IsInvoicePresent`, `ClosedDate`, `IsValidOverlap`, `Score`. **Contains PHI** (names, SSNs, DOBs, addresses on both sides) — never load into the exec dataset; use only keys and statuses. | Sampled 2026-09-14 |
| `InvestigationInvoices` | Two columns only: `InvestigationID`, `InvoiceRecorded` (a dollar amount). 771,151 investigations, one row each; amounts from −$4.7k (credits) to $1.78M. Invoiced $ per investigation, **no date** — a modelling aggregate, not a dated fact | Sampled 2026-09-14 |
| `KnownInvoicesWithGroupNames` | `OverlapKey, InvestigationStatus, GroupName, OtherGroupName` — group-name pairs for invoiced investigations (primacy modelling) | Sampled 2026-09-14 |
| (rest of `CarlQryRun`) | `dbo` holds **7,135** working tables from DMG query runs (e.g. `AllCOBCToCEM`, `<Client>_COBCToCEM_CompletedCEM__FinalExport`, `<Client>Rx_COBCToCEM_…`, `AllCEMInProcess`), `performant` 13 tables. It is a scratch/staging database for both medical and Rx COB mining, not a curated reporting layer. | Catalog listed 2026-09-14 |
| `KnownInvoicesWithGroupNames` | Invoices with employer group names (used for primacy modelling) | — |
| `ParityTestFullDataSet_2026_Q1_Q2` | Q1–Q2 2026 medical + pharmacy overlaps loaded to CEM | — |
| `CAQH_CEMs`, `CEM_Coverage_Base`, `PrimacyModelTrainingData`, `ValidatedFinitePolicies`, `OverlapSurvivalModelData`, … | modelling inputs | — |

Underlying production systems (from the DBA alias list and Slack):

| System | Alias / server | Role for us |
|---|---|---|
| **SmartII** | `SQLUserAudit` (replica `trgacap2`) | COB investigation system of record: `dbo.tblInvestigation` (InvestigationID, PotentialID, InvestigationStatus, AuditID), `dbo.tblAudit` (ClientCode, Auditor), `enterprisedistribution.CEMInvestigation`, invoice tables. |
| **aCentricReports** | `SQLUtilMine4` | DMG reporting layer: `rpt.DistributedInventory` (PotentialId, RegisteredSystemId=14 for SMART). |
| **ACT** | `SQLUserShared` (TRGACAP3, 192.168.251.12; copy on 192.168.251.18) | **Confirmed posting system for COB.** Schema discovery run 2026-09-16 with Windows auth (`sqlcmd -S TRGACAP3 -d ACT -E`): 521 tables. Recovery ledger = `dbo.Remit` (2.8 M posted remittances, `AddDate`, `DivisionId`, `AppliedAmt`/`ARDAmount`/`AuditorAmount`, `FeeValue`, `RecoveryTypeID`, `RecoveryMethodId`, `InvestigationId`, `RecoverySource`, `RemitterType`) → `RemitPendingClaim` (claim allocation: `Recovery`, `WriteOff`, `CoinDed`) → `Claim` (101.5 M lines, `DivisionID`, `ClientID`, `ParentClientCode`, `InvestigationID`, `COBID`) → `COB` (15.8 M cases, `AuditCategory`). `RemitCheck`→`Check` holds the physical check; `RemitTransaction`→`Transaction` (241 M) is the per-claim ledger with `TransactionType` 6 Posted / 10 Completed Recovery / 19 Invoice / 4 Write Off. `Division`: 1 Audit (Payment Integrity), 2 Subro, 3 Pharmacy, 4 CPS. The app's own views `vwRemitInfo` and `vTransactionDetail` show the intended joins (and `vTransactionDetail` excludes Division "Subro"). |
| **OlympicGold** | `SQLUtilMine4` | Mining. |

Volume and disposition shape (from `CEMOverlapsAndSmartIIResults`, 2021–2026): roughly 190k–250k CEM overlaps per source per year (`CAQH` vs `Production`), of which 10–13 % end with `IsInvoicePresent = 1`. Investigation statuses form a usable disposition taxonomy: invoiced outcomes are `Overpayment` (77k) and `Clsd` with invoice (197k); non-invoiced closures include `Clsd CS` (205k), `Clsd CP No Overpay` (84k), `Clsd NO OI` (57k), `Clsd Non Coop Member`, `Clsd No Person Match`, `Clsd Restricted Grp`, `Clsd Timely Filing`, and — relevant to the cost-avoidance question — **`Clsd PrePay Savings` (459 rows)**, the only explicit pre-pay outcome and far too small to headline. 1.69 M overlaps never reached a SmartII investigation (status NULL).

What this tells us about COB grain: the operational unit is the **SmartII investigation** (one per validated overlap, keyed `InvestigationID`, with `AuditID` → client), invoicing hangs off the investigation (`IsInvoicePresent`, `InvoiceRecorded`), and the investigation status text ("Overpayment", "Clsd CP No Overpay", …) is the disposition. The L2 program line will come from the audit/investigation type on the SmartII side, and the client from `ClientCode`. None of the staged tables carries a **posting date or posted amount**, which is exactly the gap for the headline.

**Resolved 2026-09-16 (pending the dollar pull):** the *posted* COB recovery with a date is `ACT.dbo.Remit.AddDate` / `AppliedAmt` (with `ARDAmount` and `AuditorAmount` as the split by who is credited, and `FeeValue` as Machinify's fee). John Marcsik pointed at ACT Division 2; the discovery confirmed the ledger structure but the monthly totals and the Division-2-is-COB check are still to be run (`hlm_dashboard/dashboard/sql/act_cob_step2_*.sql`). Two open semantics to settle with Josh Roberts / Finance once the numbers are in: (a) which of `AppliedAmt`, `ARDAmount`, `ARDAmount + AuditorAmount` is "gross recovered" and how reversals appear (`TransactionType` 11/12 Adj-Provider/Adj-Client, `RecoveryType` 29/30 Adjustment Gross/Net); (b) whether `RemitPendingClaim.WriteOff`/`CoinDed` should be excluded (they should, per the Subro definition).

### Pharma — RXP / RxTra

Documented in the Pharmacy team's Notion (source-read of the `RXP` SSDT projects, Aug 2026):

| Concept | Tables | Notes for the fact |
|---|---|---|
| Investigation | `RXP.dbo.tblInvestigation`, `tblClient` (`IsCompliancePDE` flags Part D clients) | `InvestigationType` → solution line (Pharmacy COB / Retro Term / Part D / HCD). |
| Claim | `RXP.dbo.tblClaim` (`TRC_CLAIM_STATUS`: 2 Billed, 4 Queued, 5 Paid, 6 Denied), `tblClaimStatus`, `ClaimDisposition` | Claim-level; not needed for exec fact. |
| Billing document | `RXP.dbo.tblInvoice`, `tblInvoiceClaim` (`InvoiceClaimStatusId`: 1 Billed, 2 Partially Paid, 3 Fully Paid, 4 Written Off, 5 Voided) | **Invoiced $** and invoice date. |
| A/R ledger (recoveries) | `RxTra.dbo.tblInvoice` (one row per posting, "Invoice N Partial Payment"), `tblRemitDetailTransaction`, `tblRemittance` (`RemittanceTypeId` 5 = write-off), `tblRemitDetailPendingTransaction`; views `viewClaimCurrentInvoice`, `viewClaimTotalsRxpInvoice` (Recovered / Writeoff / Outstanding per claim × invoice) | **Recovered $ = posted remittance amount by posting timestamp.** Write-offs are a separate remittance type and must be excluded (or shown as a write-off measure). |
| Recovery channel | OPR (Other Payer Recovery) file assembly, batch P2P vs portal vs USPS; Retro Term recovery source (member / pharmacy rebill / other payer) | L3 attribute. |
| Server | alias `SQLUserRx` hosts `RXP`, `RxTra`, `RxCollections`, `RxIPT`, `RxApplications` (same instance; synonyms resolve locally) | One SQL job can join RXP ↔ RxTra without linked servers. |

Not directly profiled from this environment (no Studio source for `SQLUserRx`). Request either read access for the pipeline account or a sample extract from Brian Sharp / Matt Weirich (AppDev) / Josh Roberts' team.

## 2.2 Data source inventory

| # | Source | Owner (people) | Grain | Refresh today | Reach from here | Dashboard fields it feeds |
|---|---|---|---|---|---|---|
| S1 | `SubroReports.rpt.RecoveriesbyLOBTableau` (TRGDMGREP1 / trgsubrodmg3) | Subro ODS Data Products (Jennefer Murphy); Enterprise Reporting (Dan Stephens) | File × recovery date; 2.61 M rows since 2018 | Nightly ~04:00 ET (`UpdateDate`); data through the current day | Studio 0010z JDBC ✔ | `FactRecovery`: RecoveryDate, GrossAmount (`GrossRecovery` where `IsPostedRecovery`), CaseKey (`File_key`), Team → UnitKey, LOB, Division (WC filter), ClientKey (`ContractualClientCode`), ParentName |
| S1b | `SubroReports.rpt.SubroDataWarehouseRecovery` | same | Recovery line (`rec_collect_id`); 55.8 M rows since 2003 | ODS nightly; observed data through T-2 business days (max `RecoveryDate` 2026-09-10 on 2026-09-14) | ✔ | `FactRecovery`: RecoveryDate, GrossAmount (`GrossRecovery`), FeeAmount (`TRC_Fee`), CaseKey (`file_key`), ClientKey (`clnt_id`) |
| S2 | `SubroReports.rpt.SubroFile` | same | File | ODS nightly (partial captures logged) | ✔ | `DimCase` (Subro): status, type, lien, client/parent, FinanceReportingClient, DIGClientParent, WorkComp, SourceType, Classification, SBRCategory |
| S3 | `Subro_SRS.dbo.recovery_collect`, `dbo.recovery`, `dbo.fversion`, `dbo.rep_maint` | SRS app owners (Bryan Arnold); ODS for reporting use | Recovery line / recovery / file version / rep | Live OLTP (replicated to TRGDMGREP1) | ✔ | Fallback for S1; rep → team → **unit**; remitter/source type |
| S4 | `SubroReports.rpt.TeamPod`, `rpt.AnalystPodTeamRole`, `rpt.SubrogationRecoveryPerformanceDashboard` | Subro ODS | Team/analyst | ODS | ✔ | `DimPillarUnit` (Subro unit mapping), `DimCase[Team]` |
| S5 | `SubroReports.rpt.FinanceClientCodeLookup`, `rpt.MapPlanAndFundingToLOB`, `dbo.LOBByChildCode_FinanceUpdate` | Subro ODS / Finance | Client code | Manual (Finance updates) | ✔ | `DimClient` (Subro side) |
| S6 | `SubroReports.rpt.DimDate` | Subro ODS | Day | Static | ✔ | `DimDate` |
| S7 | SmartII `dbo.tblInvestigation`, `dbo.tblAudit`, invoice tables (alias `SQLUserAudit`) | COB AppDev / Ops; DMG (Josh Roberts) for reporting | Investigation / invoice | Live OLTP; replica trgacap2 | ✖ (no Studio source) | `DimCase` (COB): investigation, client code, program line, status; invoiced $ |
| S8 | `ACT.dbo.Remit` + `RemitPendingClaim` (+ `Transaction` for reconciliation), TRGACAP3 / `SQLUserShared` | ACT AppDev; John Marcsik (pointed us to Division 2); Josh Roberts (DMG) for semantics | Posted remittance (2.8 M rows); claim allocation | Live OLTP | ✖ Studio; ✔ direct `sqlcmd` with Windows auth from the analyst laptop | `FactRecovery` (COB): RecoveryDate = `AddDate`, GrossAmount = `AppliedAmt` (TBC), FeeAmount = `FeeValue`, CaseKey = `InvestigationId`, SourceTxnId = `Remit.ID`, method = `RecoveryMethodId`/`RecoveryTypeID`, client via `RemitPendingClaim`→`Claim.ClientID`→`Client.Code`/`ParentCode`, program line via `Claim.COBID`→`COB.AuditCategory` (TBC) |
| S9 | `CarlQryRun.overlap_detection.InvestigationInvoices`, `CEMOverlapsAndSmartIIResults` (TRGACAP3) | Josh Roberts (DMG) | Investigation × invoice; overlap × investigation | Ad hoc / job-driven | Studio 0012k JDBC ✔ (user `COBOverLapPilot`) | Prototype the COB pillar and validate S7/S8 definitions before production access exists |
| S10 | `aCentricReports.rpt.DistributedInventory` (alias `SQLUtilMine4`) | DMG | Potential/inventory | DMG jobs | ✖ | COB inventory context (not needed for v1) |
| S11 | `RXP.dbo.tblInvestigation`, `tblClient`, `tblInvoice`, `tblInvoiceClaim` (alias `SQLUserRx`) | Pharmacy AppDev (Matt Weirich); LOB owner Brian Sharp | Investigation / invoice | Live OLTP | ✖ | `DimCase` (Pharma): solution line, client, PBM; invoiced $ |
| S12 | `RxTra.dbo.tblInvoice`, `tblRemitDetailTransaction`, `tblRemittance` (alias `SQLUserRx`) | Pharmacy Recovery (Stephanie Preston) / AppDev | Posting | Live OLTP | ✖ | `FactRecovery` (Pharma): posting date, amount, write-off flag, method |
| S13 | Refresh metadata: `SubroReports.log.SubroFileRefresh` + our own `rpt.ExecRecoveryLoadLog` | ODS / us | Run | Per run | ✔ | Header "Last refresh", freshness flag |

Column mapping for the union fact (target `rpt.ExecRecoveryFact` in a reporting schema; see §2.4):

| Fact column | Subro (S1/S2/S3) | COB (S7/S8) | Pharma (S11/S12) |
|---|---|---|---|
| `Pillar` | `'Subrogation'` | `'COB'` | `'Pharma'` |
| `RecoveryDate` | `SubroDataWarehouseRecovery.RecoveryDate` (date) | posting date (TBD table) | `RxTra.tblRemitDetailTransaction` posting timestamp → date |
| `GrossAmount` | `GrossRecovery` | posted amount | posted remittance amount (exclude `RemittanceTypeId = 5` write-offs) |
| `FeeAmount` | `TRC_Fee` | fee if stored, else NULL | fee if stored on remittance, else NULL |
| `CaseKey` | `file_key` | `InvestigationID` | `InvestigationId` |
| `SourceTxnId` | `rec_collect_id` | remittance/payment id | `tblRemitDetailTransaction` id |
| `UnitKey` | team → SRU/RCU/LRU (via rep on `fversion` at `RecoveryDate`; ODS logic) | program line (from investigation type / audit) | solution line (investigation type) |
| `ClientKey` | `FinanceReportingClient` / `clnt_code` | `tblAudit.ClientCode` | `tblClient` code |
| `CounterpartyKey` | remitter type (auto carrier / attorney / member) | other insurer / payer | PBM / OI carrier |
| `IsPosted` | 1 (table is posted recoveries) | 1 | 1 |
| `LoadTs` | job timestamp | | |

## 2.3 Proposed Power BI data model

```
              DimDate (1)──────────────< FactRecovery (*)  >──────────────(1) DimPillarUnit
              Date, YearMonth, IsHoliday   RecoveryDate, Pillar, UnitKey,       Pillar, Unit, UnitSortOrder,
              (from rpt.DimDate)           CaseKey, ClientKey, CounterpartyKey, AccentHex, CaseNoun,
                                           GrossAmount, FeeAmount, NetAmount,   LeadingAmountLabel, ShowPayerTable
                                           SourceTxnId, LoadTs
                                                 │  │
                          (1) DimClient ─────────┘  └───────── (1) DimCase
                          ClientKey, Pillar, ClientCode,           CaseKey, Pillar, Status, Team, Pod,
                          ClientName, ParentCode, ParentName,      LeadingAmount (lien / invoiced),
                          FinanceClient, LOB                       OpenDate, CloseDate, CounterpartyName,
                                                                   UnitAtDistribution
              RefreshLog (disconnected, 1 row per pillar): Pillar, LoadTs, RowsLoaded, MaxRecoveryDate
```

Design notes:

- **Single fact, transaction grain, ~2–3 years of history.** Subro alone posts on the order of tens of thousands of lines per month; three years across pillars stays well under a few million rows — trivial for Import mode and it makes monthly YoY possible.
- `DimPillarUnit` is a **hand-maintained 15-row table** (3 pillars × their units). It carries all the presentation metadata so pages 2 and 3 are pillar-agnostic.
- `DimClient` is the weak spot: Subro uses `FinanceReportingClient` / `DIGClientParent`, COB uses SmartII `ClientCode`, Pharma uses RXP client. There is **no cross-pillar client master today** (Joshua Caudill, Slack 2026-08-27: "one overlap result can cover multiple Rawlings child codes"; the RPS Analytics Warehouse effort is building `dim_enterprise_client` for exactly this). v1 keeps `DimClient` **pillar-scoped** (composite key `Pillar|ClientCode`); the page-2 client slicer therefore only makes sense inside a pillar, which is where it lives. Do not put a client slicer on page 1.
- `DimCase` is filtered to cases with a posting in the last 13 months to keep it small; L3 lifetime $ comes from the fact, not from `SubroFile.GrossRecovery`.
- **Gaps that block a clean model today:** (a) COB posting source unconfirmed; (b) no cost-avoidance $ anywhere; (c) client master absent; (d) Subro unit is derived, not stored on the recovery; (e) Pharma remittance "recovered" vs "applied" semantics need confirming with Recovery ops (partial payments, reversals).

## 2.4 Daily pipeline plan

### Overall shape

```
 TRGDMGREP1/trgsubrodmg3 (SubroReports)      SQLUserAudit / TRGACAP3 (SmartII, CarlQryRun)     SQLUserRx (RXP, RxTra)
   [SQL Agent 05:00 ET]                         [SQL Agent 05:00 ET, DMG-owned]                    [SQL Agent 05:00 ET]
   rpt.ExecRecoveryFact_Subro  ───┐             rpt.ExecRecoveryFact_COB  ───┐                     rpt.ExecRecoveryFact_Rx ──┐
                                  │                                          │                                                │
                                  └──────────────►  PC210344  (Windows Task Scheduler 05:45 ET)  ◄───────────────────────────┘
                                                    python consolidate_exec_recovery.py  (pyodbc, Windows auth)
                                                    → writes ExecReporting.rpt.ExecRecoveryFact / DimCase / DimClient / RefreshLog
                                                    → Slack/email on failure or freshness breach
                                                                 │
                                                    on-prem data gateway (DBA-managed, svc_pbi_dg_reports)
                                                                 │
                                                    Power BI Service — scheduled refresh 06:15 ET (Import)
```

Where `ExecReporting` is a small new schema/database on the Subro reporting server (ask ODS whether `SubroReports.rpt` is acceptable for a cross-pillar table or whether they prefer a separate `ExecReporting` DB; either is fine for the gateway).

### Pattern choice per pillar

| Pillar | Pattern | Why |
|---|---|---|
| Subrogation | **1 — SQL-only** (stored proc + SQL Agent job on the SubroReports server) | Everything needed is on one server; ODS already runs identical nightly jobs; no Python dependency. |
| COB | **1 — SQL-only** on TRGACAP3 (database `ACT`), owned/co-owned by DMG (Josh Roberts) | The posting source is `ACT.dbo.Remit` on TRGACAP3, the same server that hosts `CarlQryRun`, so the fact can be built with a single stored procedure and no linked server. SmartII investigation attributes (program line, invoiced $) come via `Remit.InvestigationId` → SmartII on `SQLUserAudit` through the linked server Josh already uses, or via `Claim.COBID`→`COB.AuditCategory` inside ACT if that proves to be the program line. Fall back to Pattern 2 on PC210344 only if a service account cannot get read on `ACT`. |
| Pharma | **1 — SQL-only** on `SQLUserRx` | RXP and RxTra are on the same instance; a single proc joins them. |
| Consolidation + monitoring | **2 — Python on PC210344** (Task Scheduler) | Cross-server union, freshness checks, alerting, and a place to run a reconciliation to ODS monthly numbers. Avoid PC210319 (crowded; DMG production). |

### Subro — draft SQL logic (stored proc `rpt.usp_Build_ExecRecoveryFact_Subro`)

```sql
-- Nightly: rebuild the trailing 400 days (idempotent; late postings are captured by re-deriving the window)
DECLARE @from date = DATEADD(DAY, -400, CAST(GETDATE() AS date));

;WITH rec AS (
    SELECT r.rec_collect_id, r.file_key, CAST(r.RecoveryDate AS date) AS RecoveryDate,
           r.GrossRecovery, r.TRC_Fee, r.clnt_id
    FROM SubroReports.rpt.SubroDataWarehouseRecovery r
    WHERE r.RecoveryDate >= @from
),
rep AS (   -- rep/team credited at the time of the recovery: file version current on RecoveryDate
    SELECT rec.rec_collect_id, fv.rep_name, rm.team
    FROM rec
    JOIN Subro_SRS.dbo.fversion fv ON fv.file_key = rec.file_key
                                   AND rec.RecoveryDate >= CAST(DATEADD(SECOND, fv.d_start, '1970-01-01') AS date)
    OUTER APPLY (SELECT TOP 1 fv2.file_ver FROM Subro_SRS.dbo.fversion fv2
                 WHERE fv2.file_key = rec.file_key
                   AND rec.RecoveryDate >= CAST(DATEADD(SECOND, fv2.d_start, '1970-01-01') AS date)
                 ORDER BY fv2.file_ver DESC) cur
    LEFT JOIN Subro_SRS.dbo.rep_maint rm ON rm.rep = fv.rep_name
    WHERE fv.file_ver = cur.file_ver
)
MERGE ExecReporting.rpt.ExecRecoveryFact_Subro AS t
USING (
    SELECT 'Subrogation' AS Pillar, rec.RecoveryDate, rec.GrossRecovery AS GrossAmount, rec.TRC_Fee AS FeeAmount,
           rec.GrossRecovery - ISNULL(rec.TRC_Fee,0) AS NetAmount,
           CAST(rec.file_key AS varchar(20)) AS CaseKey, CAST(rec.rec_collect_id AS varchar(30)) AS SourceTxnId,
           CASE WHEN sf.WorkComp = 1 THEN 'WC'
                WHEN rep.team IN (41,42) THEN 'SRU'
                WHEN rep.team = 45      THEN 'RCU'
                WHEN rep.team IS NULL   THEN 'Unassigned'
                ELSE 'LRU' END AS UnitKey,            -- replace with ODS Recovery Unit logic once confirmed
           sf.FinanceReportingClient AS ClientKey, sf.DIGClientParent AS ParentName,
           rep.team AS Team, GETDATE() AS LoadTs
    FROM rec
    LEFT JOIN rep ON rep.rec_collect_id = rec.rec_collect_id
    LEFT JOIN SubroReports.rpt.SubroFile sf ON sf.file_key = rec.file_key
) AS s ON s.SourceTxnId = t.SourceTxnId
WHEN MATCHED AND (s.GrossAmount <> t.GrossAmount OR s.RecoveryDate <> t.RecoveryDate OR s.UnitKey <> t.UnitKey) THEN UPDATE SET ...
WHEN NOT MATCHED BY TARGET THEN INSERT (...)
WHEN NOT MATCHED BY SOURCE AND t.RecoveryDate >= @from THEN DELETE;   -- removes voided lines inside the window

-- DimCase (Subro): files with a posting in the last 13 months
-- DimClient (Subro): FinanceClientCodeLookup + LOBByChildCode_FinanceUpdate
-- Log: INSERT ExecReporting.rpt.ExecRecoveryLoadLog (Pillar, LoadTs, RowsLoaded, MaxRecoveryDate, Status)
```

Notes: SRS dates are epoch seconds (`d_start`, `d_added`), hence the `DATEADD(SECOND, …, '1970-01-01')`. **Preferred simpler form:** `rpt.RecoveriesbyLOBTableau` is refreshed nightly and already carries `Team`, `LOB`, `Division` and `IsPostedRecovery`, so the proc collapses to

```sql
SELECT 'Subrogation' AS Pillar, CAST(RecoveryDate AS date) AS RecoveryDate, GrossRecovery AS GrossAmount,
       CAST(File_key AS varchar(20)) AS CaseKey, CONCAT(File_key,'|',CAST(RecoveryDate AS date),'|',Team) AS SourceTxnId,
       CASE WHEN Team IN (41,42) THEN 'SRU' WHEN Team = 45 THEN 'RCU' ELSE 'LRU' END AS UnitKey,   -- swap for ODS Recovery Unit logic
       Team, LOB, ContractualClientCode AS ClientKey, Parent_Name AS ParentName, UpdateDate
FROM   SubroReports.rpt.RecoveriesbyLOBTableau
WHERE  IsPostedRecovery = 1 AND Division = 'S' AND RecoveryDate >= DATEADD(DAY,-400,GETDATE());
```

Keep the ledger-based version above as the reconciliation query (it has `TRC_Fee` for net $ and `rec_collect_id` for line-level audit). Reconcile the monthly sum to `rpt.MonthlyKPIReport.PostedRecoveries` before go-live.

**Deployment route:** this is a new object on an ODS-owned server → open an **ADO deployment ticket** (the Rawlings TFS/ADO instance `devops.ado.rawlingslou.prod`, same route DMG used for `ADO868307`, `ADO915071`) with the DDL + proc + Agent job definition, and post in `#ask-dba` for scheduling and for the job operator/email alert (`sp_send_dbmail` operator on failure; DBA-standard). Lead time observed in Slack for comparable tickets: days to two weeks. Jennefer Murphy / Dan Stephens should be tagged as owners since it lands in their schema.

### COB — draft SQL logic (`rpt.usp_Build_ExecRecoveryFact_COB`, TRGACAP3 database `ACT`)

```sql
-- Real column names from the ACT discovery of 2026-09-16. Amount column (AppliedAmt vs ARDAmount) and
-- the Division 2 = COB assumption are to be confirmed by dashboard/sql/act_cob_step2_*.sql.
SELECT 'COB' AS Pillar,
       CAST(r.AddDate AS date)             AS RecoveryDate,      -- ACT.dbo.Remit posting date
       r.AppliedAmt                        AS GrossAmount,       -- TBC vs ARDAmount / ARDAmount + AuditorAmount
       r.FeeValue                          AS FeeAmount,
       CAST(r.InvestigationId AS varchar(20)) AS CaseKey,
       CAST(r.ID AS varchar(30))           AS SourceTxnId,
       cob.AuditCategory                   AS UnitKey,           -- TBC: program line; else SmartII investigation type via InvestigationId
       cl.Code                             AS ClientKey,         -- via RemitPendingClaim -> Claim -> Client; cl.ParentCode for the parent
       rt.Name                             AS RecoveryTypeName,  -- Cash / Direct / Retraction / Check / EFT / Card / Adjustment
       rm.Name                             AS RecoveryMethodName
FROM ACT.dbo.Remit r WITH (NOLOCK)
OUTER APPLY (SELECT TOP 1 ClaimID FROM ACT.dbo.RemitPendingClaim WITH (NOLOCK) WHERE RemitID = r.ID) rpc
LEFT JOIN ACT.dbo.Claim  c   WITH (NOLOCK) ON c.ID  = rpc.ClaimID
LEFT JOIN ACT.dbo.Client cl  WITH (NOLOCK) ON cl.ID = c.ClientID
LEFT JOIN ACT.dbo.COB    cob WITH (NOLOCK) ON cob.ID = c.COBID
LEFT JOIN ACT.dbo.RecoveryType rt ON rt.ID = r.RecoveryTypeID
LEFT JOIN ACT.ruin.RecoveryMethod rm ON rm.RecoveryMethodId = r.RecoveryMethodId
WHERE r.DivisionId = 2                                          -- COB medical per John Marcsik (ACT labels it "Subro")
  AND r.AddDate >= @from AND r.AddDate < @to;
-- Previous skeleton kept for reference (SmartII-side names):
--     CAST(p.PostedDate AS date)          AS RecoveryDate,
--     p.PostedAmount                      AS GrossAmount,
--     p.FeeAmount                         AS FeeAmount,
--     CAST(i.InvestigationID AS varchar(20)) AS CaseKey,
--     CAST(p.PostingId AS varchar(30))    AS SourceTxnId,
--     pl.ProgramLine                      AS UnitKey,
--     a.ClientCode                        AS ClientKey,
--     oi.OtherInsurerName                 AS CounterpartyKey
-- FROM SmartII.dbo.tblInvestigation i JOIN SmartII.dbo.tblAudit a ON a.AuditID = i.AuditID
-- JOIN <posting table> p ON p.InvestigationID = i.InvestigationID ...
```

Counterparty (other insurer / payer) is not on `Remit`; it comes from SmartII via `Remit.InvestigationId` once the linked server is available, or from `Remit.RemitterType` / `RecoverySource` as a coarse stand-in. Until step 2 has run, the prototype can still use `CarlQryRun.overlap_detection.InvestigationInvoices` (invoiced $, dated) for layout testing; label that card "Invoiced", never "Recovered".

**Deployment route:** Josh Roberts' DMG team owns the Agent jobs on TRGACAP3 → ask them to add this proc to their nightly chain (they already schedule reporting steps there), then the same ADO ticket route for production. Alert: their existing job-failure notifications to `#ask-dba`.

### Pharma — draft SQL logic (`rpt.usp_Build_ExecRecoveryFact_Rx`, SQLUserRx)

```sql
SELECT 'Pharma' AS Pillar,
       CAST(rdt.[TimeStamp] AS date)               AS RecoveryDate,          -- posting timestamp on the ledger row
       rdt.Recovered                               AS GrossAmount,           -- posted recovery on this ledger row
       NULL                                        AS FeeAmount,
       CAST(inv.TRC_INVESTIGATION_ID AS varchar(20)) AS CaseKey,
       CAST(rdt.RemitDetailTransactionId AS varchar(30)) AS SourceTxnId,
       it.SolutionLine                             AS UnitKey,               -- Pharmacy COB / Retro Term / Part D / HCD
       c.ClientCode                                AS ClientKey,
       oi.CarrierName                              AS CounterpartyKey,       -- PBM / OI carrier
       rm.RemittanceMethod                         AS RecoveryMethod,        -- P2P batch / portal / USPS / member
       GETDATE()                                   AS LoadTs
FROM   RxTra.dbo.tblRemitDetailTransaction rdt
JOIN   RxTra.dbo.tblRemittance r      ON r.RemittanceId = rdt.RemittanceId AND r.RemittanceTypeId <> 5   -- exclude write-offs
JOIN   RXP.dbo.tblInvoice inv          ON inv.InvoiceId = rdt.RxpInvoiceId
JOIN   RXP.dbo.tblInvestigation iv     ON iv.pk = inv.TRC_INVESTIGATION_ID
JOIN   RXP.dbo.tblClient c             ON c.pk = iv.ClientId
LEFT JOIN <investigation-type → solution-line map> it ON it.InvestigationTypeId = iv.InvestigationTypeId
LEFT JOIN <OI carrier> oi ON ...
LEFT JOIN <remittance method> rm ON ...
WHERE  rdt.[TimeStamp] >= DATEADD(DAY,-400,GETDATE())
  AND  rdt.RemitTransactionTypeId <> 1;     -- 1 = the invoice-seed row created by spPullRxpInvoice, not a payment
```

Column names for `tblRemitDetailTransaction` (`Recovered`, `Writeoff`, `Outstanding`, `RemitTransactionTypeId`, `RemittanceId`, `WriteOffReasonId`, `TimeStamp`) are as described in the Pharmacy team's source-read; verify against the schema before coding. Reconcile to RxTra's own `rptInvoice`/aging totals for one month.

**Deployment route:** Pharmacy AppDev (Matt Weirich) owns RXP/RxTra changes; a read-only proc in a reporting schema on `SQLUserRx` plus an Agent job, via ADO ticket. Alternative if AppDev prefers not to host it: Python on PC210344 reading RxTra via pyodbc and writing to `ExecReporting` (Pattern 2).

### Consolidator — Python on PC210344 (Pattern 2)

```
consolidate_exec_recovery.py   (Windows Task Scheduler, daily 05:45 ET, run as a service account, "run whether user is logged on or not")
  1. For each pillar: SELECT * FROM <server>.<db>.rpt.ExecRecoveryFact_<pillar> WHERE RecoveryDate >= today-400   (pyodbc, ODBC Driver 17, trusted_connection=yes)
  2. Validate: row count > 0; MAX(RecoveryDate) >= today-2 (Subro, Rx) / today-3 (COB); no NULL CaseKey; sum within ±25% of trailing-7-day mean (soft warning)
  3. UPSERT into ExecReporting.rpt.ExecRecoveryFact (MERGE on Pillar+SourceTxnId); rebuild DimCase/DimClient views; write RefreshLog
  4. On failure or freshness breach: Slack webhook to #rps-data-science + SMTP email (same pattern John Marcsik uses for ~20 pharmacy report scripts)
  5. Exit code non-zero so Task Scheduler history shows failure
```

Box choice: **PC210344** (or PC210345 as standby); avoid PC210319, which is DMG's de-facto production box and already crowded. Remote access to PC210344/45 must be requested through `#ask-rps-sysadmin` / Freshservice (Connor Mason / Byron Dewey handled prior box and firewall requests). Task Scheduler jobs should run under a **service account**, not a personal login — John's Jan 2026 lockout on PC210319 came from scheduled tasks holding an expired personal password.

If the DBAs would rather not have Python touch three servers, the alternative is **linked servers + one SQL Agent job** on the reporting server doing the union; functionally equivalent, but each linked server is its own security request.

## 2.5 Power BI refresh and distribution design

| Topic | Finding | Recommendation |
|---|---|---|
| Is there a central Power BI / Tableau server? | **Yes — Power BI Service is central and IT-owned.** Evidence: `app.powerbi.com/groups/…` report links shared internally (Ryan Tydlacka, Aug 2026); a `#power-bi-dba-infra` channel where Tyler Edison runs a **workspace approval workflow** (approvers per area: *Subro → Jennefer Murphy & Dan Stephens; ORG / Global Resources / Finance → Jennefer & Dan (+ Ryan Tydlacka); PMO/Implementations → Lisa Walsh & Miriam McDannold; PI → Travis W. & Kyle S.; RDP → Eric Smith & Margaret A.*); Mark Mills (DBA) administers the **on-prem data gateway** (data-source requests via Freshservice, gateway service account `trgllc\svc_pbi_dg_reports`); IT owns the tenant and handles access via Freshservice; Enterprise Analytics Engineering (Jon West, EAES Jira) publishes Import-mode semantic models (CPS Performance Hub) with a daily ~08:00 ET refresh. Tableau: only legacy `rpt.Tableau*` tables at Rawlings; no live server found. | **Do not build this in a personal workspace.** Request a workspace (e.g. `RPS - Executive Recoveries`) through Tyler Edison's ticket workflow with Jennefer Murphy and Dan Stephens as approvers (it is cross-pillar, so use the ORG/Global approvers). Publish an **App** from that workspace to the exec audience. |
| Licensing / capacity | Machinify has **F64 Fabric capacity in the l-Rawlings tenant** (Jon West, May 2025: "F64 is the minimum tier to enable the most important features… avoiding buying the same F64 capacity twice, once at Rawlings and once in CPS") and 29 Power BI Premium-per-user licenses in the apixio.com tenant. | Put the workspace on the **F64 capacity**: viewers then need only a Free license, refresh cap rises to 48/day, and large-model features are available. If capacity is not granted, fall back to Pro: every exec viewer needs Pro (or PPU), and refresh is capped at 8/day — one daily refresh is all we need anyway. Confirm which tenant the execs' identities live in (Rawlings vs Apixio) before publishing; cross-tenant viewing is the pain point Ben Mishkin flagged. |
| Storage mode | Import. Data volume is small; Import gives sub-second exec pages and lets us shape measures freely. DirectQuery is not needed and would put exec page loads on an on-prem SQL replica. | **Import mode**, scheduled refresh **06:15 ET daily**, after the 05:00 SQL jobs and the 05:45 consolidator. Add a second refresh at 12:00 ET as a safety net for late jobs (still well under 8/day). |
| Gateway | ODS SQL Servers (TRGDMGREP1, trgsubrodmg3, TRGACAP3, SQLUserRx) are on the l-Rawlings La Grange network (192.168.251.x). Power BI Service cannot reach them without a gateway. A standard-mode gateway already exists (DBA-managed). | **Yes, gateway required.** Submit a Freshservice request to Mark Mills to add a data source for `ExecReporting` (or `SubroReports`) on the existing gateway, credentials = a read-only SQL/Windows service account. One data source, since the consolidator lands everything in one place. |
| Refresh failure handling | Power BI emails the dataset owner on failure. | Set the dataset owner to a shared mailbox / distribution list, enable failure notifications to a second contact, and rely on the consolidator's freshness flag on the page header as the user-visible signal. |
| Security | Aggregates only; no PHI. | No RLS in v1. Workspace Viewer role for execs via the App; Member role for the two builders. |
| Alignment with the RPS Analytics Warehouse | EAES is designing an RPS gold layer (`rps_case`, `f_rps_recovery` with `recovery_type` = CASH_RECOVERY / COST_AVOIDANCE, Databricks medallion + Power BI). | Name our fact columns to match theirs (`recovered_amount_gross`, `vendor_fee_amount`, `recovery_type`) so the semantic model can later be re-pointed to the warehouse with no visual changes. This dashboard is the interim answer; say so on the About tooltip. |

## 2.6 Open questions and blockers (resolve before production)

| # | Item | Owner to ask | Why it blocks |
|---|---|---|---|
| 1 | **COB posted-recovery source** — located: `ACT.dbo.Remit` (`AddDate`, `AppliedAmt`), Division 2. Still to confirm: (a) Division 2 is the COB medical book (ACT labels it "Subro"); (b) gross = `AppliedAmt` vs `ARDAmount`(+`AuditorAmount`); (c) how reversals/adjustments post; (d) does Josh's Monthly Recovery Report read `Remit`? | John Marcsik (pointed at Division 2); Josh Roberts (DMG); Brian Sharp / Christine H. (COB reporting) | Until the step 2 queries run and (a)–(c) are agreed, the COB pillar has a source but no number. |
| 2 | Confirm Subro unit logic (rep team at recovery date; 41/42 SRU, 45 RCU, else LRU) matches ODS's `Recovery Unit`, and how Global / WC / senior-LRU are treated | Jennefer Murphy, Dan Stephens (Subro ODS) | L2 numbers must reconcile to ODS's own dashboard. |
| 3 | Confirm what I measured: `rpt.RecoveriesbyLOBTableau` refreshes nightly ~04:00 ET with data through the current day, `IsPostedRecovery` separates posted from submitted, and the ledger carries ~5k negative (reversal) rows per month; also whether "posted" here means finance-posted or analyst-entered | Subro ODS | Determines whether a T-1 daily number is trustworthy and what execs will call "recovered". |
| 4 | Read access for a pipeline service account to SmartII (`SQLUserAudit`), `SQLUserRx` (RXP/RxTra), and the COB posting source; or an agreed DMG-produced extract | DBAs (`#ask-dba`), Matt Weirich (AppDev), Josh Roberts | Pharma and COB procs cannot be written or tested from here. |
| 5 | Sample data from Josh Roberts: `InvestigationInvoices`, the COB recovery report output, and the Pharmacy monthly recovery report (one month each) | Josh Roberts | Validates the L2 program-line / solution-line mappings and the invoice→posting linkage. |
| 6 | Cross-pillar client master (does Finance have one? `FinanceClientCodeLookup` is Subro-only) | Finance; EAES (Jon West) | Needed before any client slicer on the landing page. |
| 7 | ADO deployment tickets for three stored procs + Agent jobs (lead time ~1–2 weeks each observed); DBA time for job operators/alerts | DBA team; ODS; DMG; AppDev | Production schedule. |
| 8 | Remote access to PC210344 / PC210345 and a service account for Task Scheduler | `#ask-rps-sysadmin` (Connor Mason) | Consolidator cannot be deployed. |
| 9 | Power BI workspace request (approvers Jennefer / Dan), placement on F64 capacity, gateway data-source request, and which tenant the exec viewers sit in | Tyler Edison (workspace workflow), Mark Mills (gateway), IT (licenses) | Distribution to execs. |
| 10 | Whether WC (Workers' Comp) recoveries are in or out of the Subrogation pillar, and whether COB "cost avoidance" needs a placeholder on the page | Jeff Bradshaw's office / Shri Santhanam (requester) | Scope of the headline number. |
| 11 | Business-day vs calendar-day windows (postings do not occur on weekends/holidays; a 30-calendar-day window with 20 vs 22 business days will show noise as Δ%) | Requester | Consider "last 30 days vs prior 30 days" plus a footnote of business days in each window; `rpt.DimDate.IsHoliday` supports it. |

## 2.7 Build sequence (suggested)

1. **Week 1** — Lock definitions (§1.1), unit logic (Q2), and the COB posting source (Q1). Get sample extracts (Q5). Submit access, box, workspace, and gateway requests (Q4, Q8, Q9) in parallel since they have the longest lead times.
2. **Week 2** — Subro proc + Agent job via ADO ticket; build the `.pbix` against Subro-only data with `DimPillarUnit` fully populated so COB/Pharma pages render empty-but-correct.
3. **Week 3** — Pharma proc on `SQLUserRx`; COB proc with DMG; consolidator on PC210344; reconcile one month per pillar to the owning team's monthly report.
4. **Week 4** — Publish to the approved workspace, App to a pilot exec, daily refresh monitored for a week, then wide release.

---

## Appendix A — Where each fact in this document came from

| Fact | Source |
|---|---|
| Database list on TRGDMGREP1 (129 DBs, no `ODS`), `SubroReports` schema counts, `rpt.*` inventory, `SubroFile` status distribution and column list | Live catalog queries through Machinify Studio project 0010z (JDBC source 192.168.251.19, user `lmachinify`), 2026-09-14 |
| `SubroDataWarehouseRecovery`, `RecoveriesbyLOBTableau`, `MonthlyKPIReport`, `TeamPod`, `DimDate`, … column lists | Resource registration in Studio 0010z, 2026-09-14 (schema returned on registration) |
| `recovery_collect`, `recovery`, `exp_recover` columns | Same |
| SRU/RCU/LRU team mapping and InventoryScore bands | `subro/ASSUMPTIONS_TO_VET.md`, `medium_large_gate_lien_refresh_analysis/sql/01_store_sample.sql`; Jason Gibson's query in `#ask-subro-ods-data-products` (2026-08-27) |
| Josh Roberts = DMG for COB; TRGACAP3 Agent jobs; `CarlQryRun` tables; SmartII / aCentricReports object names | Slack `#cob-overlap-detection`, `#caqh-refresh`, `#ask-dba`, `#project-cob-performant-to-rps-investigation-flow`; Studio 0012k data-source and table listing |
| DB → server aliases (SmartII → SQLUserAudit; aCentricReports → SQLUtilMine4; RXP/RxTra → SQLUserRx; Subro_SRS → SQLUserSubro) | Notion "DBA Database Alias List" (Database Administration Shared, 2026-05-15) |
| RXP / RxTra invoice and remittance model | Notion "Re-Invoicing a Denied Claim on the Same Investigation" (Pharmacy team, 2026-08-18); "Pharmacy Overview – Systems, Processes & Opportunities" (2026-06-26) |
| Pharmacy solution lines and revenue split; standard monthly recovery report contents | Same Notion overview; `#bcbs-az-rfp-build` thread (2025-12-05) |
| COB metrics framing (pay-and-chase today, cost avoidance future) | Notion "COB Client Value Metrics" (2026-07-01); "RPS Domain Knowledge Base" (EAES, 2026-08-24); COBE Analytics Dashboard PRD (2026-09-09) |
| Power BI tenant, workspace approvals, gateway, F64 capacity, PPU licenses | Slack `#power-bi-dba-infra` (Mar–Sep 2026), `#ask-networking` thread (May 2025), `#general-questions`, `#servicedesk`, `#cps_reporting` |
| Automation boxes PC210319 / PC210344 / PC210345 | John Marcsik DM (2026-09-14); `#ask-rps-sysadmin` history (lockout Jan 2026, IIS hosting May 2026) |

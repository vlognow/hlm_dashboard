# RPS $ Recovered — Real-Data Snapshot

_Generated 2026-09-14 21:12 EDT from Machinify Studio. No synthetic or placeholder rows anywhere below._

## Subrogation (full real time series)
- **Recovered, last 30 days:** $85.7M
- **Prior 30 days:** $86.0M (-0.3%)
- **Files with a posting in the window:** 24,676
- **Data through:** Sep 11, 2026
- **Source:** `SubroReports.rpt.RecoveriesbyLOBTableau` (Machinify Studio project 0010z / TRGDMGREP1)

## COB (real, but all-time invoiced — no date field exists)
- **Total invoiced (all-time):** $1,651.5M
- **Investigations:** 771,151 (273,926 with a positive invoice amount)
- **Source:** `overlap_detection.InvestigationInvoices` joined to `CEMOverlapsAndSmartIIResults` for client code (Machinify Studio project 0012k / TRGACAP3)
- **Caveat:** this table has no date column, so no 30-day figure can be computed. Separately, 8 other tables with the right shape for a dated recovered-$ figure (`OverpaymentReceivedAmount` + `PayDate`/`ReceivedDate`, across 7 Aetna HMO/HRP MSP audit 'Final' tables and a Cigna Professional Claims extract) were checked and every one has that column entirely NULL.

**Top 10 clients by invoiced $ (all-time, real):**

| Client Code | Investigations | Invoiced $ |
|---|---|---|
| AHP | 232,142 | $496,088,850 |
| CIGNA_PRO | 79,199 | $149,907,293 |
| CIGNA_FAC | 30,758 | $86,327,055 |
| PRE_PBWW_A | 29,729 | $53,344,770 |
| AHRP_MA | 27,336 | $50,587,083 |
| BCBSFL | 9,464 | $44,135,398 |
| OSC_IND | 6,182 | $33,624,952 |
| BCBS_FACET | 12,711 | $32,827,524 |
| CENMOHSMD | 17,787 | $30,215,209 |
| BCBSFL_HIX | 9,707 | $29,384,878 |

## Pharma
- **No reachable data source.** RXP/RxTra are not registered as a Studio data source in any project this session can access. No number is shown because none exists to show — not because a real figure was omitted.

## Chart

![Subrogation $ Recovered per day, last 90 days](real_data_chart.png)

![COB invoiced $ by client, all-time](real_data_chart_cob.png)

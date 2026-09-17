# Decision log — RPS $ Recovered dashboard

Running record of judgement calls, newest first. Each entry: what was decided, the evidence, and what would change it.

## 2026-09-17 — COB (medical) pillar = ACT `dbo.Remit` rows with `DivisionId IS NULL`

**Decision.** The medical COB posted-recovery series is `ACT.dbo.Remit` where `DivisionId IS NULL`, dated by `AddDate`, measured by `AppliedAmt`, net of adjustments (negative remits kept).

**Evidence (step 2b/2d, run 2026-09-17 via direct pymssql on TRGACAP3).**
- `Remit` has two books: `DivisionId = 2` (1.53 M rows since 2015) and `DivisionId IS NULL` (1.31 M rows since 2010). No rows with 1, 3 or 4.
- NULL-division remits allocate to claims through `RemitPendingClaim`; those claims sit in `Claim.DivisionID = 1` ("Audit", displayed as "Payment Integrity"). Parent client codes are CIGNA_PRO, OSCAR, CIGNA_FAC, AHP, GEHA, MEDICA, CEN, HNA, AHRP, EMBLEM_FAC. `COB.AuditCategory` values are COB Commercial, Medicare Age, Medicare Disability, CAQH, Medicare ESRD, plus small Rx Duplicate / Rx High Cost Drug. All-time applied ≈ $1.60 B, which matches the $1.65 B all-time invoiced in `CarlQryRun.overlap_detection.InvestigationInvoices`. This is the medical COB book.
- Division 2 remits are never allocated to ACT claims (`RemitPendingClaim` empty for all 329,677 remits in the last 12 months), carry `InvestigationId`, `RecoverySource` = Liability Carrier / Plaintiff Attorney / Worker Comp / Med Pay-No Fault, `RemitterType` = Attorney / Carrier / Provider, and `TransactionTypeID = 46 "Submitted Recovery"`. Monthly applied $70–110 M tracks the Subrogation series (Aug 2026: ACT Div 2 $100.7 M vs SubroReports posted $88.0 M). **Division 2 is Subrogation at the submitted stage, not medical COB.** John Marcsik's "Division ID = 2" pointer therefore applies to his Subro remark (claim-level recovery dates), and the COB book is the NULL-division / Audit side.
- Amount column: `AppliedAmt` is the amount applied to claims. `ARDAmount` + `AuditorAmount` is a credit split (`ARDPercent` / `AuditorPercent`) that exceeds `AppliedAmt` and diverges sharply from Jun 2026 onward, so it is not a dollars-recovered measure. `FeeValue` is tiny (≈ $1.5 K/month) and not Machinify's contingency fee.

**Consequences.**
- Subrogation stays sourced from `SubroReports.rpt.RecoveriesbyLOBTableau` (posted). ACT Division 2 is not added, to avoid double counting.
- Rx Duplicate / Rx High Cost Drug audit categories (≈ $1.6 M / 12 months) stay inside the COB pillar because they are Payment Integrity audits, not the DMG pharmacy ledger. Flagged on the page.
- Reversals: `Adj-Client` / `Adj-Provider` remits are negative and are kept, so the monthly series is net of reversals, consistent with the Pharmacy treatment.
- ~52 % of NULL-division remits have no claim allocation (write-offs at $0 and adjustments); they carry ≈ +$6 M / 12 months net and are shown as "(no claim allocation)" in the category split.

**Would change it.** Josh Roberts or COB Ops stating that a different table (e.g. `Transaction` type 6 Posted) is the finance-recognised posting; step 2c reconciliation (`act_cob_step2_transaction_monthly.sql`) is running to check that.

## 2026-09-17 — Overall RPS total = Subro posted + Pharmacy posted + COB applied, same month

Simple sum of the three pillar series for the last complete month, each net of reversals. No fee netting, no dedupe across pillars (pillars are disjoint systems: SubroReports, DMGMining Rx ledger, ACT Audit book).

## 2026-09-17 — Access path: direct pymssql from JupyterHub, not Studio

Studio JDBC sources are bound to one database each and reject three-part names. JupyterHub reaches all three SQL Servers on 1433 with the user's domain login (`~/sql_access.txt`, git-ignored). Helper: `dashboard/act_conn.py`; runner: `dashboard/run_act_discovery.py`.

## 2026-09-16 — Pharmacy pillar = `DMGMining.dbo.PostedRecoveryTrendingData`

DMG pharmacy group's posted-recovery ledger (Jan 2020 → present, ~60 clients, 12 program types). Reversals kept as negatives.

## 2026-09-14 — Subro pillar = `SubroReports.rpt.RecoveriesbyLOBTableau`, posted rows only

Transaction grain (file × recovery date), `IsPostedRecovery = 1`, `GrossRecovery`. Units from team (41/42 SRU, 45 RCU, else LRU). Not "last recovered date on file", so no pull-forward bias.

## 2026-09-17 — Claim linkage for COB splits uses RemitPendingClaim, then RemitTransaction

From Jun 2026 a growing share of NULL-division "Completed Recovery" remits (30 % of $ in Jun, 49 % in Aug) have no `RemitPendingClaim` row but do have `RemitTransaction` rows. Category and client splits therefore use `COALESCE(RemitPendingClaim.ClaimID, Transaction.ClaimID via RemitTransaction)`. After this, "(no claim allocation)" drops to ≈ $18 K in Aug 2026. Monthly totals are unaffected (they never needed the claim link). Flag for Josh Roberts: is the June change a process change or a backlog?

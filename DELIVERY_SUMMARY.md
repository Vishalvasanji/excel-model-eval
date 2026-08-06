# LAHAP_Model_v1.xlsx — Delivery Summary
**Louisiana HAP Portfolio acquisition/resyndication underwriting model · built 8/6/2026 per LA_HAP_Portfolio_Model_Spec.md**

25 tabs · 8,444 formulas · zero formula errors on full recalc · iterative calc ON (deliberate S&U ↔ Financing ↔ S&U Timing loop) · DeGaulle formatting/scorecard system cloned, zero DeGaulle deal data (contamination sweep clean: no "DeGaulle"/"DeGualle"/"New Orleans" anywhere) · every blue input carries a source comment (622 cells) · INDEX/MATCH only.

---

## 1. Solver result — maximum supportable purchase price (base assumptions)

| | Clear Horizons | New Zion | Live Oak Manor | Spanish Arms | **Portfolio** |
|---|---|---|---|---|---|
| Max supportable price | **$0** | **$0** | **$3,000,000** | **$500,000** | **$3,500,000** |
| Price/unit | $0 | $0 | $25,210 | $2,451 | $6,903 |
| Unfunded soft gap at that price | $461,898 | $148,039 | $0 | $0 | $609,937 |

Base assumptions (all one-cell overrides on Dashboard Calc, yellow-flagged): DSCR-constrained sizing at **1.15x** on stabilized NOI, perm debt **6.00%/35-yr** refinance base case, rehab **$40,000/unit** hard cost placeholder (+ contingency/GC ≈ $49.6k/unit loaded, + 15% basis soft costs), equity **$0.80**, OCAF **2.5% × 75% achievement**, expenses **3%**, insurance **6%**, relocation **$2,500/unit**, acquisition **12/1/2026**.

**Why prices are low:** the rehab scope dominates the stack. At $40k/unit, total uses ex-price run $6.9M–$15.6M per property against DSCR-sized debt + 4% equity; CH and NZ cannot balance at any price (their unfunded gaps above persist even at $0 and would need soft funds — note NZ's gap is after crediting its $187k positive bridge cash). **Sensitivity (Portfolio Consolidation tab):**

| Scenario | CH | NZ | LOM | SA | Portfolio |
|---|---|---|---|---|---|
| BASE | 0 | 0 | 3,000,000 | 500,000 | **3,500,000** |
| OCAF 2.0% / 3.0% | 0 / 0 | 0 / 0 | 2.70M / 3.15M | 500k / 500k | 3.20M / 3.65M |
| Insurance 4% / 8% | 0 / 0 | 0 / 0 | 3.15M / 2.70M | 500k / 500k | 3.65M / 3.20M |
| Equity $0.75 / $0.85 | 0 / 0 | 0 / 0 | 2.55M / 3.30M | 0 / 1.00M | 2.55M / 4.30M |
| **Rehab $25k / $55k per unit** | 853k / 0 | 1.70M / 0 | 5.25M / 600k | 4.25M / 0 | **12.05M / 600k** |

The **rehab budget (Gap #2) is the single most important open diligence item** — a CNA moves the portfolio answer by ~$9M. Second: equity pricing and the OCAF/expense growth spread (see DSCR note below).

## 2. Model Scorecard — verdicts and PENDING items

All four properties currently grade **FAIL** (portfolio verdict FAIL) — driven by honest assumption-level findings, not model errors:

- **Post-resyn DSCR band (Yr2-17): FAIL ×4.** Perm debt is sized at exactly 1.15x on Yr-1 NOI, but revenue trends at 1.875%/yr (OCAF × 75% haircut) while expenses trend 3%/6% — NOI erodes and DSCR slips below 1.15x from Yr-2. Raising the OCAF achievement to 100% (or trimming loan sizing to a cushion above 1.15x) resolves the band; this is an assumption decision, not a bug.
- **Deferred fee repaid ≤15 yrs: FAIL ×4** — same NOI-erosion cash-flow shortage.
- **Sources = Uses w/o soft gap: FAIL CH, NZ** (the $462k/$148k unfunded gaps above).
- **Bridge DSCR: FAIL CH** (CH runs ~0.57x on its assumed note; cumulative bridge carry −$47k), PASS NZ/LOM, N/A SA.
- **Vacancy floor: FAIL CH, NZ** — seeded at actual occupancy (3.6%/2.0%) per spec, below the QAP underwriting floor.
- **PENDING (4 items ×4 properties):** LA QAP minimum rehab $/unit (no confirmed 2026 value — blank threshold rather than a fabricated one), **URA applicability** (NZ's existing stack contains a HOME loan; any HOME/CDBG in the new stack triggers URA relocation costs), **QAP vintage** (register carries LA 2025 QAP values — Gap #6), price/unit vs comps = REVIEW for CH ($0 price).
- PASS across the board: developer fee % cap, TDC/unit vs HUD/LHC limits, post-rehab rents ≤ MIN(High HAP comp, 150% SAFMR) and SA LIHTC max, IRC minimum rehab, 25% bond test (OBBBA basis — all 53–86% bond-financed).

## 3. Yellow-flagged cells (89 — every one needs real diligence data)

- **Dashboard Calc (18):** Acquisition prices C12:F12 (solver outputs, re-run after any change); Land 15% of price ×4 (Gap #7 — needs appraisal); OCAF 2.5%; expense 3%; insurance 6%; post-rehab uplift 10% ("broker assumption — validate via RCS"); cost inflation 4%; perm rate 6.00%; LTV cap 90%; rehab $40k/unit; relocation $2,500/unit; SA HAP renewal assumption.
- **Rehab Scope (52):** the five hard-cost category allocations ×4 properties (interiors $20k / roofs $6k / HVAC $6k / plumbing $4k / site $4k); relocation method, downtime, and the six relocation line-item allocations ×4.
- **Sources & Uses (6):** unfunded soft-gap plugs (CH $461,898 / NZ $148,039 / LOM 0 / SA 0); NZ HOME payoff $2,027,485; bond COI 2%.
- **Tax Credit Calc (4):** soft costs in basis 15% of rehab ×4.
- **Financing Assumptions (6):** NZ HOME accrued interest $551k (needs LHC statement); NZ HOME "repay at close" treatment (pursue LHC assumption instead); financing fees 1.5% ×4.
- **QAP_Rule_Register (3, hidden):** LA 2025 QAP basis banner; IRC minimum rehab $8,500 indexed placeholder; LA QAP minimum rehab (blank = PENDING).

## 4. OM-vs-DD variances (49 recorded on OM Actuals; DD governs per Sec. 9.2)

The most consequential:

1. **Spanish Arms note rate: 5.64% per the note vs OM's 4.01%** — no modification instrument in the data room; balance-sheet-implied ~5.21%. The OM's SA "assumable-rate arbitrage" is unsupported. Open item: servicer statement / any allonge. (SA balance also runs ~$999k below the 5.64% schedule — undocumented curtailment.)
2. **NZ HOME loan not disclosed as a payoff item:** $1,476,485 principal + ~$525k accrued (growing ~$3.7k/mo), 100% due on sale absent LHC consent (HOME Loan Agmt §1.8). Also the URA trigger. (The OM's "NZ 2.89% & 3.00%" second rate is this HOME loan.)
3. **Insurance premiums:** broker "in-place premiums" (CH $79.5k / NZ $79.9k / LOM $156.4k / SA $231.2k) are unsupported by any DD document; model uses documented 2026 budget premiums (CH $87.9k / NZ $88.3k / LOM $172.4k / SA $272.0k).
4. **Broker "2025 Actual Tax Bill" silently includes personal-property tax** (CH: $23,440 RE + $9,758 PPT = $33,198). Model uses combined RE+PPT with the split documented. NZ actual RE bills are unreadable scans — assessor-report estimates corroborated by the audit.
5. **LOM balance ~$551k below its note schedule** (implied endorsement curtailment, undocumented) — balance sheet treated as authoritative.
6. **CH compliance period ends 12/31/2026 per the LHC reg agreement** (OM says TCCP 2027) — CH resyndication could potentially accelerate; close date input kept at 1/1/2028 (conservative).
7. **SA unit SF per rent roll (656–903 SF) far below OM (795–1,075 SF)**; NRSF 166,876 vs OM 191,932. OM figures retained for NRSF display with the discrepancy documented (definitional ambiguity), flagged for survey/appraisal.
8. **SA non-HAP "current rents" in the OM used the rent roll's market-rent column** ($560 1BR) instead of actual in-place rents ($649–$769) — model uses actual in-place per rent roll.
9. NZ First Allonge (2017, 4.00% period) referenced but missing from the data room; SA legal description says 202 units vs 204; rent rolls at 4/15/26 predate the current HUD schedules (pre-OCAF rents in place); CH/NZ/LOM/SA occupancy per rent rolls: 96.4% / 98.0% / 92.4% / 90.7%.

Full list: OM Actuals tab, VARIANCE NOTES block (rows 144+).

## 5. Files that could not be opened

- `NZ - 2025 Caddo Parrish RE Taxes.pdf` and `NZ - 2025 City of Shreveport RE Taxes.pdf` — image scans with no text layer. NZ RE taxes taken from the assessor property report and corroborated against the audit ($36,503). Every other DD file (≈200) opened successfully, including image-only loan documents read via page rendering.

## 6. Build & validation notes

- Built in spec Sec. 9.3 order with a clean LibreOffice recalc gate after every sheet; Spanish Arms column populated and verified first on consolidated sheets.
- Sec. 9.5 checklist: all items verified by three independent validation agents — solver sum = portfolio price (exact); Sources = Uses in all four columns; all four pay-in blocks total 100% and tie to equity to the cent; each Pro Forma Yr-1 revenue = 12 × its Unit Mix post-rehab monthly total (≤$0.01); consolidation ties to the pro formas (max diff <$0.001) incl. bridge-year branches; S&U Timing quarterly roll-up ties to the four monthly blocks; rent stacks match the DD HUD schedules and OM tables for every sampled unit type; no forbidden functions; contamination sweep clean.
- One deliberate modeling disclosure: the equity pay-in tranches beyond M18 (LOM/SA stabilization tranches) fall outside the S&U Timing window by design — the roll-up ties to the in-window draws.
- Sensitivity table values are static (computed by the build's solver loop); re-run the solver loop after changing assumptions — the acquisition-price cells and sensitivity table do not self-update.

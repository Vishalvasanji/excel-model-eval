# What each number means

Every metric the screen reports, how it is computed, and which rule governs it.

## The headline answers

**Minimum soft funding needed.** Total development cost less DSCR-sized debt,
LIHTC equity and deferred developer fee. This is a property of the deal, not of
what has been awarded: committing more CDBG does not change what the deal needs,
it changes whether the need is covered. Reported alongside what is committed and
either the shortfall or the surplus.

Subsidy drawn during construction reduces the construction loan balance and
therefore capitalised interest, so the requirement is solved inside the model's
loop rather than subtracted at the end.

**Maximum supportable price.** The highest purchase price at which the funding
gap still fits the subsidy obtainable and no hard rule breaks. Acquisition cost
is excluded from eligible basis, so a dollar of price generates no additional
equity — roughly a dollar of extra price needs a dollar of extra subsidy, and
the price/subsidy table shows the exchange rate.

**Least subsidy the deal could need.** The gap at a $0 purchase price. Nothing
about the price can bring the requirement below this.

## Operations

**Stabilised NOI** — year 2 of the pro forma, the first full year after lease-up.
Net revenue after vacancy, less operating expenses.

**Property tax.** With no PILOT, the tax is millage applied to a value
capitalised from NOI — and NOI is net of that tax, so the two settle against
each other. The screen assumes no PILOT until one is confirmed. Where a deal
just misses, this is usually the first lever to test.

**Replacement reserves** — $500/unit/year for acquisition/rehab. Governed by
`UW-RESERVE-PUPA` and `UW-RESERVE-ADEQUACY` (QAP §IV.D.10).

## Debt

**DSCR** — NOI divided by debt service, for each of years 2 through 17.

Debt is sized to the largest loan that holds the floor in **every** year. Years
2 and 3 are interest-only and year 4 begins amortising, so the binding year is
year 4, not year 2. Sizing this way minimises subsidy: every dollar the property
can carry is a dollar it does not have to be given.

The band is 1.15 to 1.40 (`UW-DSCR-Y1`, QAP §IV.D.6), and the two ends mean
opposite things:

- **Below 1.15** — the property cannot carry this much debt. Reduce the loan,
  which increases the subsidy needed.
- **Above 1.40** — the property is under-levered and absorbing more subsidy than
  it needs. A structuring problem, not a dead deal.

NOI grows faster than level debt service, so DSCR rises across the term and the
ceiling is usually what binds in the later years.

**Loan caps.** Debt is also held to 90% of cost and 90% of capitalised value.
DSCR sizing alone is unbounded above, and a lightly rehabbed property with
strong NOI would otherwise size to a loan larger than the project. When a cap
binds, DSCR sits well above the band and the deal reads as under-levered — it
is not that it should borrow more, it is that no lender would advance more.

## Credits and equity

**Qualified basis** — total development cost less acquisition, community
facilities, federal grants, HOME loans, reserves and financing fees, plus any
building basis, times the applicable fraction and any basis boost.

**Annual credit** — qualified basis times the credit rate (4% for bond deals).

**LIHTC equity** — ten years of credits net of the GP's share, at the equity
price.

The allocation is the lesser of what the basis generates and what the equity gap
supports (`ELG-CREDIT-MAX`, QAP §II.B / §IV.D). A cheap enough acquisition
generates more credit than the deal can absorb, and the agency sizes the
allocation down rather than over-funding it. The screen reports both the
allocated credit and what the basis alone would have supported, so a cut is
visible rather than silent. Soft money is not netted off before this test:
equity is the cheaper capital, so a deal takes every credit its basis supports
and reduces the subsidy it asks for.

**Basis boost** — 30% in a QCT or DDA. Confirm with `qct-dda-lookup` before
claiming it; `ELG-BOOST-ELIGIBILITY` flags a boost claimed without a qualifying
geography.

## Cost tests

**TDC per unit** vs the HUD unit TDC limit for the bedroom mix and building
type (`QAP-TDC-PERUNIT`, `UW-HUD-TDC`). Building type matters: elevator and
walk-up carry different limits.

**Fee limits** — developer fee (uncapped on 4% bond deals), architect at 7% of
the construction contract, builder profit at 6%, overhead at 2%, general
requirements at 6%, contingency at 10%.

## Verdict

- **PENCILS** — no hard fails, no warnings, nothing pending.
- **MARGINAL** — no hard fails, but warnings or pending items.
- **FAIL** — at least one hard fail.

A hard fail is a failing rule of severity `error` that the model can actually
test. Rules scoped `APP-SIDE` need application-form data the model does not
hold; rules scoped `EXCLUDED` are already enforced structurally. Both are
reported and neither counts toward the verdict.

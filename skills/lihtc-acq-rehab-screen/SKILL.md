---
name: lihtc-acq-rehab-screen
description: Screens a LIHTC 4%-bond acquisition/rehab deal from an offering memorandum or a handful of deal facts, and returns a go/no-go dashboard - the minimum soft funding the deal needs, the maximum supportable purchase price, sources and uses, DSCR, and every QAP rule that fails with its citation. Use whenever someone uploads an OM, flyer or broker package for an apartment acquisition/rehab, or gives deal facts and asks whether it works, what it pencils at, what they can pay, how much CDBG or soft money it needs, or asks to "screen", "run", or "underwrite" a deal. Also use for follow-ups on a screened deal - sensitivity to rehab cost, equity pricing, interest rate, or a PILOT.
---

# LIHTC acquisition/rehab screen

Replaces working a deal through the Excel model by hand. Pull the facts out of
the memo, run them through the screening connector, and hand back the dashboard.

## What the screen answers

1. **What is the minimum soft funding this deal needs?** The gap left after
   DSCR-sized debt, LIHTC equity and deferred developer fee. This is the
   headline number.
2. **What is the most we can pay?** The price at which that gap still fits the
   subsidy obtainable, plus the price supported at each level of subsidy.
3. **What breaks it?** Every failing QAP rule, with the citation.

## How to run one

### 1. Extract the deal

Read `reference/om_extraction.md` for what to pull and where it usually hides.
The fields that most move the answer, in order:

- **unit mix** — bedrooms, count, square feet, AMI band per type
- **county or parish** — which HUD area the property sits in
- **asking price**
- **rehab scope** — hard cost per unit
- **equity pricing** and **interest rates**

### 2. Look up the rent limits and utility allowances

**Do this for every deal.** Read `reference/sourcing_limits.md`, then find:

- the **HUD MTSP gross rent limits** for the property's county and the current
  year, for every AMI band the unit mix uses
- the **local housing authority's utility allowance schedule**, for the
  tenant-paid utilities only

Pass both to `screen_deal` as `rent_limits` and `utility_allowances`, each with
its source. These set net rent, which sets NOI, which sizes the debt, which
decides the subsidy the deal needs — a limit from the wrong county or the wrong
year is wrong all the way through.

The connector refuses to screen without rent limits, and rejects tables that are
annual, out of order, or implausible. If you cannot find them, say so and ask —
do not estimate them or carry them over from another deal.

### 3. Ask only what you cannot default

Call `get_defaults` first and show what the screen would assume. Then ask only
about facts that materially move the answer and cannot be defaulted — normally
just **rehab scope per unit**, **tax credit pricing**, and **interest rates**.
Ask them together, in one message, with your own recommendation for each.

Never invent a unit mix, a rent limit, or a utility allowance. Everything else
has a defensible default, and the screen reports every default it applied.

### 4. Screen it

Call `screen_deal` with everything you have. Then:

- Lead with the verdict and the minimum soft funding, in one sentence.
- Show the dashboard the connector returns.
- State what it was priced against — the `priced_against` field names the rent
  limit and utility allowance sources actually used.
- Surface every warning it returns. A guessed unit mix, or gross limits treated
  as net because no allowances were supplied, changes the answer materially.

### 5. Follow up

Use `sensitivity` when the deal is close, on whatever is least certain — usually
`rehab_per_unit`, then `equity_price`, then `perm_coupon`. Use `solve_max_price`
when the question is what to bid.

## Reading the result

- **PENCILS** — clears every rule.
- **MARGINAL** — clears the hard rules, with warnings worth reading.
- **FAIL** — a hard rule breaks. Say which one and what would have to change.

**DSCR fails in two opposite directions.** Below the floor the property cannot
carry its debt. Above the QAP ceiling it is under-levered — taking more subsidy
than it needs, which is a fixable structuring problem, not a dead deal. The
message says which.

**A PILOT is the lever to test first** on a deal that just misses. The screen
assumes none; property taxes are often the single largest swing item.

## What this screen does not do

- It does not verify rents against the market. Use the `lihtc-rent-screen`
  skill for whether the underwritten rents are actually achievable.
- It does not check QCT/DDA. Use `qct-dda-lookup` for basis-boost eligibility,
  then pass `basis_boost: 0.30` and `boost_eligible: "Yes"`.
- It does not replace a CNA. Rehab scope is the largest single assumption in the
  screen and the first thing real diligence should replace.

Say so when the answer turns on any of these.

## If the connector is unavailable

The same engine runs locally from the repository:

```bash
python -m lihtc_screen screen deal.json
```

Tell the user the connector is unreachable rather than estimating by hand — a
LIHTC capital stack is not something to approximate in prose.

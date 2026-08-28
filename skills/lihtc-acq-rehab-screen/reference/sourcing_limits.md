# Sourcing rent limits and utility allowances

Every screen is priced against two tables that are specific to the property's
location and change every year. Look both up for the deal in front of you and
pass them to `screen_deal`. Do not reuse a table from a previous deal unless it
is the same HUD area and the same year.

These two numbers set everything downstream — gross rent less the utility
allowance is net rent, net rent sets NOI, NOI sizes the debt, and the debt
decides how much subsidy the deal needs. A limit that is off by one bedroom
column or one year produces a screen that is confidently wrong throughout.

## 1. HUD MTSP gross rent limits

**What to search for:** `HUD MTSP income limits <year> <county> <state>`, or go
to `huduser.gov/portal/datasets/mtsp.html` and use the query tool.

**Which table.** Multifamily Tax Subsidy Project (MTSP) limits, *not* Section 8
income limits and *not* Fair Market Rents. MTSP is the LIHTC table.

**Which geography.** The HUD area containing the property's **county or parish**,
which is often a metro area named for a different city. Orleans Parish sits in
"New Orleans-Metairie, LA HUD Metro FMR Area". Get the county right and let HUD
name the area.

**Which year.** The current fiscal year's limits, published each spring. Note
the year in the source string.

**Gross rent, not income.** HUD publishes income limits by household size and
rent limits by bedroom count. You want the **rent** limits. If only income
limits are available, the rent limit is 30% of the income limit for the
imputed household size (1.5 persons per bedroom), divided by 12 — say that you
derived it rather than reading it.

**Bands.** Pull every band the unit mix uses — commonly 50% and 60%, sometimes
20%–80% for income-averaging deals.

Pass as monthly dollars for 0, 1, 2, 3 and 4 bedrooms:

```json
"rent_limits": {
  "0.50": [786, 831, 997, 1151, 1302],
  "0.60": [943, 997, 1197, 1382, 1563]
},
"rent_limits_source": "HUD FY2025 MTSP Income Limits, Orleans Parish LA"
```

## 2. Utility allowances

**What to search for:** `<city or parish> housing authority utility allowance
schedule <year>`.

**Who publishes it.** The local public housing authority — HANO in New Orleans,
and the parish or city authority elsewhere. Some deals use a utility company
estimate or an energy consumption model instead; if the memo names a method,
follow it and say which you used.

**Which column.** Match the building and fuel type — apartment vs. townhouse,
all-electric vs. gas. All-electric garden apartments are the common case for
Louisiana acquisition/rehab.

**Only tenant-paid utilities count.** An allowance is subtracted from the gross
rent limit because the tenant pays that bill directly. If the property pays
water and sewer from the operating budget, those lines are **zero** in the
allowance — they are already in operating expenses, and counting them twice
understates net rent and overstates the subsidy needed. The rent roll or the
memo's utility section says who pays what.

Pass as monthly dollars per bedroom count:

```json
"utility_allowances": {
  "electricity": [57, 67, 89, 111, 134],
  "water": [0, 0, 0, 0, 0],
  "sewer": [0, 0, 0, 0, 0],
  "trash": [0, 0, 0, 0, 0]
},
"utility_allowances_source": "HANO Utility Allowance Schedule eff. 09/01/2025"
```

Recognised utilities are `electricity`, `water`, `sewer`, `trash`, `gas` and
`other`. Fold anything else into `other` — an unrecognised name is rejected
rather than dropped, because a dropped line silently overstates net rent.

## Sanity checks before passing them

The connector validates shape, ordering and magnitude, and refuses anything that
fails. Check these yourself first, because a table can pass validation and still
be the wrong one:

- **Monthly, not annual.** A 2BR at 60% AMI is typically $700–$1,800/month.
  Four figures in the thousands means an annual table.
- **The right county.** Confirm the HUD area actually contains the property.
- **The right year.** Limits move every year.
- **Rents rise with bedrooms**, and a higher AMI band never pays less.
- **Net rent is sensible.** Gross less allowances should leave a rent a tenant
  would plausibly pay. If the allowance is most of the limit, the two tables are
  probably from different markets or vintages.

## If you cannot find them

Say so and stop. Do not estimate, interpolate from a nearby county, or carry a
figure over from another deal. Ask for the limits, or for a market study or a
LIHTC rent schedule from the memo's data room.

A screen refuses to run without rent limits for exactly this reason. Missing
utility allowances are allowed but warn loudly, because treating gross limits as
net overstates revenue and understates the subsidy the deal needs.

## Bundled markets

`list_markets` returns markets whose tables ship with the connector, with the
source of each. Those are a convenience for repeat markets, not a substitute for
checking the current year — pass `market` to use them, and pass `rent_limits` to
override them.

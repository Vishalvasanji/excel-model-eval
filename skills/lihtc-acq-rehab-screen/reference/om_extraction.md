# Pulling a deal out of an offering memorandum

What to extract, where it hides, and what to do when it is missing.

## Fields that decide the answer

### Unit mix — always extract, never guess

Bedrooms, bathrooms, square feet, unit count, and AMI band for each unit type.
Usually a table headed "Unit Mix", "Rent Roll Summary" or "Property Summary".

Rents scale directly off bedroom count and AMI band, and every downstream number
scales off rents. A guessed mix produces a confident but wrong answer, so the
screen flags it loudly. If the memo has no mix, ask for one before running.

**AMI band.** Existing LIHTC properties state restrictions ("60% AMI", "@60%").
If a property is unrestricted and being resyndicated, the screen prices at 60%
unless told otherwise — say so.

### Market — sets rent limits and utility allowances

City and parish/county. The screen needs a market whose HUD MTSP limits and
local utility allowance schedule are bundled; `list_markets` says which are.
Outside those, say so plainly rather than screening on a neighbouring market's
numbers.

### Asking price

"Offering Price", "Asking Price", "Purchase Price", or a guidance range. Take
the midpoint of a range and say that you did. "Unpriced" or "submit offers" is
common — screen at $0 to get the least subsidy the deal could possibly need,
and use `solve_max_price` for what to bid.

### Rehab scope

Rarely stated. Look for a scope of work, capital needs summary, or "recent
capital improvements" (which reduces scope). Absent that, ask — this is the
single largest assumption in the screen. Bands worth offering:

| Scope | $/unit | What it buys |
|---|---|---|
| Light | $25,000 | Paint, flooring, appliances, minor systems |
| Moderate | $40,000–60,000 | Full interiors, some roofs and HVAC |
| Gut | $80,000+ | Interiors, systems, envelope, site |

### Existing debt and restrictions

Loan balances, rates, maturity, assumability, and any HAP contract, LURA or
existing LIHTC compliance period. A HOME loan is often due on sale and can be
a payoff item the memo does not present as one.

## Fields with defensible defaults

The screen fills these and reports each with its basis. Override only when the
memo states something.

| Field | Default |
|---|---|
| Staffing | Scales with unit count |
| Insurance | $1,500/unit coastal Louisiana, $1,000/unit inland |
| Pest control | $20/unit/year |
| Pool service | $500/month when there is a pool |
| Elevator service | $250/month per set |
| Property taxes | No PILOT assumed |
| Replacement reserves | $500/unit/year |
| Lease-up | Full occupancy by month 12 |
| A&E | 2.5% of hard cost |
| Builder's risk | 1% of hard cost |
| Vacancy | 7% |

## Facts worth asking for

Ask these together, once, with a recommendation for each:

- **Rehab scope per unit** — the biggest swing in the screen
- **Tax credit pricing** — cents per credit dollar
- **Interest rates** — construction and permanent
- **Soft funding** — anything committed, and what is realistically obtainable

## Amenities that change the budget

Note whether the property has a pool, elevators (how many sets), a clubhouse,
sports courts, or a playground. Each is a construction line item and an
operating cost. Elevators also change the building type, which changes the HUD
TDC limit the deal is tested against.

## Reading a memo sceptically

A memo is a marketing document. Where it matters:

- **Broker rents** may be asking rents, market rents, or a proforma, not what is
  being collected. Prefer the rent roll.
- **"In-place" expenses** are often below what an audit shows, especially
  insurance and taxes.
- **Taxes** shown may exclude personal property tax, or assume a PILOT that has
  not been granted.
- **Square footage** in the memo often differs from the rent roll.

Note any of these you notice. They are diligence items, not reasons to stall the
screen — run it, and say what you would want confirmed.

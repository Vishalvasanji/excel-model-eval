# LIHTC acquisition/rehab screening connector

Screens a LIHTC 4%-bond acquisition/rehab deal from an offering memorandum and
answers the two questions that decide go/no-go:

1. **What is the minimum soft funding this deal needs?**
2. **What is the most we can pay for it?**

Replaces working each memo through `reference/Acq_Rehab_Model_v1.xlsx` by hand.
A screen takes well under a second against roughly 1.4 seconds for a single
workbook recalculation, and needs neither Excel nor the workbook to run.

## Layout

| | |
|---|---|
| `lihtc_screen/` | The engine. One module per workbook tab, each carrying the cell references it was ported from. |
| `lihtc_screen/refdata/` | Market rent limits, utility allowances, HUD TDC limits, and the QAP rule register. |
| `mcp_server/` | The remote MCP connector, deployed to Vercel. |
| `skills/lihtc-acq-rehab-screen/` | The Claude skill that reads a memo and calls the connector. |
| `tools/` | Baseline extraction, the LibreOffice validation oracle, and the HUD limits loader. |
| `tests/` | Workbook parity, scorecard, screen mode, reference data, connector, CLI. |
| `reference/` | The source workbook and the underwriting workflow it was built from. |

## Use it

**From Claude** — deploy the connector (`mcp_server/README.md`), add it under
Settings → Connectors, and upload a memo. The skill does the rest.

**From the command line**

```bash
python -m lihtc_screen screen deal.json
python -m lihtc_screen screen deal.json --json
python -m lihtc_screen markets
```

A deal file holds whatever the memo states; anything omitted is defaulted from
the underwriting workflow and reported back as an assumption. A unit mix is
required — rents scale off it and so does every number downstream.

```json
{
  "project_name": "Westbend",
  "market": "New Orleans", "state": "LA", "city": "New Orleans",
  "asking_price": 4000000,
  "committed_soft_money": 7500000,
  "unit_mix": [
    {"bedrooms": 1, "bathrooms": 1, "sqft": 900, "count": 110, "ami_pct": 0.6},
    {"bedrooms": 2, "bathrooms": 2, "sqft": 1100, "count": 170, "ami_pct": 0.6}
  ]
}
```

## How it is validated

The workbook is the specification, and the engine is held to it two ways.

**Against the values Excel saved.** `tests/test_westbend_parity.py` reproduces
every cached cell in the workbook — 67 headline values and 136 pro forma cells,
spanning every tab — to the cent. Needs nothing installed.

**Against the workbook itself.** `tests/test_oracle_parity.py` drives the real
workbook through LibreOffice under perturbed inputs — unit count, purchase
price, equity pricing, coupon, rehab cost, vacancy, CDBG — and checks the engine
tracks it. This is what shows the model was ported rather than one saved deal
reproduced. Skipped when LibreOffice is unavailable:

```bash
apt-get update && apt-get install -y libreoffice-calc python3-uno
python -m pytest tests/ -q
```

## Two modes

**`workbook`** reproduces the file exactly: the bond is the balancing plug and
soft money is a fixed input. Used by the parity tests, and available for
auditing a deal against the spreadsheet.

**`screen`** is the underwriting workflow: the bond is sized on DSCR and soft
money becomes the residual — how much subsidy the deal actually needs.

Four workbook behaviours are reproduced in workbook mode and corrected in screen
mode, each noted where it occurs in the code:

- `NOI Calc!J24` reads the PILOT payment rather than the tax after the PILOT
  toggle, so the pro forma always runs at the PILOT amount.
- The sizing-NOI correction on `Financing Assumptions!C25` adds the un-PILOTed
  tax difference where it should subtract it.
- `Sources & Uses!I34:I37` omit `Construction Estimates!G9`, so elevator shafts
  never reach the budget.
- `Financing Assumptions!D19` charges bridge origination on the construction
  legal fee rather than on the bridge loan.

Two constraints are added that the workbook does not have. Permanent debt is
capped at 90% of cost and 90% of capitalised value: DSCR sizing alone is
unbounded above, and a low-cost, high-NOI property otherwise sizes to a loan
larger than the project itself. And the LIHTC allocation is cut to what the
equity gap supports, which is what a state agency does when a cheap enough
acquisition generates more credit than the deal can absorb. Both are
overridable per deal.

Debt sizing also differs deliberately. `Financing Assumptions!C36` sizes on
year-2 NOI, which cannot hold the QAP's DSCR band: years 2 and 3 are
interest-only so the binding year is year 4, and NOI grows faster than level
debt service so DSCR rises toward the ceiling over the term. Screen mode sizes
to the largest loan that holds the floor in every year, which both clears the
band and minimises the subsidy the deal has to ask for.

## Reference data

Rent limits, utility allowances and TDC limits are market-specific and come from
an issuing authority. A market is either bundled with sourced tables or it is
not available — nothing is substituted from a neighbouring market, because doing
so would misprice a deal without saying so.

**New Orleans is the only market currently bundled.** Adding another needs its
HUD MTSP rent limits (`tools/load_hud_limits.py`, with a free HUD API token) and
its local housing authority's utility allowance schedule, which is not
machine-readable anywhere and has to be entered with its source and effective
date. A deal outside the bundled markets can still be screened by supplying its
own tables, and the screen says loudly when it is doing that.

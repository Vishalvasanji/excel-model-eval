"""Cross-check the engine against LibreOffice recalculating the real workbook.

The cached-value tests prove the port on the single deal the workbook was saved
with. These drive the workbook itself across perturbed inputs, which is what
distinguishes a ported model from a reproduced answer.

Skipped when LibreOffice Calc / python3-uno are not installed:
    apt-get update && apt-get install -y libreoffice-calc python3-uno
"""

from __future__ import annotations

import pytest

from lihtc_screen.inputs import DealInputs
from lihtc_screen.model import solve
from tools.lo_oracle.oracle import Oracle, available

pytestmark = pytest.mark.skipif(
    not available(), reason="LibreOffice Calc / python3-uno not installed")

ABS_TOLERANCE = 1.0        # dollars; the workbook's loop converges to ~$0.01
REL_TOLERANCE = 1e-7

# (label, cells to set in the workbook, matching DealInputs overrides)
SCENARIOS = [
    ("baseline", {}, {}),
    ("smaller-1br", {("Unit Mix+Rents", "D8"): 100},
     {"unit_mix_1br": 100}),
    ("price-8m", {("Sources & Uses", "I30"): 8_000_000},
     {"acquisition_cost": 8_000_000}),
    ("equity-0.90", {("Tax Credit Calc", "F4"): 0.90},
     {"equity_price": 0.90}),
    ("coupon-7pct", {("Financing Assumptions", "C28"): 0.07},
     {"perm_coupon": 0.07}),
    ("rehab-130k", {("Construction Estimates", "E7"): 130_000},
     {"construction_units_cost": 130_000}),
    ("vacancy-10pct", {("NOI Calc", "D11"): 0.10},
     {"vacancy_rate": 0.10}),
    ("cdbg-3m", {("Sources & Uses", "I16"): 3_000_000},
     {"cdbg": 3_000_000}),
]

CHECKS = [
    ("Sources & Uses", "I78", "total uses", lambda r: r.sources_uses.total_uses),
    ("Sources & Uses", "I43", "hard costs", lambda r: r.sources_uses.hard_costs),
    ("Sources & Uses", "I65", "developer fee", lambda r: r.sources_uses.developer_fee),
    ("Sources & Uses", "I72", "reserves", lambda r: r.sources_uses.reserves),
    ("Sources & Uses", "I74", "capitalised interest", lambda r: r.sources_uses.capitalised_interest),
    ("Sources & Uses", "I76", "financing fees", lambda r: r.sources_uses.financing_fees),
    ("Sources & Uses", "I12", "bonds", lambda r: r.sources_uses.bonds),
    ("Sources & Uses", "I14", "equity", lambda r: r.sources_uses.tax_credit_equity),
    ("NOI Calc", "J29", "NOI", lambda r: r.noi.noi),
    ("Tax Credit Calc", "F22", "annual credit", lambda r: r.tax_credit.annual_credit),
    ("Dashboard Calc", "B18", "min DSCR", lambda r: r.min_dscr),
]


def _apply(deal: DealInputs, overrides: dict) -> DealInputs:
    """Translate a scenario's overrides onto the dataclass."""
    for key, value in overrides.items():
        if key == "unit_mix_1br":
            for unit in deal.unit_mix:
                if unit.bedrooms == 1 and unit.count:
                    unit.count = value
        elif key == "construction_units_cost":
            for line in deal.construction:
                if line.key == "units":
                    line.unit_cost = value
        else:
            setattr(deal, key, value)
    return deal


@pytest.fixture(scope="module")
def oracle():
    with Oracle() as o:
        yield o


@pytest.mark.parametrize("label,cells,overrides", SCENARIOS,
                         ids=[s[0] for s in SCENARIOS])
def test_matches_workbook_under_perturbation(oracle, label, cells, overrides):
    workbook = oracle.recalc(cells, [(s, c) for s, c, _, _ in CHECKS])
    engine = solve(_apply(DealInputs(mode="workbook"), overrides))

    failures = []
    for sheet, cell, name, accessor in CHECKS:
        expected = workbook[(sheet, cell)]
        actual = accessor(engine)
        if abs(actual - expected) > max(ABS_TOLERANCE, abs(expected) * REL_TOLERANCE):
            failures.append(
                f"  {name} ({sheet}!{cell}): workbook {expected:,.2f}, "
                f"engine {actual:,.2f}, diff {actual - expected:,.2f}")
    assert not failures, f"scenario {label!r} diverged:\n" + "\n".join(failures)

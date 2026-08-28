"""Screen mode: workflow defaults, DSCR sizing, and the two solvers."""

from __future__ import annotations

import copy

import pytest

from lihtc_screen import defaults
from lihtc_screen.inputs import DealInputs
from lihtc_screen.model import solve
from lihtc_screen.scorecard import evaluate
from lihtc_screen.solver import max_supportable_price, screen, sensitivity


def westbend() -> DealInputs:
    deal = DealInputs(mode="screen", cdbg=0, lhc_home=0)
    defaults.apply(deal, state="LA", city="New Orleans")
    return deal


# -- defaults from the underwriting workflow ------------------------------

@pytest.mark.parametrize("units,leasing,maintenance", [
    (48, 1, 1), (99, 1, 1), (100, 1, 2), (199, 1, 2), (200, 2, 2), (280, 2, 2),
])
def test_staffing_scales_with_unit_count(units, leasing, maintenance):
    staff = {p.title: p.count for p in defaults.staffing(units)}
    assert staff["Property Manager"] == 1
    assert staff["Leasing Agent"] == leasing
    assert staff["Maintenance Staff"] == maintenance


@pytest.mark.parametrize("state,parish,city,expected", [
    ("LA", None, "New Orleans", defaults.INSURANCE_COASTAL_LA),
    ("LA", "Orleans", None, defaults.INSURANCE_COASTAL_LA),
    ("LA", "Caddo", "Shreveport", defaults.INSURANCE_INLAND),
    ("TX", None, "Houston", defaults.INSURANCE_INLAND),
])
def test_insurance_rate_follows_coastal_rule(state, parish, city, expected):
    deal = DealInputs(mode="screen")
    defaults.apply(deal, state=state, parish=parish, city=city)
    assert deal.insurance_per_unit == expected


def test_no_pilot_is_assumed_by_default():
    deal = DealInputs(mode="screen")
    defaults.apply(deal)
    assert deal.pilot_in_place == "No"


def test_lease_up_reaches_full_occupancy_by_month_12():
    schedule = defaults.leaseup_schedule(280)
    assert sum(schedule) == pytest.approx(280)
    assert all(s == 0 for s in schedule[defaults.LEASEUP_TARGET_MONTH:])


def test_defaults_record_their_reasoning():
    deal = DealInputs(mode="screen")
    applied = defaults.apply(deal, state="LA", city="New Orleans")
    assert applied.assumptions
    for assumption in applied.assumptions:
        assert assumption.basis, f"{assumption.field} has no stated basis"


def test_explicitly_provided_values_are_not_overwritten():
    deal = DealInputs(mode="screen", insurance_per_unit=2_400, pilot_in_place="Yes")
    defaults.apply(deal, state="LA", city="New Orleans",
                   provided={"insurance_per_unit", "pilot_in_place"})
    assert deal.insurance_per_unit == 2_400
    assert deal.pilot_in_place == "Yes"


# -- DSCR sizing -----------------------------------------------------------

def test_debt_is_sized_to_the_dscr_floor():
    result = solve(westbend())
    assert result.min_dscr >= result.deal.sizing_dscr - 1e-6
    # Sized to the floor, not comfortably above it: any material headroom is
    # debt the property could carry and subsidy it should not be asking for.
    assert result.min_dscr < result.deal.sizing_dscr + 0.01


def test_dscr_sizing_clears_the_band_the_workbook_fails():
    """The workbook's year-2 sizing breaches the QAP ceiling; this should not."""
    card = evaluate(solve(westbend()))
    dscr = next(c for c in card.checks if c.kpi_id == "UW-DSCR-Y1")
    assert dscr.status == "PASS", dscr.message


def test_more_debt_would_break_the_floor():
    """Confirms the sizing is maximal, not merely feasible."""
    result = solve(westbend())
    from lihtc_screen.engine import leaseup, loans, proforma
    bigger = result.sources_uses.bonds * 1.02
    lu = leaseup.compute(result.deal, result.mix, result.noi, result.expenses, bigger)
    pf = proforma.compute(result.deal, lu, result.noi, loans.compute(result.deal, bigger))
    assert min(pf.dscr_years_2_17()) < result.deal.sizing_dscr


# -- minimum soft funding ---------------------------------------------------

def test_sources_balance_at_the_solved_soft_money():
    result = solve(westbend())
    funded = (result.sources_uses.bonds + result.sources_uses.tax_credit_equity
              + result.sources_uses.deferred_fees + result.required_soft_money)
    assert funded == pytest.approx(result.total_development_cost, abs=1.0)


def test_soft_money_requirement_rises_with_price():
    low = solve(westbend())
    high_deal = westbend()
    high_deal.acquisition_cost += 2_000_000
    high = solve(high_deal)
    assert high.required_soft_money > low.required_soft_money


def test_committed_soft_money_is_credited_against_the_requirement():
    deal = westbend()
    baseline = solve(deal).required_soft_money
    deal.cdbg = 40_000_000
    result = solve(deal)
    # The requirement is a property of the deal, not of what is committed.
    assert result.required_soft_money == pytest.approx(baseline, rel=1e-6)
    assert result.committed_soft_money == 40_000_000
    assert result.additional_soft_money_needed == 0
    assert result.soft_money_surplus == pytest.approx(40_000_000 - baseline, rel=1e-6)


def test_shortfall_is_reported_when_commitment_falls_short():
    deal = westbend()
    deal.cdbg = 1_000_000
    result = solve(deal)
    assert result.additional_soft_money_needed == pytest.approx(
        result.required_soft_money - 1_000_000, rel=1e-6)
    assert result.soft_money_surplus == 0


# -- maximum supportable price ----------------------------------------------

def test_max_price_is_the_true_boundary():
    deal = westbend()
    deal.soft_money_available = solve(deal).required_soft_money
    price = max_supportable_price(deal)
    assert price is not None

    from lihtc_screen.solver import PRICE_TOLERANCE
    at_price = copy.deepcopy(deal)
    at_price.acquisition_cost = price
    assert solve(at_price).required_soft_money <= deal.soft_money_available + PRICE_TOLERANCE

    above = copy.deepcopy(deal)
    above.acquisition_cost = price + 10 * PRICE_TOLERANCE
    assert solve(above).required_soft_money > deal.soft_money_available + PRICE_TOLERANCE


def test_max_price_rises_with_available_subsidy():
    s = screen(westbend())
    prices = [row["max_price"] for row in s.price_by_soft_money
              if row["max_price"] is not None]
    assert prices == sorted(prices)
    assert len(prices) >= 2


def test_screen_explains_itself_when_no_price_works():
    deal = westbend()
    deal.soft_money_available = 0
    s = screen(deal)
    assert s.max_supportable_price is None
    assert s.notes, "a deal that cannot work at any price must say why"
    assert s.soft_money_at_zero_price > 0


# -- sensitivity ------------------------------------------------------------

def test_sensitivity_tracks_rehab_cost():
    rows = sensitivity(westbend(), "rehab_per_unit", [60_000, 100_000, 140_000])
    costs = [r["total_development_cost"] for r in rows]
    gaps = [r["required_soft_money"] for r in rows]
    assert costs == sorted(costs)
    assert gaps == sorted(gaps)


def test_sensitivity_tracks_equity_price():
    rows = sensitivity(westbend(), "equity_price", [0.75, 0.85, 0.95])
    gaps = [r["required_soft_money"] for r in rows]
    assert gaps == sorted(gaps, reverse=True), "richer equity should shrink the gap"


# -- credit sizing ----------------------------------------------------------

def _lightly_rehabbed() -> DealInputs:
    """A cheap deal whose basis generates more credit than its gap can absorb."""
    deal = westbend()
    deal.acquisition_cost = 0
    deal.building_basis_addition = 0
    for line in deal.construction:
        line.unit_cost = 60_000 if line.key == "units" else 0.0
    return deal


def test_credit_is_cut_to_the_gap_when_basis_over_generates():
    result = solve(_lightly_rehabbed())
    tc = result.tax_credit
    assert tc.limited_by_gap
    assert tc.annual_credit < tc.basis_annual_credit
    # Cutting the allocation must not leave the stack unbalanced.
    assert abs(result.sources_uses.balance) < 1.0


def test_an_over_credited_deal_is_not_failed_for_it():
    """Sizing the allocation down is a structuring outcome, not a no-go."""
    card = evaluate(solve(_lightly_rehabbed()))
    credit_max = next(c for c in card.checks if c.kpi_id == "ELG-CREDIT-MAX")
    assert credit_max.status == "PASS", credit_max.message


def test_credit_is_uncut_when_the_gap_is_wide():
    result = solve(westbend())
    tc = result.tax_credit
    assert not tc.limited_by_gap
    assert tc.annual_credit == pytest.approx(tc.basis_annual_credit)


def test_equity_never_exceeds_what_the_deal_needs():
    for price in (0, 1_000_000, 4_000_000, 10_000_000):
        deal = westbend()
        deal.acquisition_cost = price
        r = solve(deal)
        su = r.sources_uses
        room = su.total_uses - su.bonds - su.deferred_fees
        assert su.tax_credit_equity <= room + 1.0, f"over-equitied at ${price:,.0f}"


# -- loan caps --------------------------------------------------------------

def test_debt_never_exceeds_loan_to_cost():
    """DSCR sizing alone is unbounded; a lender's advance is not."""
    for rehab in (20_000, 40_000, 60_000, 100_000):
        deal = westbend()
        deal.acquisition_cost = 0
        for line in deal.construction:
            line.unit_cost = rehab if line.key == "units" else 0.0
        r = solve(deal)
        assert r.sources_uses.bonds <= deal.max_loan_to_cost * r.total_development_cost + 1.0, (
            f"loan exceeds {deal.max_loan_to_cost:.0%} of cost at ${rehab:,}/unit rehab")


def test_loan_to_value_binds_on_a_low_cost_deal():
    deal = westbend()
    deal.acquisition_cost = 0
    for line in deal.construction:
        line.unit_cost = 20_000 if line.key == "units" else 0.0
    r = solve(deal)
    value = r.noi.noi / deal.valuation_cap_rate
    assert r.sources_uses.bonds <= deal.max_loan_to_value * value + 1.0


def test_caps_can_be_lifted():
    deal = westbend()
    deal.max_loan_to_cost = 0
    deal.max_loan_to_value = 0
    capped = solve(westbend()).sources_uses.bonds
    assert solve(deal).sources_uses.bonds >= capped

"""Rent limits and utility allowances supplied per deal must be checked hard.

These tables arrive from outside the model, looked up at screening time. They
are the one input that can look entirely plausible and be wrong, and a wrong
rent limit is wrong all the way down: rents set NOI, NOI sets the debt, the debt
sets the subsidy requirement.
"""

from __future__ import annotations

import pytest

from lihtc_screen.inputs import DealInputs
from lihtc_screen.refdata.validate import (ReferenceDataError, apply_to_deal,
                                           check_net_rents_positive,
                                           validate_rent_limits,
                                           validate_utility_allowances)

GOOD_RENTS = {
    "0.50": [786, 831, 997, 1151, 1302],
    "0.60": [943, 997, 1197, 1382, 1563],
}
GOOD_UA = {"electricity": [57, 67, 89, 111, 134]}
RENT_SOURCE = "HUD FY2025 MTSP Income Limits, Orleans Parish LA"
UA_SOURCE = "HANO Utility Allowance Schedule eff. 09/01/2025"


# -- rent limits ------------------------------------------------------------

def test_accepts_a_well_formed_table():
    table = validate_rent_limits(GOOD_RENTS, source=RENT_SOURCE)
    assert table[0.60] == [943, 997, 1197, 1382, 1563]


def test_accepts_percentage_bands():
    table = validate_rent_limits({"60": [943, 997, 1197, 1382, 1563]},
                                 source=RENT_SOURCE)
    assert 0.60 in table


def test_requires_a_source():
    with pytest.raises(ReferenceDataError, match="requires a `source`"):
        validate_rent_limits(GOOD_RENTS)


def test_rejects_annual_rents():
    """The most likely real mistake: an annual figure passed as monthly."""
    annual = {"0.60": [11316, 11964, 14364, 16584, 18756]}
    with pytest.raises(ReferenceDataError, match="monthly, not annual"):
        validate_rent_limits(annual, source=RENT_SOURCE)


def test_rejects_rents_that_fall_with_bedroom_count():
    with pytest.raises(ReferenceDataError, match="rise with bedroom"):
        validate_rent_limits({"0.60": [1563, 1382, 1197, 997, 943]},
                             source=RENT_SOURCE)


def test_rejects_a_higher_band_paying_less():
    bad = {"0.50": [900, 950, 1150, 1300, 1500], "0.60": [800, 850, 1050, 1200, 1400]}
    with pytest.raises(ReferenceDataError, match="mislabelled"):
        validate_rent_limits(bad, source=RENT_SOURCE)


@pytest.mark.parametrize("row", [
    [943, 997, 1197],                    # too few columns
    [943, 997, 1197, 1382, 1563, 1800],  # too many
])
def test_rejects_wrong_column_count(row):
    with pytest.raises(ReferenceDataError, match="0-4 bedrooms"):
        validate_rent_limits({"0.60": row}, source=RENT_SOURCE)


def test_rejects_a_nonsense_ami_band():
    with pytest.raises(ReferenceDataError, match="outside"):
        validate_rent_limits({"5.0": [943, 997, 1197, 1382, 1563]},
                             source=RENT_SOURCE)


def test_rejects_non_numeric_values():
    with pytest.raises(ReferenceDataError, match="not a number"):
        validate_rent_limits({"0.60": [943, "n/a", 1197, 1382, 1563]},
                             source=RENT_SOURCE)


def test_rejects_an_empty_table():
    with pytest.raises(ReferenceDataError, match="non-empty"):
        validate_rent_limits({}, source=RENT_SOURCE)


# -- utility allowances -----------------------------------------------------

def test_accepts_a_well_formed_schedule():
    assert validate_utility_allowances(GOOD_UA, source=UA_SOURCE)["electricity"][2] == 89


def test_utility_allowances_require_a_source():
    with pytest.raises(ReferenceDataError, match="requires a `source`"):
        validate_utility_allowances(GOOD_UA)


def test_rejects_an_unknown_utility_rather_than_dropping_it():
    """A dropped line understates the allowance and overstates net rent."""
    with pytest.raises(ReferenceDataError, match="unknown utility"):
        validate_utility_allowances({"broadband": [30, 30, 30, 30, 30]},
                                    source=UA_SOURCE)


def test_rejects_an_annual_allowance():
    with pytest.raises(ReferenceDataError, match="monthly, not annual"):
        validate_utility_allowances({"electricity": [684, 804, 1068, 1332, 1608]},
                                    source=UA_SOURCE)


def test_rejects_negative_allowances():
    with pytest.raises(ReferenceDataError, match="negative"):
        validate_utility_allowances({"electricity": [-5, 67, 89, 111, 134]},
                                    source=UA_SOURCE)


# -- the two tables together -------------------------------------------------

def test_rejects_allowances_that_swallow_the_rent():
    """Tables from different markets or vintages leave no net rent."""
    with pytest.raises(ReferenceDataError, match="no net rent"):
        check_net_rents_positive(
            validate_rent_limits(GOOD_RENTS, source=RENT_SOURCE),
            validate_utility_allowances({"electricity": [900, 900, 900, 900, 900]},
                                        source=UA_SOURCE))


def test_gas_and_other_are_counted_not_dropped():
    deal = DealInputs(mode="screen")
    apply_to_deal(
        deal,
        rent_limits=GOOD_RENTS, rent_limits_source=RENT_SOURCE,
        utility_allowances={"electricity": [50] * 5, "gas": [10] * 5,
                            "other": [5] * 5, "trash": [8] * 5},
        utility_allowances_source=UA_SOURCE)
    total = (deal.ua_electricity[0] + deal.ua_water[0]
             + deal.ua_sewer[0] + deal.ua_trash[0])
    assert total == 73, "gas and other must still reduce net rent"


def test_applying_tables_changes_the_rents_the_model_prices():
    from lihtc_screen.model import solve
    deal = DealInputs(mode="screen")
    before = solve(deal).noi.gross_rental_income
    apply_to_deal(deal, rent_limits={"0.60": [700, 750, 900, 1050, 1200]},
                  rent_limits_source=RENT_SOURCE,
                  utility_allowances=GOOD_UA, utility_allowances_source=UA_SOURCE)
    assert solve(deal).noi.gross_rental_income < before

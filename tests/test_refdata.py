"""Reference data must be sourced, and must never be silently substituted."""

from __future__ import annotations

import json

import pytest

from lihtc_screen.inputs import DealInputs
from lihtc_screen.model import solve
from lihtc_screen.refdata import (MarketNotFound, available_markets, find_market,
                                  load_markets, tdc_limits_for_region)


def test_at_least_one_market_is_bundled():
    assert available_markets()


@pytest.mark.parametrize("query", [
    "New Orleans", "new orleans", "Metairie", "Orleans Parish",
    "new-orleans-la", "New Orleans, LA",
])
def test_new_orleans_resolves_from_common_spellings(query):
    assert find_market(query).key == "new-orleans-la"


def test_unknown_market_raises_rather_than_substituting():
    with pytest.raises(MarketNotFound) as exc:
        find_market("Baton Rouge")
    # The error has to be actionable, and name the parameters to pass.
    message = str(exc.value)
    assert "new-orleans-la" in message
    assert "rent_limits" in message and "utility_allowances" in message


def test_every_bundled_table_records_its_source():
    markets = load_markets()
    for key, entry in markets["markets"].items():
        assert entry["rent_limits"].get("source"), f"{key} rent limits have no source"
        ua_source = entry["utility_allowances"].get("source", "")
        assert ua_source, f"{key} utility allowances have no source"
        assert "NOT SET" not in ua_source, (
            f"{key} is bundled without real utility allowances; it would "
            f"overstate net rents")
    for region, entry in markets["tdc_limits"]["regions"].items():
        assert entry.get("source"), f"TDC region {region} has no source"


def test_market_tables_reproduce_the_workbook():
    """Applying New Orleans must not change the numbers it came from."""
    deal = DealInputs(mode="workbook")
    before = solve(deal)
    find_market("New Orleans").apply_to(deal)
    after = solve(deal)
    assert after.noi.gross_rental_income == before.noi.gross_rental_income
    assert after.total_development_cost == pytest.approx(
        before.total_development_cost, abs=0.01)


def test_tdc_limits_cover_every_bedroom_count_and_building_type():
    limits = tdc_limits_for_region("New Orleans")
    assert set(limits) == {0, 1, 2, 3, 4}
    for bedrooms, row in limits.items():
        assert set(row) == {"Detached/Semi-Detached", "Row House", "Walk-up", "Elevator"}
        assert all(v > 0 for v in row.values())


def test_rent_limits_rise_with_bedrooms_and_ami():
    market = find_market("New Orleans")
    for ami, row in market.rent_limits.items():
        assert row == sorted(row), f"{ami:.0%} rents do not rise with bedroom count"
    bands = sorted(b for b in market.rent_limits if b <= 0.80)
    for smaller, larger in zip(bands, bands[1:]):
        assert all(a <= b for a, b in zip(market.rent_limits[smaller],
                                          market.rent_limits[larger]))

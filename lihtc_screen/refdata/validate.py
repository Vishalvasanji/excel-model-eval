"""Validation for rent limits and utility allowances supplied per deal.

These tables normally arrive from outside the model — looked up against HUD and
the local housing authority at screening time — so they are the one input that
can be plausible-looking and wrong. A rent limit that is off by a bedroom
column, stated monthly where the model wants monthly but sourced annually, or
simply invented, produces a screen that is confidently incorrect all the way
through: rents drive NOI, NOI drives debt, debt drives the subsidy requirement.

So supplied tables are checked hard and rejected with a specific reason rather
than screened on. Every check here is a property a real HUD MTSP table has.
"""

from __future__ import annotations

BEDROOM_COUNT = 5                     # br0 through br4

# A monthly gross rent limit outside this range is not a rent limit. The floor
# catches annual-vs-monthly and dollars-vs-hundreds errors; the ceiling catches
# a table that is already annualised.
MIN_PLAUSIBLE_RENT = 100.0
MAX_PLAUSIBLE_RENT = 12_000.0

# Utility allowances are monthly, per unit.
MAX_PLAUSIBLE_UA = 1_000.0

# AMI bands the model prices against, as fractions.
MIN_AMI, MAX_AMI = 0.10, 1.50

UTILITIES = ("electricity", "water", "sewer", "trash", "gas", "other")


class ReferenceDataError(ValueError):
    """Supplied reference data is unusable. The message says exactly why."""


def _as_float(value, where: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ReferenceDataError(f"{where}: {value!r} is not a number") from None


def validate_rent_limits(table: dict, *, source: str | None = None) -> dict[float, list[float]]:
    """Check and normalise a gross rent limit table.

    Expects {ami_band: [br0, br1, br2, br3, br4]} with the band as a fraction
    (0.60) or a percentage (60). Returns bands as fractions.
    """
    if not isinstance(table, dict) or not table:
        raise ReferenceDataError(
            "rent_limits must be a non-empty object keyed by AMI band, e.g. "
            '{"0.60": [943, 997, 1197, 1382, 1563]}')

    cleaned: dict[float, list[float]] = {}
    for raw_band, raw_row in table.items():
        band = _as_float(raw_band, "rent_limits band")
        if band > MAX_AMI:               # given as a percentage
            band /= 100.0
        if not MIN_AMI <= band <= MAX_AMI:
            raise ReferenceDataError(
                f"rent_limits: AMI band {raw_band!r} is outside "
                f"{MIN_AMI:.0%}-{MAX_AMI:.0%}")

        if not isinstance(raw_row, (list, tuple)) or len(raw_row) != BEDROOM_COUNT:
            raise ReferenceDataError(
                f"rent_limits at {band:.0%} AMI: expected {BEDROOM_COUNT} monthly "
                f"rents for 0-4 bedrooms, got {raw_row!r}")

        row = [_as_float(v, f"rent_limits at {band:.0%} AMI") for v in raw_row]
        for bedrooms, rent in enumerate(row):
            if not MIN_PLAUSIBLE_RENT <= rent <= MAX_PLAUSIBLE_RENT:
                raise ReferenceDataError(
                    f"rent_limits at {band:.0%} AMI, {bedrooms}BR: ${rent:,.0f} is "
                    f"not a plausible monthly gross rent limit (expected "
                    f"${MIN_PLAUSIBLE_RENT:,.0f}-${MAX_PLAUSIBLE_RENT:,.0f}). "
                    f"Check it is monthly, not annual.")
        if row != sorted(row):
            raise ReferenceDataError(
                f"rent_limits at {band:.0%} AMI: rents must rise with bedroom "
                f"count, got {['%.0f' % r for r in row]}. The columns may be "
                f"out of order.")
        cleaned[round(band, 4)] = row

    # Across bands, a higher AMI cannot buy a lower rent.
    bands = sorted(cleaned)
    for lower, higher in zip(bands, bands[1:]):
        for bedrooms in range(BEDROOM_COUNT):
            if cleaned[higher][bedrooms] < cleaned[lower][bedrooms]:
                raise ReferenceDataError(
                    f"rent_limits: the {higher:.0%} AMI limit for {bedrooms}BR "
                    f"(${cleaned[higher][bedrooms]:,.0f}) is below the "
                    f"{lower:.0%} limit (${cleaned[lower][bedrooms]:,.0f}). "
                    f"The bands may be mislabelled.")

    if not source:
        raise ReferenceDataError(
            "rent_limits requires a `source` naming where the table came from, "
            "e.g. 'HUD FY2025 MTSP Income Limits, Orleans Parish LA'. A screen "
            "records what it priced against.")
    return cleaned


def validate_utility_allowances(table: dict, *, source: str | None = None) -> dict[str, list[float]]:
    """Check and normalise a utility allowance schedule.

    Expects {utility: [br0..br4]} in monthly dollars. Unknown utility names are
    rejected rather than dropped, since a dropped line understates the allowance
    and overstates net rent.
    """
    if not isinstance(table, dict) or not table:
        raise ReferenceDataError(
            "utility_allowances must be a non-empty object keyed by utility, "
            'e.g. {"electricity": [57, 67, 89, 111, 134]}')

    cleaned: dict[str, list[float]] = {}
    for raw_name, raw_row in table.items():
        name = str(raw_name).strip().lower()
        if name in ("source", "title", "effective"):
            continue
        if name not in UTILITIES:
            raise ReferenceDataError(
                f"utility_allowances: unknown utility {raw_name!r}. Expected one "
                f"of {', '.join(UTILITIES)}. Fold anything else into 'other' so "
                f"it is still counted.")
        if not isinstance(raw_row, (list, tuple)) or len(raw_row) != BEDROOM_COUNT:
            raise ReferenceDataError(
                f"utility_allowances for {name}: expected {BEDROOM_COUNT} monthly "
                f"allowances for 0-4 bedrooms, got {raw_row!r}")
        row = [_as_float(v, f"utility_allowances for {name}") for v in raw_row]
        for bedrooms, value in enumerate(row):
            if value < 0:
                raise ReferenceDataError(
                    f"utility_allowances for {name}, {bedrooms}BR: {value} is negative")
            if value > MAX_PLAUSIBLE_UA:
                raise ReferenceDataError(
                    f"utility_allowances for {name}, {bedrooms}BR: ${value:,.0f} is "
                    f"not a plausible monthly allowance (over ${MAX_PLAUSIBLE_UA:,.0f}). "
                    f"Check it is monthly, not annual.")
        cleaned[name] = row

    if not cleaned:
        raise ReferenceDataError("utility_allowances contained no utility lines")
    if not source:
        raise ReferenceDataError(
            "utility_allowances requires a `source` naming the schedule and its "
            "effective date, e.g. 'HANO Utility Allowance Schedule eff. 09/01/2025'.")
    return cleaned


def check_net_rents_positive(rent_limits: dict[float, list[float]],
                             allowances: dict[str, list[float]]) -> None:
    """A utility allowance that swallows the rent limit means a mismatched pair."""
    totals = [sum(row[b] for row in allowances.values()) for b in range(BEDROOM_COUNT)]
    for band, row in rent_limits.items():
        for bedrooms, gross in enumerate(row):
            if gross - totals[bedrooms] <= 0:
                raise ReferenceDataError(
                    f"At {band:.0%} AMI the {bedrooms}BR gross rent limit "
                    f"(${gross:,.0f}) is below the utility allowance "
                    f"(${totals[bedrooms]:,.0f}), leaving no net rent. The two "
                    f"tables are probably from different markets or vintages.")


def apply_to_deal(deal, rent_limits=None, rent_limits_source=None,
                  utility_allowances=None, utility_allowances_source=None) -> dict:
    """Validate supplied tables and copy them onto a deal.

    Returns a record of what was applied and where it came from, so the screen
    can state what it priced against.
    """
    applied: dict[str, str] = {}

    if rent_limits is not None:
        deal.rent_limits = validate_rent_limits(rent_limits, source=rent_limits_source)
        applied["rent_limits"] = rent_limits_source

    if utility_allowances is not None:
        cleaned = validate_utility_allowances(
            utility_allowances, source=utility_allowances_source)
        blank = [0.0] * BEDROOM_COUNT
        deal.ua_electricity = cleaned.get("electricity", list(blank))
        deal.ua_water = cleaned.get("water", list(blank))
        deal.ua_sewer = cleaned.get("sewer", list(blank))
        # The model carries four allowance lines; gas and other are folded into
        # the trash line so nothing supplied is silently dropped.
        deal.ua_trash = [
            cleaned.get("trash", blank)[b]
            + cleaned.get("gas", blank)[b]
            + cleaned.get("other", blank)[b]
            for b in range(BEDROOM_COUNT)
        ]
        applied["utility_allowances"] = utility_allowances_source

    if rent_limits is not None and utility_allowances is not None:
        check_net_rents_positive(
            deal.rent_limits,
            {"electricity": deal.ua_electricity, "water": deal.ua_water,
             "sewer": deal.ua_sewer, "trash": deal.ua_trash})

    return applied

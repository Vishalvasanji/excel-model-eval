"""Answers the two questions a screen has to settle.

    1. What is the minimum soft funding this deal needs to work?
    2. What is the most we can pay for it?

Both run the whole model repeatedly, so both are bisections rather than closed
forms: the capital stack, the credit and the reserves all move with the answer.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from .inputs import DealInputs
from .model import Result, solve
from .scorecard import Scorecard, evaluate

PRICE_SEARCH_ITERATIONS = 48
PRICE_TOLERANCE = 1_000.0      # dollars; finer than any screening decision needs


@dataclass
class Screen:
    """The result of screening one deal."""
    result: Result
    scorecard: Scorecard
    required_soft_money: float = 0.0
    committed_soft_money: float = 0.0
    additional_soft_money_needed: float = 0.0
    soft_money_surplus: float = 0.0
    max_supportable_price: float | None = None
    max_price_soft_money: float = 0.0
    price_headroom: float | None = None
    soft_money_at_zero_price: float = 0.0
    price_by_soft_money: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        return self.scorecard.verdict

    @property
    def works(self) -> bool:
        """Whether the deal clears every hard rule at the asking price."""
        return self.scorecard.hard_fails == 0


def _blocking(card: Scorecard) -> bool:
    """Hard fails other than the funding gap itself."""
    return any(c.is_hard_fail for c in card.checks)


def screen(deal: DealInputs) -> Screen:
    """Run the model, score it, and solve for the price the deal supports."""
    result = solve(deal)
    card = evaluate(result)

    s = Screen(
        result=result, scorecard=card,
        required_soft_money=result.required_soft_money,
        committed_soft_money=result.committed_soft_money,
        additional_soft_money_needed=result.additional_soft_money_needed,
        soft_money_surplus=result.soft_money_surplus,
    )

    available = deal.obtainable_soft_money()
    if s.required_soft_money > available:
        s.notes.append(
            f"Needs ${s.required_soft_money:,.0f} of soft funding against "
            f"${available:,.0f} obtainable - short by "
            f"${s.required_soft_money - available:,.0f}.")
    elif s.required_soft_money == 0:
        s.notes.append("Priced debt and equity fund the deal outright; "
                       "no subsidy needed at this price.")
    elif s.soft_money_surplus > 0:
        s.notes.append(
            f"Needs ${s.required_soft_money:,.0f} of soft funding, "
            f"${s.soft_money_surplus:,.0f} less than what is committed.")

    at_zero = copy.deepcopy(deal)
    at_zero.acquisition_cost = 0.0
    s.soft_money_at_zero_price = solve(at_zero).required_soft_money

    s.max_supportable_price = max_supportable_price(deal)
    if s.max_supportable_price is not None:
        s.price_headroom = s.max_supportable_price - deal.acquisition_cost
        priced = copy.deepcopy(deal)
        priced.acquisition_cost = s.max_supportable_price
        s.max_price_soft_money = solve(priced).required_soft_money
    else:
        blockers = [c.kpi_id for c in card.checks if c.is_hard_fail]
        if s.soft_money_at_zero_price > available:  # noqa: SIM102
            s.notes.append(
                f"No purchase price makes this work on ${available:,.0f} of soft "
                f"funding: even at a $0 price it needs "
                f"${s.soft_money_at_zero_price:,.0f}.")
        elif blockers:
            s.notes.append(
                "Price is not what breaks this deal - "
                + ", ".join(sorted(set(blockers))) + " fails at any price.")

    # How far the price can stretch as more subsidy becomes available.
    s.price_by_soft_money = price_by_soft_money(
        deal, s.soft_money_at_zero_price, s.required_soft_money)
    return s


def price_by_soft_money(deal: DealInputs, gap_at_zero: float,
                        gap_at_asking: float, steps: int = 4) -> list[dict]:
    """Max supportable price across a range of available soft funding.

    The range runs from the least subsidy the deal could possibly need (its gap
    at a $0 purchase price) up past the gap at the asking price, so the table
    brackets the decision rather than bottoming out at "nothing works".
    """
    if gap_at_zero <= 0:
        return []
    top = max(gap_at_asking, gap_at_zero * 1.5)
    rows = []
    for i in range(steps + 1):
        available = gap_at_zero + (top - gap_at_zero) * i / steps
        trial = copy.deepcopy(deal)
        trial.soft_money_available = available
        rows.append({"soft_money_available": available,
                     "max_price": max_supportable_price(trial)})
    return rows


def _works_at(deal: DealInputs, price: float) -> bool:
    """Whether the deal clears every hard rule, and its funding gap, at `price`."""
    trial = copy.deepcopy(deal)
    trial.acquisition_cost = price
    result = solve(trial)
    if result.required_soft_money > trial.obtainable_soft_money() + PRICE_TOLERANCE:
        return False
    return not _blocking(evaluate(result))


def max_supportable_price(deal: DealInputs, ceiling: float | None = None) -> float | None:
    """Highest purchase price at which the deal still works.

    Returns None when the deal fails at any price, i.e. when something other
    than the purchase price is what breaks it.
    """
    if not _works_at(deal, 0.0):
        return None

    # Bracket upward from the asking price until the deal breaks, then bisect.
    if ceiling is None:
        ceiling = max(deal.acquisition_cost * 2, 1_000_000.0)
        for _ in range(12):
            if not _works_at(deal, ceiling):
                break
            ceiling *= 2
        else:
            return ceiling      # unbounded within a sane range

    low, high = 0.0, ceiling
    for _ in range(PRICE_SEARCH_ITERATIONS):
        if high - low <= PRICE_TOLERANCE:
            break
        mid = (low + high) / 2
        if _works_at(deal, mid):
            low = mid
        else:
            high = mid
    return low


def sensitivity(deal: DealInputs, variable: str, values: list) -> list[dict]:
    """Re-screen the deal across a range of one input.

    `variable` is a `DealInputs` field name, or one of the shorthands:
        rehab_per_unit   blended hard cost per unit
    """
    rows = []
    for value in values:
        trial = copy.deepcopy(deal)
        if variable == "rehab_per_unit":
            for line in trial.construction:
                if line.key == "units":
                    line.unit_cost = value
        else:
            setattr(trial, variable, value)
        s = screen(trial)
        rows.append({
            "value": value,
            "verdict": s.verdict,
            "required_soft_money": s.required_soft_money,
            "max_supportable_price": s.max_supportable_price,
            "total_development_cost": s.result.total_development_cost,
            "min_dscr": s.result.min_dscr,
            "bond": s.result.sources_uses.bonds,
            "equity": s.result.sources_uses.tax_credit_equity,
        })
    return rows

"""`Surplus Cash-Reserve Waterfall` - reserve sizing and the surplus-cash cascade.

Two jobs. Sizing the reserves the development budget must fund (the operating
deficit and interest reserves), and running surplus cash down the priority
order: deferred developer fee, then soft loans, then replenishing reserves.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..inputs import DealInputs
from .leaseup import LeaseUp
from .loans import PRO_FORMA_YEARS
from .proforma import ProForma

OPERATING_RESERVE_MONTHS = 0.5   # B46, half a year of stabilised opex
INTEREST_RESERVE_MONTHS = 0.5    # B47, half a year of lease-up interest


@dataclass
class ReserveRequirement:
    operating: float = 0.0     # B46
    interest: float = 0.0      # B47
    total: float = 0.0         # B48


@dataclass
class Waterfall:
    deferred_fee_balance: list[float] = field(default_factory=list)  # row 19
    soft_loan_balance: list[float] = field(default_factory=list)     # row 25
    reserve_balance: list[float] = field(default_factory=list)       # row 32
    deferred_fee_payments: list[float] = field(default_factory=list) # row 7
    soft_loan_payments: list[float] = field(default_factory=list)    # row 8
    deferred_fee_repaid_year: int | None = None


def size_reserves(lu: LeaseUp, stabilised_opex: float) -> ReserveRequirement:
    """B46:B48. Sized off the lease-up shortfall and the stabilised year."""
    r = ReserveRequirement()
    # B46 takes the greater of the lease-up operating deficit and half of the
    # first stabilised year's operating expenses.
    operating_deficit = sum(
        max(0.0, -(cash + interest))
        for cash, interest in zip(lu.cash_after_fees, lu.interest)
    )
    r.operating = max(operating_deficit, OPERATING_RESERVE_MONTHS * stabilised_opex)
    r.interest = INTEREST_RESERVE_MONTHS * lu.total_interest
    r.total = r.operating + r.interest
    return r


def compute(deal: DealInputs, pf: ProForma, deferred_fee: float,
            soft_loan: float, reserve_target: float) -> Waterfall:
    w = Waterfall()
    deferred_balance = deferred_fee
    soft_balance = soft_loan
    reserve_balance = reserve_target

    for year in range(1, PRO_FORMA_YEARS + 1):
        surplus = pf.cash_after_fees[year - 1]
        available = max(0.0, surplus)

        to_deferred = min(deferred_balance, available)
        to_soft = min(soft_balance, available - to_deferred)

        draw = min(reserve_balance, max(0.0, -surplus))
        shortfall = max(0.0, reserve_target - (reserve_balance - draw))
        to_reserve = min(shortfall, available - to_deferred - to_soft)

        deferred_balance -= to_deferred
        soft_balance -= to_soft
        reserve_balance = reserve_balance + to_reserve - draw

        w.deferred_fee_payments.append(to_deferred)
        w.soft_loan_payments.append(to_soft)
        w.deferred_fee_balance.append(deferred_balance)
        w.soft_loan_balance.append(soft_balance)
        w.reserve_balance.append(reserve_balance)

        if w.deferred_fee_repaid_year is None and deferred_balance <= 0.01:
            w.deferred_fee_repaid_year = year

    return w

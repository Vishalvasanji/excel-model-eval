"""Permanent debt: the perm block of `Loan Amortization`, rows 32-40.

Year 1 carries no debt service (the loan closes at conversion), years 2 and 3
are interest-only, and level annual amortisation begins in year 4.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..inputs import DealInputs
from .financing import pmt

PRO_FORMA_YEARS = 17
INTEREST_ONLY_THROUGH = 3      # years 2-3 pay interest only; year 4 amortises


@dataclass
class PermLoan:
    beginning_balance: list[float] = field(default_factory=list)  # row 33
    payment: list[float] = field(default_factory=list)            # row 34
    interest: list[float] = field(default_factory=list)           # row 35
    principal: list[float] = field(default_factory=list)          # row 36
    ending_balance: list[float] = field(default_factory=list)     # row 37
    issuer_fee: list[float] = field(default_factory=list)         # row 38
    trustee_fee: list[float] = field(default_factory=list)        # row 39
    servicing_fee: list[float] = field(default_factory=list)      # row 40


def compute(deal: DealInputs, loan_amount: float) -> PermLoan:
    p = PermLoan()
    level = pmt(deal.perm_coupon, deal.perm_amortization_years, loan_amount)

    balance = 0.0
    for year in range(1, PRO_FORMA_YEARS + 1):
        if year == 1:
            beginning = 0.0
        elif year == 2:
            beginning = loan_amount
        else:
            beginning = balance

        interest = beginning * deal.perm_coupon
        if year == 1:
            payment = 0.0
        elif year <= INTEREST_ONLY_THROUGH:
            payment = interest
        else:
            payment = level
        principal = payment - interest
        balance = beginning - principal

        p.beginning_balance.append(beginning)
        p.payment.append(payment)
        p.interest.append(interest)
        p.principal.append(principal)
        p.ending_balance.append(balance)
        p.issuer_fee.append(beginning * deal.issuer_fee_pct)
        p.trustee_fee.append(0.0 if year == 1 else deal.trustee_fee)
        p.servicing_fee.append(beginning * deal.servicing_fee_pct)
    return p

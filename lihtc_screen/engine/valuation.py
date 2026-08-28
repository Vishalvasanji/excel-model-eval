"""`Valuation` - direct capitalisation of NOI, net of the debt and soft stack."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..inputs import DealInputs
from .loans import PermLoan
from .proforma import ProForma
from .waterfall import Waterfall


@dataclass
class Valuation:
    property_value: list[float] = field(default_factory=list)   # row 9
    net_equity: list[float] = field(default_factory=list)       # row 15
    net_equity_ex_soft: list[float] = field(default_factory=list)  # row 17


def compute(deal: DealInputs, pf: ProForma, loan: PermLoan,
            w: Waterfall) -> Valuation:
    v = Valuation()
    cap = deal.valuation_cap_rate
    for i, noi in enumerate(pf.noi):
        value = noi / cap if cap else 0.0
        # Year 1 sits before the perm loan converts, so it carries the full
        # balance; later years step down the amortisation schedule.
        senior = loan.beginning_balance[1] if i == 0 else loan.ending_balance[i - 1]
        deferred = w.deferred_fee_balance[i]
        soft = w.soft_loan_balance[i]
        v.property_value.append(value)
        v.net_equity.append(value - senior - deferred - soft)
        v.net_equity_ex_soft.append(value - senior - deferred)
    return v

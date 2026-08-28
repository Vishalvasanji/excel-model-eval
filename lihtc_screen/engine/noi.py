"""`NOI Calc` - stabilised revenue, operating expenses and net operating income."""

from __future__ import annotations

from dataclasses import dataclass

from ..inputs import DealInputs
from .expenses import Expenses
from .unitmix import UnitMix


@dataclass
class NOI:
    gross_rental_income: float = 0.0   # J5
    other_income: float = 0.0          # J6 + J7
    gross_revenue: float = 0.0         # J9
    vacancy: float = 0.0               # J11 (negative)
    net_revenue: float = 0.0           # J13

    management_fee: float = 0.0        # J16
    payroll: float = 0.0               # J17
    maintenance: float = 0.0           # J18
    utilities: float = 0.0             # J19
    contract_services: float = 0.0     # J20
    compliance: float = 0.0            # J21
    admin: float = 0.0                 # J22
    insurance: float = 0.0             # J23
    property_tax: float = 0.0          # J24
    total_opex: float = 0.0            # J26

    noi: float = 0.0                   # J29
    replacement_reserves: float = 0.0  # J33
    sizing_noi: float = 0.0            # `Financing Assumptions` C25


def compute(deal: DealInputs, mix: UnitMix, exp: Expenses) -> NOI:
    units = mix.units
    n = NOI()

    n.gross_rental_income = mix.monthly_net_rent * 12
    n.other_income = (deal.tenant_charges_per_unit_month
                      + deal.pet_fees_per_unit_month) * units * 12
    n.gross_revenue = n.gross_rental_income + n.other_income
    n.vacancy = -n.gross_revenue * deal.vacancy_rate
    n.net_revenue = n.gross_revenue + n.vacancy

    n.management_fee = n.net_revenue * deal.management_fee_pct
    n.payroll = exp.payroll
    n.maintenance = exp.maintenance
    n.utilities = exp.utilities
    n.contract_services = exp.contract_services
    n.compliance = deal.compliance_per_unit * units
    n.admin = deal.admin_per_unit * units
    n.insurance = exp.insurance

    # `NOI Calc` J24 references Expense Detail F60 - the PILOT payment - rather
    # than F61, the tax after the PILOT toggle. The pro forma therefore always
    # runs at the PILOT amount. Reproduced in workbook mode; screen mode uses
    # the tax the deal will actually pay.
    n.property_tax = exp.pilot_payment if deal.mode == "workbook" else exp.property_tax

    n.total_opex = (n.management_fee + n.payroll + n.maintenance + n.utilities
                    + n.contract_services + n.compliance + n.admin
                    + n.insurance + n.property_tax)
    n.noi = n.net_revenue - n.total_opex
    n.replacement_reserves = deal.replacement_reserve_per_unit * units

    # `Financing Assumptions` C25, the NOI debt is sized on. The workbook adds
    # (F61 - F60); since NOI already deducted the PILOT amount, charging the
    # higher un-PILOTed tax should *reduce* sizing NOI, so the sign is wrong.
    # Reproduced in workbook mode, corrected in screen mode.
    delta = exp.property_tax - exp.pilot_payment
    n.sizing_noi = n.noi + delta if deal.mode == "workbook" else n.noi
    return n

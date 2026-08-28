"""`Lease-Up Period` - the 12 monthly columns of year one.

Revenue ramps with occupancy; each expense line carries a fixed share that is
incurred regardless of how many units are occupied.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..inputs import DealInputs
from .expenses import Expenses
from .noi import NOI
from .unitmix import UnitMix

MONTHS = 12


@dataclass
class LeaseUp:
    occupancy: list[float] = field(default_factory=list)       # row 55
    net_revenue: list[float] = field(default_factory=list)     # row 12
    opex: list[float] = field(default_factory=list)            # row 24
    noi: list[float] = field(default_factory=list)             # row 26
    cash_after_fees: list[float] = field(default_factory=list) # row 41
    interest: list[float] = field(default_factory=list)        # row 30

    # column P, the annual totals the pro forma's year 1 is built from
    total_gross_rent: float = 0.0
    total_other_income: float = 0.0
    total_vacancy: float = 0.0
    total_net_revenue: float = 0.0
    total_management_fee: float = 0.0
    total_payroll: float = 0.0
    total_maintenance: float = 0.0
    total_utilities: float = 0.0
    total_admin: float = 0.0
    total_insurance: float = 0.0
    total_property_tax: float = 0.0
    total_opex: float = 0.0
    total_noi: float = 0.0
    total_reserves: float = 0.0
    total_interest: float = 0.0
    total_principal: float = 0.0
    total_issuer_fee: float = 0.0
    total_trustee_fee: float = 0.0
    total_servicing_fee: float = 0.0
    total_asset_mgmt_fee: float = 0.0
    total_cash_after_fees: float = 0.0


def compute(deal: DealInputs, mix: UnitMix, n: NOI, exp: Expenses,
            loan_amount: float) -> LeaseUp:
    lu = LeaseUp()
    units = mix.units

    monthly_rent = n.gross_rental_income / 12
    monthly_other = n.other_income / 12
    # Administrative on this sheet bundles contract services, compliance and admin.
    monthly_admin_base = (n.contract_services + n.compliance + n.admin) / 12

    occupied = 0.0
    for month in range(MONTHS):
        leased = deal.leaseup_schedule[month] if month < len(deal.leaseup_schedule) else 0
        occupied = min(occupied + leased, units)
        occ = occupied / units if units else 0.0
        lu.occupancy.append(occ)

        gross = monthly_rent + monthly_other
        # Vacancy is the worse of the stabilised rate and actual vacancy.
        vacancy = -max(deal.vacancy_rate, 1 - occ) * gross
        net_revenue = gross + vacancy

        def scaled(annual: float, fixed: float) -> float:
            return (annual / 12) * (fixed + (1 - fixed) * occ)

        management = net_revenue * deal.management_fee_pct
        payroll = scaled(n.payroll, deal.fixed_share_payroll)
        maintenance = scaled(n.maintenance, deal.fixed_share_maintenance)
        utilities = scaled(n.utilities, deal.fixed_share_utilities)
        admin = (monthly_admin_base
                 * (deal.fixed_share_admin + (1 - deal.fixed_share_admin) * occ))
        insurance = scaled(n.insurance, deal.fixed_share_insurance)
        # `Lease-Up Period` row 22 uses the PILOT payment directly.
        tax = (exp.pilot_payment if deal.mode == "workbook" else exp.property_tax) / 12

        opex = management + payroll + maintenance + utilities + admin + insurance + tax
        noi_m = net_revenue - opex
        reserves = n.replacement_reserves / 12
        interest = loan_amount * deal.perm_coupon / 12
        cash_after_debt = noi_m - reserves - interest

        issuer = loan_amount * deal.issuer_fee_pct / 12
        trustee = deal.trustee_fee / 12
        servicing = loan_amount * deal.servicing_fee_pct / 12
        asset_mgmt = max(0.0, 0.1 * cash_after_debt)
        cash_after_fees = cash_after_debt - (issuer + trustee + servicing + asset_mgmt)

        lu.net_revenue.append(net_revenue)
        lu.opex.append(opex)
        lu.noi.append(noi_m)
        lu.interest.append(interest)
        lu.cash_after_fees.append(cash_after_fees)

        lu.total_gross_rent += monthly_rent
        lu.total_other_income += monthly_other
        lu.total_vacancy += vacancy
        lu.total_net_revenue += net_revenue
        lu.total_management_fee += management
        lu.total_payroll += payroll
        lu.total_maintenance += maintenance
        lu.total_utilities += utilities
        lu.total_admin += admin
        lu.total_insurance += insurance
        lu.total_property_tax += tax
        lu.total_opex += opex
        lu.total_noi += noi_m
        lu.total_reserves += reserves
        lu.total_interest += interest
        lu.total_issuer_fee += issuer
        lu.total_trustee_fee += trustee
        lu.total_servicing_fee += servicing
        lu.total_asset_mgmt_fee += asset_mgmt
        lu.total_cash_after_fees += cash_after_fees

    return lu

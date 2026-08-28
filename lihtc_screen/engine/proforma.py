"""`17-year Pro Forma` - years 1-17, and the DSCR series the scorecard reads.

Year 1 is the lease-up year and comes straight from `Lease-Up Period` column P.
Year 2 is the first stabilised year: revenue restarts from the full stabilised
figure rather than trending off the suppressed lease-up total. Years 3 onward
trend revenue and expenses at their own rates.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..inputs import DealInputs
from .leaseup import LeaseUp
from .loans import PermLoan, PRO_FORMA_YEARS
from .noi import NOI

# `17-year Pro Forma` row 22: property tax is held flat at the year-1 amount
# through year 10, resets to the stabilised figure in year 11, then trends.
TAX_FLAT_THROUGH_YEAR = 10
TAX_RESET_YEAR = 11


@dataclass
class ProForma:
    gross_rent: list[float] = field(default_factory=list)     # row 6
    other_income: list[float] = field(default_factory=list)   # row 7
    gross_revenue: list[float] = field(default_factory=list)  # row 9
    vacancy: list[float] = field(default_factory=list)        # row 10
    net_revenue: list[float] = field(default_factory=list)    # row 12
    management_fee: list[float] = field(default_factory=list) # row 16
    payroll: list[float] = field(default_factory=list)        # row 17
    maintenance: list[float] = field(default_factory=list)    # row 18
    utilities: list[float] = field(default_factory=list)      # row 19
    admin: list[float] = field(default_factory=list)          # row 20
    insurance: list[float] = field(default_factory=list)      # row 21
    property_tax: list[float] = field(default_factory=list)   # row 22
    opex: list[float] = field(default_factory=list)           # row 24
    noi: list[float] = field(default_factory=list)            # row 26
    reserves: list[float] = field(default_factory=list)       # row 28
    interest: list[float] = field(default_factory=list)       # row 30
    principal: list[float] = field(default_factory=list)      # row 31
    cash_after_debt: list[float] = field(default_factory=list)  # row 33
    issuer_fee: list[float] = field(default_factory=list)     # row 35
    trustee_fee: list[float] = field(default_factory=list)    # row 36
    servicing_fee: list[float] = field(default_factory=list)  # row 37
    asset_mgmt_fee: list[float] = field(default_factory=list) # row 38
    cash_after_fees: list[float] = field(default_factory=list)  # row 40
    dscr: list[float] = field(default_factory=list)           # row 46

    def dscr_years_2_17(self) -> list[float]:
        """DSCR for every year that carries debt service. Dashboard E3:E18."""
        return [d for d in self.dscr[1:] if d is not None]

    def dscr_after_reserves(self) -> list[float]:
        return [d for d in self._dscr_after_reserves[1:] if d is not None]

    _dscr_after_reserves: list[float] = field(default_factory=list)


def compute(deal: DealInputs, lu: LeaseUp, n: NOI, loan: PermLoan) -> ProForma:
    pf = ProForma()
    g, eg = deal.revenue_growth, deal.expense_growth

    for year in range(1, PRO_FORMA_YEARS + 1):
        i = year - 1
        if year == 1:
            gross_rent = lu.total_gross_rent
            other = lu.total_other_income
            vacancy = lu.total_vacancy
            management = lu.total_management_fee
            payroll = lu.total_payroll
            maintenance = lu.total_maintenance
            utilities = lu.total_utilities
            admin = lu.total_admin
            insurance = lu.total_insurance
            tax = lu.total_property_tax
            reserves = lu.total_reserves
        else:
            gross_rent = pf.gross_rent[i - 1] * (1 + g)
            other = pf.other_income[i - 1] * (1 + g)
            if year == 2:
                # Expenses restart from the stabilised figures where lease-up
                # suppressed them, and trend off year 1 where it did not.
                payroll = pf.payroll[0] * (1 + eg)
                maintenance = n.maintenance * (1 + eg)
                utilities = n.utilities * (1 + eg)
                admin = pf.admin[0] * (1 + eg)
                insurance = pf.insurance[0] * (1 + eg)
                tax = pf.property_tax[0]
            else:
                payroll = pf.payroll[i - 1] * (1 + eg)
                maintenance = pf.maintenance[i - 1] * (1 + eg)
                utilities = pf.utilities[i - 1] * (1 + eg)
                admin = pf.admin[i - 1] * (1 + eg)
                insurance = pf.insurance[i - 1] * (1 + eg)
                if year <= TAX_FLAT_THROUGH_YEAR:
                    tax = pf.property_tax[0]
                elif year == TAX_RESET_YEAR:
                    tax = n.property_tax
                else:
                    tax = pf.property_tax[i - 1] * (1 + eg)
            reserves = pf.reserves[i - 1] * (1 + eg)
            vacancy = None      # computed below from gross revenue
            management = None

        gross_revenue = gross_rent + other
        if vacancy is None:
            vacancy = -deal.vacancy_rate * gross_revenue
        net_revenue = gross_revenue + vacancy
        if management is None:
            management = net_revenue * deal.management_fee_pct

        opex = (management + payroll + maintenance + utilities + admin
                + insurance + tax)
        noi_y = net_revenue - opex

        if year == 1:
            interest, principal = lu.total_interest, lu.total_principal
            issuer, trustee = lu.total_issuer_fee, lu.total_trustee_fee
            servicing, asset_mgmt = lu.total_servicing_fee, lu.total_asset_mgmt_fee
            cash_after_debt = noi_y - reserves - interest - principal
        else:
            # Pro forma year Y reads the amortisation schedule's year Y: the
            # schedule's first entry is the pre-conversion year that carries no
            # debt service, so year 2 of the pro forma is entry 1.
            j = year - 1
            interest, principal = loan.interest[j], loan.principal[j]
            issuer, trustee = loan.issuer_fee[j], loan.trustee_fee[j]
            servicing = loan.servicing_fee[j]
            cash_after_debt = noi_y - reserves - interest - principal
            asset_mgmt = max(0.0, 0.1 * cash_after_debt)

        cash_after_fees = cash_after_debt - (issuer + trustee + servicing + asset_mgmt)
        debt_service = interest + principal

        pf.gross_rent.append(gross_rent)
        pf.other_income.append(other)
        pf.gross_revenue.append(gross_revenue)
        pf.vacancy.append(vacancy)
        pf.net_revenue.append(net_revenue)
        pf.management_fee.append(management)
        pf.payroll.append(payroll)
        pf.maintenance.append(maintenance)
        pf.utilities.append(utilities)
        pf.admin.append(admin)
        pf.insurance.append(insurance)
        pf.property_tax.append(tax)
        pf.opex.append(opex)
        pf.noi.append(noi_y)
        pf.reserves.append(reserves)
        pf.interest.append(interest)
        pf.principal.append(principal)
        pf.cash_after_debt.append(cash_after_debt)
        pf.issuer_fee.append(issuer)
        pf.trustee_fee.append(trustee)
        pf.servicing_fee.append(servicing)
        pf.asset_mgmt_fee.append(asset_mgmt)
        pf.cash_after_fees.append(cash_after_fees)
        pf.dscr.append(noi_y / debt_service if debt_service else None)
        pf._dscr_after_reserves.append(
            (noi_y - reserves) / debt_service if debt_service else None)

    return pf

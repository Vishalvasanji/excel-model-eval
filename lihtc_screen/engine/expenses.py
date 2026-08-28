"""`Expense Detail` - payroll, maintenance, utilities, contract services, taxes."""

from __future__ import annotations

from dataclasses import dataclass

from ..inputs import DealInputs
from .unitmix import UnitMix

HOURS_PER_YEAR = 2080          # `Expense Detail` F6: count x rate x 2080


@dataclass
class Expenses:
    payroll: float = 0.0             # F13
    maintenance: float = 0.0         # F20
    utilities: float = 0.0           # F39
    contract_services: float = 0.0   # F50
    property_tax: float = 0.0        # F61, after the PILOT toggle
    pilot_payment: float = 0.0       # F60
    unpiloted_tax: float = 0.0       # F57, millage x capitalised value
    assessed_value: float = 0.0      # F55
    insurance: float = 0.0           # F65


def compute(deal: DealInputs, mix: UnitMix, noi_for_tax: float) -> Expenses:
    """Operating expense detail.

    `noi_for_tax` is the NOI used to capitalise an assessed value for the
    property-tax estimate (`Expense Detail` F53). It only matters when no PILOT
    is in place; with a PILOT the tax is the negotiated payment.
    """
    units = mix.units
    exp = Expenses()

    # -- payroll (rows 6-13) ------------------------------------------------
    base = sum(p.count * p.hourly * HOURS_PER_YEAR for p in deal.payroll)
    exp.payroll = base * (1 + deal.payroll_tax_burden + deal.payroll_benefits_burden)

    # -- maintenance + make ready (rows 17-20) ------------------------------
    turns_per_month = units * deal.turnover_rate / 12
    make_ready = turns_per_month * deal.make_ready_cost * 12
    maintenance = deal.maintenance_per_unit_month * units * 12
    exp.maintenance = make_ready + maintenance

    # -- utilities (rows 25-39) ---------------------------------------------
    sewer_rate = deal.water_per_unit_month * deal.sewer_multiple_of_water
    unit_utils = (deal.water_per_unit_month + sewer_rate
                  + deal.gas_per_unit_month + deal.electric_per_unit_month)
    clubhouse = (deal.clubhouse_water_month
                 + deal.clubhouse_water_month * deal.sewer_multiple_of_water
                 + deal.clubhouse_gas_month + deal.clubhouse_electric_month)
    common = (deal.property_water_month
              + deal.property_water_month * deal.sewer_multiple_of_water
              + deal.property_gas_month + deal.property_electric_month)
    exp.utilities = (unit_utils * units + clubhouse + common) * 12

    # -- contract services (rows 43-50) -------------------------------------
    exp.contract_services = 12 * (
        deal.landscaping_month + deal.elevator_maint_month + deal.pest_control_month
        + deal.janitorial_month + deal.security_month
        + deal.waste_collection_month + deal.pool_maint_month
    )

    # -- property taxes (rows 53-61) ----------------------------------------
    exp.assessed_value = noi_for_tax / deal.tax_cap_rate if deal.tax_cap_rate else 0.0
    exp.unpiloted_tax = exp.assessed_value * deal.millage_rate
    exp.pilot_payment = deal.pilot_annual_payment
    exp.property_tax = (deal.pilot_annual_payment
                        if deal.pilot_in_place == "Yes" else exp.unpiloted_tax)

    # -- insurance (row 65) --------------------------------------------------
    exp.insurance = deal.insurance_per_unit * units
    return exp

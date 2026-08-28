"""Deal inputs for the LIHTC acquisition/rehab underwriting engine.

Field names follow the language of the underlying workbook
(`reference/Acq_Rehab_Model_v1.xlsx`) so a number here can be traced to the tab
and cell it came from. Cell references appear in comments throughout.

Everything has a default that reproduces the workbook's Westbend deal, so a
partially-specified deal still runs; `lihtc_screen.defaults` supplies the
screening defaults drawn from the underwriting workflow instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

# Bedroom columns used throughout the rent-limit and utility-allowance tables.
BEDROOM_COLUMNS = (0, 1, 2, 3, 4)

BUILDING_TYPES = ("Detached/Semi-Detached", "Row House", "Walk-up", "Elevator")
PROJECT_TYPES = ("Family", "Senior", "Rehab")
CREDIT_TYPES = ("4% bond", "9% competitive")
SYNDICATION_TYPES = ("Private", "Public")
POOLS = ("Metro", "Rural", "Rural QNP-CHDO", "Reprocessing")


@dataclass
class UnitType:
    """One row of the unit mix. `Unit Mix+Rents` rows 4-13."""
    bedrooms: int                      # col A
    bathrooms: float = 1.0             # col B
    sqft: float = 0.0                  # col C
    count: int = 0                     # col D
    lihtc: bool = True                 # col E
    staff_unit: bool = False           # col F
    subsidy: bool = False              # col G
    psh: bool = False                  # col H
    ami_pct: float = 0.60              # col I


@dataclass
class PayrollPosition:
    """`Expense Detail` rows 6-8. Annualised as count x hourly x 2080."""
    title: str
    count: float
    hourly: float


@dataclass
class ConstructionLine:
    """One line of `Construction Estimates` rows 4-12.

    `basis` is how the quantity is determined:
      "lump"      - quantity is 1 (or the count of items, e.g. elevator shafts)
      "per_unit"  - quantity is the project's unit count
    """
    key: str
    label: str
    basis: str
    unit_cost: float
    quantity: float = 1.0


def _westbend_unit_mix() -> list[UnitType]:
    """The workbook's unit mix: 110 1BR and 170 2BR, all at 60% AMI."""
    rows: list[UnitType] = []
    for br, sqft, baths in ((1, 900, 1.0), (2, 1100, 2.0)):
        for ami in (0.20, 0.30, 0.40, 0.50, 0.60):
            count = 0
            if ami == 0.60:
                count = 110 if br == 1 else 170
            rows.append(UnitType(bedrooms=br, bathrooms=baths, sqft=sqft,
                                 count=count, ami_pct=ami))
    return rows


def _westbend_construction() -> list[ConstructionLine]:
    """`Construction Estimates` rows 4-12, in workbook order.

    All nine line items are retained: the screening workflow prices an
    acquisition/rehab through the same categories as new construction.
    """
    return [
        ConstructionLine("sitework", "Sitework", "lump", 500_000, 1),
        ConstructionLine("abatement", "Abatement", "lump", 0, 1),
        ConstructionLine("demolition", "Demolition", "per_unit", 1_500),
        ConstructionLine("units", "Construction Cost - Units", "per_unit", 100_000),
        ConstructionLine("clubhouse", "Construction Cost - Clubhouse", "lump", 200_000, 1),
        ConstructionLine("elevators", "Elevators", "lump", 0, 0),
        ConstructionLine("pool", "Pool", "lump", 100_000, 1),
        ConstructionLine("sports_courts", "Sports Courts", "lump", 25_000, 1),
        ConstructionLine("playground", "Playground", "lump", 100_000, 1),
    ]


# `Construction Estimates` C29:C47 - share of hard cost drawn each month.
DEFAULT_DRAW_CURVE = (
    0.000, 0.020, 0.035, 0.050, 0.065, 0.070, 0.075, 0.075, 0.075, 0.075,
    0.075, 0.070, 0.070, 0.065, 0.055, 0.045, 0.035, 0.025, 0.020,
)


@dataclass
class DealInputs:
    """Every per-deal input the model consumes."""

    # -- Dashboard Calc, deal inputs (rows 3-11) ---------------------------
    project_name: str = "Westbend"
    project_type: str = "Family"
    credit_type: str = "4% bond"
    boost_eligible: str = "No"                  # Yes/No; QCT/DDA screen
    rd_hud_financed: str = "No"
    syndication: str = "Private"
    pool: str = "Metro"
    building_type: str = "Walk-up"
    tdc_region: str = "New Orleans"

    # -- Unit Mix+Rents ----------------------------------------------------
    unit_mix: list[UnitType] = field(default_factory=_westbend_unit_mix)
    # Gross rent limits: {ami_fraction: [br0, br1, br2, br3, br4]}. Rows 20-27.
    rent_limits: dict[float, list[float]] = field(default_factory=lambda: {
        1.20: [1887, 2022, 2427, 2802, 3126],
        0.20: [314, 337, 404, 467, 521],
        0.30: [471, 498, 598, 691, 781],
        0.40: [629, 674, 809, 934, 1042],
        0.50: [786, 831, 997, 1151, 1302],
        0.60: [943, 997, 1197, 1382, 1563],
        0.70: [1100, 1163, 1396, 1612, 1823],
        0.80: [1258, 1348, 1618, 1868, 2084],
    })
    # Utility allowances by bedroom count. Rows 33-36.
    ua_electricity: list[float] = field(default_factory=lambda: [57, 67, 89, 111, 134])
    ua_water: list[float] = field(default_factory=lambda: [0, 0, 0, 0, 0])
    ua_sewer: list[float] = field(default_factory=lambda: [0, 0, 0, 0, 0])
    ua_trash: list[float] = field(default_factory=lambda: [0, 0, 0, 0, 0])

    # -- Expense Detail ----------------------------------------------------
    payroll: list[PayrollPosition] = field(default_factory=lambda: [
        PayrollPosition("Property Manager", 1, 24),
        PayrollPosition("Leasing Agent", 1, 18),
        PayrollPosition("Maintenance Staff", 2, 20),
    ])
    payroll_tax_burden: float = 0.10            # E10
    payroll_benefits_burden: float = 0.00       # E11
    turnover_rate: float = 0.40                 # C17, annual turns per unit
    make_ready_cost: float = 400                # E17, $/turn
    maintenance_per_unit_month: float = 50      # E19

    water_per_unit_month: float = 20            # E25
    sewer_multiple_of_water: float = 2          # C26
    gas_per_unit_month: float = 0               # E27
    electric_per_unit_month: float = 0          # E28
    clubhouse_water_month: float = 20           # E30
    clubhouse_gas_month: float = 0              # E32
    clubhouse_electric_month: float = 300       # E33
    property_water_month: float = 50            # E35
    property_gas_month: float = 0               # E37
    property_electric_month: float = 200        # E38

    landscaping_month: float = 1_500            # E43
    elevator_maint_month: float = 0             # E44
    pest_control_month: float = 500             # E45
    janitorial_month: float = 500               # E46
    security_month: float = 500                 # E47
    waste_collection_month: float = 1_500       # E48
    pool_maint_month: float = 500               # E49

    tax_cap_rate: float = 0.08                  # F54, for assessed value
    millage_rate: float = 0.017                 # F56
    pilot_in_place: str = "Yes"                 # F58
    pilot_term_years: int = 10                  # F59
    pilot_annual_payment: float = 50_000        # F60
    insurance_per_unit: float = 1_500           # G65

    # -- NOI Calc ----------------------------------------------------------
    tenant_charges_per_unit_month: float = 5    # H6
    pet_fees_per_unit_month: float = 5          # H7
    vacancy_rate: float = 0.07                  # D11
    management_fee_pct: float = 0.035           # D16
    compliance_per_unit: float = 45             # H21
    admin_per_unit: float = 100                 # H22
    replacement_reserve_per_unit: float = 500   # K33

    # -- Construction Estimates -------------------------------------------
    construction: list[ConstructionLine] = field(default_factory=_westbend_construction)
    draw_curve: tuple[float, ...] = DEFAULT_DRAW_CURVE

    # -- Sources & Uses ----------------------------------------------------
    acquisition_cost: float = 4_000_000         # I30
    cdbg: float = 7_500_000                     # I16, soft money already committed
    lhc_home: float = 0                         # I17, soft money already committed
    deferred_gc_fee: float = 0                  # I21
    deferred_fee_pct: float = 0.36              # D22, share of developer fee
    general_requirements_pct: float = 0.06      # D38
    gc_overhead_pct: float = 0.02               # D39
    gc_profit_pct: float = 0.06                 # D40
    contingency_pct: float = 0.05               # D41
    developer_fee_pct: float = 0.15             # I65 = 0.15 * base

    market_analysis: float = 6_000              # I45
    architecture_engineering: float = 750_000   # I46
    environmental_geotech: float = 40_000       # I49
    builders_risk: float = 125_000              # I50
    accounting_fees: float = 40_000             # I51
    appraisal: float = 25_000                   # I53
    title_recording: float = 125_000            # I54
    re_taxes_during_construction: float = 0     # I55
    survey: float = 7_000                       # I56
    marketing_leaseup: float = 75_000           # I57
    ffe_common: float = 40_000                  # I58
    owners_counsel: float = 100_000             # I59
    replacement_reserve_deposit: float = 0      # I69
    insurance_reserves: float = 0               # I70
    hard_cost_at_closing: float = 250_000       # S&U Timing L33

    # HUD unit TDC limits, $/unit by bedroom count and building type.
    # `Sources & Uses` G89:K94 / Dashboard L57:Q62.
    tdc_limits: dict[int, dict[str, float]] = field(default_factory=lambda: {
        0: {"Detached/Semi-Detached": 199618, "Row House": 172976, "Walk-up": 156737, "Elevator": 161035},
        1: {"Detached/Semi-Detached": 258890, "Row House": 227077, "Walk-up": 213098, "Elevator": 225448},
        2: {"Detached/Semi-Detached": 310326, "Row House": 276477, "Walk-up": 269309, "Elevator": 289862},
        3: {"Detached/Semi-Detached": 370970, "Row House": 339946, "Walk-up": 354388, "Elevator": 386483},
        4: {"Detached/Semi-Detached": 437537, "Row House": 404791, "Walk-up": 438588, "Elevator": 483104},
    })

    # -- Tax Credit Calc ---------------------------------------------------
    equity_price: float = 0.80                  # F4
    building_basis_addition: float = 2_000_000  # F8
    federal_grants: float = 0                   # F10
    applicable_fraction: float = 1.0            # F16
    basis_boost: float = 0.0                    # F17
    credit_rate: float = 0.04                   # F20
    gp_credit_share: float = 0.01               # D28, GP share of credits

    # -- Financing Assumptions --------------------------------------------
    construction_rate: float = 0.06             # C11
    construction_origination_pct: float = 0.005 # C12
    construction_legal: float = 45_000          # D13
    construction_servicing_setup: float = 10_000  # D14
    bridge_rate: float = 0.06                   # C18
    bridge_origination_pct: float = 0.01        # C19
    bridge_legal: float = 45_000                # D20
    bridge_servicing_setup: float = 10_000      # D21
    sizing_dscr: float = 1.15                   # C26
    perm_coupon: float = 0.055                  # C28
    perm_amortization_years: int = 40           # C29
    issuer_fee_pct: float = 0.002               # C30
    trustee_fee: float = 5_000                  # C31
    servicing_fee_pct: float = 0.001            # C32
    perm_origination_pct: float = 0.01          # C33
    placement_fee_pct: float = 0.0025           # C34
    perm_legal: float = 45_000                  # D35
    bond_counsel: float = 45_000                # D39
    financial_advisor: float = 35_000           # D40
    trustee_setup: float = 12_500               # D41
    issuer_closing_fee_pct: float = 0.0042      # C42
    bond_issuance_misc: float = 35_000          # D43
    equity_legal: float = 45_000                # D48
    syndication_costs: float = 50_000           # D49
    financing_misc: float = 25_000              # D51

    # Equity pay-in schedule, as {S&U Timing period index: share of equity}.
    # Period 0 is closing, 1-5 preconstruction, 6-23 construction months 1-18,
    # 24 the first stabilised year. The tax-equity bridge loan advances
    # whatever has not yet been paid in, and is repaid at each installment.
    equity_payin: dict[int, float] = field(default_factory=lambda: {
        0: 0.20, 19: 0.50, 24: 0.30,
    })

    # -- Lease-Up Period ---------------------------------------------------
    # Units leased per month, months 1-12. `Lease-Up Period` row 53.
    leaseup_schedule: tuple[float, ...] = (30, 30, 30, 30, 30, 30, 30, 30, 30, 10, 0, 0)
    # Share of each expense that is fixed during lease-up. Row 17-21, col C.
    fixed_share_payroll: float = 1.00
    fixed_share_maintenance: float = 0.00
    fixed_share_utilities: float = 0.75
    fixed_share_admin: float = 1.00
    fixed_share_insurance: float = 1.00

    # -- 17-year Pro Forma -------------------------------------------------
    revenue_growth: float = 0.02                # D48
    expense_growth: float = 0.03                # D49

    # -- Valuation ---------------------------------------------------------
    valuation_cap_rate: float = 0.06            # B22

    # -- screening controls (not in the workbook) --------------------------
    # "workbook" reproduces the file exactly (bond is the balancing plug).
    # "screen"  sizes the bond on DSCR and solves soft money to its minimum.
    mode: str = "screen"
    # Total soft funding obtainable, committed or not. Defaults to what is
    # already committed (cdbg + lhc_home) when left unset.
    soft_money_available: float | None = None

    def committed_soft_money(self) -> float:
        return self.cdbg + self.lhc_home

    def obtainable_soft_money(self) -> float:
        if self.soft_money_available is None:
            return self.committed_soft_money()
        return self.soft_money_available

    def units(self) -> int:
        return sum(u.count for u in self.unit_mix)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DealInputs":
        data = dict(data)
        if "unit_mix" in data:
            data["unit_mix"] = [
                u if isinstance(u, UnitType) else UnitType(**u) for u in data["unit_mix"]
            ]
        if "payroll" in data:
            data["payroll"] = [
                p if isinstance(p, PayrollPosition) else PayrollPosition(**p)
                for p in data["payroll"]
            ]
        if "construction" in data:
            data["construction"] = [
                c if isinstance(c, ConstructionLine) else ConstructionLine(**c)
                for c in data["construction"]
            ]
        if "rent_limits" in data:
            data["rent_limits"] = {float(k): v for k, v in data["rent_limits"].items()}
        if "tdc_limits" in data:
            data["tdc_limits"] = {int(k): v for k, v in data["tdc_limits"].items()}
        if "equity_payin" in data and data["equity_payin"] is not None:
            data["equity_payin"] = {int(k): float(v)
                                    for k, v in data["equity_payin"].items()}
        for key in ("draw_curve", "leaseup_schedule"):
            if key in data and data[key] is not None:
                data[key] = tuple(data[key])
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

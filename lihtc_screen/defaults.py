"""Screening defaults, taken from the underwriting workflow.

Where the workflow document and the workbook disagree, the workflow wins: these
are the rules actually applied when screening a memo. Everything here is a
starting point that a deal-specific value overrides.

Each default records why it is what it is, so the screen can say what it
assumed and the reader can judge whether it holds for this property.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .inputs import DealInputs, PayrollPosition

# -- staffing ------------------------------------------------------------
# One property manager, one leasing agent and one maintenance tech always;
# a second maintenance tech at 100 units, a second leasing agent at 200.
SECOND_MAINTENANCE_AT_UNITS = 100
SECOND_LEASING_AT_UNITS = 200
PROPERTY_MANAGER_RATE = 24.0
LEASING_AGENT_RATE = 18.0
MAINTENANCE_RATE = 20.0

# -- insurance -----------------------------------------------------------
INSURANCE_COASTAL_LA = 1_500.0     # $/unit/yr, coastal Louisiana
INSURANCE_INLAND = 1_000.0         # $/unit/yr, everywhere else

# Louisiana parishes treated as coastal for insurance pricing.
COASTAL_LA_PARISHES = frozenset({
    "orleans", "jefferson", "st. bernard", "st bernard", "plaquemines",
    "st. tammany", "st tammany", "st. charles", "st charles",
    "st. john the baptist", "st john the baptist", "lafourche",
    "terrebonne", "st. mary", "st mary", "iberia", "vermilion",
    "cameron", "calcasieu", "assumption", "st. james", "st james",
})
COASTAL_LA_CITIES = frozenset({
    "new orleans", "metairie", "kenner", "houma", "thibodaux", "slidell",
    "lake charles", "morgan city", "new iberia", "chalmette", "gretna",
})

# -- contract services ---------------------------------------------------
ELEVATOR_MAINTENANCE_PER_SET_MONTH = 250.0
POOL_MAINTENANCE_MONTH = 500.0
PEST_CONTROL_PER_UNIT_YEAR = 20.0

# -- soft costs ----------------------------------------------------------
ARCHITECTURE_PCT_OF_HARD = 0.025    # A&E, 2.5% of hard cost
BUILDERS_RISK_PCT_OF_HARD = 0.01    # builder's risk, 1% of hard cost

# -- reserves and lease-up ------------------------------------------------
REPLACEMENT_RESERVE_PER_UNIT = 500.0
LEASEUP_TARGET_MONTH = 12           # 100% occupancy by month 12


def is_coastal_louisiana(state: str | None, parish: str | None,
                         city: str | None) -> bool:
    """Whether a property prices insurance at the coastal Louisiana rate."""
    if (state or "").strip().lower() not in ("la", "louisiana"):
        return False
    if parish and parish.strip().lower().replace(" parish", "") in COASTAL_LA_PARISHES:
        return True
    return bool(city and city.strip().lower() in COASTAL_LA_CITIES)


def staffing(units: int) -> list[PayrollPosition]:
    """Site staffing for a property of this size."""
    maintenance = 2 if units >= SECOND_MAINTENANCE_AT_UNITS else 1
    leasing = 2 if units >= SECOND_LEASING_AT_UNITS else 1
    return [
        PayrollPosition("Property Manager", 1, PROPERTY_MANAGER_RATE),
        PayrollPosition("Leasing Agent", leasing, LEASING_AGENT_RATE),
        PayrollPosition("Maintenance Staff", maintenance, MAINTENANCE_RATE),
    ]


def leaseup_schedule(units: int, months: int = LEASEUP_TARGET_MONTH) -> tuple[float, ...]:
    """Lease at an even pace that reaches full occupancy by the target month."""
    if units <= 0 or months <= 0:
        return tuple([0.0] * 12)
    per_month = units / months
    schedule = [per_month] * months
    # Absorb rounding into the final month so the schedule totals exactly.
    schedule[-1] += units - sum(schedule)
    return tuple(schedule + [0.0] * (12 - months))[:12]


@dataclass
class Assumption:
    """A default the screen applied, and the reason it applied it."""
    field: str
    label: str
    value: float | str
    basis: str


@dataclass
class AppliedDefaults:
    deal: DealInputs
    assumptions: list[Assumption] = field(default_factory=list)


def apply(deal: DealInputs, *, state: str | None = None, parish: str | None = None,
          city: str | None = None, has_pool: bool | None = None,
          elevator_sets: int = 0, provided: set[str] | None = None) -> AppliedDefaults:
    """Fill unspecified inputs with the workflow's screening defaults.

    `provided` names fields the deal supplied explicitly; those are left alone.
    Returns the deal alongside a record of every assumption made.
    """
    provided = provided or set()
    applied = AppliedDefaults(deal=deal)
    units = deal.units()

    def note(field_name, label, value, basis):
        applied.assumptions.append(Assumption(field_name, label, value, basis))

    # -- staffing ---------------------------------------------------------
    if "payroll" not in provided:
        deal.payroll = staffing(units)
        plural = {"Property Manager": "property managers",
                  "Leasing Agent": "leasing agents",
                  "Maintenance Staff": "maintenance techs"}
        detail = ", ".join(
            f"{int(p.count)} "
            + (plural[p.title] if p.count != 1 else p.title.lower())
            for p in deal.payroll)
        note("payroll", "Site staffing", detail,
             f"{units} units: 1 manager, plus a second maintenance tech at "
             f"{SECOND_MAINTENANCE_AT_UNITS} units and a second leasing agent at "
             f"{SECOND_LEASING_AT_UNITS}")

    # -- insurance --------------------------------------------------------
    if "insurance_per_unit" not in provided:
        coastal = is_coastal_louisiana(state, parish, city)
        deal.insurance_per_unit = INSURANCE_COASTAL_LA if coastal else INSURANCE_INLAND
        note("insurance_per_unit", "Property insurance",
             f"${deal.insurance_per_unit:,.0f}/unit/yr",
             "coastal Louisiana" if coastal
             else "not coastal Louisiana - confirm against a real quote")

    # -- contract services -------------------------------------------------
    if "pest_control_month" not in provided:
        deal.pest_control_month = PEST_CONTROL_PER_UNIT_YEAR * units / 12
        note("pest_control_month", "Pest control",
             f"${deal.pest_control_month * 12:,.0f}/yr",
             f"${PEST_CONTROL_PER_UNIT_YEAR:.0f}/unit/yr x {units} units")

    if "elevator_maint_month" not in provided:
        deal.elevator_maint_month = ELEVATOR_MAINTENANCE_PER_SET_MONTH * elevator_sets
        if elevator_sets:
            note("elevator_maint_month", "Elevator maintenance",
                 f"${deal.elevator_maint_month:,.0f}/mo",
                 f"${ELEVATOR_MAINTENANCE_PER_SET_MONTH:.0f}/mo x {elevator_sets} sets")

    if "pool_maint_month" not in provided:
        pool = has_pool if has_pool is not None else _has_line(deal, "pool")
        deal.pool_maint_month = POOL_MAINTENANCE_MONTH if pool else 0.0
        note("pool_maint_month", "Pool maintenance",
             f"${deal.pool_maint_month:,.0f}/mo",
             "pool on site" if pool else "no pool")

    # -- property taxes ----------------------------------------------------
    if "pilot_in_place" not in provided:
        deal.pilot_in_place = "No"
        note("pilot_in_place", "PILOT", "none assumed",
             "no PILOT assumed until one is confirmed; a PILOT is a lever that "
             "can move a marginal deal")

    # -- reserves and lease-up ---------------------------------------------
    if "replacement_reserve_per_unit" not in provided:
        deal.replacement_reserve_per_unit = REPLACEMENT_RESERVE_PER_UNIT
        note("replacement_reserve_per_unit", "Replacement reserves",
             f"${REPLACEMENT_RESERVE_PER_UNIT:,.0f}/unit/yr", "acq/rehab standard")

    if "leaseup_schedule" not in provided:
        deal.leaseup_schedule = leaseup_schedule(units)
        note("leaseup_schedule", "Lease-up", f"100% by month {LEASEUP_TARGET_MONTH}",
             f"{units / LEASEUP_TARGET_MONTH:,.0f} units/month")

    return applied


def _has_line(deal: DealInputs, key: str) -> bool:
    return any(l.key == key and l.unit_cost * l.quantity > 0 for l in deal.construction)


def derived_soft_costs(deal: DealInputs, hard_cost: float,
                       provided: set[str] | None = None) -> list[Assumption]:
    """Soft costs the workflow derives from hard cost rather than quoting flat."""
    provided = provided or set()
    notes: list[Assumption] = []
    if "architecture_engineering" not in provided:
        deal.architecture_engineering = ARCHITECTURE_PCT_OF_HARD * hard_cost
        notes.append(Assumption(
            "architecture_engineering", "Architecture & engineering",
            f"${deal.architecture_engineering:,.0f}",
            f"{ARCHITECTURE_PCT_OF_HARD:.1%} of hard cost"))
    if "builders_risk" not in provided:
        deal.builders_risk = BUILDERS_RISK_PCT_OF_HARD * hard_cost
        notes.append(Assumption(
            "builders_risk", "Builder's risk insurance",
            f"${deal.builders_risk:,.0f}",
            f"{BUILDERS_RISK_PCT_OF_HARD:.1%} of hard cost"))
    return notes

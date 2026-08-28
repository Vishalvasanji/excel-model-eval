"""`Sources & Uses` - the development budget and the capital stack."""

from __future__ import annotations

from dataclasses import dataclass

from ..inputs import DealInputs
from .construction import AMENITY_KEYS
from .unitmix import UnitMix

# `Sources & Uses` I52 - fixed LHC application/allocation fees, plus 10% of the
# annual credit amount.
LHC_FIXED_FEES = 4_000 + 6_000 + 6_000 + 3_000 + 500
LHC_CREDIT_FEE_PCT = 0.10


@dataclass
class SourcesUses:
    # uses
    acquisition: float = 0.0            # I30
    onsite_improvements: float = 0.0    # I34
    special_site: float = 0.0           # I35
    residential: float = 0.0            # I36
    community_facilities: float = 0.0   # I37
    general_requirements: float = 0.0   # I38
    gc_overhead: float = 0.0            # I39
    gc_profit: float = 0.0              # I40
    contingency: float = 0.0            # I41
    hard_costs: float = 0.0             # I43
    soft_costs: float = 0.0             # I61
    construction_costs: float = 0.0     # I63
    developer_fee: float = 0.0          # I65
    operating_reserve: float = 0.0      # I67
    interest_reserve: float = 0.0       # I68
    reserves: float = 0.0               # I72
    capitalised_interest: float = 0.0   # I74
    financing_fees: float = 0.0         # I76
    total_uses: float = 0.0             # I78

    # sources
    bonds: float = 0.0                  # I12
    tax_credit_equity: float = 0.0      # I14
    soft_money: float = 0.0             # I19
    deferred_fees: float = 0.0          # I24
    deferred_developer_fee: float = 0.0 # I22
    total_sources: float = 0.0          # I26

    balance: float = 0.0                # I80 = uses - sources
    builder_fee_base: float = 0.0       # I81
    developer_fee_base: float = 0.0     # I82
    tdc_limit_per_unit: float = 0.0     # I85
    tdc_limit_total: float = 0.0        # I86
    soft_cost_detail: dict = None


def hard_costs(deal: DealInputs, amounts: dict[str, float]) -> dict[str, float]:
    """Hard-cost block I34:I43, including the GC fee fixed point.

    General requirements, overhead and profit are percentages of I81, which is
    itself the hard-cost total net of those same three fees, and contingency is
    a percentage of everything above it. The workbook resolves this by
    iteration; it has a closed form, derived here.

    Let D be the direct construction lines and f = genreq + overhead + profit:
        I81 = D + contingency
        contingency = c * (D + f * I81)
        => I81 = D * (1 + c) / (1 - c * f)
    """
    direct_onsite = amounts.get("sitework", 0.0)
    direct_special = amounts.get("abatement", 0.0)
    direct_residential = amounts.get("demolition", 0.0) + amounts.get("units", 0.0)
    direct_community = sum(amounts.get(k, 0.0) for k in AMENITY_KEYS)

    # `Sources & Uses` I34:I37 omit `Construction Estimates` G9, so an elevator
    # building's shafts never reach the budget. Reproduced in workbook mode.
    elevators = amounts.get("elevators", 0.0)
    if deal.mode != "workbook":
        direct_community += elevators

    direct = direct_onsite + direct_special + direct_residential + direct_community

    f = (deal.general_requirements_pct + deal.gc_overhead_pct + deal.gc_profit_pct)
    c = deal.contingency_pct
    base = direct * (1 + c) / (1 - c * f) if (1 - c * f) else direct

    genreq = deal.general_requirements_pct * base
    overhead = deal.gc_overhead_pct * base
    profit = deal.gc_profit_pct * base
    contingency = c * (direct + genreq + overhead + profit)
    total = direct + genreq + overhead + profit + contingency

    return {
        "onsite_improvements": direct_onsite,
        "special_site": direct_special,
        "residential": direct_residential,
        "community_facilities": direct_community,
        "general_requirements": genreq,
        "gc_overhead": overhead,
        "gc_profit": profit,
        "contingency": contingency,
        "hard_costs": total,
        "builder_fee_base": base,
        "elevators_excluded": elevators if deal.mode == "workbook" else 0.0,
    }


def soft_costs(deal: DealInputs, hard: float, annual_credit: float) -> dict[str, float]:
    """Soft-cost block I45:I61."""
    detail = {
        "market_analysis": deal.market_analysis,
        "architecture_engineering": deal.architecture_engineering,
        "plan_review": max(60.0, 0.001 * hard),              # I47
        "permit_row_impact": 60.0 + 0.005 * hard,            # I48
        "environmental_geotech": deal.environmental_geotech,
        "builders_risk": deal.builders_risk,
        "accounting_fees": deal.accounting_fees,
        "lhc_fees": LHC_FIXED_FEES + LHC_CREDIT_FEE_PCT * annual_credit,  # I52
        "appraisal": deal.appraisal,
        "title_recording": deal.title_recording,
        "re_taxes_during_construction": deal.re_taxes_during_construction,
        "survey": deal.survey,
        "marketing_leaseup": deal.marketing_leaseup,
        "ffe_common": deal.ffe_common,
        "owners_counsel": deal.owners_counsel,
    }
    detail["total"] = sum(detail.values())
    return detail


def tdc_limit(deal: DealInputs, mix: UnitMix) -> tuple[float, float]:
    """HUD unit TDC limit for the mix. `Sources & Uses` H99:H100."""
    total = 0.0
    for bedrooms, count in mix.units_by_bedroom().items():
        row = deal.tdc_limits.get(bedrooms) or {}
        total += count * row.get(deal.building_type, 0.0)
    per_unit = total / mix.units if mix.units else 0.0
    return per_unit, total


def compute(deal: DealInputs, mix: UnitMix, *, amounts: dict[str, float],
            annual_credit: float, reserves: float, operating_reserve: float,
            interest_reserve: float, capitalised_interest: float,
            financing_fees: float, bonds: float, equity: float) -> SourcesUses:
    su = SourcesUses()
    su.acquisition = deal.acquisition_cost

    hard = hard_costs(deal, amounts)
    for key in ("onsite_improvements", "special_site", "residential",
                "community_facilities", "general_requirements", "gc_overhead",
                "gc_profit", "contingency", "builder_fee_base"):
        setattr(su, key, hard[key])
    su.hard_costs = hard["hard_costs"]

    soft = soft_costs(deal, su.hard_costs, annual_credit)
    su.soft_cost_detail = soft
    su.soft_costs = soft["total"]
    su.construction_costs = su.hard_costs + su.soft_costs

    su.operating_reserve = operating_reserve
    su.interest_reserve = interest_reserve
    su.reserves = reserves
    su.capitalised_interest = capitalised_interest
    su.financing_fees = financing_fees

    # I65 = 15% of I82, and I82 is total uses net of the fee itself. Solved
    # directly rather than iterated:
    #   base = uses_ex_fee + fee - acq - fee - reserves - synd
    #   fee  = pct * base  =>  fee = pct * (uses_ex_fee - acq - reserves - synd)
    uses_ex_fee = (su.acquisition + su.construction_costs + su.reserves
                   + su.capitalised_interest + su.financing_fees)
    su.developer_fee_base = (uses_ex_fee - su.acquisition - su.reserves
                             - deal.syndication_costs)
    su.developer_fee = deal.developer_fee_pct * su.developer_fee_base
    su.total_uses = uses_ex_fee + su.developer_fee

    su.bonds = bonds
    su.tax_credit_equity = equity
    su.soft_money = deal.cdbg + deal.lhc_home
    su.deferred_developer_fee = deal.deferred_fee_pct * su.developer_fee
    su.deferred_fees = deal.deferred_gc_fee + su.deferred_developer_fee
    su.total_sources = (su.bonds + su.tax_credit_equity + su.soft_money
                        + su.deferred_fees)
    su.balance = su.total_uses - su.total_sources

    su.tdc_limit_per_unit, su.tdc_limit_total = tdc_limit(deal, mix)
    return su

"""`Construction Estimates` - the nine hard-cost line items and the draw curve."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..inputs import DealInputs
from .unitmix import UnitMix

# Lines that roll up into `Sources & Uses` I37, "Community Facilities", and are
# netted out of the per-unit construction line (`Construction Estimates` G7).
AMENITY_KEYS = ("clubhouse", "pool", "sports_courts", "playground")


@dataclass
class Construction:
    amounts: dict[str, float] = field(default_factory=dict)  # G4:G12 by key
    vertical: float = 0.0        # G13, total vertical construction
    general_requirements: float = 0.0  # G14
    overhead: float = 0.0        # G15
    profit: float = 0.0          # G16
    contingency: float = 0.0     # G17
    hard_cost: float = 0.0       # G18


def compute(deal: DealInputs, mix: UnitMix,
            general_requirements: float, overhead: float,
            profit: float, contingency: float) -> Construction:
    """Line amounts plus the GC fees, which come back from `Sources & Uses`."""
    c = Construction()
    for line in deal.construction:
        qty = mix.units if line.basis == "per_unit" else line.quantity
        c.amounts[line.key] = line.unit_cost * qty

    # G7 nets the amenity buildings out of the blended per-unit cost, so the
    # per-unit figure can be quoted all-in without double counting them.
    amenities = sum(c.amounts.get(k, 0.0) for k in AMENITY_KEYS)
    c.amounts["units"] = c.amounts.get("units", 0.0) - amenities

    c.vertical = sum(c.amounts.values())
    c.general_requirements = general_requirements
    c.overhead = overhead
    c.profit = profit
    c.contingency = contingency
    c.hard_cost = (c.vertical + general_requirements + overhead
                   + profit + contingency)
    return c


def draw_share(deal: DealInputs, month: int) -> float:
    """Share of hard cost drawn in construction month `month` (1-18)."""
    curve = deal.draw_curve
    return curve[month] if 0 <= month < len(curve) else 0.0

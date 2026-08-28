"""`Unit Mix+Rents` - unit counts, rent limits, utility allowances, net rents."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..inputs import DealInputs


@dataclass
class UnitLine:
    bedrooms: int
    sqft: float
    count: int
    ami_pct: float
    gross_rent: float        # col K, the MTSP gross rent limit
    utility_allowance: float # col L
    net_rent: float          # col J = K - L


@dataclass
class UnitMix:
    lines: list[UnitLine] = field(default_factory=list)
    units: int = 0                    # D14
    total_sqft: float = 0.0           # C14
    monthly_net_rent: float = 0.0     # J14
    monthly_gross_rent: float = 0.0   # K14
    monthly_ua: float = 0.0           # L14
    weighted_ami: float = 0.0         # I14

    def units_by_bedroom(self) -> dict[int, int]:
        out: dict[int, int] = {}
        for line in self.lines:
            out[line.bedrooms] = out.get(line.bedrooms, 0) + line.count
        return out


def _utility_allowance(deal: DealInputs, bedrooms: int) -> float:
    """Total utility allowance for a bedroom count.

    `Unit Mix+Rents` L4: HLOOKUP(bedrooms, B32:F37, 6) - row 6 of that range is
    the Total row, i.e. the sum of the individual utility lines.
    """
    idx = min(max(bedrooms, 0), 4)
    return (deal.ua_electricity[idx] + deal.ua_water[idx]
            + deal.ua_sewer[idx] + deal.ua_trash[idx])


def _gross_rent(deal: DealInputs, bedrooms: int, ami_pct: float) -> float:
    """MTSP gross rent limit.

    `Unit Mix+Rents` K4: VLOOKUP(ami, A20:F27, bedrooms + 2, FALSE) - an exact
    match on the AMI band, then the column for that bedroom count.
    """
    row = deal.rent_limits.get(round(ami_pct, 4))
    if row is None:
        # The workbook's exact-match VLOOKUP returns #N/A here. Say which band
        # is missing instead: a supplied table often covers only the bands the
        # deal actually uses, and the fix is to add the one named.
        have = ", ".join(f"{b:.0%}" for b in sorted(deal.rent_limits))
        raise KeyError(
            f"no gross rent limit for {ami_pct:.0%} AMI (the table has {have}). "
            f"Add that band to rent_limits, or set the unit type's ami_pct to a "
            f"band the table covers.")
    return row[min(max(bedrooms, 0), 4)]


def compute(deal: DealInputs) -> UnitMix:
    mix = UnitMix()
    for unit in deal.unit_mix:
        if unit.count <= 0:
            # An empty row contributes nothing, so it does not need a rent limit
            # to exist for its band. The workbook carries such rows as scaffolding
            # for bands a deal may or may not use.
            continue
        ua = _utility_allowance(deal, unit.bedrooms)
        gross = _gross_rent(deal, unit.bedrooms, unit.ami_pct)
        mix.lines.append(UnitLine(
            bedrooms=unit.bedrooms, sqft=unit.sqft, count=unit.count,
            ami_pct=unit.ami_pct, gross_rent=gross,
            utility_allowance=ua, net_rent=gross - ua,
        ))

    mix.units = sum(l.count for l in mix.lines)
    mix.total_sqft = sum(l.sqft * l.count for l in mix.lines)
    mix.monthly_net_rent = sum(l.count * l.net_rent for l in mix.lines)
    mix.monthly_gross_rent = sum(l.count * l.gross_rent for l in mix.lines)
    mix.monthly_ua = sum(l.count * l.utility_allowance for l in mix.lines)
    if mix.units:
        mix.weighted_ami = sum(l.ami_pct * l.count for l in mix.lines) / mix.units
    return mix

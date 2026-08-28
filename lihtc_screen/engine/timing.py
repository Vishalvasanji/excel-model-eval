"""`S&U Timing` and the construction/bridge blocks of `Loan Amortization`.

25 periods, matching columns G:AE of the sheet:
    0       closing
    1-5     preconstruction
    6-23    construction months 1-18, drawn on the `Construction Estimates` curve
    24      the first stabilised year

Bond draws and capitalised interest are mutually dependent within each period:
the bond funds whatever uses the other sources do not, and interest accrues on
what the bond has drawn, which is itself part of uses. The workbook resolves
this by iteration; it is solved directly here (see `_period_interest`).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..inputs import DealInputs

N_PERIODS = 25
CLOSING = 0
PRECONSTRUCTION = range(1, 6)
CONSTRUCTION = range(6, 24)      # 18 months
STABILISED = 24

SOFT_COST_AT_CLOSING = 0.60      # G34


@dataclass
class Timing:
    bond_draws: list[float] = field(default_factory=list)          # row 10
    bond_balance: list[float] = field(default_factory=list)        # row 51
    construction_interest: list[float] = field(default_factory=list)  # row 41
    bridge_interest: list[float] = field(default_factory=list)     # row 42
    bond_total: float = 0.0              # D10, sum over periods 0-23
    bridge_total: float = 0.0            # D11
    capitalised_interest: float = 0.0    # D44
    capitalised_construction: float = 0.0  # D41
    capitalised_bridge: float = 0.0      # D42


def _draw(deal: DealInputs, period: int) -> float:
    """Share of a construction-period total drawn in `period`."""
    if period not in CONSTRUCTION:
        return 0.0
    # curve index 0 is month 0; construction period 6 is month 1.
    idx = period - 5
    curve = deal.draw_curve
    return curve[idx] if idx < len(curve) else 0.0


def _period_interest(balance: float, base_uses: float, other_sources: float,
                     rate: float) -> tuple[float, float]:
    """Interest and bond draw for one period, solved rather than iterated.

        draw     = base_uses + interest - other_sources
        interest = (balance + draw) * rate
    =>  interest = (balance + base_uses - other_sources) * rate / (1 - rate)
    """
    if rate >= 1:
        raise ValueError("period interest rate must be below 100%")
    interest = (balance + base_uses - other_sources) * rate / (1 - rate)
    draw = base_uses + interest - other_sources
    return interest, draw


def compute(deal: DealInputs, *, acquisition: float, hard_costs: float,
            soft_costs: float, developer_fee: float, reserves: float,
            financing_fees: float, equity: float, deferred_fee: float) -> Timing:
    t = Timing()

    payin = {p: equity * share for p, share in deal.equity_payin.items()}
    # The bridge advances whatever equity has not been paid in by the time
    # construction draws begin (`S&U Timing` row 11 is sized off $L$52, the
    # outstanding equity at the end of preconstruction).
    paid_in_by_preconstruction = sum(
        amount for p, amount in payin.items() if p <= PRECONSTRUCTION[-1])
    bridge_total = equity - paid_in_by_preconstruction
    soft_at_close = SOFT_COST_AT_CLOSING * soft_costs
    soft_preconstruction = (soft_costs - soft_at_close) / len(PRECONSTRUCTION)
    hard_at_close = min(deal.hard_cost_at_closing, hard_costs)

    bond_balance = 0.0
    bridge_balance = 0.0

    for p in range(N_PERIODS):
        share = _draw(deal, p)
        monthly = p != STABILISED

        # -- uses for this period (rows 32-37, 39, 46) ---------------------
        uses = 0.0
        if p == CLOSING:
            uses += acquisition + soft_at_close + financing_fees
        elif p in PRECONSTRUCTION:
            uses += soft_preconstruction
            if p == PRECONSTRUCTION[-1]:
                uses += hard_at_close
        if share:
            uses += (hard_costs - hard_at_close) * share + developer_fee * share
        if p == max(CONSTRUCTION):
            uses += reserves

        # -- non-bond sources for this period (rows 11, 12, 16, 18, 19, 24) -
        bridge_draw = bridge_total * share
        equity_in = payin.get(p, 0.0)
        # Each equity installment pays down the bridge that stood in for it.
        bridge_payback = -equity_in if p > PRECONSTRUCTION[-1] else 0.0
        soft_money = (deal.cdbg + deal.lhc_home) * share
        deferred = deferred_fee * share
        other = bridge_draw + bridge_payback + equity_in + soft_money + deferred

        # -- bridge interest (independent of the bond draw) -----------------
        rate_b = deal.bridge_rate / 12 if monthly else deal.bridge_rate
        bridge_interest = (bridge_balance + bridge_draw) * rate_b
        bridge_balance += bridge_draw + bridge_payback

        # -- bond draw and construction interest, solved together -----------
        rate_c = deal.construction_rate / 12 if monthly else deal.construction_rate
        if p == STABILISED:
            # The stabilised column offsets its own capitalised interest
            # against reserves, so it neither draws nor funds anything.
            interest, draw = 0.0, 0.0
        else:
            interest, draw = _period_interest(
                bond_balance, uses + bridge_interest, other, rate_c)

        t.construction_interest.append(interest)
        t.bridge_interest.append(bridge_interest)
        t.bond_draws.append(draw)
        bond_balance += draw
        t.bond_balance.append(bond_balance)

    # D10/D41/D42 sum periods 0-23; the stabilised column is excluded.
    live = slice(0, STABILISED)
    t.bond_total = sum(t.bond_draws[live])
    t.bridge_total = bridge_total
    t.capitalised_construction = sum(t.construction_interest[live])
    t.capitalised_bridge = sum(t.bridge_interest[live])
    t.capitalised_interest = t.capitalised_construction + t.capitalised_bridge
    return t

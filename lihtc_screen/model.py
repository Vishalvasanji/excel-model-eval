"""Runs the whole model, resolving the circular loop the workbook iterates.

The workbook has a deliberate circular reference (`calcPr iterate="1"`): total
development cost drives the developer fee, the draw schedule and the reserves;
those drive capitalised interest and financing fees; and those feed back into
total development cost. Excel settles it by iteration and so does `solve`,
running the sheets in dependency order until total uses stops moving.

Two modes:

  "workbook"  reproduces `reference/Acq_Rehab_Model_v1.xlsx` exactly. The bond
              is the balancing plug and soft money is a fixed input. Used by the
              parity tests, and available for auditing a deal against the file.

  "screen"    the underwriting workflow. The bond is sized on DSCR and soft
              money becomes the residual: how much subsidy the deal needs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .inputs import DealInputs
from .engine import (construction, expenses, financing, leaseup, loans, noi,
                     proforma, sources_uses, timing, unitmix, valuation,
                     waterfall)

MAX_ITERATIONS = 400
NOI_MAX_ITERATIONS = 200
TOLERANCE = 1e-7        # dollars of movement in total uses


@dataclass
class Result:
    """Everything the model computes, one attribute per sheet."""
    deal: DealInputs
    mix: unitmix.UnitMix
    expenses: expenses.Expenses
    noi: noi.NOI
    construction: construction.Construction
    sources_uses: sources_uses.SourcesUses
    timing: timing.Timing
    financing: financing.Financing
    tax_credit: Any
    perm_loan: loans.PermLoan
    leaseup: leaseup.LeaseUp
    proforma: proforma.ProForma
    reserves: waterfall.ReserveRequirement
    waterfall: waterfall.Waterfall
    valuation: valuation.Valuation
    iterations: int = 0
    converged: bool = False
    # Total soft funding the deal needs: the gap left after DSCR-sized debt,
    # LIHTC equity and deferred fees.
    required_soft_money: float = 0.0
    # What is already committed, and the two ways that can differ from the need.
    committed_soft_money: float = 0.0
    additional_soft_money_needed: float = 0.0
    soft_money_surplus: float = 0.0

    # -- headline figures --------------------------------------------------
    @property
    def units(self) -> int:
        return self.mix.units

    @property
    def total_development_cost(self) -> float:
        return self.sources_uses.total_uses

    @property
    def tdc_per_unit(self) -> float:
        return self.total_development_cost / self.units if self.units else 0.0

    @property
    def min_dscr(self) -> float:
        series = self.proforma.dscr_years_2_17()
        return min(series) if series else 0.0

    @property
    def max_dscr(self) -> float:
        series = self.proforma.dscr_years_2_17()
        return max(series) if series else 0.0

    @property
    def min_dscr_year(self) -> int:
        series = self.proforma.dscr_years_2_17()
        return series.index(min(series)) + 2 if series else 0

    @property
    def max_dscr_year(self) -> int:
        series = self.proforma.dscr_years_2_17()
        return series.index(max(series)) + 2 if series else 0

    @property
    def cumulative_cash_year_15(self) -> float:
        return sum(self.proforma.cash_after_fees[1:15])

    @property
    def stabilised_noi(self) -> float:
        return self.proforma.noi[1] if len(self.proforma.noi) > 1 else 0.0


def solve(deal: DealInputs) -> Result:
    """Run the model to convergence."""
    mix = unitmix.compute(deal)

    # Circular quantities, seeded at zero and refined each pass.
    state = dict(
        noi_for_tax=0.0, bond=0.0, equity=0.0, annual_credit=0.0,
        reserves=0.0, operating_reserve=0.0, interest_reserve=0.0,
        capitalised_interest=0.0, financing_fees=0.0, total_uses=0.0,
        soft_money=None if deal.mode == "screen" else None,
    )
    if deal.mode == "screen":
        state["soft_money"] = deal.cdbg + deal.lhc_home

    # The DSCR-sized loan depends only on NOI and the debt terms, neither of
    # which moves with total development cost, so it is solved once rather than
    # re-bisected on every pass of the loop.
    sized_loan = None
    if deal.mode != "workbook":
        seed_exp, seed_noi = stabilised_noi(deal, mix)
        sized_loan = _dscr_sized_loan(deal, mix, seed_noi, seed_exp)

    iterations = 0
    converged = False
    for iterations in range(1, MAX_ITERATIONS + 1):
        previous = state["total_uses"]

        # -- property level -------------------------------------------------
        exp, n = stabilised_noi(deal, mix)
        state["noi_for_tax"] = n.noi

        # -- development budget ---------------------------------------------
        cst = construction.compute(deal, mix, 0, 0, 0, 0)
        su = sources_uses.compute(
            deal, mix,
            amounts=cst.amounts,
            annual_credit=state["annual_credit"],
            reserves=state["reserves"],
            operating_reserve=state["operating_reserve"],
            interest_reserve=state["interest_reserve"],
            capitalised_interest=state["capitalised_interest"],
            financing_fees=state["financing_fees"],
            bonds=state["bond"],
            equity=state["equity"],
            soft_money=state["soft_money"],
        )
        cst = construction.compute(deal, mix, su.general_requirements,
                                   su.gc_overhead, su.gc_profit, su.contingency)

        # -- debt sizing -----------------------------------------------------
        if deal.mode == "workbook":
            # The bond funds whatever the other sources do not, period by period.
            bond = state["bond"]
        else:
            bond = sized_loan

        fin = financing.compute(deal, bond, n.sizing_noi)

        # -- draw schedule and capitalised interest --------------------------
        tm = timing.compute(
            deal,
            acquisition=su.acquisition, hard_costs=su.hard_costs,
            soft_costs=su.soft_costs, developer_fee=su.developer_fee,
            reserves=su.reserves, financing_fees=fin.total_fees,
            equity=state["equity"], deferred_fee=su.deferred_fees,
            soft_money=su.soft_money,
        )
        if deal.mode == "workbook":
            bond = tm.bond_total
            fin = financing.compute(deal, bond, n.sizing_noi)

        # -- equity -----------------------------------------------------------
        tc = taxcredit_compute(deal, su, state["bond"], state["equity"], fin)

        # -- cash flows -------------------------------------------------------
        lu = leaseup.compute(deal, mix, n, exp, bond)
        perm = loans.compute(deal, bond)
        pf = proforma.compute(deal, lu, n, perm)
        reserve_req = waterfall.size_reserves(lu, pf.opex[1] if len(pf.opex) > 1 else 0.0)

        # In screen mode the subsidy requirement is itself part of the loop:
        # it is whatever the priced stack cannot cover, and it feeds the basis.
        if deal.mode == "screen":
            state["soft_money"] = max(
                0.0, su.total_uses - bond - tc.equity - su.deferred_fees)

        # -- feed back ---------------------------------------------------------
        state.update(
            bond=bond,
            equity=tc.equity,
            annual_credit=tc.annual_credit,
            operating_reserve=reserve_req.operating,
            interest_reserve=reserve_req.interest,
            reserves=(reserve_req.total + deal.replacement_reserve_deposit
                      + deal.insurance_reserves),
            capitalised_interest=tm.capitalised_interest,
            financing_fees=fin.total_fees,
            total_uses=su.total_uses,
        )

        if abs(su.total_uses - previous) < TOLERANCE:
            converged = True
            break

    # -- final pass, so every sheet reflects the converged inputs -------------
    exp, n = stabilised_noi(deal, mix)
    cst = construction.compute(deal, mix, 0, 0, 0, 0)
    su = sources_uses.compute(
        deal, mix, amounts=cst.amounts, annual_credit=state["annual_credit"],
        reserves=state["reserves"], operating_reserve=state["operating_reserve"],
        interest_reserve=state["interest_reserve"],
        capitalised_interest=state["capitalised_interest"],
        financing_fees=state["financing_fees"], bonds=state["bond"],
        equity=state["equity"], soft_money=state["soft_money"],
    )
    cst = construction.compute(deal, mix, su.general_requirements, su.gc_overhead,
                               su.gc_profit, su.contingency)
    fin = financing.compute(deal, state["bond"], n.sizing_noi)
    tm = timing.compute(
        deal, acquisition=su.acquisition, hard_costs=su.hard_costs,
        soft_costs=su.soft_costs, developer_fee=su.developer_fee,
        reserves=su.reserves, financing_fees=fin.total_fees,
        equity=state["equity"], deferred_fee=su.deferred_fees,
        soft_money=su.soft_money,
    )
    tc = taxcredit_compute(deal, su, state["bond"], state["equity"], fin)
    lu = leaseup.compute(deal, mix, n, exp, state["bond"])
    perm = loans.compute(deal, state["bond"])
    pf = proforma.compute(deal, lu, n, perm)
    reserve_req = waterfall.size_reserves(lu, pf.opex[1] if len(pf.opex) > 1 else 0.0)
    wf = waterfall.compute(deal, pf, su.deferred_fees, su.soft_money, reserve_req.total)
    val = valuation.compute(deal, pf, perm, wf)

    result = Result(
        deal=deal, mix=mix, expenses=exp, noi=n, construction=cst,
        sources_uses=su, timing=tm, financing=fin, tax_credit=tc,
        perm_loan=perm, leaseup=lu, proforma=pf, reserves=reserve_req,
        waterfall=wf, valuation=val, iterations=iterations, converged=converged,
    )

    # The subsidy the deal needs is whatever priced debt, equity and deferred
    # fees cannot cover. A negative gap means the priced stack alone over-funds
    # the budget and no subsidy is needed at all.
    gap = su.total_uses - (su.bonds + su.tax_credit_equity + su.deferred_fees)
    committed = deal.committed_soft_money()
    result.required_soft_money = max(0.0, gap)
    result.committed_soft_money = committed
    result.additional_soft_money_needed = max(0.0, result.required_soft_money - committed)
    result.soft_money_surplus = max(0.0, committed - result.required_soft_money)
    return result


def stabilised_noi(deal: DealInputs, mix):
    """Operating expenses and NOI, with the property-tax loop resolved.

    Without a PILOT the tax is millage on a value capitalised from NOI, and NOI
    is net of that tax, so the two have to settle against each other. With a
    PILOT the tax is a fixed payment and this converges on the first pass.
    """
    noi_estimate = 0.0
    exp = n = None
    for _ in range(NOI_MAX_ITERATIONS):
        exp = expenses.compute(deal, mix, noi_estimate)
        n = noi.compute(deal, mix, exp)
        if abs(n.noi - noi_estimate) < TOLERANCE:
            break
        noi_estimate = n.noi
    return exp, n


def _dscr_sized_loan(deal, mix, n, exp) -> float:
    """Largest loan whose DSCR holds the floor in every year, 2-17.

    `Financing Assumptions` C36 sizes on year-2 NOI alone, which is both too
    little and too much: too little because years 2-3 are interest-only, so the
    binding year is year 4 when amortisation starts; too much because NOI trends
    and the floor has to hold in every year, not the first one.

    Taking the largest loan that holds the floor is what minimises the subsidy
    the deal needs - every dollar of debt the property can carry is a dollar of
    soft funding it does not have to ask for. It also pulls the later years down
    off the QAP's DSCR ceiling, which is the constraint that actually binds here:
    NOI grows faster than level debt service, so DSCR rises over the term.
    """
    floor = deal.sizing_dscr

    def min_dscr(amount: float) -> float:
        if amount <= 0:
            return float("inf")
        lu = leaseup.compute(deal, mix, n, exp, amount)
        perm = loans.compute(deal, amount)
        pf = proforma.compute(deal, lu, n, perm)
        series = pf.dscr_years_2_17()
        return min(series) if series else 0.0

    # Start from the workbook's year-2 sizing and bracket outward.
    start = financing.supportable_loan(deal, n.sizing_noi)
    if start <= 0:
        return 0.0

    if min_dscr(start) < floor:
        low, high = 0.0, start          # too much debt; search down
    else:
        low, high = start, start * 2    # room for more; search up
        for _ in range(20):
            if min_dscr(high) < floor:
                break
            low, high = high, high * 2
        else:
            return low

    for _ in range(80):
        mid = (low + high) / 2
        if min_dscr(mid) >= floor:
            low = mid
        else:
            high = mid
    return low


def taxcredit_compute(deal, su, bond, equity, fin):
    """`Tax Credit Calc`, whose basis starts from total development cost.

    The workbook's F6 reads total *sources* (I26), which equals total uses once
    the loop converges. Reading uses directly is the same number in workbook
    mode and the correct one in screen mode, where soft money is still being
    solved and the sources side has not yet closed.
    """
    from .engine import taxcredit
    return taxcredit.compute(
        deal,
        total_sources=su.total_uses,
        acquisition=su.acquisition,
        community_facilities=su.community_facilities,
        reserves=su.reserves,
        financing_fees=fin.total_fees,
    )

"""Turns a screen into something a reader can act on.

`to_dict` is the wire format the connector returns. `to_markdown` is the
dashboard: the answer first, then the stack that produces it, then what would
have to be true for it to change.
"""

from __future__ import annotations

from typing import Any

from .scorecard import Check, Scorecard
from .solver import Screen

VERDICT_HEADLINE = {
    "PENCILS": "PENCILS - clears every rule",
    "MARGINAL": "MARGINAL - clears the hard rules, with items to watch",
    "FAIL": "FAIL - one or more hard rules break",
}


def _money(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"${value:,.0f}"


def _check_to_dict(check: Check) -> dict[str, Any]:
    return {
        "id": check.kpi_id, "group": check.group, "metric": check.metric,
        "value": check.value, "threshold": check.threshold,
        "status": check.status, "severity": check.severity, "scope": check.scope,
        "citation": check.citation, "message": check.message,
    }


def to_dict(screen: Screen) -> dict[str, Any]:
    """The full screen as JSON."""
    r, su, deal = screen.result, screen.result.sources_uses, screen.result.deal
    return {
        "project": {
            "name": deal.project_name,
            "units": r.units,
            "type": deal.project_type,
            "credit_type": deal.credit_type,
            "building_type": deal.building_type,
            "market": deal.tdc_region,
        },
        "verdict": {
            "verdict": screen.verdict,
            "headline": VERDICT_HEADLINE.get(screen.verdict, screen.verdict),
            "hard_fails": screen.scorecard.hard_fails,
            "warnings": screen.scorecard.warnings,
            "pending": screen.scorecard.pending,
            "notes": screen.notes,
        },
        "answer": {
            "asking_price": deal.acquisition_cost,
            "required_soft_money": screen.required_soft_money,
            "committed_soft_money": screen.committed_soft_money,
            "additional_soft_money_needed": screen.additional_soft_money_needed,
            "soft_money_surplus": screen.soft_money_surplus,
            "soft_money_at_zero_price": screen.soft_money_at_zero_price,
            "max_supportable_price": screen.max_supportable_price,
            "price_headroom": screen.price_headroom,
            "price_by_soft_money": screen.price_by_soft_money,
        },
        "sources_and_uses": {
            "total_development_cost": r.total_development_cost,
            "tdc_per_unit": r.tdc_per_unit,
            "acquisition": su.acquisition,
            "hard_costs": su.hard_costs,
            "soft_costs": su.soft_costs,
            "developer_fee": su.developer_fee,
            "reserves": su.reserves,
            "capitalised_interest": su.capitalised_interest,
            "financing_fees": su.financing_fees,
            "bonds": su.bonds,
            "tax_credit_equity": su.tax_credit_equity,
            "soft_money": su.soft_money,
            "deferred_fees": su.deferred_fees,
            "balance": su.balance,
        },
        "operations": {
            "stabilised_noi": r.stabilised_noi,
            "gross_rental_income": r.noi.gross_rental_income,
            "vacancy_rate": deal.vacancy_rate,
            "operating_expenses": r.noi.total_opex,
            "opex_per_unit": r.noi.total_opex / r.units if r.units else 0,
            "property_tax": r.expenses.property_tax,
            "pilot_assumed": deal.pilot_in_place == "Yes",
            "replacement_reserves_per_unit": deal.replacement_reserve_per_unit,
        },
        "debt": {
            "perm_bond": su.bonds,
            "coupon": deal.perm_coupon,
            "amortisation_years": deal.perm_amortization_years,
            "sizing_dscr": deal.sizing_dscr,
            "min_dscr": r.min_dscr,
            "min_dscr_year": r.min_dscr_year,
            "max_dscr": r.max_dscr,
            "max_dscr_year": r.max_dscr_year,
        },
        "credits": {
            "annual_credit": r.tax_credit.annual_credit,
            "qualified_basis": r.tax_credit.qualified_basis,
            "equity_price": deal.equity_price,
            "basis_boost": deal.basis_boost,
            "equity": r.tax_credit.equity,
        },
        "scorecard": {
            "verdict": screen.scorecard.verdict,
            "checks": [_check_to_dict(c) for c in screen.scorecard.checks],
            "failing": [_check_to_dict(c) for c in screen.scorecard.failing()],
        },
        "model": {
            "mode": deal.mode,
            "converged": r.converged,
            "iterations": r.iterations,
        },
    }


def to_markdown(screen: Screen, assumptions: list | None = None) -> str:
    """The screening dashboard."""
    r, su, deal = screen.result, screen.result.sources_uses, screen.result.deal
    out: list[str] = []

    out.append(f"## {deal.project_name} - {r.units} units, "
               f"{deal.project_type.lower()}, {deal.credit_type}")
    out.append("")
    out.append(f"**{VERDICT_HEADLINE.get(screen.verdict, screen.verdict)}**")
    out.append("")

    # -- the answer ---------------------------------------------------------
    out.append("| | |")
    out.append("|---|---|")
    out.append(f"| Asking price | {_money(deal.acquisition_cost)} |")
    out.append(f"| **Minimum soft funding needed** | **{_money(screen.required_soft_money)}** |")
    if screen.committed_soft_money:
        out.append(f"| Already committed | {_money(screen.committed_soft_money)} |")
        if screen.additional_soft_money_needed:
            out.append(f"| **Still to find** | **{_money(screen.additional_soft_money_needed)}** |")
        elif screen.soft_money_surplus:
            out.append(f"| Surplus over what is needed | {_money(screen.soft_money_surplus)} |")
    if screen.max_supportable_price is not None:
        headroom = screen.price_headroom or 0
        direction = "above" if headroom >= 0 else "below"
        out.append(f"| **Maximum supportable price** | **{_money(screen.max_supportable_price)}** "
                   f"({_money(abs(headroom))} {direction} asking) |")
    elif screen.price_by_soft_money:
        # No subsidy is committed, so price is not capped by the deal - it is
        # set by how much subsidy can be raised. The exchange rate is the answer.
        out.append("| Maximum supportable price | set by the subsidy raised - "
                   "see *What price the subsidy buys* below |")
    else:
        out.append("| Maximum supportable price | no price works |")
    out.append(f"| Least subsidy the deal could need (at a $0 price) "
               f"| {_money(screen.soft_money_at_zero_price)} |")
    out.append("")

    for note in screen.notes:
        out.append(f"> {note}")
    if screen.notes:
        out.append("")

    # -- what breaks it -----------------------------------------------------
    failing = screen.scorecard.failing()
    if failing:
        out.append("### What breaks it")
        out.append("")
        out.append("| | Rule | Issue | Authority |")
        out.append("|---|---|---|---|")
        label = {"error": "HARD FAIL", "warning": "warning", "info": "note"}
        for check in failing:
            out.append(f"| {label.get(check.severity, check.severity)} | {check.metric} "
                       f"| {check.message} | {check.citation or '-'} |")
        out.append("")
    else:
        out.append("Every rule in the register passes.")
        out.append("")

    # -- the stack ----------------------------------------------------------
    out.append("### Sources and uses")
    out.append("")
    out.append("| Uses | Amount | Per unit | | Sources | Amount | Share |")
    out.append("|---|---:|---:|---|---|---:|---:|")
    uses = [
        ("Acquisition", su.acquisition), ("Hard costs", su.hard_costs),
        ("Soft costs", su.soft_costs), ("Developer fee", su.developer_fee),
        ("Reserves", su.reserves), ("Capitalised interest", su.capitalised_interest),
        ("Financing fees", su.financing_fees),
    ]
    sources = [
        ("Perm bonds", su.bonds), ("LIHTC equity", su.tax_credit_equity),
        ("Soft funding", su.soft_money), ("Deferred fees", su.deferred_fees),
    ]
    total = su.total_uses or 1
    for i in range(max(len(uses), len(sources))):
        u = uses[i] if i < len(uses) else ("", None)
        s = sources[i] if i < len(sources) else ("", None)
        per_unit = f"{_money(u[1] / r.units)}" if u[1] is not None and r.units else ""
        share = f"{s[1] / total:.1%}" if s[1] is not None else ""
        out.append(f"| {u[0]} | {_money(u[1]) if u[1] is not None else ''} | {per_unit} "
                   f"| | {s[0]} | {_money(s[1]) if s[1] is not None else ''} | {share} |")
    out.append(f"| **Total** | **{_money(su.total_uses)}** | **{_money(r.tdc_per_unit)}** "
               f"| | **Total** | **{_money(su.total_sources)}** | |")
    out.append("")

    # -- operations and debt -------------------------------------------------
    out.append("### Operations and debt")
    out.append("")
    out.append("| | |")
    out.append("|---|---|")
    out.append(f"| Stabilised NOI | {_money(r.stabilised_noi)} |")
    out.append(f"| Operating expenses | {_money(r.noi.total_opex)} "
               f"({_money(r.noi.total_opex / r.units if r.units else 0)}/unit) |")
    out.append(f"| Property tax | {_money(r.expenses.property_tax)}"
               f"{' (PILOT)' if deal.pilot_in_place == 'Yes' else ' (no PILOT assumed)'} |")
    out.append(f"| Perm bond | {_money(su.bonds)} at {deal.perm_coupon:.2%}, "
               f"{deal.perm_amortization_years}-yr |")
    out.append(f"| DSCR | {r.min_dscr:.3f} low (Yr{r.min_dscr_year}) to "
               f"{r.max_dscr:.3f} high (Yr{r.max_dscr_year}), sized at {deal.sizing_dscr:.2f} |")
    out.append(f"| Annual LIHTC credit | {_money(r.tax_credit.annual_credit)} "
               f"at {deal.equity_price:.2f} = {_money(r.tax_credit.equity)} equity |")
    out.append("")

    # -- price vs subsidy ----------------------------------------------------
    if screen.price_by_soft_money:
        out.append("### What price the subsidy buys")
        out.append("")
        out.append("| Soft funding available | Maximum price |")
        out.append("|---:|---:|")
        for row in screen.price_by_soft_money:
            price = row["max_price"]
            out.append(f"| {_money(row['soft_money_available'])} | "
                       f"{_money(price) if price is not None else 'nothing works'} |")
        out.append("")

    # -- assumptions ----------------------------------------------------------
    if assumptions:
        out.append("### What was assumed")
        out.append("")
        out.append("| Input | Assumed | Basis |")
        out.append("|---|---|---|")
        for a in assumptions:
            out.append(f"| {a.label} | {a.value} | {a.basis} |")
        out.append("")

    return "\n".join(out)

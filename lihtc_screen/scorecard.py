"""The QAP scorecard: 34 KPIs, their thresholds, and the go/no-go verdict.

A port of the rule register on `Dashboard Calc` J3:V36, whose thresholds,
severities and citations live on the hidden `QAP_Rule_Register` tab. Both are
extracted into `refdata/qap_rules.json`, so a QAP change is a data edit rather
than a code change.

Verdict, per `Dashboard Calc` B29:
    FAIL      one or more hard fails (a failing rule of severity "error")
    MARGINAL  no hard fails, but at least one warning or pending item
    PENCILS   clean

Rules scoped APP-SIDE (needing application-form data the model does not hold)
or EXCLUDED (already enforced structurally) are reported but do not count
toward the verdict, matching the workbook's COUNTIFS.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

RULES_PATH = Path(__file__).parent / "refdata" / "qap_rules.json"

PASS, FAIL, NA, PENDING = "PASS", "FAIL", "N/A", "PENDING"
COUNTED_SCOPES = {"COMPUTED", "INPUT"}


def _load() -> dict:
    return json.loads(RULES_PATH.read_text())


_DATA = _load()
PARAMS = {k: v["value"] for k, v in _DATA["parameters"].items()}
CITATIONS = {r["rule_id"]: r.get("citation") for r in _DATA["rules"]}
QAP_BASIS = _DATA["qap_basis"]


@dataclass
class Check:
    kpi_id: str
    group: str
    metric: str
    value: Any
    threshold: Any
    status: str
    severity: str
    scope: str
    citation: str | None = None
    message: str = ""

    @property
    def is_hard_fail(self) -> bool:
        return (self.status == FAIL and self.severity == "error"
                and self.scope in COUNTED_SCOPES)

    @property
    def is_warning(self) -> bool:
        return (self.status == FAIL and self.severity == "warning"
                and self.scope in COUNTED_SCOPES)

    @property
    def is_pending(self) -> bool:
        return self.status == PENDING and self.scope in COUNTED_SCOPES


@dataclass
class Scorecard:
    checks: list[Check] = field(default_factory=list)
    verdict: str = PENCILS if False else "PENCILS"
    hard_fails: int = 0
    warnings: int = 0
    pending: int = 0

    def failing(self) -> list[Check]:
        """Everything that needs attention, worst first."""
        rank = {"error": 0, "warning": 1, "info": 2}
        issues = [c for c in self.checks
                  if c.is_hard_fail or c.is_warning or c.is_pending]
        return sorted(issues, key=lambda c: (rank.get(c.severity, 3), c.kpi_id))

    def by_group(self) -> dict[str, list[Check]]:
        out: dict[str, list[Check]] = {}
        for c in self.checks:
            out.setdefault(c.group, []).append(c)
        return out


def _format(value) -> str:
    if not isinstance(value, (int, float)):
        return str(value)
    if 0 < abs(value) < 10:
        return f"{value:,.3f}"
    return f"{value:,.0f}"


def _describe(metric: str, value, threshold, status: str) -> str:
    """A default explanation for a rule that failed without a bespoke message."""
    if status == PENDING:
        return f"{metric}: needs a value before this can be tested"
    return f"{metric} is {_format(value)} against a threshold of {_format(threshold)}"


def _dscr_message(low: float, high: float, floor: float, ceiling: float,
                  low_year: int | None = None, high_year: int | None = None) -> str:
    """Name the side of the DSCR band that is actually breached.

    Both ends matter and they mean opposite things: below the floor the deal
    cannot carry its debt, above the ceiling it is under-levered and is
    absorbing more subsidy than it needs.
    """
    if low < floor:
        where = f" in year {low_year}" if low_year else ""
        return (f"DSCR falls to {low:.3f}{where}, below the {floor:.2f} floor - "
                f"the deal cannot carry this much debt")
    if high > ceiling:
        where = f" in year {high_year}" if high_year else ""
        return (f"DSCR reaches {high:.3f}{where}, above the {ceiling:.2f} ceiling - "
                f"the deal is under-levered and is taking more subsidy than it needs")
    return ""


def _reserve_floor(project_type: str) -> float:
    if project_type == "Senior":
        return PARAMS["reserve_floor_senior"]
    if project_type == "Rehab":
        return PARAMS["reserve_floor_rehab"]
    return PARAMS["reserve_floor_family"]


def _pool_cap(pool: str) -> float:
    return {
        "Metro": PARAMS["pool_cap_metro"],
        "Rural": PARAMS["pool_cap_rural"],
        "Rural QNP-CHDO": PARAMS["pool_cap_rural_qnp"],
    }.get(pool, PARAMS["pool_cap_reprocessing"])


def evaluate(result) -> Scorecard:
    """Run every KPI against a solved model result."""
    deal = result.deal
    su = result.sources_uses
    pf = result.proforma
    tc = result.tax_credit
    units = result.units
    is_4pct = deal.credit_type == "4% bond"
    stabilised_opex = pf.opex[1] if len(pf.opex) > 1 else 0.0

    card = Scorecard()

    def add(kpi_id, group, metric, value, threshold, status, severity, scope,
            message=""):
        # Every failing or pending rule explains itself, so the screen output
        # never shows a bare FAIL the reader has to decode.
        if not message and status in (FAIL, PENDING):
            message = _describe(metric, value, threshold, status)
        card.checks.append(Check(kpi_id, group, metric, value, threshold, status,
                                 severity, scope, CITATIONS.get(kpi_id), message))

    def gate(ok: bool) -> str:
        return PASS if ok else FAIL

    # -- credit structure ---------------------------------------------------
    add("ELG-4PCT-BOND", "Credit Structure", "4% credit requires bonds",
        su.bonds if is_4pct else "n/a", "Bonds > $0",
        gate(su.bonds > 0) if is_4pct else NA, "error", "COMPUTED",
        "" if su.bonds > 0 else "4% credit elected but no tax-exempt bonds present")

    is_9pct = deal.credit_type == "9% competitive"
    add("ELG-9PCT-BOND", "Credit Structure", "9% + bonds mutually exclusive",
        su.bonds if is_9pct else "n/a", "Bonds = $0",
        gate(su.bonds == 0) if is_9pct else NA, "error", "COMPUTED")

    # -- credit sizing ------------------------------------------------------
    add("ELG-BOOST-30", "Credit Sizing", "Construction basis boost cap",
        deal.basis_boost, PARAMS["boost_cap_pct"],
        gate(deal.basis_boost <= PARAMS["boost_cap_pct"]), "error", "COMPUTED")

    boost_ok = deal.basis_boost == 0 or deal.boost_eligible == "Yes"
    add("ELG-BOOST-ELIGIBILITY", "Credit Sizing", "Basis-boost geo eligibility",
        deal.boost_eligible, "Qualifying geo",
        PENDING if not deal.boost_eligible else gate(boost_ok),
        "warning", "INPUT",
        "" if boost_ok else "Basis boost claimed without a qualifying QCT/DDA geography")

    add("ELG-POOL-CAP", "Credit Sizing", "Per-project pool cap",
        "n/a" if is_4pct else tc.annual_credit,
        "N/A (PAB cap)" if is_4pct else _pool_cap(deal.pool),
        NA if is_4pct else gate(tc.annual_credit <= _pool_cap(deal.pool)),
        "error", "COMPUTED")

    # Gap credit: what the equity gap alone would support.
    gap = su.total_uses - su.bonds - su.soft_money - su.deferred_fees
    per_credit_dollar = deal.equity_price * 10 * (1 - deal.gp_credit_share)
    gap_credit = gap / per_credit_dollar if per_credit_dollar else 0.0
    max_credit = min(tc.annual_credit, gap_credit)
    add("ELG-CREDIT-MAX", "Credit Sizing", "Maximum allowable credit",
        tc.annual_credit, max_credit,
        gate(tc.annual_credit <= max_credit * 1.001), "error", "COMPUTED",
        "" if tc.annual_credit <= max_credit * 1.001
        else "Credit exceeds what the equity gap supports")

    # -- DSCR ---------------------------------------------------------------
    floor, ceiling = PARAMS["dscr_floor"], PARAMS["dscr_ceiling"]
    add("UW-DSCR-Y1", "DSCR", "Annual DSCR band (Yr2-17)", result.min_dscr,
        f"{floor:.2f}-{ceiling:.2f}",
        gate(result.min_dscr >= floor and result.max_dscr <= ceiling),
        "error", "COMPUTED",
        _dscr_message(result.min_dscr, result.max_dscr, floor, ceiling,
                      result.min_dscr_year, result.max_dscr_year))

    spot = [pf.dscr[y - 1] for y in (5, 10, 15) if pf.dscr[y - 1] is not None]
    spot_min = min(spot) if spot else 0.0
    spot_max = max(spot) if spot else 0.0
    spot_floor = PARAMS["dscr_15yr_floor"]
    add("UW-DSCR-15", "DSCR", "15-yr projected DSCR (y5/10/15)", spot_min,
        f"{spot_floor:.2f}-{ceiling:.2f}",
        gate(spot_min >= spot_floor and spot_max <= ceiling), "error", "COMPUTED",
        _dscr_message(spot_min, spot_max, spot_floor, ceiling))

    # -- fee limits ---------------------------------------------------------
    dev_cap = min(PARAMS["developer_fee_cap_abs"],
                  PARAMS["developer_fee_cap_pct"] * su.developer_fee_base)
    add("FEE-DEVELOPER", "Fee Limits", "Developer fee", su.developer_fee,
        "No cap (4% bond)" if is_4pct else dev_cap,
        PASS if is_4pct else gate(su.developer_fee <= dev_cap), "error", "COMPUTED")

    arch_cap = PARAMS["arch_pct"] * su.hard_costs
    add("FEE-ARCHITECT", "Fee Limits", "Architect / design fee",
        deal.architecture_engineering, arch_cap,
        gate(deal.architecture_engineering <= arch_cap), "error", "COMPUTED")

    for kpi, label, value, pct in (
        ("FEE-BUILDER-PROFIT", "Builder profit", su.gc_profit, "builder_profit_pct"),
        ("FEE-BUILDER-OVERHEAD", "Builder overhead", su.gc_overhead, "builder_oh_pct"),
        ("FEE-GENERAL-REQUIREMENTS", "General requirements", su.general_requirements, "gen_req_pct"),
    ):
        cap = PARAMS[pct] * su.builder_fee_base
        add(kpi, "Fee Limits", label, value, cap, gate(value <= cap + 1),
            "error", "COMPUTED")

    cont_cap = PARAMS["contingency_pct"] * su.hard_costs
    add("FEE-CONTINGENCY", "Fee Limits", "Construction contingency",
        su.contingency, cont_cap, gate(su.contingency <= cont_cap),
        "error", "COMPUTED")

    # -- operating and reserves ---------------------------------------------
    opex_floor = PARAMS["opex_min_pu"] * units
    add("UW-OPEX-MIN", "Operating & Reserves", "Minimum operating expenses",
        stabilised_opex, opex_floor, gate(stabilised_opex >= opex_floor),
        "warning", "COMPUTED")

    res_floor = PARAMS["op_reserve_frac"] * stabilised_opex
    add("UW-OPERATING-RESERVE-6MO", "Operating & Reserves", "Operating reserve (6 mo)",
        su.operating_reserve, res_floor,
        gate(su.operating_reserve >= res_floor), "warning", "COMPUTED")

    pupa_floor = _reserve_floor(deal.project_type)
    yr1_pupa = pf.reserves[0] / units if units else 0.0
    add("UW-RESERVE-PUPA", "Operating & Reserves", "Repl-reserve deposit / unit",
        yr1_pupa, pupa_floor, gate(yr1_pupa >= pupa_floor), "warning", "EXCLUDED")

    min_pupa = min(pf.reserves) / units if units else 0.0
    add("UW-RESERVE-ADEQUACY", "Operating & Reserves", "Repl-reserve adequacy (all yrs)",
        min_pupa, pupa_floor, gate(min_pupa >= pupa_floor), "warning", "COMPUTED")

    add("FEE-ASSET-MGMT-CAP", "Operating & Reserves", "Asset-mgmt fee cap (opex)",
        "n/a", "$5,000/yr", NA, "info", "APP-SIDE")

    # -- vacancy and trending ------------------------------------------------
    vac_min = PARAMS["vacancy_min"]
    for kpi, label in (("UW-VACANCY13", "Vacancy, years 1-3"),
                       ("UW-VACANCY4", "Vacancy, years 4+")):
        add(kpi, "Vacancy & Trending", label, deal.vacancy_rate, vac_min,
            gate(deal.vacancy_rate >= vac_min), "warning", "COMPUTED")

    rent_max = PARAMS["rent_trend_max"]
    trend_13 = pf.gross_rent[1] / pf.gross_rent[0] - 1 if pf.gross_rent[0] else 0.0
    trend_415 = pf.gross_rent[4] / pf.gross_rent[3] - 1 if pf.gross_rent[3] else 0.0
    add("UW-TREND-RENT13", "Vacancy & Trending", "Rent inflation, years 1-3",
        trend_13, rent_max, gate(trend_13 <= rent_max + 0.0001), "warning", "COMPUTED")
    add("UW-TREND-RENT415", "Vacancy & Trending", "Rent inflation, years 4-15",
        trend_415, rent_max, gate(trend_415 <= rent_max + 0.0001), "warning", "COMPUTED")

    exp_min = PARAMS["exp_trend_min"]
    exp_trend = pf.payroll[2] / pf.payroll[1] - 1 if pf.payroll[1] else 0.0
    add("UW-TREND-EXPENSE", "Vacancy & Trending", "Expense inflation (payroll YoY)",
        exp_trend, exp_min, gate(exp_trend >= exp_min - 0.0001), "warning", "COMPUTED")

    # -- cost and TDC --------------------------------------------------------
    hud_limit = su.tdc_limit_total
    add("UW-HUD-TDC", "Cost & TDC", "HUD Total Dev Cost limit", su.total_uses,
        hud_limit if hud_limit else "(no limit loaded)",
        PENDING if not hud_limit else gate(su.total_uses <= hud_limit),
        "error", "INPUT",
        "" if not hud_limit or su.total_uses <= hud_limit
        else "Total development cost exceeds the HUD per-unit TDC limit")

    tol = PARAMS["su_balance_tol"]
    add("UW-SOURCES-USES", "Cost & TDC", "Sources = Uses balance", su.balance, tol,
        gate(abs(su.balance) <= tol), "warning", "EXCLUDED")

    add("UW-BASIS-RECON", "Cost & TDC", "Eligible-basis reconciliation",
        "n/a", "No recon errors", NA, "info", "APP-SIDE")

    add("QAP-TDC-PERUNIT", "Cost & TDC", "Per-unit TDC vs QAP max",
        result.tdc_per_unit, su.tdc_limit_per_unit,
        gate(result.tdc_per_unit <= su.tdc_limit_per_unit), "error", "COMPUTED",
        "" if result.tdc_per_unit <= su.tdc_limit_per_unit
        else "Per-unit cost exceeds the QAP maximum")
    add("QAP-TDC-TOTAL", "Cost & TDC", "Total TDC vs QAP max",
        su.total_uses, su.tdc_limit_total,
        gate(su.total_uses <= su.tdc_limit_total), "error", "COMPUTED")

    # -- syndication ---------------------------------------------------------
    synd_pct = (PARAMS["syndication_cap_public"] if deal.syndication == "Public"
                else PARAMS["syndication_cap_private"])
    synd_cap = synd_pct * tc.equity
    add("UW-SYND-COSTCAP", "Syndication", "Syndication cost cap",
        deal.syndication_costs, synd_cap,
        gate(deal.syndication_costs <= synd_cap), "error", "EXCLUDED")
    add("UW-SYND-PARTVI", "Syndication", "Syndication cost reconciliation",
        "n/a", "Part VI = Dev Costs", NA, "info", "APP-SIDE")
    add("ELG-EQUITY-MATCH", "Credit Structure", "LIHTC equity reconciliation",
        "n/a", "Must match", NA, "info", "APP-SIDE")

    # -- cash flow and deferred fee -------------------------------------------
    cash_ceiling = PARAMS["cashflow_ceil_pct"] * stabilised_opex
    yr2_cash = pf.cash_after_fees[1] if len(pf.cash_after_fees) > 1 else 0.0
    add("UW-CASHFLOW-10PCT", "Cash Flow", "Year-1 cash-flow ceiling",
        yr2_cash, cash_ceiling, gate(yr2_cash <= cash_ceiling),
        "warning", "COMPUTED",
        "" if yr2_cash <= cash_ceiling
        else "Stabilised cash flow exceeds 10% of operating expenses")

    deferred = su.deferred_fees
    cum15 = result.cumulative_cash_year_15
    add("UW-DEFERRED-DEV-FEE-15YR", "Deferred Fee", "Deferred dev-fee payoff by Yr15",
        cum15, deferred,
        NA if deferred == 0 else gate(cum15 >= deferred), "warning", "COMPUTED",
        "" if deferred == 0 or cum15 >= deferred
        else "Deferred developer fee is not repaid within 15 years")

    # -- verdict --------------------------------------------------------------
    card.hard_fails = sum(1 for c in card.checks if c.is_hard_fail)
    card.warnings = sum(1 for c in card.checks if c.is_warning)
    card.pending = sum(1 for c in card.checks if c.is_pending)
    if card.hard_fails:
        card.verdict = "FAIL"
    elif card.warnings or card.pending:
        card.verdict = "MARGINAL"
    else:
        card.verdict = "PENCILS"
    return card

"""`Tax Credit Calc` - eligible basis, annual credit, and LIHTC equity."""

from __future__ import annotations

from dataclasses import dataclass

from ..inputs import DealInputs

CREDIT_PERIOD_YEARS = 10       # rows 28-37


@dataclass
class TaxCredit:
    total_development_cost: float = 0.0   # F6 (Total *Sources*, per the workbook)
    adjusted_basis: float = 0.0           # F15
    qualified_basis: float = 0.0          # F19
    annual_credit: float = 0.0            # F22, the credit actually allocated
    basis_annual_credit: float = 0.0      # what the basis alone would support
    lp_credits: float = 0.0               # E39
    equity: float = 0.0                   # F41
    limited_by_gap: bool = False          # allocation cut to the equity gap


def compute(deal: DealInputs, *, total_sources: float, acquisition: float,
            community_facilities: float, reserves: float,
            financing_fees: float) -> TaxCredit:
    tc = TaxCredit()
    tc.total_development_cost = total_sources

    # F6:F14 - start from cost, strip everything not in eligible basis.
    tc.adjusted_basis = (
        total_sources
        - acquisition                       # F7
        + deal.building_basis_addition      # F8
        - community_facilities              # F9
        - deal.federal_grants               # F10
        - deal.lhc_home                     # F11
        - reserves                          # F12
        - financing_fees                    # F13
    )
    tc.qualified_basis = (tc.adjusted_basis * deal.applicable_fraction
                          * (1 + deal.basis_boost))
    tc.annual_credit = tc.qualified_basis * deal.credit_rate
    tc.basis_annual_credit = tc.annual_credit

    # The GP takes a token share; the LP buys the rest at the equity price.
    lp_annual = tc.annual_credit * (1 - deal.gp_credit_share)
    tc.lp_credits = lp_annual * CREDIT_PERIOD_YEARS
    tc.equity = tc.lp_credits * deal.equity_price
    return tc


def limit_to_equity(tc: TaxCredit, deal, equity: float) -> TaxCredit:
    """Re-state the allocation at a capped equity amount.

    A state agency allocates the lesser of what the basis generates and what the
    equity gap supports, so an over-credited deal has its allocation cut rather
    than being over-funded.
    """
    if equity >= tc.equity - 0.01:
        return tc
    scale = equity / tc.equity if tc.equity else 0.0
    tc.equity = equity
    tc.lp_credits *= scale
    tc.annual_credit *= scale
    tc.limited_by_gap = True
    return tc

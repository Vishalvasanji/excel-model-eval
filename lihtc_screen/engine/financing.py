"""`Financing Assumptions` - financing fees and DSCR-based loan sizing."""

from __future__ import annotations

from dataclasses import dataclass

from ..inputs import DealInputs


def pmt(rate: float, nper: float, pv: float) -> float:
    """Excel PMT, sign-flipped to a positive payment."""
    if rate == 0:
        return pv / nper
    return pv * rate / (1 - (1 + rate) ** -nper)


@dataclass
class Financing:
    bond_amount: float = 0.0            # D6
    mortgage_constant: float = 0.0      # C27
    supportable_loan: float = 0.0       # C36, NOI / (DSCR x constant)
    annual_payment: float = 0.0         # level debt service once amortising
    total_fees: float = 0.0             # D53


def mortgage_constant(deal: DealInputs) -> float:
    """`Financing Assumptions` C27: annualised constant on a $1 loan."""
    return pmt(deal.perm_coupon / 12, deal.perm_amortization_years * 12, 1.0) * 12


def supportable_loan(deal: DealInputs, sizing_noi: float) -> float:
    """`Financing Assumptions` C36 - the DSCR-constrained loan amount."""
    constant = mortgage_constant(deal)
    if constant <= 0 or deal.sizing_dscr <= 0:
        return 0.0
    return sizing_noi / (deal.sizing_dscr * constant)


def compute(deal: DealInputs, bond_amount: float, sizing_noi: float) -> Financing:
    f = Financing(bond_amount=bond_amount)
    f.mortgage_constant = mortgage_constant(deal)
    f.supportable_loan = supportable_loan(deal, sizing_noi)
    f.annual_payment = pmt(deal.perm_coupon, deal.perm_amortization_years, bond_amount)

    construction = (deal.construction_origination_pct * bond_amount   # D12
                    + deal.construction_legal                          # D13
                    + deal.construction_servicing_setup)               # D14

    # D19 reads `=C19*D13` - 1% of the construction *legal fee*, not of the
    # bridge loan. Reproduced in workbook mode; screen mode charges the fee on
    # the bridge loan, which is what the label describes.
    if deal.mode == "workbook":
        bridge_origination = deal.bridge_origination_pct * deal.construction_legal
    else:
        bridge_origination = deal.bridge_origination_pct * bond_amount
    bridge = bridge_origination + deal.bridge_legal + deal.bridge_servicing_setup

    perm = (deal.perm_origination_pct * bond_amount                    # D33
            + deal.placement_fee_pct * bond_amount                     # D34
            + deal.perm_legal)                                         # D35

    issuance = (deal.bond_counsel + deal.financial_advisor             # D39, D40
                + deal.trustee_setup                                   # D41
                + deal.issuer_closing_fee_pct * bond_amount            # D42
                + deal.bond_issuance_misc)                             # D43

    equity = (deal.equity_legal + deal.syndication_costs               # D48, D49
              + deal.financing_misc)                                   # D51

    f.total_fees = construction + bridge + perm + issuance + equity
    return f

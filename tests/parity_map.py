"""Map from workbook cells to engine values, used by the parity tests.

Each entry is (sheet, cell, label, accessor). The accessor takes a
`lihtc_screen.model.Result` and returns the engine's equivalent number.
"""

from __future__ import annotations

PARITY_MAP = [
    # -- Unit Mix+Rents ----------------------------------------------------
    ("Unit Mix+Rents", "D14", "units", lambda r: r.mix.units),
    ("Unit Mix+Rents", "C14", "total sqft", lambda r: r.mix.total_sqft),
    ("Unit Mix+Rents", "J14", "monthly net rent", lambda r: r.mix.monthly_net_rent),
    ("Unit Mix+Rents", "K14", "monthly gross rent", lambda r: r.mix.monthly_gross_rent),
    ("Unit Mix+Rents", "L14", "monthly UA", lambda r: r.mix.monthly_ua),

    # -- Expense Detail ----------------------------------------------------
    ("Expense Detail", "F13", "payroll", lambda r: r.expenses.payroll),
    ("Expense Detail", "F20", "maintenance", lambda r: r.expenses.maintenance),
    ("Expense Detail", "F39", "utilities", lambda r: r.expenses.utilities),
    ("Expense Detail", "F50", "contract services", lambda r: r.expenses.contract_services),
    ("Expense Detail", "F61", "property tax", lambda r: r.expenses.property_tax),
    ("Expense Detail", "F65", "insurance", lambda r: r.expenses.insurance),

    # -- NOI Calc ----------------------------------------------------------
    ("NOI Calc", "J5", "gross rental income", lambda r: r.noi.gross_rental_income),
    ("NOI Calc", "J9", "gross revenue", lambda r: r.noi.gross_revenue),
    ("NOI Calc", "J13", "net revenue", lambda r: r.noi.net_revenue),
    ("NOI Calc", "J26", "total opex", lambda r: r.noi.total_opex),
    ("NOI Calc", "J29", "NOI", lambda r: r.noi.noi),
    ("NOI Calc", "J33", "replacement reserves", lambda r: r.noi.replacement_reserves),

    # -- Construction Estimates -------------------------------------------
    ("Construction Estimates", "G13", "vertical construction", lambda r: r.construction.vertical),
    ("Construction Estimates", "G18", "total hard cost", lambda r: r.construction.hard_cost),

    # -- Sources & Uses ----------------------------------------------------
    ("Sources & Uses", "I34", "on-site improvements", lambda r: r.sources_uses.onsite_improvements),
    ("Sources & Uses", "I36", "residential structures", lambda r: r.sources_uses.residential),
    ("Sources & Uses", "I37", "community facilities", lambda r: r.sources_uses.community_facilities),
    ("Sources & Uses", "I38", "general requirements", lambda r: r.sources_uses.general_requirements),
    ("Sources & Uses", "I39", "GC overhead", lambda r: r.sources_uses.gc_overhead),
    ("Sources & Uses", "I40", "GC profit", lambda r: r.sources_uses.gc_profit),
    ("Sources & Uses", "I41", "contingency", lambda r: r.sources_uses.contingency),
    ("Sources & Uses", "I43", "total hard costs", lambda r: r.sources_uses.hard_costs),
    ("Sources & Uses", "I61", "total soft costs", lambda r: r.sources_uses.soft_costs),
    ("Sources & Uses", "I63", "total construction costs", lambda r: r.sources_uses.construction_costs),
    ("Sources & Uses", "I65", "developer fee", lambda r: r.sources_uses.developer_fee),
    ("Sources & Uses", "I67", "operating reserve", lambda r: r.sources_uses.operating_reserve),
    ("Sources & Uses", "I68", "interest reserve", lambda r: r.sources_uses.interest_reserve),
    ("Sources & Uses", "I72", "total reserves", lambda r: r.sources_uses.reserves),
    ("Sources & Uses", "I74", "capitalised interest", lambda r: r.sources_uses.capitalised_interest),
    ("Sources & Uses", "I76", "financing fees", lambda r: r.sources_uses.financing_fees),
    ("Sources & Uses", "I78", "TOTAL USES", lambda r: r.sources_uses.total_uses),
    ("Sources & Uses", "I12", "bonds", lambda r: r.sources_uses.bonds),
    ("Sources & Uses", "I14", "tax credit equity", lambda r: r.sources_uses.tax_credit_equity),
    ("Sources & Uses", "I19", "soft money", lambda r: r.sources_uses.soft_money),
    ("Sources & Uses", "I22", "deferred developer fee", lambda r: r.sources_uses.deferred_developer_fee),
    ("Sources & Uses", "I26", "TOTAL SOURCES", lambda r: r.sources_uses.total_sources),
    ("Sources & Uses", "I81", "builder fee base", lambda r: r.sources_uses.builder_fee_base),
    ("Sources & Uses", "I82", "developer fee base", lambda r: r.sources_uses.developer_fee_base),
    ("Sources & Uses", "I85", "TDC limit per unit", lambda r: r.sources_uses.tdc_limit_per_unit),
    ("Sources & Uses", "I86", "TDC limit total", lambda r: r.sources_uses.tdc_limit_total),

    # -- S&U Timing --------------------------------------------------------
    ("S&U Timing", "D10", "bond par", lambda r: r.timing.bond_total),
    ("S&U Timing", "D41", "capitalised construction interest", lambda r: r.timing.capitalised_construction),
    ("S&U Timing", "D42", "capitalised bridge interest", lambda r: r.timing.capitalised_bridge),
    ("S&U Timing", "D44", "total capitalised interest", lambda r: r.timing.capitalised_interest),

    # -- Financing Assumptions --------------------------------------------
    ("Financing Assumptions", "C27", "mortgage constant", lambda r: r.financing.mortgage_constant),
    ("Financing Assumptions", "C36", "supportable loan", lambda r: r.financing.supportable_loan),
    ("Financing Assumptions", "D53", "total financing fees", lambda r: r.financing.total_fees),

    # -- Tax Credit Calc ---------------------------------------------------
    ("Tax Credit Calc", "F15", "adjusted basis", lambda r: r.tax_credit.adjusted_basis),
    ("Tax Credit Calc", "F19", "qualified basis", lambda r: r.tax_credit.qualified_basis),
    ("Tax Credit Calc", "F22", "annual credit", lambda r: r.tax_credit.annual_credit),
    ("Tax Credit Calc", "F41", "tax credit equity", lambda r: r.tax_credit.equity),

    # -- Lease-Up Period (column P totals) ---------------------------------
    ("Lease-Up Period", "P12", "lease-up net revenue", lambda r: r.leaseup.total_net_revenue),
    ("Lease-Up Period", "P24", "lease-up opex", lambda r: r.leaseup.total_opex),
    ("Lease-Up Period", "P26", "lease-up NOI", lambda r: r.leaseup.total_noi),
    ("Lease-Up Period", "P30", "lease-up interest", lambda r: r.leaseup.total_interest),
    ("Lease-Up Period", "P41", "lease-up cash after fees", lambda r: r.leaseup.total_cash_after_fees),

    # -- Surplus Cash-Reserve Waterfall ------------------------------------
    ("Surplus Cash-Reserve Waterfall", "B46", "operating deficit reserve", lambda r: r.reserves.operating),
    ("Surplus Cash-Reserve Waterfall", "B47", "interest expense reserve", lambda r: r.reserves.interest),
    ("Surplus Cash-Reserve Waterfall", "B48", "total reserve requirement", lambda r: r.reserves.total),

    # -- Dashboard Calc ----------------------------------------------------
    ("Dashboard Calc", "B18", "min DSCR", lambda r: r.min_dscr),
    ("Dashboard Calc", "B20", "max DSCR", lambda r: r.max_dscr),
    ("Dashboard Calc", "B23", "cumulative cash to Yr15", lambda r: r.cumulative_cash_year_15),
]

# Pro forma rows checked across all 17 years.
PRO_FORMA_ROWS = [
    ("6", "gross rent", lambda r: r.proforma.gross_rent),
    ("12", "net revenue", lambda r: r.proforma.net_revenue),
    ("24", "opex", lambda r: r.proforma.opex),
    ("26", "NOI", lambda r: r.proforma.noi),
    ("28", "replacement reserves", lambda r: r.proforma.reserves),
    ("30", "interest", lambda r: r.proforma.interest),
    ("31", "principal", lambda r: r.proforma.principal),
    ("40", "cash after fees", lambda r: r.proforma.cash_after_fees),
]
PRO_FORMA_COLUMNS = "DEFGHIJKLMNOPQRST"

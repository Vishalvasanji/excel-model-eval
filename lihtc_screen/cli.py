"""Command line entry point, for running a screen without the connector.

    python -m lihtc_screen screen deal.json
    python -m lihtc_screen screen deal.json --json
    python -m lihtc_screen markets

`deal.json` holds any `DealInputs` fields; everything omitted is defaulted.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import defaults
from .inputs import DealInputs
from .refdata import MarketNotFound, available_markets, find_market, load_markets
from .report import to_dict, to_markdown
from .solver import screen as run_screen


# `DealInputs` defaults reproduce the workbook's Westbend deal, which is what
# the parity tests need and exactly what a real screen must not inherit. These
# are deal facts with no defensible default: a screen that silently borrowed
# another property's price or subsidy award would look entirely plausible.
DEAL_SPECIFIC = {
    "acquisition_cost": 0.0,
    "cdbg": 0.0,
    "lhc_home": 0.0,
    "building_basis_addition": 0.0,
}


def _load(path: Path) -> tuple[DealInputs, list, list[str]]:
    raw = json.loads(path.read_text())
    warnings: list[str] = []
    market_query = raw.pop("market", None)

    # Accept the connector's field names too, so one deal file drives both.
    aliases = {"asking_price": "acquisition_cost",
               "committed_soft_money": "cdbg"}
    for alias, field in aliases.items():
        if alias in raw:
            raw[field] = raw.pop(alias)

    if not raw.get("unit_mix"):
        raise SystemExit(
            "The deal file needs a unit_mix: bedrooms, count, sqft and ami_pct "
            "per unit type. Rents scale off the mix and so does everything else.")

    deal = DealInputs.from_dict({**raw, "mode": raw.get("mode", "screen")})
    provided = {k for k in raw if k in DealInputs.__dataclass_fields__}

    for field, blank in DEAL_SPECIFIC.items():
        if field not in provided:
            setattr(deal, field, blank)

    if market_query:
        try:
            find_market(market_query, raw.get("state")).apply_to(deal)
            provided |= {"rent_limits", "ua_electricity"}
        except MarketNotFound as exc:
            warnings.append(str(exc))

    applied = defaults.apply(
        deal, state=raw.get("state"), parish=raw.get("parish"),
        city=raw.get("city"), provided=provided)
    return deal, applied.assumptions, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lihtc_screen", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("screen", help="screen a deal from a JSON file")
    run.add_argument("deal", type=Path)
    run.add_argument("--json", action="store_true", help="emit JSON instead of a dashboard")

    sub.add_parser("markets", help="list markets with bundled reference data")

    args = parser.parse_args(argv)

    if args.command == "markets":
        data = load_markets()["markets"]
        for key in available_markets():
            entry = data[key]
            print(f"{key}\n  {entry['name']}")
            print(f"  rents: {entry['rent_limits'].get('source')}")
            print(f"  utilities: {entry['utility_allowances'].get('source')}")
        return 0

    if not args.deal.exists():
        print(f"no such file: {args.deal}", file=sys.stderr)
        return 1

    deal, assumptions, warnings = _load(args.deal)
    result = run_screen(deal)

    if args.json:
        print(json.dumps({"warnings": warnings, "screen": to_dict(result)},
                         indent=2, default=str))
    else:
        for warning in warnings:
            print(f"! {warning}\n", file=sys.stderr)
        print(to_markdown(result, assumptions))
    return 0

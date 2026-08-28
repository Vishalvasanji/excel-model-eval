"""Populate a market's MTSP rent limits in `markets.json` from HUD's API.

Rent limits must come from HUD, not from an estimate, so this fetches them
rather than letting anyone hand-enter a market. It writes the source and the
effective year alongside the numbers.

HUD's API needs a free token from https://www.huduser.gov/portal/dataset/
fmr-api.html. Put it in HUD_API_TOKEN.

    export HUD_API_TOKEN=...
    python tools/load_hud_limits.py --fips 2207199999 --key baton-rouge-la \
        --name "Baton Rouge, LA MSA" --state LA --year 2025

Utility allowances are published by the local housing authority, not HUD, and
are not fetched here: add them to the market entry by hand with their source
and effective date. A market with rent limits but no utility allowances will
overstate net rents, so the loader marks it incomplete until they are supplied.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

MARKETS_PATH = Path(__file__).resolve().parent.parent / "lihtc_screen" / "refdata" / "markets.json"
API = "https://www.huduser.gov/hudapi/public/mtspil/data/{year}"

# The AMI bands the model prices against.
AMI_BANDS = (0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 1.20)


def fetch(fips: str, year: int, token: str) -> dict:
    request = urllib.request.Request(
        API.format(year=year) + f"?entityId={fips}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise SystemExit(
                "HUD rejected the token. Get one at "
                "https://www.huduser.gov/portal/dataset/fmr-api.html and set "
                "HUD_API_TOKEN."
            ) from exc
        raise SystemExit(f"HUD API error {exc.code}: {exc.reason}") from exc


def to_rent_table(payload: dict) -> dict[str, list[float]]:
    """Reshape HUD's response into {ami_band: [br0..br4]}.

    HUD's MTSP payload keys rents by bedroom count within each income band; the
    exact shape has changed between vintages, so anything unrecognised is
    reported rather than guessed at.
    """
    data = payload.get("data", payload)
    table: dict[str, list[float]] = {}
    for band in AMI_BANDS:
        pct = int(round(band * 100))
        row = []
        for bedrooms in range(5):
            value = (data.get(f"il{pct}_p{bedrooms}")
                     or data.get(f"rent_{pct}_{bedrooms}")
                     or data.get(f"MTSP_{pct}_{bedrooms}"))
            if value is None:
                break
            row.append(float(value))
        if len(row) == 5:
            table[f"{band:.2f}"] = row
    if not table:
        raise SystemExit(
            "Could not find rent limits in HUD's response. Keys returned: "
            + ", ".join(sorted(data)[:40])
            + "\nAdd the mapping to to_rent_table() rather than entering the "
              "numbers by hand."
        )
    return table


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fips", required=True, help="HUD entity id for the area")
    parser.add_argument("--key", required=True, help="market key, e.g. baton-rouge-la")
    parser.add_argument("--name", required=True, help="full HUD area name")
    parser.add_argument("--state", required=True)
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--tdc-region", default=None)
    parser.add_argument("--coastal", action="store_true")
    parser.add_argument("--alias", action="append", default=[],
                        help="city or parish name that should resolve here")
    args = parser.parse_args()

    token = os.environ.get("HUD_API_TOKEN")
    if not token:
        raise SystemExit(
            "HUD_API_TOKEN is not set. Get a free token at "
            "https://www.huduser.gov/portal/dataset/fmr-api.html"
        )

    table = to_rent_table(fetch(args.fips, args.year, token))

    markets = json.loads(MARKETS_PATH.read_text())
    entry = markets["markets"].setdefault(args.key, {})
    entry.update({
        "name": args.name,
        "state": args.state,
        "coastal": args.coastal or entry.get("coastal", False),
        "tdc_region": args.tdc_region or entry.get("tdc_region"),
        "aliases": sorted(set(entry.get("aliases", []) + args.alias)),
        "rent_limits": {
            "source": f"HUD FY{args.year} MTSP Income Limits (entity {args.fips})",
            "title": f"{args.year} {args.name} Gross Rent Limits",
            "table": table,
        },
    })
    entry.setdefault("utility_allowances", {
        "source": "NOT SET - add the local housing authority's schedule",
        "electricity": [0, 0, 0, 0, 0], "water": [0, 0, 0, 0, 0],
        "sewer": [0, 0, 0, 0, 0], "trash": [0, 0, 0, 0, 0],
    })

    MARKETS_PATH.write_text(json.dumps(markets, indent=1))
    print(f"wrote {args.key}: {len(table)} AMI bands from HUD FY{args.year}")
    if "NOT SET" in entry["utility_allowances"].get("source", ""):
        print("  still needed: utility allowances from the local housing authority")
    return 0


if __name__ == "__main__":
    sys.exit(main())

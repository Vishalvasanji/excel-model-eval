"""Lookup for market reference data.

Rent limits, utility allowances and TDC limits are all market-specific and all
come from an issuing authority: HUD publishes MTSP limits and unit TDC limits,
the local housing authority publishes utility allowances. None of them can be
inferred from a property's address, and using a neighbouring market's numbers
would silently misprice a deal.

So a market is either loaded with sourced tables or it is not available, and
`find_market` says which. A deal in an unloaded market can still be screened by
supplying its tables on `DealInputs` directly; what it cannot do is quietly
borrow another market's.

Adding a market means adding an entry to `markets.json` with the source and
effective date of every table. `tools/load_hud_limits.py` will populate rent
limits from HUD's API when a token is configured.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

MARKETS_PATH = Path(__file__).parent / "markets.json"


class MarketNotFound(LookupError):
    """Raised when a market has no sourced reference data bundled."""

    def __init__(self, query: str, available: list[str]):
        self.query = query
        self.available = available
        super().__init__(
            f"No reference data bundled for {query!r} "
            f"(bundled: {', '.join(available) or 'none'}). Look up this market's "
            f"HUD MTSP gross rent limits and its local housing authority's "
            f"utility allowance schedule, and pass them as `rent_limits` and "
            f"`utility_allowances` with their sources. Screening it on another "
            f"market's rents would be wrong all the way through."
        )


@dataclass
class Market:
    key: str
    name: str
    state: str
    coastal: bool
    tdc_region: str | None
    rent_limits: dict[float, list[float]]
    ua_electricity: list[float]
    ua_water: list[float]
    ua_sewer: list[float]
    ua_trash: list[float]
    sources: dict[str, str] = field(default_factory=dict)

    def apply_to(self, deal) -> "Market":
        """Copy this market's tables onto a deal."""
        deal.rent_limits = dict(self.rent_limits)
        deal.ua_electricity = list(self.ua_electricity)
        deal.ua_water = list(self.ua_water)
        deal.ua_sewer = list(self.ua_sewer)
        deal.ua_trash = list(self.ua_trash)
        if self.tdc_region:
            deal.tdc_region = self.tdc_region
            limits = tdc_limits_for_region(self.tdc_region)
            if limits:
                deal.tdc_limits = limits
        return self


@lru_cache(maxsize=1)
def load_markets() -> dict:
    return json.loads(MARKETS_PATH.read_text())


def available_markets() -> list[str]:
    return sorted(load_markets()["markets"])


def tdc_limits_for_region(region: str) -> dict[int, dict[str, float]] | None:
    """HUD unit TDC limits, $/unit by bedroom count and building type."""
    regions = load_markets().get("tdc_limits", {}).get("regions", {})
    entry = regions.get(region)
    if not entry:
        return None
    return {int(br): row for br, row in entry["limits"].items()}


def _normalise(text: str) -> str:
    return " ".join(text.lower().replace(",", " ").replace("-", " ").split())


def find_market(query: str, state: str | None = None) -> Market:
    """Look a market up by key, name, city, or parish.

    Raises `MarketNotFound` rather than falling back to a nearby market.
    """
    data = load_markets()["markets"]
    wanted = _normalise(query or "")

    for key, entry in data.items():
        if state and entry.get("state", "").lower() != state.lower():
            continue
        candidates = {_normalise(key), _normalise(entry["name"])}
        candidates |= {_normalise(a) for a in entry.get("aliases", [])}
        if wanted in candidates or any(wanted and wanted in c for c in candidates):
            return _build(key, entry)

    raise MarketNotFound(query, available_markets())


def _build(key: str, entry: dict) -> Market:
    rents = entry["rent_limits"]
    ua = entry["utility_allowances"]
    return Market(
        key=key,
        name=entry["name"],
        state=entry.get("state", ""),
        coastal=bool(entry.get("coastal")),
        tdc_region=entry.get("tdc_region"),
        rent_limits={float(k): list(v) for k, v in rents["table"].items()},
        ua_electricity=list(ua.get("electricity", [0] * 5)),
        ua_water=list(ua.get("water", [0] * 5)),
        ua_sewer=list(ua.get("sewer", [0] * 5)),
        ua_trash=list(ua.get("trash", [0] * 5)),
        sources={
            "rent_limits": rents.get("source", ""),
            "utility_allowances": ua.get("source", ""),
        },
    )

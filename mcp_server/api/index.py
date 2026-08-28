"""Remote MCP server for the LIHTC acquisition/rehab screen.

Speaks MCP over streamable HTTP as a single Vercel Python function, and imports
`lihtc_screen` directly so the connector and the local CLI run the same engine
against the same reference data.

Auth is a shared bearer token from SCREEN_API_TOKEN, checked on every request.

Local:
    SCREEN_API_TOKEN=dev python mcp_server/api/index.py
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lihtc_screen import defaults                       # noqa: E402
from lihtc_screen.inputs import DealInputs              # noqa: E402
from lihtc_screen.refdata import (MarketNotFound, available_markets,  # noqa: E402
                                  find_market, load_markets)
from lihtc_screen.report import to_dict, to_markdown    # noqa: E402
from lihtc_screen.solver import screen as run_screen, sensitivity  # noqa: E402

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "lihtc-acq-rehab-screen", "version": "1.0.0"}

# JSON-RPC error codes.
PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS, INTERNAL = (
    -32700, -32600, -32601, -32602, -32603)


# ---------------------------------------------------------------- tools ----

TOOLS = [
    {
        "name": "screen_deal",
        "description": (
            "Screen a LIHTC acquisition/rehab deal. Returns the go/no-go verdict, "
            "the minimum soft funding the deal needs, the maximum supportable "
            "purchase price, the full sources and uses, and every QAP rule that "
            "fails with its citation. Supply whatever the memo states; anything "
            "omitted is filled from the underwriting workflow's defaults and "
            "reported back as an assumption."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_name": {"type": "string"},
                "units": {
                    "type": "integer",
                    "description": "Total units. Only needed if unit_mix is omitted."},
                "unit_mix": {
                    "type": "array",
                    "description": (
                        "One entry per unit type. Without this, units are spread "
                        "across a default mix, which is a rough approximation."),
                    "items": {
                        "type": "object",
                        "properties": {
                            "bedrooms": {"type": "integer"},
                            "bathrooms": {"type": "number"},
                            "sqft": {"type": "number"},
                            "count": {"type": "integer"},
                            "ami_pct": {
                                "type": "number",
                                "description": "AMI band as a fraction, e.g. 0.6"},
                        },
                        "required": ["bedrooms", "count"],
                    },
                },
                "market": {
                    "type": "string",
                    "description": (
                        "City, parish or HUD area name. Sets rent limits, utility "
                        "allowances and TDC limits. Call list_markets for what is "
                        "loaded.")},
                "state": {"type": "string"},
                "parish": {"type": "string"},
                "city": {"type": "string"},
                "asking_price": {"type": "number"},
                "rehab_per_unit": {
                    "type": "number",
                    "description": "Blended hard cost per unit for the rehab scope."},
                "committed_soft_money": {
                    "type": "number",
                    "description": "CDBG/HOME or other subsidy already awarded."},
                "soft_money_available": {
                    "type": "number",
                    "description": (
                        "Total subsidy obtainable, committed or not. Caps the "
                        "maximum supportable price.")},
                "building_type": {
                    "type": "string",
                    "enum": ["Detached/Semi-Detached", "Row House", "Walk-up", "Elevator"]},
                "project_type": {"type": "string", "enum": ["Family", "Senior", "Rehab"]},
                "credit_type": {"type": "string", "enum": ["4% bond", "9% competitive"]},
                "equity_price": {"type": "number", "description": "Cents per credit dollar, e.g. 0.85"},
                "basis_boost": {"type": "number", "description": "0.30 in a QCT/DDA, else 0"},
                "boost_eligible": {"type": "string", "enum": ["Yes", "No"]},
                "perm_coupon": {"type": "number"},
                "construction_rate": {"type": "number"},
                "sizing_dscr": {"type": "number"},
                "vacancy_rate": {"type": "number"},
                "pilot_in_place": {"type": "string", "enum": ["Yes", "No"]},
                "pilot_annual_payment": {"type": "number"},
                "insurance_per_unit": {"type": "number"},
                "has_pool": {"type": "boolean"},
                "elevator_sets": {"type": "integer"},
                "format": {"type": "string", "enum": ["markdown", "json", "both"],
                           "default": "both"},
            },
        },
    },
    {
        "name": "solve_max_price",
        "description": (
            "The most that can be paid for a deal given the subsidy obtainable, "
            "and the price supported at each level of subsidy. Takes the same "
            "fields as screen_deal."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "soft_money_available": {"type": "number"},
                "deal": {"type": "object", "description": "Any screen_deal fields."},
            },
        },
    },
    {
        "name": "sensitivity",
        "description": (
            "Re-screen a deal across a range of one input, to see what actually "
            "moves the answer. Common variables: rehab_per_unit, equity_price, "
            "perm_coupon, vacancy_rate, acquisition_cost, sizing_dscr."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "variable": {"type": "string"},
                "values": {"type": "array", "items": {"type": "number"}},
                "deal": {"type": "object", "description": "Any screen_deal fields."},
            },
            "required": ["variable", "values"],
        },
    },
    {
        "name": "get_defaults",
        "description": (
            "What the screen would assume for a property of this size and "
            "location, before running it. Use to show assumptions up front, or "
            "to check one before committing to it."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "units": {"type": "integer"},
                "state": {"type": "string"},
                "parish": {"type": "string"},
                "city": {"type": "string"},
                "has_pool": {"type": "boolean"},
                "elevator_sets": {"type": "integer"},
            },
            "required": ["units"],
        },
    },
    {
        "name": "list_markets",
        "description": (
            "Markets with bundled rent limits, utility allowances and TDC limits, "
            "and the source of each. A deal outside these can still be screened "
            "by supplying its own tables."),
        "inputSchema": {"type": "object", "properties": {}},
    },
]


# ------------------------------------------------------------ deal build ----

# Fields that pass straight through to DealInputs.
PASSTHROUGH = (
    "project_name", "project_type", "credit_type", "building_type",
    "boost_eligible", "basis_boost", "equity_price", "perm_coupon",
    "construction_rate", "sizing_dscr", "vacancy_rate", "pilot_in_place",
    "pilot_annual_payment", "insurance_per_unit", "syndication", "pool",
    "revenue_growth", "expense_growth", "valuation_cap_rate",
    "replacement_reserve_per_unit", "developer_fee_pct", "deferred_fee_pct",
)

DEFAULT_AMI = 0.60


def _default_mix(units: int) -> list[dict]:
    """A plain 1BR/2BR split, used only when a memo gives no unit mix."""
    two = units // 2
    return [
        {"bedrooms": 1, "bathrooms": 1, "sqft": 750, "count": units - two,
         "ami_pct": DEFAULT_AMI},
        {"bedrooms": 2, "bathrooms": 2, "sqft": 1000, "count": two,
         "ami_pct": DEFAULT_AMI},
    ]


def build_deal(args: dict) -> tuple[DealInputs, list, list[str]]:
    """Turn tool arguments into a solved-ready deal, plus assumptions and warnings."""
    warnings: list[str] = []
    provided: set[str] = set()

    mix = args.get("unit_mix")
    units = args.get("units")
    if not mix:
        if not units:
            raise ValueError("Provide either unit_mix or units.")
        mix = _default_mix(int(units))
        warnings.append(
            f"No unit mix given, so {units} units were split evenly between 1BR "
            f"and 2BR at {DEFAULT_AMI:.0%} AMI. Rents, and therefore the whole "
            f"screen, move materially with the real mix.")
    for row in mix:
        row.setdefault("ami_pct", DEFAULT_AMI)

    deal = DealInputs(mode="screen")
    deal.unit_mix = DealInputs.from_dict({"unit_mix": mix}).unit_mix

    for field in PASSTHROUGH:
        if args.get(field) is not None:
            setattr(deal, field, args[field])
            provided.add(field)

    if args.get("asking_price") is not None:
        deal.acquisition_cost = float(args["asking_price"])
    deal.cdbg = float(args.get("committed_soft_money") or 0)
    deal.lhc_home = 0.0
    if args.get("soft_money_available") is not None:
        deal.soft_money_available = float(args["soft_money_available"])

    if args.get("rehab_per_unit") is not None:
        for line in deal.construction:
            if line.key == "units":
                line.unit_cost = float(args["rehab_per_unit"])
    # Amenity lines a memo did not mention are not priced into the budget.
    if not args.get("has_pool"):
        for line in deal.construction:
            if line.key == "pool":
                line.unit_cost = 0.0
    if not args.get("elevator_sets"):
        for line in deal.construction:
            if line.key == "elevators":
                line.unit_cost = line.quantity = 0.0

    # -- market tables -------------------------------------------------------
    query = args.get("market") or args.get("city") or args.get("parish")
    if query:
        try:
            market = find_market(query, args.get("state"))
            market.apply_to(deal)
            provided |= {"rent_limits", "ua_electricity"}
        except MarketNotFound as exc:
            warnings.append(str(exc))
    else:
        warnings.append(
            "No market given, so New Orleans rent limits and utility allowances "
            "were used. Set `market` for anywhere else.")

    applied = defaults.apply(
        deal, state=args.get("state"), parish=args.get("parish"),
        city=args.get("city"), has_pool=args.get("has_pool"),
        elevator_sets=int(args.get("elevator_sets") or 0), provided=provided)

    # Soft costs that key off hard cost need the budget solved first.
    from lihtc_screen.engine import construction as construction_engine
    from lihtc_screen.engine import unitmix as unitmix_engine
    from lihtc_screen.engine.sources_uses import hard_costs
    mix_result = unitmix_engine.compute(deal)
    amounts = construction_engine.compute(deal, mix_result, 0, 0, 0, 0).amounts
    hard = hard_costs(deal, amounts)["hard_costs"]
    applied.assumptions.extend(defaults.derived_soft_costs(deal, hard, provided))

    return deal, applied.assumptions, warnings


# ------------------------------------------------------------ handlers ------

def tool_screen_deal(args: dict) -> dict:
    deal, assumptions, warnings = build_deal(args)
    result = run_screen(deal)
    fmt = args.get("format", "both")
    payload: dict = {"warnings": warnings}
    if fmt in ("json", "both"):
        payload["screen"] = to_dict(result)
        payload["assumptions"] = [
            {"input": a.label, "value": a.value, "basis": a.basis} for a in assumptions]
    if fmt in ("markdown", "both"):
        payload["dashboard"] = to_markdown(result, assumptions)
    return payload


def tool_solve_max_price(args: dict) -> dict:
    deal_args = dict(args.get("deal") or {})
    if args.get("soft_money_available") is not None:
        deal_args["soft_money_available"] = args["soft_money_available"]
    deal, assumptions, warnings = build_deal(deal_args)
    result = run_screen(deal)
    return {
        "warnings": warnings,
        "asking_price": deal.acquisition_cost,
        "max_supportable_price": result.max_supportable_price,
        "price_headroom": result.price_headroom,
        "required_soft_money": result.required_soft_money,
        "soft_money_at_zero_price": result.soft_money_at_zero_price,
        "price_by_soft_money": result.price_by_soft_money,
        "verdict": result.verdict,
    }


def tool_sensitivity(args: dict) -> dict:
    deal, _, warnings = build_deal(dict(args.get("deal") or {}))
    variable = args["variable"]
    values = args["values"]
    if not values:
        raise ValueError("values must not be empty")
    if len(values) > 12:
        raise ValueError("at most 12 values per run")
    return {"warnings": warnings, "variable": variable,
            "rows": sensitivity(deal, variable, values)}


def tool_get_defaults(args: dict) -> dict:
    units = int(args["units"])
    deal = DealInputs(mode="screen")
    deal.unit_mix = DealInputs.from_dict({"unit_mix": _default_mix(units)}).unit_mix
    applied = defaults.apply(
        deal, state=args.get("state"), parish=args.get("parish"),
        city=args.get("city"), has_pool=args.get("has_pool"),
        elevator_sets=int(args.get("elevator_sets") or 0))
    return {"units": units,
            "assumptions": [{"input": a.label, "value": a.value, "basis": a.basis}
                            for a in applied.assumptions]}


def tool_list_markets(_args: dict) -> dict:
    data = load_markets()
    markets = []
    for key in available_markets():
        entry = data["markets"][key]
        markets.append({
            "key": key, "name": entry["name"], "state": entry.get("state"),
            "aliases": entry.get("aliases", []),
            "rent_limit_source": entry["rent_limits"].get("source"),
            "utility_allowance_source": entry["utility_allowances"].get("source"),
            "tdc_region": entry.get("tdc_region"),
        })
    return {
        "markets": markets,
        "note": ("A deal outside these markets can still be screened by supplying "
                 "its own rent limits and utility allowances; nothing is "
                 "substituted from a neighbouring market."),
    }


HANDLERS = {
    "screen_deal": tool_screen_deal,
    "solve_max_price": tool_solve_max_price,
    "sensitivity": tool_sensitivity,
    "get_defaults": tool_get_defaults,
    "list_markets": tool_list_markets,
}


# ------------------------------------------------------------ JSON-RPC ------

def rpc_error(request_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id,
            "error": {"code": code, "message": message}}


def handle_rpc(message: dict) -> dict | None:
    request_id = message.get("id")
    method = message.get("method")
    params = message.get("params") or {}

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }}
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None                     # notifications take no reply
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name")
        handler = HANDLERS.get(name)
        if handler is None:
            return rpc_error(request_id, METHOD_NOT_FOUND, f"unknown tool {name!r}")
        try:
            payload = handler(params.get("arguments") or {})
        except (ValueError, KeyError, LookupError) as exc:
            return {"jsonrpc": "2.0", "id": request_id, "result": {
                "isError": True,
                "content": [{"type": "text", "text": str(exc)}],
            }}
        except Exception:                                  # noqa: BLE001
            traceback.print_exc()
            return rpc_error(request_id, INTERNAL, "the screen failed to run")
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "content": [{"type": "text", "text": json.dumps(payload, default=str)}],
            "structuredContent": payload,
        }}

    return rpc_error(request_id, METHOD_NOT_FOUND, f"unknown method {method!r}")


def authorised(header: str | None) -> bool:
    """Constant-time bearer check. With no token configured, refuse everything."""
    import hmac
    expected = os.environ.get("SCREEN_API_TOKEN")
    if not expected:
        return False
    if not header or not header.startswith("Bearer "):
        return False
    return hmac.compare_digest(header[7:], expected)


class handler(BaseHTTPRequestHandler):        # noqa: N801  (Vercel's entry point)
    server_version = "lihtc-screen"

    def _send(self, status: int, body: dict, extra: dict | None = None) -> None:
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):                          # noqa: N802
        # A liveness probe that does not require the token, and leaks nothing.
        if self.path.rstrip("/").endswith("/health"):
            self._send(200, {"status": "ok", "server": SERVER_INFO,
                             "markets": available_markets()})
            return
        self._send(405, {"error": "POST JSON-RPC to this endpoint"})

    def do_POST(self):                         # noqa: N802
        if not authorised(self.headers.get("Authorization")):
            self._send(401, {"error": "unauthorised"},
                       {"WWW-Authenticate": 'Bearer realm="lihtc-screen"'})
            return

        length = int(self.headers.get("Content-Length") or 0)
        if length > 2_000_000:
            self._send(413, rpc_error(None, INVALID_REQUEST, "request too large"))
            return
        try:
            message = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send(400, rpc_error(None, PARSE_ERROR, "invalid JSON"))
            return

        if isinstance(message, list):          # JSON-RPC batch
            replies = [r for r in (handle_rpc(m) for m in message) if r is not None]
            self._send(200, replies or {})
            return

        reply = handle_rpc(message)
        if reply is None:
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self._send(200, reply)

    def log_message(self, *args):
        pass                                    # keep the function logs quiet


if __name__ == "__main__":
    from http.server import HTTPServer
    port = int(os.environ.get("PORT", 8000))
    print(f"listening on http://127.0.0.1:{port}  (SCREEN_API_TOKEN required)")
    HTTPServer(("127.0.0.1", port), handler).serve_forever()

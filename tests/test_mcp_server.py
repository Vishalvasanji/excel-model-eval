"""The MCP connector: protocol, auth, and the tools it exposes."""

from __future__ import annotations

import json
import os
import sys
import threading
from http.server import HTTPServer
from pathlib import Path
from urllib import error, request

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp_server" / "api"))
os.environ.setdefault("SCREEN_API_TOKEN", "test-token")

import index as server  # noqa: E402

TOKEN = os.environ["SCREEN_API_TOKEN"]


@pytest.fixture(scope="module")
def base_url():
    httpd = HTTPServer(("127.0.0.1", 0), server.handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def rpc(base_url: str, method: str, params: dict | None = None,
        token: str | None = TOKEN, request_id: int = 1):
    body = json.dumps({"jsonrpc": "2.0", "id": request_id,
                       "method": method, "params": params or {}}).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = request.Request(base_url, data=body, headers=headers, method="POST")
    with request.urlopen(req, timeout=120) as response:
        return response.status, json.loads(response.read() or b"{}")


def call(base_url: str, name: str, arguments: dict):
    status, body = rpc(base_url, "tools/call", {"name": name, "arguments": arguments})
    assert status == 200, body
    assert "error" not in body, body["error"]
    return body["result"]


# -- auth -------------------------------------------------------------------

def test_rejects_missing_token(base_url):
    with pytest.raises(error.HTTPError) as exc:
        rpc(base_url, "tools/list", token=None)
    assert exc.value.code == 401


def test_rejects_wrong_token(base_url):
    with pytest.raises(error.HTTPError) as exc:
        rpc(base_url, "tools/list", token="not-the-token")
    assert exc.value.code == 401


def test_refuses_everything_when_no_token_is_configured(monkeypatch):
    monkeypatch.delenv("SCREEN_API_TOKEN", raising=False)
    assert not server.authorised("Bearer anything")
    assert not server.authorised(None)


def test_health_needs_no_token(base_url):
    with request.urlopen(base_url + "/health", timeout=30) as response:
        body = json.loads(response.read())
    assert body["status"] == "ok"


# -- protocol ---------------------------------------------------------------

def test_initialize(base_url):
    status, body = rpc(base_url, "initialize")
    assert status == 200
    assert body["result"]["protocolVersion"] == server.PROTOCOL_VERSION
    assert body["result"]["serverInfo"]["name"]


def test_tools_list_is_complete_and_well_formed(base_url):
    _, body = rpc(base_url, "tools/list")
    tools = {t["name"]: t for t in body["result"]["tools"]}
    assert set(tools) == set(server.HANDLERS)
    for name, tool in tools.items():
        assert tool["description"].strip(), f"{name} has no description"
        assert tool["inputSchema"]["type"] == "object"


def test_unknown_method_and_unknown_tool_are_errors(base_url):
    _, body = rpc(base_url, "nope/nope")
    assert body["error"]["code"] == server.METHOD_NOT_FOUND
    _, body = rpc(base_url, "tools/call", {"name": "nope", "arguments": {}})
    assert body["error"]["code"] == server.METHOD_NOT_FOUND


def test_notification_gets_no_reply(base_url):
    assert server.handle_rpc({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


# -- tools ------------------------------------------------------------------

WESTBEND = {
    "project_name": "Westbend",
    "market": "New Orleans", "state": "LA", "city": "New Orleans",
    "asking_price": 4_000_000,
    "unit_mix": [
        {"bedrooms": 1, "bathrooms": 1, "sqft": 900, "count": 110, "ami_pct": 0.6},
        {"bedrooms": 2, "bathrooms": 2, "sqft": 1100, "count": 170, "ami_pct": 0.6},
    ],
}


def test_screen_deal_returns_the_answer(base_url):
    result = call(base_url, "screen_deal", dict(WESTBEND))
    payload = result["structuredContent"]
    assert payload["screen"]["project"]["units"] == 280
    assert payload["screen"]["verdict"]["verdict"] in ("PENCILS", "MARGINAL", "FAIL")
    assert payload["screen"]["answer"]["required_soft_money"] > 0
    assert "Minimum soft funding needed" in payload["dashboard"]
    # Sources must balance against uses.
    su = payload["screen"]["sources_and_uses"]
    assert abs(su["balance"]) < 1.0


def test_screen_deal_reports_its_assumptions(base_url):
    payload = call(base_url, "screen_deal", dict(WESTBEND))["structuredContent"]
    assert payload["assumptions"]
    for assumption in payload["assumptions"]:
        assert assumption["basis"]


def test_screen_deal_warns_when_the_unit_mix_is_guessed(base_url):
    payload = call(base_url, "screen_deal",
                   {"units": 100, "market": "New Orleans"})["structuredContent"]
    assert any("unit mix" in w.lower() for w in payload["warnings"])


def test_screen_deal_warns_on_an_unloaded_market(base_url):
    args = dict(WESTBEND, market="Baton Rouge")
    payload = call(base_url, "screen_deal", args)["structuredContent"]
    assert any("Baton Rouge" in w for w in payload["warnings"])


def test_screen_deal_needs_units_or_a_mix(base_url):
    result = call(base_url, "screen_deal", {"market": "New Orleans"})
    assert result["isError"]
    assert "unit_mix" in result["content"][0]["text"]


def test_committed_soft_money_flows_through(base_url):
    args = dict(WESTBEND, committed_soft_money=5_000_000)
    answer = call(base_url, "screen_deal", args)["structuredContent"]["screen"]["answer"]
    assert answer["committed_soft_money"] == 5_000_000
    assert answer["additional_soft_money_needed"] == pytest.approx(
        max(0.0, answer["required_soft_money"] - 5_000_000), abs=1.0)


def test_solve_max_price(base_url):
    payload = call(base_url, "solve_max_price", {
        "soft_money_available": 12_000_000, "deal": dict(WESTBEND)})["structuredContent"]
    assert payload["max_supportable_price"] is not None
    assert payload["price_by_soft_money"]


def test_sensitivity(base_url):
    payload = call(base_url, "sensitivity", {
        "variable": "rehab_per_unit", "values": [60_000, 100_000, 140_000],
        "deal": dict(WESTBEND)})["structuredContent"]
    costs = [row["total_development_cost"] for row in payload["rows"]]
    assert costs == sorted(costs)


def test_sensitivity_rejects_an_unbounded_run(base_url):
    result = call(base_url, "sensitivity", {
        "variable": "equity_price", "values": list(range(20)), "deal": dict(WESTBEND)})
    assert result["isError"]


def test_get_defaults(base_url):
    payload = call(base_url, "get_defaults",
                   {"units": 150, "state": "LA", "city": "Shreveport"})["structuredContent"]
    staffing = next(a for a in payload["assumptions"] if a["input"] == "Site staffing")
    assert "2 maintenance staffs" in staffing["value"] or "2 maintenance" in staffing["value"]
    insurance = next(a for a in payload["assumptions"] if a["input"] == "Property insurance")
    assert "1,000" in insurance["value"], "Shreveport is inland"


def test_list_markets(base_url):
    payload = call(base_url, "list_markets", {})["structuredContent"]
    assert payload["markets"]
    for market in payload["markets"]:
        assert market["rent_limit_source"]
        assert market["utility_allowance_source"]

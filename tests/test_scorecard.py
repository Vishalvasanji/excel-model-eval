"""The scorecard must reproduce the workbook's KPI statuses and verdict."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lihtc_screen.inputs import DealInputs
from lihtc_screen.model import solve
from lihtc_screen.scorecard import evaluate

FIXTURE = Path(__file__).parent / "fixtures" / "westbend_expected.json"


@pytest.fixture(scope="module")
def dashboard() -> dict:
    return json.loads(FIXTURE.read_text())["sheets"]["Dashboard Calc"]["cells"]


@pytest.fixture(scope="module")
def card():
    return evaluate(solve(DealInputs(mode="workbook")))


def _workbook_status(dashboard: dict, kpi_id: str) -> str | None:
    for row in range(3, 37):
        if dashboard.get(f"K{row}") == kpi_id:
            return dashboard.get(f"P{row}")
    return None


def test_verdict(dashboard, card):
    assert card.verdict == dashboard["B29"]


def test_counts(dashboard, card):
    assert card.hard_fails == int(dashboard["B26"])
    assert card.warnings == int(dashboard["B27"])
    assert card.pending == int(dashboard["B28"])


def test_all_kpis_present(dashboard, card):
    expected = {dashboard[f"K{row}"] for row in range(3, 37) if dashboard.get(f"K{row}")}
    assert {c.kpi_id for c in card.checks} == expected


def test_every_kpi_status_matches(dashboard, card):
    mismatches = [
        f"{c.kpi_id}: engine {c.status}, workbook {_workbook_status(dashboard, c.kpi_id)}"
        for c in card.checks
        if c.status != _workbook_status(dashboard, c.kpi_id)
    ]
    assert not mismatches, "\n".join(mismatches)


def test_failing_rules_carry_citations_and_messages(card):
    for check in card.failing():
        assert check.citation, f"{check.kpi_id} has no QAP citation"
        assert check.message, f"{check.kpi_id} fails without explaining why"


def test_verdict_responds_to_a_hard_fail():
    """A deal priced far beyond the QAP cost cap must fail."""
    deal = DealInputs(mode="workbook", acquisition_cost=60_000_000)
    card = evaluate(solve(deal))
    assert card.verdict == "FAIL"
    assert any(c.kpi_id == "QAP-TDC-PERUNIT" and c.status == "FAIL"
               for c in card.checks)

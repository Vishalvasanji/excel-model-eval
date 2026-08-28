"""The CLI must never let one deal inherit another's facts."""

from __future__ import annotations

import json

import pytest

from lihtc_screen.cli import DEAL_SPECIFIC, main

DEAL = {
    "project_name": "Test Court",
    "market": "New Orleans", "state": "LA", "city": "New Orleans",
    "asking_price": 3_000_000,
    "unit_mix": [
        {"bedrooms": 1, "bathrooms": 1, "sqft": 800, "count": 40, "ami_pct": 0.6},
        {"bedrooms": 2, "bathrooms": 2, "sqft": 1000, "count": 60, "ami_pct": 0.6},
    ],
}


def _write(tmp_path, deal):
    path = tmp_path / "deal.json"
    path.write_text(json.dumps(deal))
    return str(path)


def test_screens_a_deal(tmp_path, capsys):
    assert main(["screen", _write(tmp_path, DEAL)]) == 0
    out = capsys.readouterr().out
    assert "Test Court - 100 units" in out
    assert "Minimum soft funding needed" in out


def test_emits_json(tmp_path, capsys):
    assert main(["screen", _write(tmp_path, DEAL), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["screen"]["project"]["units"] == 100
    assert abs(payload["screen"]["sources_and_uses"]["balance"]) < 1.0


def test_a_missing_unit_mix_is_refused(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main(["screen", _write(tmp_path, {"project_name": "X", "asking_price": 1})])
    assert "unit_mix" in str(exc.value)


@pytest.mark.parametrize("field", sorted(DEAL_SPECIFIC))
def test_deal_specific_facts_are_never_inherited(tmp_path, capsys, field):
    """A fact the deal file omits must be blank, not the workbook's value."""
    main(["screen", _write(tmp_path, DEAL), "--json"])
    payload = json.loads(capsys.readouterr().out)
    screened = {
        "acquisition_cost": payload["screen"]["answer"]["asking_price"],
        "cdbg": payload["screen"]["answer"]["committed_soft_money"],
        "lhc_home": payload["screen"]["answer"]["committed_soft_money"],
        "building_basis_addition": None,
    }[field]
    if field == "acquisition_cost":
        assert screened == DEAL["asking_price"]      # supplied, so honoured
    elif screened is not None:
        assert screened == 0, f"{field} was inherited from the workbook defaults"


def test_committed_soft_money_is_honoured(tmp_path, capsys):
    main(["screen", _write(tmp_path, dict(DEAL, committed_soft_money=2_000_000)),
          "--json"])
    answer = json.loads(capsys.readouterr().out)["screen"]["answer"]
    assert answer["committed_soft_money"] == 2_000_000


def test_markets_command_lists_sources(capsys):
    assert main(["markets"]) == 0
    out = capsys.readouterr().out
    assert "new-orleans-la" in out
    assert "HUD FY2025 MTSP" in out


def test_unbundled_market_warns_but_still_screens(tmp_path, capsys):
    main(["screen", _write(tmp_path, dict(DEAL, market="Baton Rouge")), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert any("Baton Rouge" in w for w in payload["warnings"])
    assert payload["screen"]["verdict"]["verdict"]

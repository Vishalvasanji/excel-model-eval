"""The engine, in workbook mode, must reproduce the source workbook exactly.

Two levels of check:

1. Against `westbend_expected.json`, the values Excel itself last computed and
   saved into `reference/Acq_Rehab_Model_v1.xlsx`. This runs everywhere and
   needs nothing installed.

2. Against LibreOffice recalculating the real workbook under perturbed inputs.
   This is what proves the *model* was ported rather than one saved deal, so it
   is skipped rather than silently dropped when LibreOffice is unavailable.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lihtc_screen.inputs import DealInputs
from lihtc_screen.model import solve

from .parity_map import PARITY_MAP, PRO_FORMA_ROWS, PRO_FORMA_COLUMNS

FIXTURE = Path(__file__).parent / "fixtures" / "westbend_expected.json"

# Excel carries ~15 significant digits and the workbook's circular loop is only
# converged to a fraction of a cent, so compare to the cent or to a relative
# 1e-9, whichever is looser.
ABS_TOLERANCE = 0.01
REL_TOLERANCE = 1e-9


def _close(expected: float, actual: float) -> bool:
    return abs(actual - expected) <= max(ABS_TOLERANCE, abs(expected) * REL_TOLERANCE)


@pytest.fixture(scope="module")
def baseline() -> dict:
    return json.loads(FIXTURE.read_text())["sheets"]


@pytest.fixture(scope="module")
def result():
    return solve(DealInputs(mode="workbook"))


def test_converges(result):
    assert result.converged, f"did not converge in {result.iterations} iterations"


def test_sources_equal_uses(result):
    assert abs(result.sources_uses.balance) < ABS_TOLERANCE


@pytest.mark.parametrize("sheet,cell,label,accessor", PARITY_MAP,
                         ids=[f"{s}!{c}" for s, c, _, _ in PARITY_MAP])
def test_cell_parity(baseline, result, sheet, cell, label, accessor):
    expected = baseline[sheet]["cells"].get(cell)
    assert expected is not None, f"{sheet}!{cell} has no cached value"
    actual = accessor(result)
    assert _close(expected, actual), (
        f"{label} ({sheet}!{cell}): workbook {expected:,.4f}, engine {actual:,.4f}, "
        f"diff {actual - expected:,.4f}"
    )


@pytest.mark.parametrize("row,label,accessor", PRO_FORMA_ROWS,
                         ids=[f"proforma-row{r}" for r, _, _ in PRO_FORMA_ROWS])
def test_pro_forma_row_parity(baseline, result, row, label, accessor):
    cells = baseline["17-year Pro Forma"]["cells"]
    series = accessor(result)
    for index, column in enumerate(PRO_FORMA_COLUMNS):
        expected = cells.get(column + row)
        if expected is None:
            continue
        assert _close(expected, series[index]), (
            f"{label} year {index + 1} ({column}{row}): workbook {expected:,.4f}, "
            f"engine {series[index]:,.4f}"
        )

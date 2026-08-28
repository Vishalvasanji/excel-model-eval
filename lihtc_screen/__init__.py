"""LIHTC acquisition/rehab underwriting screen.

A Python port of `reference/Acq_Rehab_Model_v1.xlsx`, validated against the
workbook cell for cell. `model.solve` runs the model; `solver.screen` answers
the two screening questions - the minimum soft funding a deal needs and the
maximum price it supports.
"""

from .inputs import DealInputs
from .model import Result, solve
from .scorecard import Scorecard, evaluate
from .solver import Screen, max_supportable_price, screen, sensitivity

__all__ = ["DealInputs", "Result", "solve", "Scorecard", "evaluate",
           "Screen", "screen", "max_supportable_price", "sensitivity"]

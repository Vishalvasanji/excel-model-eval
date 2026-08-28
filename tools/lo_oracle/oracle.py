"""Recalculate the real workbook with LibreOffice Calc, as a validation oracle.

Why this exists: the Python engine in `lihtc_screen` is a port of
`reference/Acq_Rehab_Model_v1.xlsx`. The workbook's own cached values prove the
port on exactly one deal (Westbend). This oracle drives the real workbook across
arbitrary input perturbations, so the port can be checked against Excel's own
logic on many deals rather than one.

Two things were established the hard way and are load-bearing here:

1. Cells are set through UNO, in place, rather than with openpyxl. openpyxl
   drops every cached value on save, and those cached values seed the workbook's
   deliberate Sources&Uses <-> Financing circular loop. Without them the
   iteration starts from zero and does not converge: an edit-free openpyxl round
   trip throws Sources vs Uses out by $34M, while the same file straight through
   LibreOffice reproduces Excel to the cent.
2. Iterative calculation is enabled on the *document* (`IsIterationEnabled`).
   LibreOffice does not honour the `iterate="1"` flag the xlsx carries, and the
   equivalent profile setting did not take effect in this environment.

Requires `libreoffice-calc` and `python3-uno`. `available()` reports whether the
oracle can run, so tests can skip rather than fail.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
DEFAULT_WORKBOOK = REPO / "reference" / "Acq_Rehab_Model_v1.xlsx"

# The workbook's own setting; mirrored here because LibreOffice ignores the file's.
ITERATION_COUNT = 1000
ITERATION_EPSILON = 1e-7

# calculateAll() advances the circular loop by a bounded amount, so it is called
# repeatedly until the loop settles. Convergence is judged on the workbook's own
# Sources-minus-Uses balance, which is zero exactly when the loop has closed.
# A large input change needs ~40 passes; each pass is only a few milliseconds.
BALANCE_CELL = ("Sources & Uses", "I80")
BALANCE_TOLERANCE = 0.01          # dollars
MAX_CONVERGENCE_PASSES = 200
MIN_CONVERGENCE_PASSES = 5


def available() -> bool:
    """True when LibreOffice Calc and python3-uno are both usable."""
    if shutil.which("soffice") is None:
        return False
    if not Path("/usr/lib/libreoffice/share/registry/calc.xcd").exists():
        return False
    try:
        import uno  # noqa: F401
    except ImportError:
        return False
    return True


class Oracle:
    """A headless LibreOffice instance that recalculates the workbook on demand.

    Starting soffice costs a few seconds, so the process is kept alive for the
    life of the object and reused across `recalc` calls. Use as a context
    manager, or call `close()`.
    """

    def __init__(self, workbook: Path | None = None, startup_timeout: int = 120):
        if not available():
            raise RuntimeError(
                "LibreOffice Calc / python3-uno not installed. Install with: "
                "apt-get update && apt-get install -y libreoffice-calc python3-uno"
            )
        self.workbook = Path(workbook or DEFAULT_WORKBOOK)
        self._tmp = tempfile.TemporaryDirectory(prefix="lo-oracle-")
        self._root = Path(self._tmp.name)
        self._pipe = f"lo_oracle_{uuid.uuid4().hex[:12]}"
        self._proc = None
        self._desktop = None
        self._start(startup_timeout)

    # -- lifecycle ---------------------------------------------------------
    def _start(self, timeout: int) -> None:
        import uno
        from com.sun.star.connection import NoConnectException

        profile = self._root / "profile"
        profile.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        env["HOME"] = str(self._root)

        self._proc = subprocess.Popen(
            [
                "soffice",
                f"-env:UserInstallation=file://{profile}",
                f"--accept=pipe,name={self._pipe};urp;",
                "--headless", "--norestore", "--nolockcheck",
                "--nodefault", "--nofirststartwizard",
            ],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext(
            "com.sun.star.bridge.UnoUrlResolver", local)
        url = f"uno:pipe,name={self._pipe};urp;StarOffice.ComponentContext"

        deadline = time.time() + timeout
        while True:
            try:
                ctx = resolver.resolve(url)
                break
            except NoConnectException:
                if time.time() > deadline:
                    raise RuntimeError("LibreOffice did not accept a UNO connection in time")
                if self._proc.poll() is not None:
                    raise RuntimeError("LibreOffice exited during startup")
                time.sleep(0.3)

        self._desktop = ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", ctx)

    def close(self) -> None:
        if self._proc is not None:
            try:
                self._desktop.terminate()
            except Exception:
                pass
            try:
                self._proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None
        self._tmp.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # -- the one useful operation ------------------------------------------
    def recalc(self, sets: dict[tuple[str, str], object],
               gets: list[tuple[str, str]]) -> dict[tuple[str, str], object]:
        """Apply `sets` to a fresh copy of the workbook, recalculate, read `gets`.

        Keys are (sheet_name, cell_ref), e.g. ("Unit Mix+Rents", "D8").
        Numeric cells come back as float, text cells as str, blanks as None.
        The reference workbook on disk is never modified.
        """
        import uno
        from com.sun.star.beans import PropertyValue

        scratch = self._root / f"run_{uuid.uuid4().hex[:8]}.xlsx"
        shutil.copy(self.workbook, scratch)

        hidden = PropertyValue(); hidden.Name = "Hidden"; hidden.Value = True
        doc = self._desktop.loadComponentFromURL(
            uno.systemPathToFileUrl(str(scratch)), "_blank", 0, (hidden,))
        try:
            # LibreOffice ignores the xlsx's own iterate flag, so set it here.
            doc.IsIterationEnabled = True
            doc.IterationCount = ITERATION_COUNT
            doc.IterationEpsilon = ITERATION_EPSILON

            sheets = doc.Sheets
            for (sheet_name, ref), value in sets.items():
                cell = sheets.getByName(sheet_name).getCellRangeByName(ref)
                if isinstance(value, bool):
                    cell.setString(str(value))
                elif isinstance(value, (int, float)):
                    cell.setValue(float(value))
                else:
                    cell.setString(str(value))

            balance = sheets.getByName(BALANCE_CELL[0]).getCellRangeByName(BALANCE_CELL[1])
            for i in range(MAX_CONVERGENCE_PASSES):
                doc.calculateAll()
                if i + 1 >= MIN_CONVERGENCE_PASSES and abs(balance.getValue()) < BALANCE_TOLERANCE:
                    break
            else:
                raise RuntimeError(
                    f"circular loop did not converge: Sources - Uses = "
                    f"{balance.getValue():,.2f} after {MAX_CONVERGENCE_PASSES} passes"
                )

            out: dict[tuple[str, str], object] = {}
            for sheet_name, ref in gets:
                cell = sheets.getByName(sheet_name).getCellRangeByName(ref)
                # getType(): EMPTY=0, VALUE=1, TEXT=2, FORMULA=3
                kind = cell.getType().value
                if kind == "EMPTY":
                    out[(sheet_name, ref)] = None
                elif kind == "TEXT":
                    out[(sheet_name, ref)] = cell.getString()
                elif kind == "FORMULA":
                    # A formula resolves to either a number or a string; the
                    # displayed string is number-formatted, so only trust it
                    # when the result really is text.
                    out[(sheet_name, ref)] = (
                        cell.getString()
                        if cell.FormulaResultType.value == "TEXT"
                        else cell.getValue()
                    )
                else:
                    out[(sheet_name, ref)] = cell.getValue()
            return out
        finally:
            doc.close(False)
            scratch.unlink(missing_ok=True)

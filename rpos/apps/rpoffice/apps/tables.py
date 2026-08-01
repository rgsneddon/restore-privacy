"""Tables — Raskul independent spreadsheet program (standalone).

Corel-historical independent suite design (not Microsoft Excel; not Quattro Pro
trademark). Core: grid, formulas (refs, SUM, IF), multi-sheet workbook,
insert/delete rows/cols, undo/redo, durable JSON round-trip.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .. import __version__
from ..brand import DESIGN_LINEAGE, MAKER, PRODUCT_FAMILY, TABLES
from ..sheet import (
    FormulaError,
    Workbook,
    WorkbookEditor,
    create_spreadsheet,
    create_workbook,
)


def smoke() -> dict[str, Any]:
    """Ship-path smoke: independent spreadsheet core + round-trip + edit ops."""
    wb = create_workbook(f"{TABLES} budget", "Main")
    ed = WorkbookEditor(wb)
    ed.set_ref("A1", 10)
    ed.set_ref("B1", 5)
    ed.set_ref("C1", "=A1+B1")
    ed.set_ref("A2", 1)
    ed.set_ref("A3", 2)
    ed.set_ref("A4", 3)
    ed.set_ref("B2", "=SUM(A2:A4)")
    ed.set_ref("D1", '=IF(A1>0,"yes","no")')
    total = ed.evaluate("=A1+B1")
    ssum = ed.evaluate("=SUM(A2:A4)")
    iff = ed.evaluate("=IF(A1>0,1,0)")
    # change dependency
    ed.set_ref("A1", 20)
    total2 = ed.sheet.value_ref("C1")
    # second sheet isolation
    ed.add_sheet("Other")
    ed.set_ref("A1", 999)
    ed.select_sheet("Main")
    assert ed.sheet.get_ref("A1") == 20
    # structure + undo
    ed.insert_rows(1, 1)
    ed.undo()
    # fail closed
    bad = None
    try:
        ed.evaluate("=NOPE()")
    except FormulaError as exc:
        bad = exc.code
    raw = wb.dumps()
    again = Workbook.loads(raw)
    return {
        "ok": True,
        "product": TABLES,
        "family": PRODUCT_FAMILY,
        "version": __version__,
        "kind": "spreadsheet",
        "maker": MAKER,
        "design_lineage": DESIGN_LINEAGE,
        "title": again.title,
        "sheets": again.list_sheets(),
        "formula_A1_plus_B1": total,
        "formula_after_recalc": total2,
        "sum_A2_A4": ssum,
        "if_result": iff,
        "bad_formula": bad,
        "rows": again.active.nrows,
        "schema_version": again.schema_version,
        "round_trip": again.active.get_ref("B1") == 5,
        "honesty": (
            "Tables independent spreadsheet core (grid, formulas, multi-sheet, "
            "structure, undo); Corel-historical suite design; "
            "not full Microsoft Excel parity; not Corel Quattro Pro trademark"
        ),
    }


def cmd_demo(out: Path | None) -> dict[str, Any]:
    r = smoke()
    wb = create_workbook("Tables demo", "Data")
    ed = WorkbookEditor(wb)
    ed.set_ref("A1", "Item")
    ed.set_ref("B1", "Qty")
    ed.set_ref("A2", "Pens")
    ed.set_ref("B2", 3)
    ed.set_ref("A3", "Ink")
    ed.set_ref("B3", 7)
    ed.set_ref("B4", "=SUM(B2:B3)")
    path = str(out) if out else ""
    if out:
        wb.save(out)
    return {"ok": True, "product": TABLES, "path": path, "smoke": r, "B4": ed.sheet.value_ref("B4")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="tables",
        description=(
            f"{TABLES} — Raskul independent spreadsheets "
            f"({DESIGN_LINEAGE}; not Microsoft Excel)"
        ),
    )
    ap.add_argument("--version", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("-o", "--output", default="")
    args = ap.parse_args(argv)
    if args.version:
        print(f"{TABLES} {__version__} ({MAKER})")
        return 0
    out = Path(args.output) if args.output else None
    if args.demo:
        print(json.dumps(cmd_demo(out), indent=2))
        return 0
    print(json.dumps(smoke(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

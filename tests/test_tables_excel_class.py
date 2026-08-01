"""Tables Excel-class core: grid, formulas, sheets, structure, undo, entry."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "rpos" / "apps"))


class TestTablesGridRoundTrip(unittest.TestCase):
    def test_grid_values_round_trip(self) -> None:
        from rpoffice.sheet import Spreadsheet, create_spreadsheet

        s = create_spreadsheet("Budget")
        s.set_cell(0, 0, 10)
        s.set_cell(0, 1, "hello")
        s.set_cell(1, 0, "")
        s.set_cell(2, 2, 3.5)
        again = Spreadsheet.loads(s.dumps())
        self.assertEqual(again.title, "Budget")
        self.assertEqual(again.get_cell(0, 0), 10)
        self.assertEqual(again.get_cell(0, 1), "hello")
        self.assertEqual(again.get_cell(1, 0), "")
        self.assertEqual(again.get_cell(2, 2), 3.5)
        self.assertGreaterEqual(again.nrows, 3)
        self.assertGreaterEqual(again.ncols, 3)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "s.tables.json"
            again.save(path)
            loaded = Spreadsheet.load(path)
            self.assertEqual(loaded.get_ref("A1"), 10)
            self.assertEqual(loaded.get_ref("B1"), "hello")


class TestTablesFormulas(unittest.TestCase):
    def test_sum_if_arithmetic_recalc_fail_closed(self) -> None:
        from rpoffice.sheet import FormulaError, create_spreadsheet

        s = create_spreadsheet("F")
        s.set_ref("A1", 10)
        s.set_ref("B1", 5)
        s.set_ref("C1", "=A1+B1")
        self.assertEqual(s.evaluate("=A1+B1"), 15)
        self.assertEqual(s.value_ref("C1"), 15)
        s.set_ref("A2", 1)
        s.set_ref("A3", 2)
        s.set_ref("A4", 3)
        self.assertEqual(s.evaluate("=SUM(A2:A4)"), 6)
        self.assertEqual(s.evaluate("=IF(A1>0,1,0)"), 1)
        self.assertEqual(s.evaluate('=IF(A1>100,"hi","lo")'), "lo")
        # recalc after change
        s.set_ref("A1", 20)
        self.assertEqual(s.value_ref("C1"), 25)
        self.assertEqual(s.evaluate("=IF(A1>0,1,0)"), 1)
        # fail closed
        with self.assertRaises(FormulaError) as ctx:
            s.evaluate("=NOPE()")
        self.assertTrue(str(ctx.exception.code).startswith("#"))
        # div zero
        s.set_ref("D1", 0)
        self.assertEqual(s.evaluate("=A1/D1"), "#DIV/0!")
        # recalculate map
        s.set_ref("E1", "=SUM(A2:A4)")
        calc = s.recalculate()
        self.assertEqual(calc.get("C1"), 25)
        self.assertEqual(calc.get("E1"), 6)


class TestTablesStructureEdit(unittest.TestCase):
    def test_sheets_insert_delete_undo(self) -> None:
        from rpoffice.sheet import WorkbookEditor, create_workbook

        wb = create_workbook("WB", "Main")
        ed = WorkbookEditor(wb)
        self.assertIs(ed.workbook, wb)
        ed.set_ref("A1", 1)
        ed.set_ref("B1", 2)
        ed.add_sheet("Other")
        ed.set_ref("A1", 999)
        ed.select_sheet("Main")
        self.assertEqual(ed.sheet.get_ref("A1"), 1)
        self.assertEqual(wb.select_sheet("Other").get_ref("A1"), 999)
        ed.select_sheet("Main")
        ed.insert_rows(0, 1)
        # A1 content shifted down
        self.assertEqual(ed.sheet.get_ref("A2"), 1)
        self.assertTrue(ed.undo())
        self.assertIs(ed.workbook, wb)
        self.assertEqual(ed.sheet.get_ref("A1"), 1)
        ed.insert_cols(0, 1)
        self.assertEqual(ed.sheet.get_ref("B1"), 1)
        ed.delete_cols(0, 1)
        self.assertEqual(ed.sheet.get_ref("A1"), 1)
        # shared identity after undo
        ed.set_ref("Z9", "x")
        self.assertTrue(ed.undo())
        self.assertNotEqual(wb.active.get_ref("Z9"), "x")


class TestTablesEntry(unittest.TestCase):
    def test_smoke_and_cli_twice(self) -> None:
        from rpoffice.apps.tables import main, smoke
        from rpoffice.brand import TABLES
        from rpoffice.parity_scope import matrix_as_dict, tables_excel_class_core_rows

        for _ in range(2):
            r = smoke()
            self.assertTrue(r["ok"])
            self.assertEqual(r["product"], TABLES)
            self.assertEqual(r["maker"], "Raskul")
            self.assertEqual(r["formula_A1_plus_B1"], 15)
            self.assertEqual(r["formula_after_recalc"], 25)
            self.assertEqual(r["sum_A2_A4"], 6)
            self.assertEqual(r["if_result"], 1)
            self.assertTrue(str(r["bad_formula"]).startswith("#"))
            self.assertTrue(r["round_trip"])
            self.assertIn("not full microsoft excel", r["honesty"].lower())
            self.assertIn("Main", r["sheets"])

        self.assertEqual(main(["--version"]), 0)
        self.assertEqual(main(["--smoke"]), 0)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "demo.tables.json"
            self.assertEqual(main(["--demo", "-o", str(path)]), 0)
            self.assertTrue(path.is_file())
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data.get("product"), "Tables")
            self.assertEqual(data.get("kind"), "tables_workbook")

        m = matrix_as_dict()
        self.assertIn(TABLES, m["implemented_pillars"])
        core = tables_excel_class_core_rows()
        self.assertGreaterEqual(len(core), 4)
        out = [r for r in m["matrix"] if r["pillar"] == TABLES and r["status"] == "out_of_scope"]
        self.assertTrue(out)


if __name__ == "__main__":
    unittest.main()

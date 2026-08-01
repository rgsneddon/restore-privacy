"""Tables / Excel-class spreadsheet model (handmade Raskul — not Microsoft Excel).

Core: 2D grid, numbers/text/blank, A1 refs, formulas (=A1+B1, SUM, IF), multi-sheet
workbooks, insert/delete rows/cols, undo/redo, JSON round-trip.

Honesty: Excel-class *core* outcomes — not XLSX/VBA/charts/pivots/collaboration.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

KIND_SHEET = "tables_sheet"
KIND_WORKBOOK = "tables_workbook"
SCHEMA_VERSION = 2

_CELL_REF = re.compile(r"\b([A-Z]+)([0-9]+)\b")
_RANGE_REF = re.compile(
    r"([A-Z]+)([0-9]+)\s*:\s*([A-Z]+)([0-9]+)", re.IGNORECASE
)


class FormulaError(Exception):
    """Fail-closed formula evaluation error (never silent wrong success)."""

    def __init__(self, message: str, code: str = "#ERROR!") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def col_letters_to_index(letters: str) -> int:
    n = 0
    for ch in letters.upper():
        if not ("A" <= ch <= "Z"):
            raise ValueError(f"bad column letters: {letters!r}")
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n - 1


def index_to_col_letters(index: int) -> str:
    if index < 0:
        raise ValueError("column index must be >= 0")
    n = index + 1
    out = []
    while n:
        n, rem = divmod(n - 1, 26)
        out.append(chr(ord("A") + rem))
    return "".join(reversed(out))


def cell_ref_to_rc(ref: str) -> tuple[int, int]:
    m = _CELL_REF.fullmatch(ref.strip().upper())
    if not m:
        raise ValueError(f"bad cell ref: {ref!r}")
    col = col_letters_to_index(m.group(1))
    row = int(m.group(2)) - 1
    if row < 0:
        raise ValueError(f"bad cell ref: {ref!r}")
    return row, col


def rc_to_cell_ref(row: int, col: int) -> str:
    return f"{index_to_col_letters(col)}{row + 1}"


def parse_range(ref: str) -> tuple[int, int, int, int]:
    """Return (r1, c1, r2, c2) inclusive, normalized min/max."""
    m = _RANGE_REF.fullmatch(ref.strip().upper())
    if not m:
        raise ValueError(f"bad range: {ref!r}")
    r1, c1 = cell_ref_to_rc(m.group(1) + m.group(2))
    r2, c2 = cell_ref_to_rc(m.group(3) + m.group(4))
    return min(r1, r2), min(c1, c2), max(r1, r2), max(c1, c2)


@dataclass
class Cell:
    """One grid cell: stored value or formula text."""

    raw: Any = ""  # number, str, blank; formulas as strings starting with =

    def is_formula(self) -> bool:
        return isinstance(self.raw, str) and self.raw.strip().startswith("=")

    def to_dict(self) -> dict[str, Any]:
        return {"raw": self.raw}

    @classmethod
    def from_dict(cls, data: Any) -> "Cell":
        if isinstance(data, dict):
            return cls(raw=data.get("raw", ""))
        # legacy plain value
        return cls(raw=data)


@dataclass
class Spreadsheet:
    """One named worksheet grid."""

    title: str
    cells: dict[str, Cell] = field(default_factory=dict)  # "A1" -> Cell
    nrows: int = 1
    ncols: int = 1
    sheet_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    # --- dimensions ---
    def _ensure_size(self, row: int, col: int) -> None:
        if row < 0 or col < 0:
            raise ValueError("row/col must be >= 0")
        self.nrows = max(self.nrows, row + 1)
        self.ncols = max(self.ncols, col + 1)

    def set_cell(self, row: int, col: int, value: Any) -> None:
        self._ensure_size(row, col)
        ref = rc_to_cell_ref(row, col)
        self.cells[ref] = Cell(raw=value)

    def set_ref(self, ref: str, value: Any) -> None:
        r, c = cell_ref_to_rc(ref)
        self.set_cell(r, c, value)

    def get_cell(self, row: int, col: int) -> Any:
        if row < 0 or col < 0:
            return None
        ref = rc_to_cell_ref(row, col)
        cell = self.cells.get(ref)
        if cell is None:
            return ""
        return cell.raw

    def get_ref(self, ref: str) -> Any:
        r, c = cell_ref_to_rc(ref)
        return self.get_cell(r, c)

    def get_cell_obj(self, row: int, col: int) -> Cell | None:
        return self.cells.get(rc_to_cell_ref(row, col))

    # legacy rows view for simple consumers / round-trip of dense grid
    @property
    def rows(self) -> list[list[Any]]:
        grid: list[list[Any]] = []
        for r in range(self.nrows):
            row: list[Any] = []
            for c in range(self.ncols):
                row.append(self.get_cell(r, c))
            grid.append(row)
        return grid

    @rows.setter
    def rows(self, value: list[list[Any]]) -> None:
        self.cells.clear()
        self.nrows = max(1, len(value) if value else 1)
        self.ncols = 1
        for r, row in enumerate(value or []):
            if not isinstance(row, list):
                continue
            for c, v in enumerate(row):
                if v != "" and v is not None:
                    self.set_cell(r, c, v)
                else:
                    self._ensure_size(r, c)

    def _numeric(
        self,
        value: Any,
        *,
        depth: int = 0,
        visiting: set[str] | None = None,
    ) -> float:
        if depth > 32:
            raise FormulaError("formula too deep or circular", "#CYCLE!")
        if value is None or value == "":
            return 0.0
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip()
        if s.startswith("="):
            res = self.evaluate(s, depth=depth + 1, visiting=visiting)
            if isinstance(res, str) and res.startswith("#"):
                raise FormulaError(res, res)
            return float(res)
        try:
            return float(s)
        except ValueError as exc:
            raise FormulaError(f"not a number: {value!r}", "#VALUE!") from exc

    def evaluate(
        self,
        formula: str,
        *,
        depth: int = 0,
        visiting: set[str] | None = None,
    ) -> float | str | bool:
        """Evaluate formula; fail closed with FormulaError or #CODE! strings for div0."""
        f = (formula or "").strip()
        if not f.startswith("="):
            raise FormulaError("formula must start with =", "#ERROR!")
        expr = f[1:].strip()
        # normalize for matching but keep original case for IF strings
        expr_u = expr.upper()
        visiting = set(visiting or ())

        try:
            # IF(cond, a, b) — cond: A1>0 / A1=1 / TRUE / FALSE / A1
            m = re.fullmatch(
                r"IF\s*\(\s*(.+?)\s*,\s*(.+?)\s*,\s*(.+)\s*\)",
                expr,
                re.IGNORECASE | re.DOTALL,
            )
            if m:
                cond_raw, a_raw, b_raw = m.group(1), m.group(2), m.group(3)
                cond = self._eval_condition(cond_raw, depth=depth, visiting=visiting)
                branch = a_raw if cond else b_raw
                return self._eval_atom(branch.strip(), depth=depth, visiting=visiting)

            # SUM(A1:A3) or SUM(A1,B1)
            m = re.fullmatch(r"SUM\s*\(\s*(.+)\s*\)", expr_u, re.DOTALL)
            if m and expr_u.startswith("SUM"):
                # re-parse with original for refs
                m2 = re.fullmatch(r"SUM\s*\(\s*(.+)\s*\)", expr, re.IGNORECASE | re.DOTALL)
                assert m2
                return self._eval_sum_args(m2.group(1), depth=depth, visiting=visiting)

            # binary A1+B1
            m = re.fullmatch(
                r"([A-Z]+[0-9]+)\s*([+\-*/])\s*([A-Z]+[0-9]+)",
                expr_u,
            )
            if m:
                a = self._numeric(self.get_ref(m.group(1)), depth=depth, visiting=visiting)
                b = self._numeric(self.get_ref(m.group(3)), depth=depth, visiting=visiting)
                return self._apply_op(a, m.group(2), b)

            # number op number / mixed: 1+2, A1+2
            m = re.fullmatch(
                r"([A-Z]+[0-9]+|-?\d+(?:\.\d+)?)\s*([+\-*/])\s*([A-Z]+[0-9]+|-?\d+(?:\.\d+)?)",
                expr_u,
            )
            if m:
                a = self._numeric(self._atom_value(m.group(1)), depth=depth, visiting=visiting)
                b = self._numeric(self._atom_value(m.group(3)), depth=depth, visiting=visiting)
                return self._apply_op(a, m.group(2), b)

            # bare cell ref
            if _CELL_REF.fullmatch(expr_u):
                ref = expr_u
                if ref in visiting:
                    raise FormulaError(f"circular: {ref}", "#CYCLE!")
                visiting.add(ref)
                try:
                    return self._numeric(self.get_ref(ref), depth=depth, visiting=visiting)
                finally:
                    visiting.discard(ref)

            # bare number
            try:
                return float(expr_u)
            except ValueError:
                pass

            raise FormulaError(f"unsupported formula: {formula!r}", "#ERROR!")
        except FormulaError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise FormulaError(str(exc), "#ERROR!") from exc

    def _atom_value(self, token: str) -> Any:
        t = token.strip().upper()
        if _CELL_REF.fullmatch(t):
            return self.get_ref(t)
        return float(t)

    def _eval_atom(
        self,
        token: str,
        *,
        depth: int,
        visiting: set[str],
    ) -> float | str | bool:
        t = token.strip()
        tu = t.upper()
        if tu in ("TRUE", "FALSE"):
            return tu == "TRUE"
        if t.startswith("="):
            return self.evaluate(t, depth=depth + 1, visiting=visiting)
        if (t.startswith('"') and t.endswith('"')) or (
            t.startswith("'") and t.endswith("'")
        ):
            return t[1:-1]
        if _CELL_REF.fullmatch(tu):
            val = self.get_ref(tu)
            if isinstance(val, str) and val.strip().startswith("="):
                return self.evaluate(val, depth=depth + 1, visiting=visiting)
            return val if val != "" else 0
        try:
            return float(t)
        except ValueError:
            return t

    def _eval_condition(
        self,
        cond: str,
        *,
        depth: int,
        visiting: set[str],
    ) -> bool:
        c = cond.strip()
        cu = c.upper()
        if cu in ("TRUE", "FALSE"):
            return cu == "TRUE"
        for op in (">=", "<=", "<>", "!=", ">", "<", "="):
            if op in c:
                left, right = c.split(op, 1)
                lv = self._eval_atom(left.strip(), depth=depth, visiting=visiting)
                rv = self._eval_atom(right.strip(), depth=depth, visiting=visiting)
                try:
                    lf, rf = float(lv), float(rv)  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    lf, rf = str(lv), str(rv)
                if op == ">=":
                    return lf >= rf  # type: ignore[operator]
                if op == "<=":
                    return lf <= rf  # type: ignore[operator]
                if op in ("<>", "!="):
                    return lf != rf
                if op == ">":
                    return lf > rf  # type: ignore[operator]
                if op == "<":
                    return lf < rf  # type: ignore[operator]
                if op == "=":
                    return lf == rf
        # bare cell / number truthiness
        v = self._eval_atom(c, depth=depth, visiting=visiting)
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return v != 0
        return bool(v)

    def _eval_sum_args(
        self,
        args: str,
        *,
        depth: int,
        visiting: set[str],
    ) -> float:
        total = 0.0
        # split on commas not inside nested parens — simple: ranges or cells
        parts = [p.strip() for p in args.split(",") if p.strip()]
        for part in parts:
            if ":" in part:
                r1, c1, r2, c2 = parse_range(part)
                for r in range(r1, r2 + 1):
                    for c in range(c1, c2 + 1):
                        total += self._numeric(
                            self.get_cell(r, c), depth=depth, visiting=visiting
                        )
            else:
                total += self._numeric(
                    self._atom_value(part), depth=depth, visiting=visiting
                )
        return total

    @staticmethod
    def _apply_op(a: float, op: str, b: float) -> float | str:
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            if b == 0:
                return "#DIV/0!"
            return a / b
        raise FormulaError(f"bad op {op!r}")

    def value_at(self, row: int, col: int) -> Any:
        """Display value: evaluate formula if needed."""
        raw = self.get_cell(row, col)
        if isinstance(raw, str) and raw.strip().startswith("="):
            try:
                return self.evaluate(raw)
            except FormulaError as exc:
                return exc.code
        return raw

    def value_ref(self, ref: str) -> Any:
        r, c = cell_ref_to_rc(ref)
        return self.value_at(r, c)

    def recalculate(self) -> dict[str, Any]:
        """Evaluate all formula cells; return map of ref -> result."""
        out: dict[str, Any] = {}
        for ref, cell in sorted(self.cells.items()):
            if cell.is_formula():
                try:
                    out[ref] = self.evaluate(str(cell.raw))
                except FormulaError as exc:
                    out[ref] = exc.code
        return out

    # --- structure ---
    def insert_rows(self, at: int, count: int = 1) -> None:
        count = max(1, int(count))
        at = max(0, int(at))
        new_cells: dict[str, Cell] = {}
        for ref, cell in self.cells.items():
            r, c = cell_ref_to_rc(ref)
            if r >= at:
                r += count
            new_cells[rc_to_cell_ref(r, c)] = cell
        self.cells = new_cells
        self.nrows = max(self.nrows + count, at + count)

    def delete_rows(self, at: int, count: int = 1) -> None:
        count = max(1, int(count))
        at = max(0, int(at))
        new_cells: dict[str, Cell] = {}
        for ref, cell in self.cells.items():
            r, c = cell_ref_to_rc(ref)
            if at <= r < at + count:
                continue
            if r >= at + count:
                r -= count
            new_cells[rc_to_cell_ref(r, c)] = cell
        self.cells = new_cells
        self.nrows = max(1, self.nrows - count)

    def insert_cols(self, at: int, count: int = 1) -> None:
        count = max(1, int(count))
        at = max(0, int(at))
        new_cells: dict[str, Cell] = {}
        for ref, cell in self.cells.items():
            r, c = cell_ref_to_rc(ref)
            if c >= at:
                c += count
            new_cells[rc_to_cell_ref(r, c)] = cell
        self.cells = new_cells
        self.ncols = max(self.ncols + count, at + count)

    def delete_cols(self, at: int, count: int = 1) -> None:
        count = max(1, int(count))
        at = max(0, int(at))
        new_cells: dict[str, Cell] = {}
        for ref, cell in self.cells.items():
            r, c = cell_ref_to_rc(ref)
            if at <= c < at + count:
                continue
            if c >= at + count:
                c -= count
            new_cells[rc_to_cell_ref(r, c)] = cell
        self.cells = new_cells
        self.ncols = max(1, self.ncols - count)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": KIND_SHEET,
            "schema_version": SCHEMA_VERSION,
            "title": self.title,
            "sheet_id": self.sheet_id,
            "nrows": self.nrows,
            "ncols": self.ncols,
            "cells": {ref: cell.to_dict() for ref, cell in self.cells.items()},
            # dense mirror for simple consumers
            "rows": self.rows,
        }

    def dumps(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def save(self, path: str | Any) -> None:
        from pathlib import Path

        Path(path).write_text(self.dumps() + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: str | Any) -> "Spreadsheet":
        from pathlib import Path

        return cls.loads(Path(path).read_text(encoding="utf-8"))

    @classmethod
    def loads(cls, raw: str) -> "Spreadsheet":
        data = json.loads(raw)
        cells_raw = data.get("cells")
        sheet = cls(
            title=str(data.get("title") or "Sheet"),
            sheet_id=str(data.get("sheet_id") or uuid.uuid4().hex[:12]),
            nrows=max(1, int(data.get("nrows") or 1)),
            ncols=max(1, int(data.get("ncols") or 1)),
        )
        if isinstance(cells_raw, dict) and cells_raw:
            for ref, cdata in cells_raw.items():
                try:
                    r, c = cell_ref_to_rc(str(ref))
                except ValueError:
                    continue
                sheet.set_cell(r, c, Cell.from_dict(cdata).raw)
        else:
            # schema v1: rows only
            for r, row in enumerate(data.get("rows") or []):
                if not isinstance(row, list):
                    continue
                for c, v in enumerate(row):
                    if v != "" and v is not None:
                        sheet.set_cell(r, c, v)
                    else:
                        sheet._ensure_size(r, c)
        return sheet

    def restore_snapshot(self, raw: str) -> None:
        """Reload state in place (shared identity for undo)."""
        other = Spreadsheet.loads(raw)
        self.title = other.title
        self.cells = other.cells
        self.nrows = other.nrows
        self.ncols = other.ncols
        self.sheet_id = other.sheet_id


@dataclass
class Workbook:
    """Multi-sheet workbook (Excel-class core)."""

    title: str = "Workbook"
    sheets: list[Spreadsheet] = field(default_factory=list)
    active_index: int = 0
    workbook_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    schema_version: int = SCHEMA_VERSION

    def add_sheet(self, title: str = "Sheet1") -> Spreadsheet:
        # unique title
        base = title
        n = 1
        existing = {s.title for s in self.sheets}
        while title in existing:
            n += 1
            title = f"{base}{n}"
        s = Spreadsheet(title=title)
        self.sheets.append(s)
        self.active_index = len(self.sheets) - 1
        return s

    def list_sheets(self) -> list[str]:
        return [s.title for s in self.sheets]

    def select_sheet(self, name: str) -> Spreadsheet:
        for i, s in enumerate(self.sheets):
            if s.title == name:
                self.active_index = i
                return s
        raise KeyError(f"no sheet named {name!r}")

    def select_index(self, index: int) -> Spreadsheet:
        if not (0 <= index < len(self.sheets)):
            raise IndexError("sheet index out of range")
        self.active_index = index
        return self.sheets[index]

    @property
    def active(self) -> Spreadsheet:
        if not self.sheets:
            self.add_sheet("Sheet1")
        self.active_index = max(0, min(self.active_index, len(self.sheets) - 1))
        return self.sheets[self.active_index]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": KIND_WORKBOOK,
            "schema_version": self.schema_version,
            "product": "Tables",
            "maker": "Raskul",
            "title": self.title,
            "workbook_id": self.workbook_id,
            "active_index": self.active_index,
            "sheets": [s.to_dict() for s in self.sheets],
        }

    def dumps(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def save(self, path: str | Any) -> None:
        from pathlib import Path

        Path(path).write_text(self.dumps() + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: str | Any) -> "Workbook":
        from pathlib import Path

        return cls.loads(Path(path).read_text(encoding="utf-8"))

    @classmethod
    def loads(cls, raw: str) -> "Workbook":
        data = json.loads(raw)
        # single sheet legacy
        if data.get("kind") in ("sheet", KIND_SHEET) or (
            "rows" in data and "sheets" not in data
        ):
            wb = cls(title=str(data.get("title") or "Workbook"))
            wb.sheets = [Spreadsheet.loads(raw)]
            wb.active_index = 0
            return wb
        wb = cls(
            title=str(data.get("title") or "Workbook"),
            workbook_id=str(data.get("workbook_id") or uuid.uuid4().hex[:12]),
            active_index=int(data.get("active_index") or 0),
            schema_version=int(data.get("schema_version") or SCHEMA_VERSION),
        )
        for s in data.get("sheets") or []:
            wb.sheets.append(Spreadsheet.loads(json.dumps(s)))
        if not wb.sheets:
            wb.add_sheet("Sheet1")
        return wb

    def restore_snapshot(self, raw: str) -> None:
        other = Workbook.loads(raw)
        self.title = other.title
        self.sheets = other.sheets
        self.active_index = other.active_index
        self.workbook_id = other.workbook_id
        self.schema_version = other.schema_version


def create_spreadsheet(title: str = "Sheet1") -> Spreadsheet:
    return Spreadsheet(title=title)


def create_workbook(title: str = "Workbook", sheet: str = "Sheet1") -> Workbook:
    wb = Workbook(title=title)
    wb.add_sheet(sheet)
    return wb


class WorkbookEditor:
    """Edit API with undo/redo on a shared Workbook instance."""

    def __init__(self, workbook: Workbook, *, max_history: int = 64) -> None:
        self.workbook = workbook
        self.max_history = max(1, int(max_history))
        self._undo: list[str] = []
        self._redo: list[str] = []

    def _push(self) -> None:
        self._undo.append(self.workbook.dumps())
        if len(self._undo) > self.max_history:
            self._undo = self._undo[-self.max_history :]
        self._redo.clear()

    def undo(self) -> bool:
        if not self._undo:
            return False
        self._redo.append(self.workbook.dumps())
        self.workbook.restore_snapshot(self._undo.pop())
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        self._undo.append(self.workbook.dumps())
        self.workbook.restore_snapshot(self._redo.pop())
        return True

    @property
    def sheet(self) -> Spreadsheet:
        return self.workbook.active

    def set_cell(self, row: int, col: int, value: Any) -> None:
        self._push()
        self.sheet.set_cell(row, col, value)

    def set_ref(self, ref: str, value: Any) -> None:
        r, c = cell_ref_to_rc(ref)
        self.set_cell(r, c, value)

    def add_sheet(self, title: str = "Sheet") -> Spreadsheet:
        self._push()
        return self.workbook.add_sheet(title)

    def select_sheet(self, name: str) -> Spreadsheet:
        # selection alone is not undoable content — still fine without push
        return self.workbook.select_sheet(name)

    def insert_rows(self, at: int, count: int = 1) -> None:
        self._push()
        self.sheet.insert_rows(at, count)

    def delete_rows(self, at: int, count: int = 1) -> None:
        self._push()
        self.sheet.delete_rows(at, count)

    def insert_cols(self, at: int, count: int = 1) -> None:
        self._push()
        self.sheet.insert_cols(at, count)

    def delete_cols(self, at: int, count: int = 1) -> None:
        self._push()
        self.sheet.delete_cols(at, count)

    def evaluate(self, formula: str) -> Any:
        return self.sheet.evaluate(formula)

    def recalculate(self) -> dict[str, Any]:
        return self.sheet.recalculate()

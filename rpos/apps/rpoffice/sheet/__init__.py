"""Spreadsheet model with simple formula evaluation (Excel pillar)."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any


_CELL_REF = re.compile(r"\b([A-Z]+)([0-9]+)\b")


def col_letters_to_index(letters: str) -> int:
    n = 0
    for ch in letters.upper():
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n - 1


def cell_ref_to_rc(ref: str) -> tuple[int, int]:
    m = _CELL_REF.fullmatch(ref.strip().upper())
    if not m:
        raise ValueError(f"bad cell ref: {ref!r}")
    col = col_letters_to_index(m.group(1))
    row = int(m.group(2)) - 1
    return row, col


@dataclass
class Spreadsheet:
    title: str
    rows: list[list[Any]] = field(default_factory=list)
    sheet_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def set_cell(self, row: int, col: int, value: Any) -> None:
        while len(self.rows) <= row:
            self.rows.append([])
        while len(self.rows[row]) <= col:
            self.rows[row].append("")
        self.rows[row][col] = value

    def get_cell(self, row: int, col: int) -> Any:
        if row < 0 or col < 0:
            return None
        if row >= len(self.rows) or col >= len(self.rows[row]):
            return None
        return self.rows[row][col]

    def get_ref(self, ref: str) -> Any:
        r, c = cell_ref_to_rc(ref)
        return self.get_cell(r, c)

    def _numeric(self, value: Any) -> float:
        if value is None or value == "":
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip()
        if s.startswith("="):
            return float(self.evaluate(s))
        return float(s)

    def evaluate(self, formula: str) -> float | str:
        """Evaluate a simple formula: =A1+B1, =A1-B2, =SUM(A1:A3)."""
        f = (formula or "").strip()
        if not f.startswith("="):
            raise ValueError("formula must start with =")
        expr = f[1:].strip().upper()

        # SUM(A1:A3)
        m = re.fullmatch(r"SUM\(([A-Z]+[0-9]+):([A-Z]+[0-9]+)\)", expr)
        if m:
            r1, c1 = cell_ref_to_rc(m.group(1))
            r2, c2 = cell_ref_to_rc(m.group(2))
            total = 0.0
            for r in range(min(r1, r2), max(r1, r2) + 1):
                for c in range(min(c1, c2), max(c1, c2) + 1):
                    total += self._numeric(self.get_cell(r, c))
            return total

        # A1+B1 or A1-B1 or A1*B1
        m = re.fullmatch(r"([A-Z]+[0-9]+)\s*([+\-*/])\s*([A-Z]+[0-9]+)", expr)
        if m:
            a = self._numeric(self.get_ref(m.group(1)))
            b = self._numeric(self.get_ref(m.group(3)))
            op = m.group(2)
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

        # bare cell ref
        if _CELL_REF.fullmatch(expr):
            return self._numeric(self.get_ref(expr))

        raise ValueError(f"unsupported formula: {formula!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "sheet",
            "title": self.title,
            "rows": self.rows,
            "sheet_id": self.sheet_id,
        }

    def dumps(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def loads(cls, raw: str) -> "Spreadsheet":
        data = json.loads(raw)
        return cls(
            title=str(data.get("title") or "Sheet"),
            rows=list(data.get("rows") or []),
            sheet_id=str(data.get("sheet_id") or uuid.uuid4().hex[:12]),
        )


@dataclass
class Workbook:
    """Partial multi-sheet Excel surface."""

    title: str = "Workbook"
    sheets: list[Spreadsheet] = field(default_factory=list)
    workbook_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def add_sheet(self, title: str = "Sheet1") -> Spreadsheet:
        s = Spreadsheet(title=title, rows=[[]])
        self.sheets.append(s)
        return s

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "workbook",
            "title": self.title,
            "workbook_id": self.workbook_id,
            "sheets": [s.to_dict() for s in self.sheets],
        }

    def dumps(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def loads(cls, raw: str) -> "Workbook":
        data = json.loads(raw)
        wb = cls(
            title=str(data.get("title") or "Workbook"),
            workbook_id=str(data.get("workbook_id") or uuid.uuid4().hex[:12]),
        )
        for s in data.get("sheets") or []:
            wb.sheets.append(Spreadsheet.loads(json.dumps(s)))
        return wb


def create_spreadsheet(title: str = "Sheet1") -> Spreadsheet:
    return Spreadsheet(title=title, rows=[[]])

"""Tables — Restore Privacy spreadsheet program (standalone)."""

from __future__ import annotations

import argparse
import json

from .. import __version__
from ..brand import PRODUCT_FAMILY, TABLES
from ..sheet import create_spreadsheet


def smoke() -> dict:
    s = create_spreadsheet(f"{TABLES} budget")
    s.set_cell(0, 0, 10)
    s.set_cell(0, 1, 5)
    total = s.evaluate("=A1+B1")
    return {
        "ok": True,
        "product": TABLES,
        "family": PRODUCT_FAMILY,
        "version": __version__,
        "kind": "spreadsheet",
        "title": s.title,
        "formula_A1_plus_B1": total,
        "rows": len(s.rows),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tables", description=f"{TABLES} — Restore Privacy spreadsheets")
    ap.add_argument("--version", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args(argv)
    if args.version:
        print(f"{TABLES} {__version__}")
        return 0
    print(json.dumps(smoke(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

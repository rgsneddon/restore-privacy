"""CLI entry for rpOffice — Pens · Tables · Slides."""

from __future__ import annotations

import argparse
import json

from . import PRODUCT_NAME, __version__
from .apps import pens, slides, tables
from .brand import PENS, SLIDES, TABLES
from .parity_scope import matrix_as_dict, required_pillars_present
from .shell import create, suite_status


def smoke() -> dict:
    status = suite_status()
    status["variant"] = "Pens · Tables · Slides"
    status["parity_required_ok"] = required_pillars_present()
    status["apps"] = {
        PENS: pens.smoke(),
        TABLES: tables.smoke(),
        SLIDES: slides.smoke(),
    }
    # Ensure primary brands present
    status["brands_ok"] = status["brands"] == [PENS, TABLES, SLIDES]
    status["parity"] = matrix_as_dict()
    status["smoke"] = True
    return status


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="rpoffice", description="rpOffice — Pens · Tables · Slides")
    ap.add_argument("--version", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--parity", action="store_true")
    args = ap.parse_args(argv)
    if args.version:
        print(f"{PRODUCT_NAME} {__version__} ({PENS} · {TABLES} · {SLIDES})")
        return 0
    if args.parity:
        print(json.dumps(matrix_as_dict(), indent=2))
        return 0
    if args.smoke:
        print(json.dumps(smoke(), indent=2, default=str))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

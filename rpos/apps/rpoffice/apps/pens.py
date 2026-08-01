"""Pens — Restore Privacy document program (standalone)."""

from __future__ import annotations

import argparse
import json

from .. import __version__
from ..brand import PENS, PRODUCT_FAMILY
from ..word import create_document


def smoke() -> dict:
    doc = create_document(f"Welcome to {PENS}", f"{PENS} is ready.")
    doc.add_paragraph(f"{PENS} — privacy-first writing.", style="Heading1")
    again = type(doc).loads(doc.dumps())
    return {
        "ok": True,
        "product": PENS,
        "family": PRODUCT_FAMILY,
        "version": __version__,
        "kind": "document",
        "title": again.title,
        "paragraphs": len(again.paragraphs),
        "body_len": len(again.body),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pens", description=f"{PENS} — Restore Privacy documents")
    ap.add_argument("--version", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args(argv)
    if args.version:
        print(f"{PENS} {__version__}")
        return 0
    print(json.dumps(smoke(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

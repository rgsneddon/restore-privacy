"""Pens — Raskul structure-first document program (standalone).

Corel-historical design ethos: structure control (Reveal Codes spirit).
Not Microsoft Word; not Corel WordPerfect trademark. Core: create/edit/format,
headings, lists, tables, structure/reveal, find/replace, undo/redo, JSON round-trip.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .. import __version__
from ..brand import DESIGN_LINEAGE, MAKER, PENS, PRODUCT_FAMILY
from ..word import (
    Document,
    DocumentEditor,
    create_document,
)


def smoke() -> dict[str, Any]:
    """Ship-path smoke: structure-first core + reveal + round-trip + edit ops."""
    doc = create_document(f"Welcome to {PENS}", f"{PENS} is ready.")
    ed = DocumentEditor(doc)
    ed.add_heading(f"{PENS} — privacy-first writing", level=1)
    ed.add_paragraph(
        "Bold and italic body.",
        bold=True,
        italic=True,
        font_size=12,
        align="left",
    )
    ed.add_bullet("First idea")
    ed.add_bullet("Second idea")
    ed.add_numbered("Step one")
    ed.add_numbered("Step two")
    t = ed.add_table(2, 2, fill="")
    t.set_cell_text(0, 0, "A1")
    t.set_cell_text(0, 1, "B1")
    t.set_cell_text(1, 0, "A2")
    t.set_cell_text(1, 1, "B2")
    ed.document.add_image_placeholder("figure-1", alt="placeholder")
    reveal_before = ed.reveal_structure()
    tokens_before = ed.structure_tokens()
    n = ed.replace_all("idea", "point")
    assert n == 2
    tokens_after = ed.structure_tokens()
    reveal_after = ed.reveal_structure()
    raw = ed.document.dumps()
    again = Document.loads(raw)
    # undo last replace
    assert ed.undo()
    assert "idea" in ed.document.plain_text()
    assert ed.redo()
    assert "point" in ed.document.plain_text()

    tables = [b for b in again.blocks if b.kind == "table"]
    lists = [
        p
        for p in again.paragraphs
        if p.list_type in ("bullet", "number")
    ]
    headings = [p for p in again.paragraphs if p.style.startswith("Heading")]
    has_heading_code = any(
        any(str(c).startswith("Style:Heading") for c in (t.get("codes") or []))
        for t in tokens_before
        if t.get("kind") == "paragraph"
    )
    has_list_code = any(
        any(str(c).startswith("List:") for c in (t.get("codes") or []))
        for t in tokens_before
        if t.get("kind") == "paragraph"
    )
    has_table_code = any(t.get("kind") == "table" for t in tokens_before)
    return {
        "ok": True,
        "product": PENS,
        "family": PRODUCT_FAMILY,
        "version": __version__,
        "kind": "document",
        "maker": MAKER,
        "design_lineage": DESIGN_LINEAGE,
        "title": again.title,
        "paragraphs": len(again.paragraphs),
        "blocks": len(again.blocks),
        "body_len": len(again.body),
        "headings": len(headings),
        "list_items": len(lists),
        "tables": len(tables),
        "schema_version": again.schema_version,
        "round_trip": again.title == ed.document.title,
        "reveal_ok": has_heading_code and has_list_code and has_table_code,
        "reveal_changed": reveal_before != reveal_after or tokens_before != tokens_after,
        "reveal_preview": reveal_after[:240],
        "honesty": (
            "Structure-first Pens core (create/edit/format, reveal codes ethos, "
            "find/replace, undo); Corel-historical independent design; "
            "not full Microsoft Word parity; not Corel WordPerfect trademark"
        ),
    }


def cmd_new(title: str, body: str, out: Path | None) -> dict[str, Any]:
    doc = create_document(title=title, body=body)
    if out:
        doc.save(out)
    return {
        "ok": True,
        "product": PENS,
        "doc_id": doc.doc_id,
        "title": doc.title,
        "path": str(out) if out else "",
        "bytes": len(doc.dumps()),
    }


def cmd_demo(out: Path | None) -> dict[str, Any]:
    """Build a sample structure-first document and optionally save."""
    r = smoke()
    # Rebuild for save with rich content
    doc = create_document("Pens demo", "Opening line.")
    ed = DocumentEditor(doc)
    ed.add_heading("Chapter One", level=1)
    ed.add_paragraph("Normal body with emphasis.", italic=True)
    ed.add_bullet("Bullet A")
    ed.add_numbered("Number 1")
    t = ed.add_table(2, 2)
    t.set_cell_text(0, 0, "Name")
    t.set_cell_text(0, 1, "Value")
    path = str(out) if out else ""
    if out:
        ed.document.save(out)
    return {
        "ok": True,
        "product": PENS,
        "path": path,
        "smoke": r,
        "plain_preview": ed.document.plain_text()[:200],
        "reveal_preview": ed.reveal_structure()[:200],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="pens",
        description=(
            f"{PENS} — Raskul structure-first documents "
            f"({DESIGN_LINEAGE}; not Microsoft Word)"
        ),
    )
    ap.add_argument("--version", action="store_true")
    ap.add_argument("--smoke", action="store_true", help="Run structure-first core smoke")
    ap.add_argument("--new", action="store_true", help="Create a new document")
    ap.add_argument("--demo", action="store_true", help="Create a sample document")
    ap.add_argument("--title", default="Untitled")
    ap.add_argument("--body", default="")
    ap.add_argument("-o", "--output", default="", help="Write .pens.json path")
    args = ap.parse_args(argv)
    if args.version:
        print(f"{PENS} {__version__} ({MAKER})")
        return 0
    out = Path(args.output) if args.output else None
    if args.new:
        print(json.dumps(cmd_new(args.title, args.body, out), indent=2))
        return 0
    if args.demo:
        print(json.dumps(cmd_demo(out), indent=2))
        return 0
    # default: smoke
    print(json.dumps(smoke(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

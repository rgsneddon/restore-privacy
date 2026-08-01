"""Slides — Raskul independent presentation program (standalone).

Corel-historical independent suite design (not Microsoft PowerPoint; not Corel
Presentations trademark). Core: multi-slide deck, title/body/bullets/notes,
add/delete/duplicate/reorder, undo/redo, durable JSON round-trip.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .. import __version__
from ..brand import DESIGN_LINEAGE, MAKER, PRODUCT_FAMILY, SLIDES
from ..deck import Presentation, PresentationEditor, create_presentation


def smoke() -> dict[str, Any]:
    """Ship-path smoke: independent presentation core + round-trip + edit ops."""
    p = create_presentation(f"{SLIDES} intro")
    ed = PresentationEditor(p)
    # create_presentation seeds one title slide; enrich it
    ed.set_title(0, "Privacy")
    ed.set_body(0, "Restore Privacy Suite")
    ed.set_notes(0, "Open with residual honesty.")
    ed.set_bullets(0, ["No MS branding", "Raskul-made", "Local-first"])
    ed.add_slide("Ned", "Your helper", notes="Second slide notes", bullets=["Helpful", "Local"])
    ed.add_slide("Roadmap", "Next steps")
    # structure ops
    ed.duplicate_slide(1)
    ed.reorder_slide(3, 1)  # move last toward front
    titles_before_undo_delete = list(p.slide_titles())
    ed.delete_slide(len(p.slides) - 1)
    self_assert_count = len(p.slides)
    ed.undo()  # restore deleted
    # shared identity
    assert ed.presentation is p
    assert len(p.slides) == self_assert_count + 1
    # round-trip
    raw = p.dumps()
    again = Presentation.loads(raw)
    return {
        "ok": True,
        "product": SLIDES,
        "family": PRODUCT_FAMILY,
        "version": __version__,
        "kind": "presentation",
        "maker": MAKER,
        "design_lineage": DESIGN_LINEAGE,
        "title": again.title,
        "slide_count": len(again.slides),
        "titles": [s.title for s in again.slides],
        "first_bullets": list(again.slides[0].bullets) if again.slides else [],
        "first_notes": again.slides[0].notes if again.slides else "",
        "schema_version": again.schema_version,
        "round_trip": (
            again.slides[0].title == p.slides[0].title
            and again.slides[0].bullets == p.slides[0].bullets
            and again.slides[0].notes == p.slides[0].notes
            and len(again.slides) == len(p.slides)
        ),
        "structure_ops_titles": titles_before_undo_delete,
        "honesty": (
            "Slides independent presentation core (multi-slide, bullets, notes, "
            "structure, undo); Corel-historical suite design; "
            "not full Microsoft PowerPoint parity; not Corel Presentations trademark"
        ),
    }


def cmd_demo(out: Path | None) -> dict[str, Any]:
    r = smoke()
    p = create_presentation("Slides demo")
    ed = PresentationEditor(p)
    ed.set_title(0, "Welcome")
    ed.set_body(0, "Restore Privacy Suite")
    ed.set_bullets(0, ["Pens", "Tables", "Slides"])
    ed.set_notes(0, "Presenter: introduce the three pillars.")
    ed.add_slide(
        "Agenda",
        "What we ship",
        bullets=["Structure-first Pens", "Independent Tables", "Independent Slides"],
    )
    path = str(out) if out else ""
    if out:
        p.save(out)
    return {
        "ok": True,
        "product": SLIDES,
        "path": path,
        "smoke": r,
        "demo_titles": p.slide_titles(),
        "demo_count": len(p.slides),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="slides",
        description=(
            f"{SLIDES} — Raskul independent presentations "
            f"({DESIGN_LINEAGE}; not Microsoft PowerPoint)"
        ),
    )
    ap.add_argument("--version", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("-o", "--output", default="")
    args = ap.parse_args(argv)
    if args.version:
        print(f"{SLIDES} {__version__} ({MAKER})")
        return 0
    out = Path(args.output) if args.output else None
    if args.demo:
        print(json.dumps(cmd_demo(out), indent=2))
        return 0
    print(json.dumps(smoke(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Office full-parity scope — Restore Privacy brands: Pens · Tables · Slides."""

from __future__ import annotations

from typing import Any

from .brand import OFFICE_PILLARS_BRANDED, PENS, SLIDES, TABLES

# Primary pillars are Restore Privacy brand names
OFFICE_PILLARS: tuple[str, ...] = OFFICE_PILLARS_BRANDED

# Honest matrix: Pens Word-class *core* is implemented; full MS Word is not.
OFFICE_PARITY_MATRIX: list[dict[str, str]] = [
    {
        "pillar": PENS,
        "feature": "Document body + character/paragraph format + serialize round-trip",
        "status": "implemented",
        "analogue": "Word-class core",
    },
    {
        "pillar": PENS,
        "feature": "Headings (H1–H3) + body styles",
        "status": "implemented",
        "analogue": "Word-class core",
    },
    {
        "pillar": PENS,
        "feature": "Bulleted and numbered lists",
        "status": "implemented",
        "analogue": "Word-class core",
    },
    {
        "pillar": PENS,
        "feature": "Tables (cells, edit text, round-trip)",
        "status": "implemented",
        "analogue": "Word-class core",
    },
    {
        "pillar": PENS,
        "feature": "Find/replace + undo/redo",
        "status": "implemented",
        "analogue": "Word-class core",
    },
    {
        "pillar": PENS,
        "feature": "Image placeholder / attachment hook",
        "status": "implemented",
        "analogue": "Word-class core",
    },
    {
        "pillar": PENS,
        "feature": "Full OOXML/DOCX fidelity, VBA, Track Changes collaboration",
        "status": "out_of_scope",
        "analogue": "Microsoft Word (not claimed)",
    },
    {
        "pillar": TABLES,
        "feature": "Grid cells + simple formula evaluation",
        "status": "implemented",
        "analogue": "Excel-class",
    },
    {
        "pillar": SLIDES,
        "feature": "Multi-slide create/reorder/serialize",
        "status": "implemented",
        "analogue": "PowerPoint-class",
    },
    {
        "pillar": TABLES,
        "feature": "Named worksheets in workbook",
        "status": "partial",
        "analogue": "Excel-class",
    },
    {
        "pillar": TABLES,
        "feature": "Charts / pivot tables",
        "status": "planned",
        "analogue": "Excel-class",
    },
    {
        "pillar": SLIDES,
        "feature": "Animations / masters",
        "status": "planned",
        "analogue": "PowerPoint-class",
    },
]


def required_pillars_present() -> bool:
    found = {row["pillar"] for row in OFFICE_PARITY_MATRIX}
    return all(p in found for p in OFFICE_PILLARS)


def implemented_pillars() -> list[str]:
    return sorted(
        {
            row["pillar"]
            for row in OFFICE_PARITY_MATRIX
            if row["status"] == "implemented" and row["pillar"] in OFFICE_PILLARS
        }
    )


def pens_word_class_core_rows() -> list[dict[str, str]]:
    """Pens rows that constitute gating Word-class core (for honesty reports)."""
    return [
        r
        for r in OFFICE_PARITY_MATRIX
        if r["pillar"] == PENS and r["status"] == "implemented"
    ]


def matrix_as_dict() -> dict[str, Any]:
    return {
        "product": "rpOffice",
        "variant": "from-scratch Restore Privacy suite (Raskul)",
        "brands": list(OFFICE_PILLARS),
        "required_pillars": list(OFFICE_PILLARS),
        "matrix": list(OFFICE_PARITY_MATRIX),
        "implemented_pillars": implemented_pillars(),
        "pens_word_class_core": pens_word_class_core_rows(),
        "note": (
            "Primary names are Pens, Tables, Slides — not Microsoft brand labels. "
            "Pens Word-class core is implemented; full Microsoft Word parity is not claimed."
        ),
    }

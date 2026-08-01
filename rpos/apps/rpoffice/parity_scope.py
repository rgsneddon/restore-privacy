"""Office full-parity scope — Restore Privacy brands: Pens · Tables · Slides."""

from __future__ import annotations

from typing import Any

from .brand import OFFICE_PILLARS_BRANDED, PENS, SLIDES, TABLES

# Primary pillars are Restore Privacy brand names
OFFICE_PILLARS: tuple[str, ...] = OFFICE_PILLARS_BRANDED

OFFICE_PARITY_MATRIX: list[dict[str, str]] = [
    {"pillar": PENS, "feature": "Document body + styles + serialize round-trip", "status": "implemented", "analogue": "Word-class"},
    {"pillar": TABLES, "feature": "Grid cells + simple formula evaluation", "status": "implemented", "analogue": "Excel-class"},
    {"pillar": SLIDES, "feature": "Multi-slide create/reorder/serialize", "status": "implemented", "analogue": "PowerPoint-class"},
    {"pillar": PENS, "feature": "Paragraph list / headings", "status": "partial", "analogue": "Word-class"},
    {"pillar": TABLES, "feature": "Named worksheets in workbook", "status": "partial", "analogue": "Excel-class"},
    {"pillar": PENS, "feature": "Tables / images", "status": "planned", "analogue": "Word-class"},
    {"pillar": TABLES, "feature": "Charts / pivot tables", "status": "planned", "analogue": "Excel-class"},
    {"pillar": SLIDES, "feature": "Animations / masters", "status": "planned", "analogue": "PowerPoint-class"},
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


def matrix_as_dict() -> dict[str, Any]:
    return {
        "product": "rpOffice",
        "variant": "from-scratch Restore Privacy suite",
        "brands": list(OFFICE_PILLARS),
        "required_pillars": list(OFFICE_PILLARS),
        "matrix": list(OFFICE_PARITY_MATRIX),
        "implemented_pillars": implemented_pillars(),
        "note": "Primary names are Pens, Tables, Slides — not Microsoft brand labels",
    }

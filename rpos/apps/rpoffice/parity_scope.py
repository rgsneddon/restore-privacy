"""Office full-parity scope — Restore Privacy brands: Pens · Tables · Slides.

Design lineage: Corel-historical independent suite (Raskul) — not Microsoft
Office workalike, not Corel/WordPerfect trademark use.
"""

from __future__ import annotations

from typing import Any

from .brand import (
    DESIGN_ETHOS,
    DESIGN_LINEAGE,
    DESIGN_NOTE,
    MAKER,
    OFFICE_PILLARS_BRANDED,
    PENS,
    SLIDES,
    TABLES,
)

# Primary pillars are Restore Privacy brand names
OFFICE_PILLARS: tuple[str, ...] = OFFICE_PILLARS_BRANDED

# Honest matrix: structure-first independent suite cores; full WP/MS clones out of scope.
OFFICE_PARITY_MATRIX: list[dict[str, str]] = [
    {
        "pillar": PENS,
        "feature": "Document body + character/paragraph format + serialize round-trip",
        "status": "implemented",
        "analogue": "Pens structure-first core",
    },
    {
        "pillar": PENS,
        "feature": "Headings (H1–H3) + body styles",
        "status": "implemented",
        "analogue": "Pens structure-first core",
    },
    {
        "pillar": PENS,
        "feature": "Bulleted and numbered lists",
        "status": "implemented",
        "analogue": "Pens structure-first core",
    },
    {
        "pillar": PENS,
        "feature": "Tables (cells, edit text, round-trip)",
        "status": "implemented",
        "analogue": "Pens structure-first core",
    },
    {
        "pillar": PENS,
        "feature": "Find/replace + undo/redo",
        "status": "implemented",
        "analogue": "Pens structure-first core",
    },
    {
        "pillar": PENS,
        "feature": "Structure/reveal view (ordered structural codes)",
        "status": "implemented",
        "analogue": "Pens structure-first core (Reveal Codes ethos)",
    },
    {
        "pillar": PENS,
        "feature": "Image placeholder / attachment hook",
        "status": "implemented",
        "analogue": "Pens structure-first core",
    },
    {
        "pillar": PENS,
        "feature": "Full WordPerfect Reveal Codes UI, PerfectScript, legal line-numbering",
        "status": "out_of_scope",
        "analogue": "Corel WordPerfect (not claimed)",
    },
    {
        "pillar": PENS,
        "feature": "Full OOXML/DOCX fidelity, VBA, Track Changes collaboration",
        "status": "out_of_scope",
        "analogue": "Microsoft Word (not claimed)",
    },
    {
        "pillar": TABLES,
        "feature": "2D grid + numbers/text/blank + serialize round-trip",
        "status": "implemented",
        "analogue": "Tables independent spreadsheet core",
    },
    {
        "pillar": TABLES,
        "feature": "Formulas with cell refs, arithmetic, SUM, IF + recalculation",
        "status": "implemented",
        "analogue": "Tables independent spreadsheet core",
    },
    {
        "pillar": TABLES,
        "feature": "Named worksheets in workbook (add/select/list; sheet isolation)",
        "status": "implemented",
        "analogue": "Tables independent spreadsheet core",
    },
    {
        "pillar": TABLES,
        "feature": "Insert/delete rows and columns + undo/redo",
        "status": "implemented",
        "analogue": "Tables independent spreadsheet core",
    },
    {
        "pillar": TABLES,
        "feature": "Charts, pivot tables, XLSX/VBA, Power Query, collaboration",
        "status": "out_of_scope",
        "analogue": "Microsoft Excel (not claimed)",
    },
    {
        "pillar": TABLES,
        "feature": "Full Quattro Pro feature set / Corel trademark",
        "status": "out_of_scope",
        "analogue": "Corel Quattro Pro (not claimed)",
    },
    {
        "pillar": SLIDES,
        "feature": "Multi-slide deck + title/body/bullets/notes + serialize round-trip",
        "status": "implemented",
        "analogue": "Slides independent presentation core",
    },
    {
        "pillar": SLIDES,
        "feature": "Add/delete/duplicate/reorder slides",
        "status": "implemented",
        "analogue": "Slides independent presentation core",
    },
    {
        "pillar": SLIDES,
        "feature": "Undo/redo of edit actions on shared presentation",
        "status": "implemented",
        "analogue": "Slides independent presentation core",
    },
    {
        "pillar": SLIDES,
        "feature": "Animations, transitions, slide masters, full PPTX/VBA, collaboration",
        "status": "out_of_scope",
        "analogue": "Microsoft PowerPoint (not claimed)",
    },
    {
        "pillar": SLIDES,
        "feature": "Full Corel Presentations feature set / Corel trademark",
        "status": "out_of_scope",
        "analogue": "Corel Presentations (not claimed)",
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
    """Pens rows that constitute gating document core (legacy helper name)."""
    return [
        r
        for r in OFFICE_PARITY_MATRIX
        if r["pillar"] == PENS and r["status"] == "implemented"
    ]


def pens_structure_first_core_rows() -> list[dict[str, str]]:
    """Pens structure-first core rows (Corel-historical design framing)."""
    return pens_word_class_core_rows()


def tables_excel_class_core_rows() -> list[dict[str, str]]:
    """Tables rows that constitute gating spreadsheet core."""
    return [
        r
        for r in OFFICE_PARITY_MATRIX
        if r["pillar"] == TABLES and r["status"] == "implemented"
    ]


def slides_powerpoint_class_core_rows() -> list[dict[str, str]]:
    """Slides rows that constitute gating presentation core."""
    return [
        r
        for r in OFFICE_PARITY_MATRIX
        if r["pillar"] == SLIDES and r["status"] == "implemented"
    ]


def matrix_as_dict() -> dict[str, Any]:
    return {
        "product": "rpOffice",
        "variant": "Corel-historical independent suite (Raskul / Restore Privacy)",
        "maker": MAKER,
        "design_lineage": DESIGN_LINEAGE,
        "design_ethos": DESIGN_ETHOS,
        "brands": list(OFFICE_PILLARS),
        "required_pillars": list(OFFICE_PILLARS),
        "matrix": list(OFFICE_PARITY_MATRIX),
        "implemented_pillars": implemented_pillars(),
        "pens_word_class_core": pens_word_class_core_rows(),
        "pens_structure_first_core": pens_structure_first_core_rows(),
        "tables_excel_class_core": tables_excel_class_core_rows(),
        "slides_powerpoint_class_core": slides_powerpoint_class_core_rows(),
        "microsoft_workalike": False,
        "corel_trademark_claimed": False,
        "note": (
            "Primary names are Pens, Tables, Slides — independent suite brands, "
            "not Microsoft or Corel product labels. Design lineage is "
            f"{DESIGN_LINEAGE}: {DESIGN_ETHOS}. {DESIGN_NOTE} "
            "Document/spreadsheet/presentation cores are implemented; full "
            "WordPerfect/Quattro/Presentations and full Microsoft Office parity "
            "are not claimed."
        ),
    }

"""Restore Privacy branded standalone office programs.

Design lineage: Corel-historical *independent* office suite (Raskul) — not a
Microsoft Office workalike. Primary brands are Pens · Tables · Slides.
"""

from __future__ import annotations

SUITE_NAME = "rpOffice"
PRODUCT_FAMILY = "Restore Privacy Suite"
MAKER = "Raskul"

# Historical Corel office design: independent suite identity, structure-first
# control (Reveal Codes ethos), seamless multi-app integration — inspired by,
# not trademarked as, Corel WordPerfect Office / Quattro Pro / Presentations.
DESIGN_LINEAGE = "Corel-historical independent office suite"
DESIGN_ETHOS = (
    "structure-first control; seamless multi-app suite; "
    "not a Microsoft Office workalike"
)
DESIGN_NOTE = (
    "Inspired by historical Corel suite independence and structure control "
    "(Reveal Codes ethos). Not Corel, WordPerfect, Quattro Pro, or Presentations "
    "trademarks. Not a Microsoft Office clone."
)

# Primary user-facing brand names (not Word / Excel / PowerPoint)
PENS = "Pens"
TABLES = "Tables"
SLIDES = "Slides"

APP_ORDER: tuple[str, ...] = (PENS, TABLES, SLIDES)

# Map brand → domain pillar module key
BRAND_TO_MODULE: dict[str, str] = {
    PENS: "word",
    TABLES: "sheet",
    SLIDES: "deck",
}

MODULE_TO_BRAND: dict[str, str] = {v: k for k, v in BRAND_TO_MODULE.items()}

# Office-class pillar labels for parity docs (brand first)
OFFICE_PILLARS_BRANDED: tuple[str, ...] = (PENS, TABLES, SLIDES)

# Primary capability labels (independent suite — brand first)
CAPABILITY: dict[str, str] = {
    PENS: "structure-first documents",
    TABLES: "grid spreadsheets with formulas",
    SLIDES: "multi-slide presentations",
}

# Secondary capability-class analogues only (never primary product positioning)
ANALOGUE: dict[str, str] = {
    PENS: "secondary: Word-class document capability (not Word)",
    TABLES: "secondary: Excel-class spreadsheet capability (not Excel)",
    SLIDES: "secondary: PowerPoint-class presentation capability (not PowerPoint)",
}


def primary_app_names() -> list[str]:
    return list(APP_ORDER)


def assert_primary_brands(text: str) -> bool:
    """True when text presents Pens/Tables/Slides as names (for tests)."""
    t = text or ""
    return all(n in t for n in APP_ORDER)


def suite_identity() -> dict[str, str | bool | list[str]]:
    """Shared suite identity fields for shell, smoke, and honesty reports."""
    return {
        "product": SUITE_NAME,
        "family": PRODUCT_FAMILY,
        "maker": MAKER,
        "brands": list(APP_ORDER),
        "design_lineage": DESIGN_LINEAGE,
        "design_ethos": DESIGN_ETHOS,
        "design_note": DESIGN_NOTE,
        "microsoft_workalike": False,
        "corel_trademark_claimed": False,
    }

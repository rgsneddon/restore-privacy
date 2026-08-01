"""Restore Privacy branded standalone office programs."""

from __future__ import annotations

SUITE_NAME = "rpOffice"
PRODUCT_FAMILY = "Restore Privacy Suite"

# Primary user-facing brand names (not Microsoft Word/Excel/PowerPoint)
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

# Legacy Microsoft-class analogues (secondary only — never primary brand)
ANALOGUE: dict[str, str] = {
    PENS: "Word-class documents",
    TABLES: "Excel-class spreadsheets",
    SLIDES: "PowerPoint-class presentations",
}


def primary_app_names() -> list[str]:
    return list(APP_ORDER)


def assert_primary_brands(text: str) -> bool:
    """True when text presents Pens/Tables/Slides as names (for tests)."""
    t = text or ""
    return all(n in t for n in APP_ORDER)

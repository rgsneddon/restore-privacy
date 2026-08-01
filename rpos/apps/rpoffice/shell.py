"""Unified suite shell — Pens · Tables · Slides (Corel-historical seamless design)."""

from __future__ import annotations

from typing import Any, Literal

from . import BRAND_NAMES, MODULE_NAMES, PRODUCT_FAMILY, PRODUCT_NAME, __version__
from .brand import (
    DESIGN_ETHOS,
    DESIGN_LINEAGE,
    DESIGN_NOTE,
    MAKER,
    PENS,
    SLIDES,
    TABLES,
    suite_identity,
)
from .deck import Presentation, create_presentation
from .sheet import Spreadsheet, Workbook, create_spreadsheet, create_workbook
from .word import Document, create_document

DocKind = Literal["word", "sheet", "deck", "pens", "tables", "slides"]


def _normalize_kind(kind: str) -> str:
    k = (kind or "").strip().lower()
    alias = {
        "pens": "word",
        "tables": "sheet",
        "slides": "deck",
        "word": "word",
        "sheet": "sheet",
        "deck": "deck",
    }
    if k not in alias:
        raise ValueError(f"unknown kind: {kind!r} (use pens/tables/slides)")
    return alias[k]


def create(kind: DocKind | str, title: str = "") -> Document | Spreadsheet | Workbook | Presentation:
    k = _normalize_kind(str(kind))
    if k == "word":
        return create_document(title or f"{PENS} document")
    if k == "sheet":
        return create_spreadsheet(title or f"{TABLES} sheet")
    if k == "deck":
        return create_presentation(title or f"{SLIDES} deck")
    raise ValueError(f"unknown kind: {kind!r}")


def suite_status() -> dict[str, Any]:
    """One coherent suite surface for all three pillars."""
    ident = suite_identity()
    return {
        "product": PRODUCT_NAME,
        "family": PRODUCT_FAMILY,
        "version": __version__,
        "maker": MAKER,
        "brands": list(BRAND_NAMES),
        "modules": list(MODULE_NAMES),
        "pillars": list(BRAND_NAMES),
        "primary_names": {"Pens": PENS, "Tables": TABLES, "Slides": SLIDES},
        "design_lineage": DESIGN_LINEAGE,
        "design_ethos": DESIGN_ETHOS,
        "design_note": DESIGN_NOTE,
        "microsoft_workalike": False,
        "corel_trademark_claimed": False,
        "suite_order": list(BRAND_NAMES),
        "seamless": True,
        "identity": ident,
        "ok": True,
    }

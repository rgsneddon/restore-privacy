"""Unified suite shell — Pens · Tables · Slides."""

from __future__ import annotations

from typing import Any, Literal

from . import BRAND_NAMES, MODULE_NAMES, PRODUCT_FAMILY, PRODUCT_NAME, __version__
from .brand import PENS, SLIDES, TABLES
from .deck import Presentation, create_presentation
from .sheet import Spreadsheet, Workbook, create_spreadsheet
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


def create(kind: DocKind | str, title: str = "") -> Document | Spreadsheet | Presentation:
    k = _normalize_kind(str(kind))
    if k == "word":
        return create_document(title or f"{PENS} document")
    if k == "sheet":
        return create_spreadsheet(title or f"{TABLES} sheet")
    if k == "deck":
        return create_presentation(title or f"{SLIDES} deck")
    raise ValueError(f"unknown kind: {kind!r}")


def suite_status() -> dict[str, Any]:
    return {
        "product": PRODUCT_NAME,
        "family": PRODUCT_FAMILY,
        "version": __version__,
        "brands": list(BRAND_NAMES),
        "modules": list(MODULE_NAMES),
        "pillars": list(BRAND_NAMES),
        "primary_names": {"Pens": PENS, "Tables": TABLES, "Slides": SLIDES},
        "ok": True,
    }

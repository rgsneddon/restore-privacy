"""rpOffice — Restore Privacy Office: Pens · Tables · Slides.

Corel-historical independent suite design (Raskul) — not a Microsoft workalike.
"""

from .brand import (
    APP_ORDER,
    DESIGN_LINEAGE,
    MAKER,
    PENS,
    PRODUCT_FAMILY,
    SLIDES,
    SUITE_NAME,
    TABLES,
)

__version__ = "0.3.0"
PRODUCT_NAME = SUITE_NAME
MODULE_NAMES = ("word", "sheet", "deck")  # domain modules
BRAND_NAMES = APP_ORDER

__all__ = [
    "APP_ORDER",
    "BRAND_NAMES",
    "DESIGN_LINEAGE",
    "MAKER",
    "MODULE_NAMES",
    "PENS",
    "PRODUCT_FAMILY",
    "PRODUCT_NAME",
    "SLIDES",
    "SUITE_NAME",
    "TABLES",
    "__version__",
]

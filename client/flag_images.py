"""Catalog country flag images for UI (Windows dropdown / list rows).

Emoji regional-indicator flags often fail to paint in Tk OptionMenu menus on
Windows. Shipped PNG flags under ``client/windows/native/flags/`` are the
reliable presentation for IS / DE (live residual catalog).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

# Codes that ship explicit flag bitmaps (product residual catalog).
# Live peers only: IS, DE. US and Romania are deprecated (stale prefs map to DE).
CATALOG_FLAG_CODES: tuple[str, ...] = ("DE",)


def flag_images_dir() -> Path:
    """Directory containing catalog flag PNGs (``is.png``, ``de.png``, ``us.png``)."""
    # client/flag_images.py → client/windows/native/flags
    return Path(__file__).resolve().parent / "windows" / "native" / "flags"


def flag_image_path(code: str | None) -> Optional[Path]:
    """Return path to the shipped flag PNG for *code*, or None if missing."""
    c = (code or "").strip().upper()
    if not c:
        return None
    p = flag_images_dir() / f"{c.lower()}.png"
    if p.is_file() and p.stat().st_size > 0:
        return p
    return None


def catalog_flag_image_paths() -> dict[str, Path]:
    """Map catalog code → existing flag PNG path (IS / DE when present)."""
    out: dict[str, Path] = {}
    for code in CATALOG_FLAG_CODES:
        p = flag_image_path(code)
        if p is not None:
            out[code] = p
    return out


def assert_catalog_flag_images_present() -> list[str]:
    """Return list of missing live-catalog flag codes (empty when all exist)."""
    missing: list[str] = []
    for code in CATALOG_FLAG_CODES:
        if flag_image_path(code) is None:
            missing.append(code)
    return missing

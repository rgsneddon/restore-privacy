"""Assemble and serve the public Restore Privacy media kit (ZIP).

Sources: ``assets/brand/`` masters + ``status_page/static/`` site icons.
No secrets. Public download path: ``/media-kit/restore-privacy-media-kit.zip``.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Iterable

STATUS_DIR = Path(__file__).resolve().parent
REPO_ROOT = STATUS_DIR.parent
BRAND_DIR = REPO_ROOT / "assets" / "brand"
STATIC_DIR = STATUS_DIR / "static"
PUBLIC_KIT_DIR = STATUS_DIR / "public" / "media-kit"
KIT_FILENAME = "restore-privacy-media-kit.zip"
PUBLIC_URL_PATH = f"/media-kit/{KIT_FILENAME}"


def _iter_brand_files() -> Iterable[tuple[str, Path]]:
    """Yield (arcname, path) for kit members."""
    if BRAND_DIR.is_dir():
        for p in sorted(BRAND_DIR.rglob("*")):
            if not p.is_file():
                continue
            if p.suffix.lower() in (".png", ".ico", ".jpg", ".jpeg", ".webp", ".svg", ".txt", ".md", ".json"):
                rel = p.relative_to(BRAND_DIR).as_posix()
                yield f"brand/{rel}", p
    # Site static icons (may duplicate brand; useful for web drop-in paths)
    static_names = (
        "favicon.ico",
        "favicon.png",
        "logo.png",
        "logo_transparent.png",
        "apple-touch-icon.png",
        "stripe_brand_icon.png",
        "stripe_brand_logo.png",
    )
    for name in static_names:
        p = STATIC_DIR / name
        if p.is_file():
            yield f"status_static/{name}", p


def build_media_kit_bytes() -> bytes:
    """Build ZIP bytes in memory."""
    buf = io.BytesIO()
    readme = """Restore Privacy — media kit
================================

Public brand assets for press, partners, and store listings.
Do not use Stripe Dashboard brand files as the product logo for non-Stripe contexts
without checking assets/brand/stripe/README.md.

Contents
--------
brand/             Master logos, favicons, flat/primary/rounded variants
status_static/     Same icons as served on restoreprivacy.online (/logo.png, etc.)

Suggested use
-------------
- Favicon / app icon: brand/favicon.ico, brand/favicon-32.png, apple-touch-icon via status_static/
- Square mark: brand/logo-256.png, brand/logo-512.png, primary_*_1024.png
- Transparent: brand/logo transparent variants / status_static/logo_transparent.png
- Stripe Checkout branding only: brand/stripe/*

Public URL on the status host: /media-kit/restore-privacy-media-kit.zip
(no admin login required).

© RASKUL LTD / Restore Privacy — brand assets for legitimate promotion of the product.
"""
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", readme)
        seen: set[str] = set()
        for arc, path in _iter_brand_files():
            if arc in seen:
                continue
            seen.add(arc)
            zf.write(path, arcname=arc)
    return buf.getvalue()


def ensure_media_kit_on_disk() -> Path:
    """Write kit under status_page/public/media-kit/ and return path."""
    PUBLIC_KIT_DIR.mkdir(parents=True, exist_ok=True)
    dest = PUBLIC_KIT_DIR / KIT_FILENAME
    data = build_media_kit_bytes()
    dest.write_bytes(data)
    return dest


def copy_media_kit_to_downloads(downloads_dir: Path | None = None) -> Path:
    """Copy kit into the operator Downloads folder; return destination path."""
    if downloads_dir is None:
        downloads_dir = Path.home() / "Downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    src = ensure_media_kit_on_disk()
    dest = downloads_dir / KIT_FILENAME
    dest.write_bytes(src.read_bytes())
    return dest


def media_kit_file_path() -> Path:
    """Path to staged kit (builds if missing)."""
    dest = PUBLIC_KIT_DIR / KIT_FILENAME
    if not dest.is_file() or dest.stat().st_size < 1000:
        return ensure_media_kit_on_disk()
    return dest

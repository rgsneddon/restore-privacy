#!/usr/bin/env python3
"""Generate favicon + multi-platform app icons from assets/brand masters.

Source of truth (prefer): assets/brand/primary_dark_1024.png
Imported from ~/Downloads/RestorePrivacy_VPN_Icons per that package README:
  - Primary dark → default app icons / website logo
  - Primary transparent → Android adaptive foreground
  - Flat dark/transparent → small/notification sizes when needed
  - iOS rounded dark → optional iOS master (same 1024 used for AppIcon)

Outputs: status_page static favicon/logo, Android mipmaps, Windows ICO,
Flutter Windows/macOS/iOS AppIcons, native Windows client icon.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BRAND_DIR = ROOT / "assets" / "brand"

# User export package (Downloads)
DOWNLOADS_PKG = Path.home() / "Downloads" / "RestorePrivacy_VPN_Icons"
# Canonical masters in-repo (after import)
PRIMARY_DARK = BRAND_DIR / "primary_dark_1024.png"
PRIMARY_TRANSPARENT = BRAND_DIR / "primary_transparent_1024.png"
# Public header: transparent outside shield+key; interior holes filled dark blue.
PRIMARY_TRANSPARENT_FILLED = BRAND_DIR / "primary_transparent_filled_1024.png"
FLAT_DARK = BRAND_DIR / "flat_dark_1024.png"
IOS_ROUNDED_DARK = BRAND_DIR / "rounded_dark_1024.png"
# Legacy fallback
LEGACY_JPG = BRAND_DIR / "vpnlogo.jpg"

STATUS_STATIC = ROOT / "status_page" / "static"
WIN_CLIENT_ICON = ROOT / "client" / "windows" / "native" / "app_icon.ico"
WIN_CLIENT_PNG = ROOT / "client" / "windows" / "native" / "app_icon.png"
FLUTTER_WIN_ICO = ROOT / "client_app" / "windows" / "runner" / "resources" / "app_icon.ico"
FLUTTER_BRAND_DIR = ROOT / "client_app" / "assets" / "brand"
BROWSER_EXT_ICONS = ROOT / "browser_extension" / "icons"

ANDROID_MIPMAPS = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}
ANDROID_RES = ROOT / "client_app" / "android" / "app" / "src" / "main" / "res"
ANDROID_ADAPTIVE_FG = (
    ANDROID_RES / "drawable-xxxhdpi" / "ic_launcher_foreground.png"
)

IOS_ICONS = [
    ("Icon-App-20x20@1x.png", 20),
    ("Icon-App-20x20@2x.png", 40),
    ("Icon-App-20x20@3x.png", 60),
    ("Icon-App-29x29@1x.png", 29),
    ("Icon-App-29x29@2x.png", 58),
    ("Icon-App-29x29@3x.png", 87),
    ("Icon-App-40x40@1x.png", 40),
    ("Icon-App-40x40@2x.png", 80),
    ("Icon-App-40x40@3x.png", 120),
    ("Icon-App-60x60@2x.png", 120),
    ("Icon-App-60x60@3x.png", 180),
    ("Icon-App-76x76@1x.png", 76),
    ("Icon-App-76x76@2x.png", 152),
    ("Icon-App-83.5x83.5@2x.png", 167),
    ("Icon-App-1024x1024@1x.png", 1024),
]
IOS_DIR = ROOT / "client_app" / "ios" / "Runner" / "Assets.xcassets" / "AppIcon.appiconset"

MAC_ICONS = [
    ("app_icon_16.png", 16),
    ("app_icon_32.png", 32),
    ("app_icon_64.png", 64),
    ("app_icon_128.png", 128),
    ("app_icon_256.png", 256),
    ("app_icon_512.png", 512),
    ("app_icon_1024.png", 1024),
]
MAC_DIR = ROOT / "client_app" / "macos" / "Runner" / "Assets.xcassets" / "AppIcon.appiconset"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def import_from_downloads() -> None:
    """Copy README-recommended masters into assets/brand/."""
    BRAND_DIR.mkdir(parents=True, exist_ok=True)
    if not DOWNLOADS_PKG.is_dir():
        return
    mapping = [
        (DOWNLOADS_PKG / "01_Primary_Detailed" / "dark.png", PRIMARY_DARK),
        (DOWNLOADS_PKG / "01_Primary_Detailed" / "transparent.png", PRIMARY_TRANSPARENT),
        (DOWNLOADS_PKG / "01_Primary_Detailed" / "light.png", BRAND_DIR / "primary_light_1024.png"),
        (DOWNLOADS_PKG / "03_Simplified_Flat" / "dark.png", FLAT_DARK),
        (DOWNLOADS_PKG / "03_Simplified_Flat" / "transparent.png", BRAND_DIR / "flat_transparent_1024.png"),
        (DOWNLOADS_PKG / "02_iOS_Rounded" / "dark.png", IOS_ROUNDED_DARK),
        (DOWNLOADS_PKG / "masters_1024" / "primary_dark_1024.png", PRIMARY_DARK),
    ]
    for src, dest in mapping:
        if src.is_file():
            shutil.copy2(src, dest)
    # Keep README snapshot for operators
    readme = DOWNLOADS_PKG / "README.txt"
    if readme.is_file():
        shutil.copy2(readme, BRAND_DIR / "README_icons_export.txt")


def ensure_source() -> Path:
    import_from_downloads()
    if PRIMARY_DARK.is_file():
        return PRIMARY_DARK
    if LEGACY_JPG.is_file():
        return LEGACY_JPG
    raise FileNotFoundError(
        f"Missing brand master: {PRIMARY_DARK} (import from {DOWNLOADS_PKG})"
    )


def load_square_rgba(path: Path) -> Image.Image:
    img = Image.open(path).convert("RGBA")
    w, h = img.size
    if w != h:
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))
    return img


# Product dark navy (#0a1628) — fallback when solid plate pixel is missing.
_FILL_NAVY = (10, 22, 40, 255)


def fill_shield_interior_holes(
    transparent: Image.Image,
    solid_plate: Image.Image | None = None,
    *,
    navy: tuple[int, int, int, int] = _FILL_NAVY,
) -> Image.Image:
    """Fill fully transparent pixels *inside* the mark with dark blue; keep exterior alpha.

    Outer exterior is identified by flood-filling alpha==0 from the four corners.
    Enclosed transparent islands (holes inside the shield) become opaque navy,
    preferably sampled from *solid_plate* at the same coordinates.
    """
    from PIL import ImageDraw

    trans = transparent.convert("RGBA")
    w, h = trans.size
    solid = None
    if solid_plate is not None:
        solid = solid_plate.convert("RGBA")
        if solid.size != (w, h):
            solid = solid.resize((w, h), Image.Resampling.LANCZOS)

    # Binary: fully transparent → 255; then flood exterior as 128
    outer = Image.new("L", (w, h), 0)
    tp = trans.load()
    op = outer.load()
    for y in range(h):
        for x in range(w):
            if tp[x, y][3] == 0:
                op[x, y] = 255
    for seed in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        if outer.getpixel(seed) == 255:
            ImageDraw.floodfill(outer, seed, 128, thresh=0)

    out = trans.copy()
    outp = out.load()
    sp = solid.load() if solid is not None else None
    outerp = outer.load()
    for y in range(h):
        for x in range(w):
            if tp[x, y][3] != 0:
                continue
            if outerp[x, y] == 128:
                continue  # exterior — stay transparent
            if sp is not None:
                r, g, b, a = sp[x, y]
                outp[x, y] = (r, g, b, 255) if a >= 200 else navy
            else:
                outp[x, y] = navy
    return out


def resize_png(src: Image.Image, size: int) -> Image.Image:
    return src.resize((size, size), Image.Resampling.LANCZOS)


def save_png(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG", optimize=True)


def save_ico(src: Image.Image, path: Path, sizes: list[int] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sizes = sizes or [16, 32, 48, 64, 128, 256]
    base = resize_png(src, max(sizes))
    base.save(path, format="ICO", sizes=[(s, s) for s in sizes])


def generate_all() -> dict:
    source = ensure_source()
    master = load_square_rgba(source)
    # Small icons: prefer flat when available (README: simplified flat for small sizes)
    small_src = load_square_rgba(FLAT_DARK) if FLAT_DARK.is_file() else master
    # Adaptive foreground: transparent primary (raw master, not interior-filled)
    fg = (
        load_square_rgba(PRIMARY_TRANSPARENT)
        if PRIMARY_TRANSPARENT.is_file()
        else master
    )
    # Public header cutout: fill holes inside shield with dark plate colour
    if PRIMARY_TRANSPARENT.is_file():
        filled = fill_shield_interior_holes(
            load_square_rgba(PRIMARY_TRANSPARENT),
            master if PRIMARY_DARK.is_file() else None,
        )
        save_png(filled, PRIMARY_TRANSPARENT_FILLED)
    else:
        filled = None
    # iOS: prefer rounded dark if present
    ios_master = (
        load_square_rgba(IOS_ROUNDED_DARK) if IOS_ROUNDED_DARK.is_file() else master
    )

    written: list[str] = []

    save_png(resize_png(master, 512), BRAND_DIR / "logo-512.png")
    written.append(str(BRAND_DIR / "logo-512.png"))
    save_png(resize_png(master, 256), BRAND_DIR / "logo-256.png")
    written.append(str(BRAND_DIR / "logo-256.png"))
    save_png(resize_png(small_src, 32), BRAND_DIR / "favicon-32.png")
    written.append(str(BRAND_DIR / "favicon-32.png"))
    save_ico(small_src, BRAND_DIR / "favicon.ico", [16, 32, 48])
    written.append(str(BRAND_DIR / "favicon.ico"))

    STATUS_STATIC.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BRAND_DIR / "favicon.ico", STATUS_STATIC / "favicon.ico")
    shutil.copy2(BRAND_DIR / "favicon-32.png", STATUS_STATIC / "favicon.png")
    shutil.copy2(BRAND_DIR / "logo-256.png", STATUS_STATIC / "logo.png")
    save_png(resize_png(master, 180), STATUS_STATIC / "apple-touch-icon.png")
    # Public header: outer transparent; interior shield holes filled dark blue.
    if filled is not None:
        save_png(filled, STATUS_STATIC / "logo_transparent.png")
        written.append(str(PRIMARY_TRANSPARENT_FILLED))
    elif PRIMARY_TRANSPARENT.is_file():
        shutil.copy2(PRIMARY_TRANSPARENT, STATUS_STATIC / "logo_transparent.png")
    else:
        save_png(resize_png(fg, 512), STATUS_STATIC / "logo_transparent.png")
    written.extend(
        [
            str(STATUS_STATIC / "favicon.ico"),
            str(STATUS_STATIC / "favicon.png"),
            str(STATUS_STATIC / "logo.png"),
            str(STATUS_STATIC / "apple-touch-icon.png"),
            str(STATUS_STATIC / "logo_transparent.png"),
        ]
    )

    save_ico(master, WIN_CLIENT_ICON)
    save_png(resize_png(master, 256), WIN_CLIENT_PNG)
    written.extend([str(WIN_CLIENT_ICON), str(WIN_CLIENT_PNG)])

    save_ico(master, FLUTTER_WIN_ICO)
    written.append(str(FLUTTER_WIN_ICO))

    # Flutter asset bundle brand (was historically a stale smaller plate)
    FLUTTER_BRAND_DIR.mkdir(parents=True, exist_ok=True)
    save_png(resize_png(master, 256), FLUTTER_BRAND_DIR / "logo-256.png")
    save_png(resize_png(master, 512), FLUTTER_BRAND_DIR / "logo-512.png")
    save_png(resize_png(master, 256), FLUTTER_BRAND_DIR / "app_icon.png")
    written.extend(
        [
            str(FLUTTER_BRAND_DIR / "logo-256.png"),
            str(FLUTTER_BRAND_DIR / "logo-512.png"),
            str(FLUTTER_BRAND_DIR / "app_icon.png"),
        ]
    )

    # Browser extension toolbar icons from current flat/primary
    if BROWSER_EXT_ICONS.is_dir():
        for name, px in (("icon-16.png", 16), ("icon-48.png", 48), ("icon-128.png", 128)):
            save_png(resize_png(small_src if px <= 48 else master, px), BROWSER_EXT_ICONS / name)
            written.append(str(BROWSER_EXT_ICONS / name))

    for folder, px in ANDROID_MIPMAPS.items():
        out = ANDROID_RES / folder / "ic_launcher.png"
        save_png(resize_png(master, px), out)
        written.append(str(out))
        # adaptive / round aliases if present
        for name in ("ic_launcher_round.png", "ic_launcher_foreground.png"):
            alt = ANDROID_RES / folder / name
            if alt.parent.is_dir():
                save_png(resize_png(fg if "foreground" in name else master, px), alt)
                written.append(str(alt))

    if ANDROID_ADAPTIVE_FG.parent.is_dir() or True:
        ANDROID_ADAPTIVE_FG.parent.mkdir(parents=True, exist_ok=True)
        save_png(resize_png(fg, 432), ANDROID_ADAPTIVE_FG)
        written.append(str(ANDROID_ADAPTIVE_FG))

    if IOS_DIR.is_dir():
        for name, px in IOS_ICONS:
            save_png(resize_png(ios_master, px), IOS_DIR / name)
            written.append(str(IOS_DIR / name))

    if MAC_DIR.is_dir():
        for name, px in MAC_ICONS:
            save_png(resize_png(master, px), MAC_DIR / name)
            written.append(str(MAC_DIR / name))

    meta = {
        "source": str(source.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": sha256_file(source),
        "source_bytes": source.stat().st_size,
        "outputs": len(written),
        "files": [Path(p).relative_to(ROOT).as_posix() for p in written],
    }
    (BRAND_DIR / "manifest.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    return meta


def main() -> int:
    meta = generate_all()
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Generate favicon + multi-platform app icons from assets/brand/vpnlogo.jpg.

Source of truth: assets/brand/vpnlogo.jpg (copied from user Downloads).
Outputs: status_page static favicon, Android mipmaps, Windows ICO, iOS/mac AppIcons,
and client/windows icon for the native Python client.
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
SOURCE_NAME = "vpnlogo.jpg"
SOURCE = BRAND_DIR / SOURCE_NAME
DOWNLOADS_SRC = Path.home() / "Downloads" / "vpnlogo.jpg"

# Status page static assets
STATUS_STATIC = ROOT / "status_page" / "static"
# Windows Python client
WIN_CLIENT_ICON = ROOT / "client" / "windows" / "native" / "app_icon.ico"
WIN_CLIENT_PNG = ROOT / "client" / "windows" / "native" / "app_icon.png"
# Flutter Windows
FLUTTER_WIN_ICO = ROOT / "client_app" / "windows" / "runner" / "resources" / "app_icon.ico"
# Android densities (px)
ANDROID_MIPMAPS = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}
ANDROID_RES = ROOT / "client_app" / "android" / "app" / "src" / "main" / "res"
# iOS: (filename, pixel size)
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
# macOS
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


def ensure_source() -> Path:
    BRAND_DIR.mkdir(parents=True, exist_ok=True)
    if not SOURCE.is_file():
        if not DOWNLOADS_SRC.is_file():
            raise FileNotFoundError(
                f"Missing brand source: {SOURCE} and {DOWNLOADS_SRC}"
            )
        shutil.copy2(DOWNLOADS_SRC, SOURCE)
    return SOURCE


def load_square_rgba(path: Path) -> Image.Image:
    img = Image.open(path).convert("RGBA")
    # Center-crop to square if needed
    w, h = img.size
    if w != h:
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))
    return img


def resize_png(src: Image.Image, size: int) -> Image.Image:
    return src.resize((size, size), Image.Resampling.LANCZOS)


def save_png(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG", optimize=True)


def save_ico(src: Image.Image, path: Path, sizes: list[int] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sizes = sizes or [16, 32, 48, 64, 128, 256]
    # Pillow multi-size ICO: pass largest as base and sizes=
    base = resize_png(src, max(sizes))
    base.save(
        path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
    )


def generate_all() -> dict:
    ensure_source()
    master = load_square_rgba(SOURCE)
    written: list[str] = []

    # Master derivatives in brand/
    logo512 = resize_png(master, 512)
    save_png(logo512, BRAND_DIR / "logo-512.png")
    written.append(str(BRAND_DIR / "logo-512.png"))
    save_png(resize_png(master, 256), BRAND_DIR / "logo-256.png")
    written.append(str(BRAND_DIR / "logo-256.png"))
    save_png(resize_png(master, 32), BRAND_DIR / "favicon-32.png")
    written.append(str(BRAND_DIR / "favicon-32.png"))
    save_ico(master, BRAND_DIR / "favicon.ico", [16, 32, 48])
    written.append(str(BRAND_DIR / "favicon.ico"))

    # Status page static
    STATUS_STATIC.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BRAND_DIR / "favicon.ico", STATUS_STATIC / "favicon.ico")
    shutil.copy2(BRAND_DIR / "favicon-32.png", STATUS_STATIC / "favicon.png")
    shutil.copy2(BRAND_DIR / "logo-256.png", STATUS_STATIC / "logo.png")
    # Also serve source-derived apple-touch
    save_png(resize_png(master, 180), STATUS_STATIC / "apple-touch-icon.png")
    written.extend(
        [
            str(STATUS_STATIC / "favicon.ico"),
            str(STATUS_STATIC / "favicon.png"),
            str(STATUS_STATIC / "logo.png"),
            str(STATUS_STATIC / "apple-touch-icon.png"),
        ]
    )

    # Windows Python client
    save_ico(master, WIN_CLIENT_ICON)
    save_png(resize_png(master, 256), WIN_CLIENT_PNG)
    written.extend([str(WIN_CLIENT_ICON), str(WIN_CLIENT_PNG)])

    # Flutter Windows
    save_ico(master, FLUTTER_WIN_ICO)
    written.append(str(FLUTTER_WIN_ICO))

    # Android launcher
    for folder, px in ANDROID_MIPMAPS.items():
        out = ANDROID_RES / folder / "ic_launcher.png"
        save_png(resize_png(master, px), out)
        written.append(str(out))

    # iOS
    if IOS_DIR.is_dir():
        for name, px in IOS_ICONS:
            save_png(resize_png(master, px), IOS_DIR / name)
            written.append(str(IOS_DIR / name))

    # macOS
    if MAC_DIR.is_dir():
        for name, px in MAC_ICONS:
            save_png(resize_png(master, px), MAC_DIR / name)
            written.append(str(MAC_DIR / name))

    meta = {
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": sha256_file(SOURCE),
        "source_bytes": SOURCE.stat().st_size,
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

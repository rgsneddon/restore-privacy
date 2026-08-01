"""Slides — Restore Privacy presentation program (standalone)."""

from __future__ import annotations

import argparse
import json

from .. import __version__
from ..brand import PRODUCT_FAMILY, SLIDES
from ..deck import create_presentation


def smoke() -> dict:
    p = create_presentation(f"{SLIDES} intro")
    p.add_slide("Privacy", "Restore Privacy Suite")
    p.add_slide("Ned", "Your helper")
    return {
        "ok": True,
        "product": SLIDES,
        "family": PRODUCT_FAMILY,
        "version": __version__,
        "kind": "presentation",
        "title": p.title,
        "slide_count": len(p.slides),
        "titles": [s.title for s in p.slides],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="slides", description=f"{SLIDES} — Restore Privacy presentations")
    ap.add_argument("--version", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args(argv)
    if args.version:
        print(f"{SLIDES} {__version__}")
        return 0
    print(json.dumps(smoke(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

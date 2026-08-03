"""Support-log client_version must follow client/VERSION monopin (not 0.5.8)."""

from __future__ import annotations

import importlib
from pathlib import Path

from client.connection_log import product_client_version


def test_product_client_version_matches_client_version_file() -> None:
    pin_path = Path(__file__).resolve().parent / "VERSION"
    assert pin_path.is_file(), "client/VERSION must exist for residual pin"
    pin = pin_path.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    assert pin, "client/VERSION empty"
    # Never ship historical residual freeze pins
    assert pin != "0.5.8"
    assert not pin.startswith("0.5.")
    got = product_client_version()
    assert got == pin.lstrip("vV"), f"support log version {got!r} != pin {pin!r}"


def test_product_client_version_not_stale_half_line() -> None:
    v = product_client_version()
    assert v not in ("0.5.8", "0.0.0", "unknown")
    # Catalog monopin shape X.Y.Z
    parts = v.split(".")
    assert len(parts) >= 2
    assert all(p.isdigit() for p in parts[:3] if p)


if __name__ == "__main__":
    test_product_client_version_matches_client_version_file()
    test_product_client_version_not_stale_half_line()
    print("ok", product_client_version())

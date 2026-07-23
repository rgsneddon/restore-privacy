"""Free-tier product flavor — permanent version label **3.3.3**.

Free clients:
- Version string is always ``3.3.3`` (never auto-bumps with paid 0.x catalog).
- Settings privacy-scale / multi-hop / shape / obfs are locked (not user-amendable).
- Residual path: Iceland entry only, lean residual (no pad/cover/jitter, no outer wrap).

Enable with process env ``RPT_FREE_TIER=1`` (or packaging that sets it).
Paid catalog builds leave this unset.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Permanent free-tier marketing / package pin — never inherit paid 0.x bumps.
FREE_TIER_VERSION = "3.3.3"

# Iceland product entry (same as client.endpoint.PRODUCT_NODE_HOST).
FREE_TIER_ENTRY_HOST = "82.221.101.241"
FREE_TIER_ENTRY_PORT = 44044


def free_tier_enabled() -> bool:
    """True when this process is a free-tier build/session."""
    raw = (os.environ.get("RPT_FREE_TIER") or "").strip().lower()
    return raw in ("1", "true", "yes", "on", "free")


@dataclass(frozen=True)
class FreeTierConnectivityPolicy:
    """Locked basic connectivity for free 3.3.3 (not user-amendable)."""

    version: str = FREE_TIER_VERSION
    settings_locked: bool = True
    entry_host: str = FREE_TIER_ENTRY_HOST
    entry_port: int = FREE_TIER_ENTRY_PORT
    multihop: bool = False
    traffic_shape: bool = False
    outer_obfuscation: bool = False
    # Core residual VPN still on (HELLO/session/tunnel).
    residual_vpn_core: bool = True

    def residual_host(self) -> str:
        return self.entry_host


def free_tier_policy() -> FreeTierConnectivityPolicy:
    """Resolved free-tier policy (same defaults whether flag on/off for testing)."""
    return FreeTierConnectivityPolicy()


def free_tier_product_version() -> str:
    """UI / package pin: always 3.3.3 when free tier is active."""
    if free_tier_enabled():
        return FREE_TIER_VERSION
    # Paid path reads client/VERSION elsewhere; this helper is free-aware only.
    try:
        from pathlib import Path

        pin = (Path(__file__).resolve().parent / "VERSION").read_text(encoding="utf-8")
        return pin.strip() or FREE_TIER_VERSION
    except OSError:
        return FREE_TIER_VERSION


def free_tier_settings_locked() -> bool:
    return free_tier_enabled()


def free_tier_privacy_scale_locked_off() -> tuple[bool, bool, bool]:
    """Return (traffic_shape, outer_obfuscation, multihop) forced values when free.

    When free tier is off, returns product defaults (shape/obfs/multihop all off).
    """
    if free_tier_enabled():
        return (False, False, False)
    return (False, False, False)

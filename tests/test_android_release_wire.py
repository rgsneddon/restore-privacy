"""Shipped Android APK must embed product residual wire (PFS + outer obfs).

The live node defaults to require_pfs=True and silent-drops HELLOs that omit the
X25519 eph field — that surfaces on-device as ``Poll timed out``. Licence/Settings
strings must also be present in the Flutter AOT blob for the seamless UI.

Catalog monopin: ``releases/{VERSION}/restore-privacy-client-{VERSION}-android.apk``
must pass these gates (carry-forward without PFS is a Connect regression).
"""

from __future__ import annotations

import hashlib
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
PRODUCT_PUB_PIN = (
    ROOT / "product" / "NODE_ELGAMAL_PUB.sha256"
).read_text(encoding="utf-8").strip().split()[0]

# Current catalog first — never let a stale prior hide a broken monopin APK.
# Pre-RUST product line only (this monorepo); do not resolve sibling RUST-IN-PRIVACY.
_CANDIDATES = [
    ROOT / "releases" / VERSION / f"restore-privacy-client-{VERSION}-android.apk",
    ROOT / "status_page" / "assets" / VERSION / f"restore-privacy-client-{VERSION}-android.apk",
]


def _resolve_apk() -> Path:
    for p in _CANDIDATES:
        if p.is_file():
            return p
    return _CANDIDATES[0]


APK = _resolve_apk()


def _assert_wire(apk: Path) -> None:
    assert apk.is_file(), f"missing release APK: {apk}"
    assert apk.stat().st_size > 1_000_000, f"APK too small: {apk.stat().st_size}"
    with zipfile.ZipFile(apk) as z:
        pub = z.read("assets/secrets/node_elgamal.pub")
        assert (
            hashlib.sha256(pub).hexdigest() == PRODUCT_PUB_PIN
        ), "APK node_elgamal.pub must match product pin"
        dex = z.read("classes.dex")
        # Product residual HELLO (node require_pfs) — silent drop without these
        assert b"pfs-x25519" in dex, f"{apk.name} missing PFS wire (Connect times out)"
        assert b"RPT-OBFS-LAYER" in dex, f"{apk.name} missing outer obfs wire"
        assert b"RPTP" in dex
        assert b"RPTC" in dex
        # Flutter AOT may hold licence/Settings copy
        blob = z.read("lib/arm64-v8a/libapp.so")
        combined = dex + blob
        assert b"Accept licence" in combined
        assert b"licence_accepted" in combined


class TestAndroidReleaseApkWire(unittest.TestCase):
    def test_catalog_apk_has_pfs_obfs_and_pub_pin(self):
        """Current catalog Android package must be residual-wire complete."""
        catalog = (
            ROOT
            / "releases"
            / VERSION
            / f"restore-privacy-client-{VERSION}-android.apk"
        )
        self.assertTrue(catalog.is_file(), f"missing catalog APK: {catalog}")
        _assert_wire(catalog)

    def test_apk_present_with_pfs_obfs_and_pub_pin(self):
        apk = _resolve_apk()
        self.assertTrue(apk.is_file(), f"missing release APK among {_CANDIDATES}")
        _assert_wire(apk)


if __name__ == "__main__":
    unittest.main()

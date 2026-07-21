"""Shipped Android APK must embed product residual wire (PFS + outer obfs).

The live node defaults to require_pfs=True and silent-drops HELLOs that omit the
X25519 eph field — that surfaces on-device as ``Poll timed out``. Licence/Settings
strings must also be present in the Flutter AOT blob for the seamless UI.

Public v1.0.0 asset name: restore-privacy-client-0.2.3-android.apk
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

# Prefer public RUST-IN-PRIVACY basename, then private client release path.
_CANDIDATES = [
    ROOT / "releases" / "1.0.0" / "restore-privacy-client-0.2.3-android.apk",
    ROOT.parents[0] / "RUST-IN-PRIVACY" / "releases" / "1.0.0" / "restore-privacy-client-0.2.3-android.apk",
    ROOT / "releases" / VERSION / f"restore-privacy-client-{VERSION}-android.apk",
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
        # Product residual HELLO (node require_pfs)
        assert b"pfs-x25519" in dex
        assert b"RPT-OBFS-LAYER" in dex
        assert b"RPTP" in dex
        assert b"RPTC" in dex
        # Flutter AOT may hold licence/Settings copy
        blob = z.read("lib/arm64-v8a/libapp.so")
        combined = dex + blob
        assert b"Accept licence" in combined
        assert b"licence_accepted" in combined


class TestAndroidReleaseApkWire(unittest.TestCase):
    def test_apk_present_with_pfs_obfs_and_pub_pin(self):
        apk = _resolve_apk()
        self.assertTrue(apk.is_file(), f"missing release APK among {_CANDIDATES}")
        _assert_wire(apk)
        # Public product name must be used when present under releases/1.0.0
        public = ROOT / "releases" / "1.0.0" / "restore-privacy-client-0.2.3-android.apk"
        if public.is_file():
            _assert_wire(public)
            self.assertEqual(public.name, "restore-privacy-client-0.2.3-android.apk")


if __name__ == "__main__":
    unittest.main()

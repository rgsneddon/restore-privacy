"""Shipped Android APK must embed product residual wire (PFS + outer obfs).

The live node defaults to require_pfs=True and silent-drops HELLOs that omit the
X25519 eph field — that surfaces on-device as ``Poll timed out``. Licence/Settings
strings must also be present in the Flutter AOT blob for the seamless UI.
"""

from __future__ import annotations

import hashlib
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
APK = ROOT / "releases" / VERSION / f"restore-privacy-client-{VERSION}-android.apk"
PRODUCT_PUB_PIN = (
    ROOT / "product" / "NODE_ELGAMAL_PUB.sha256"
).read_text(encoding="utf-8").strip().split()[0]


class TestAndroidReleaseApkWire(unittest.TestCase):
    def test_apk_present_with_pfs_obfs_and_pub_pin(self):
        self.assertTrue(APK.is_file(), f"missing release APK: {APK}")
        with zipfile.ZipFile(APK) as z:
            pub = z.read("assets/secrets/node_elgamal.pub")
            self.assertEqual(
                hashlib.sha256(pub).hexdigest(),
                PRODUCT_PUB_PIN,
                "APK node_elgamal.pub must match product pin",
            )
            dex = z.read("classes.dex")
            # Product residual HELLO (node require_pfs)
            self.assertIn(b"pfs-x25519", dex)
            self.assertIn(b"RPT-OBFS-LAYER", dex)
            self.assertIn(b"RPTP", dex)
            self.assertIn(b"RPTC", dex)
            # Flutter AOT may hold licence/Settings copy
            blob = z.read("lib/arm64-v8a/libapp.so")
            combined = dex + blob
            self.assertIn(b"Accept licence", combined)
            self.assertIn(b"licence_accepted", combined)


if __name__ == "__main__":
    unittest.main()

"""Catalog 0.3.7 package pins (source monopin + Windows PE presence).

Apple/Linux deep binary multihop embedding may be carry-forward until Mac/operator
rebuild; source pins and Windows multihop PE are required on this host.
"""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

VERSION = "0.3.7"
REL = ROOT / "releases" / VERSION
WINDOWS = REL / f"restore-privacy-client-{VERSION}-windows-x64-setup.exe"
EXIT_PUB_PIN = (
    "a36a3f38066ece7b33abfab6a57942fb998919b4a753ee0d9e9ec9c97c1c7352"
)


class Test037SourcePins(unittest.TestCase):
    def test_client_version_pin(self):
        ver = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(ver, VERSION)

    def test_downloads_catalog_pin(self):
        sys.path.insert(0, str(ROOT / "status_page"))
        from downloads import RELEASE_VERSION, RELEASE_TAG

        self.assertEqual(RELEASE_VERSION, VERSION)
        self.assertEqual(RELEASE_TAG, VERSION)

    def test_multihop_routing_implemented(self):
        from client.multihop import MULTI_HOP_ROUTING_IMPLEMENTED, PRODUCT_EXIT_HOST

        self.assertIs(MULTI_HOP_ROUTING_IMPLEMENTED, True)
        self.assertEqual(PRODUCT_EXIT_HOST, "185.146.232.107")

    def test_exit_pub_tracked_and_distinct_from_entry(self):
        exit_p = ROOT / "product" / "exit_node_elgamal.pub"
        entry_p = ROOT / "product" / "node_elgamal.pub"
        self.assertTrue(exit_p.is_file())
        self.assertTrue(entry_p.is_file())
        exit_b = exit_p.read_bytes()
        entry_b = entry_p.read_bytes()
        self.assertGreaterEqual(len(exit_b), 32)
        self.assertNotEqual(exit_b, entry_b)
        self.assertEqual(hashlib.sha256(exit_b).hexdigest(), EXIT_PUB_PIN)

    def test_windows_pe_built(self):
        self.assertTrue(WINDOWS.is_file(), f"missing {WINDOWS}")
        self.assertGreater(WINDOWS.stat().st_size, 1_000_000)

    def test_apple_handoff_present(self):
        h = ROOT / "client_app" / "APPLE_HANDOFF_0.3.7.md"
        self.assertTrue(h.is_file())
        text = h.read_text(encoding="utf-8")
        self.assertIn("0.3.7", text)

    def test_readme_catalog_0_3_7(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("0.3.7", text)


if __name__ == "__main__":
    unittest.main()

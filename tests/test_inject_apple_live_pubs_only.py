"""Apple inject ships live residual pubs only (IS/DE/exit); US retired."""

from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import inject_apple_secrets as ias  # noqa: E402


class TestInjectAppleLivePubsOnly(unittest.TestCase):
    def test_public_pubs_tuple_excludes_us(self):
        self.assertEqual(
            ias.PUBLIC_PUBS,
            (ias.NODE_PUB, ias.DE_PUB, ias.EXIT_PUB),
        )
        self.assertNotIn(ias.US_PUB, ias.PUBLIC_PUBS)
        self.assertEqual(ias.US_PUB, "us_node_elgamal.pub")

    def test_inject_ios_layout_no_us_and_entry_matches_product(self):
        product = ROOT / "product"
        entry = product / "node_elgamal.pub"
        if not entry.is_file():
            self.skipTest("product/node_elgamal.pub missing")
        pin = hashlib.sha256(entry.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as td:
            app = Path(td) / "Runner.app"
            (app / "PlugIns" / "PacketTunnel.appex").mkdir(parents=True)
            # Pre-seed retired US pin so inject must strip it
            stale = app / "secrets" / "us_node_elgamal.pub"
            stale.parent.mkdir(parents=True)
            stale.write_bytes(b"x" * 64)
            dest = ias.inject(app, product, ios=True)
            self.assertEqual(dest, app / "secrets")
            self.assertTrue((dest / "node_elgamal.pub").is_file())
            self.assertTrue((dest / "de_node_elgamal.pub").is_file())
            self.assertTrue((dest / "exit_node_elgamal.pub").is_file())
            self.assertFalse(
                (dest / "us_node_elgamal.pub").exists(),
                "retired US pin must be removed/not injected",
            )
            got = hashlib.sha256(
                (dest / "node_elgamal.pub").read_bytes()
            ).hexdigest()
            self.assertEqual(got, pin)
            ape = app / "PlugIns" / "PacketTunnel.appex" / "secrets"
            self.assertTrue((ape / "node_elgamal.pub").is_file())
            self.assertFalse((ape / "us_node_elgamal.pub").exists())

    def test_inject_script_doc_macos_notary_vs_ios_distribution(self):
        text = (ROOT / "scripts" / "inject_apple_secrets.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Developer ID", text)
        self.assertIn("notary", text.lower())
        self.assertIn("Apple Distribution", text)
        self.assertIn("not accepted for iOS", text)
        self.assertNotIn(
            "iOS Developer ID notarized",
            text,
        )


if __name__ == "__main__":
    unittest.main()

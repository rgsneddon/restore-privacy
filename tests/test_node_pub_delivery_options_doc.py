"""Structural: shipped recommendations for public node pin delivery exist."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "NODE_PUB_DELIVERY_OPTIONS.md"


class TestNodePubDeliveryOptionsDoc(unittest.TestCase):
    def test_doc_recommends_methods_and_honesty(self):
        self.assertTrue(DOC.is_file(), "missing docs/NODE_PUB_DELIVERY_OPTIONS.md")
        text = DOC.read_text(encoding="utf-8")
        self.assertGreater(len(text), 800)
        # Current path
        self.assertIn("node_elgamal.pub", text)
        self.assertIn("secrets_loader", text)
        # Never private key
        self.assertIn("node_elgamal.priv", text)
        self.assertRegex(text, r"[Nn]ever")
        # At least three options (headings / numbered)
        self.assertIn("Authenticated pin fetch", text)
        self.assertIn("Entitlement-gated", text)
        self.assertIn("obfuscation", text.lower())
        # Honesty: public key not secret
        low = text.lower()
        self.assertTrue(
            "not" in low and "secret" in low,
            "must state public pin is not a confidential secret",
        )
        # Entry vs exit
        self.assertIn("exit_node_elgamal.pub", text)
        self.assertIn("HELLO", text)

    def test_loader_still_documents_public_embed(self):
        sl = (ROOT / "client" / "secrets_loader.py").read_text(encoding="utf-8")
        self.assertIn("node_elgamal.pub", sl)
        self.assertIn("public", sl.lower())
        self.assertIn("HELLO", sl)


if __name__ == "__main__":
    unittest.main()

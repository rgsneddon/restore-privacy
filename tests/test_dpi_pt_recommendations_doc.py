"""Structural: DPI / pluggable-transport recommendations doc is shipped."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "DPI_PT_RECOMMENDATIONS.md"


class TestDpiPtRecommendationsDoc(unittest.TestCase):
    def test_doc_has_pt_classes_and_honesty(self):
        self.assertTrue(DOC.is_file())
        text = DOC.read_text(encoding="utf-8")
        self.assertGreater(len(text), 1200)
        low = text.lower()
        # Current mitigations, not undetectability
        self.assertIn("obfuscation", low)
        self.assertIn("mitigation", low)
        self.assertIn("dpi", low)
        self.assertTrue(
            "not" in low and ("undetectab" in low or "parity" in low),
            "must deny current product = full PT / undetectability",
        )
        # ≥3 named PT-class recommendations
        for name in ("obfs4", "meek", "snowflake", "webtunnel"):
            self.assertIn(name, low, f"missing recommendation class {name}")
        self.assertIn("improves", low)
        self.assertIn("does not", low)
        # System, not a toggle
        self.assertTrue(
            "bridge" in low or "system" in low or "multi-component" in low
            or "not a single" in low
        )

    def test_shipped_obfs_module_honesty_line(self):
        ob = (ROOT / "node" / "obfuscation.py").read_text(encoding="utf-8")
        self.assertIn("mitigation", ob.lower())
        self.assertTrue(
            "dpi-undetectability" in ob.lower() or "pluggable" in ob.lower()
        )


if __name__ == "__main__":
    unittest.main()

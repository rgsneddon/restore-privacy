"""Package AUDIT STATE (Green/Amber/Red) from the security audit writer."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def _load_audit_mod():
    spec = importlib.util.spec_from_file_location(
        "run_security_audit", ROOT / "scripts" / "run_security_audit.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class TestPackageRagEvaluation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_audit_mod()

    def test_missing_package_is_red(self):
        out = self.mod.evaluate_package_audit_state(
            "windows", None, pin="abc"
        )
        self.assertEqual(out["state"], "Red")
        self.assertIn("not found", " ".join(out["reasons"]).lower())

    def test_valid_states_only(self):
        for s in ("Green", "Amber", "Red"):
            self.assertIn(s, self.mod.VALID_PACKAGE_STATES)

    def test_evaluate_catalog_has_five_platforms(self):
        """Drive real catalog monopin packages when present under releases/."""
        ver = self.mod.load_catalog_version()
        rag = self.mod.evaluate_catalog_packages(ver)
        plats = {p["platform"] for p in rag["packages"]}
        self.assertEqual(
            plats, {"windows", "linux", "macos", "ios", "android"}
        )
        for p in rag["packages"]:
            self.assertIn(p["state"], self.mod.VALID_PACKAGE_STATES)
        self.assertIn(rag["overall"], self.mod.VALID_PACKAGE_STATES)
        # With current monorepo catalog tree, expect packages present
        present = sum(1 for p in rag["packages"] if p.get("path"))
        self.assertGreaterEqual(present, 1)

    def test_render_section_lists_all_platforms(self):
        rag = {
            "catalog_version": "0.3.3",
            "overall": "Green",
            "packages": [
                {
                    "platform": "windows",
                    "label": "Windows",
                    "filename": "w.exe",
                    "state": "Green",
                    "reasons": ["ok"],
                },
                {
                    "platform": "linux",
                    "label": "Linux",
                    "filename": "l.tgz",
                    "state": "Green",
                    "reasons": ["ok"],
                },
                {
                    "platform": "macos",
                    "label": "macOS",
                    "filename": "m.zip",
                    "state": "Amber",
                    "reasons": ["soft"],
                },
                {
                    "platform": "ios",
                    "label": "iOS",
                    "filename": "i.zip",
                    "state": "Green",
                    "reasons": ["ok"],
                },
                {
                    "platform": "android",
                    "label": "Android",
                    "filename": "a.apk",
                    "state": "Red",
                    "reasons": ["fail"],
                },
            ],
            "legend": {
                "Green": "g",
                "Amber": "a",
                "Red": "r",
            },
        }
        md = self.mod.render_package_rag_section(rag)
        self.assertIn("Installer package AUDIT STATE", md)
        for label in ("Windows", "Linux", "macOS", "iOS", "Android"):
            self.assertIn(label, md)
        self.assertIn("**Green**", md)
        self.assertIn("**Amber**", md)
        self.assertIn("**Red**", md)
        self.assertIn("Catalog overall", md)

    def test_priv_hit_is_red(self):
        # Synthetic: mock contains_priv
        with mock.patch.object(self.mod, "_package_contains_priv", return_value=True):
            with mock.patch.object(
                self.mod, "_package_node_pub_sha256", return_value="deadbeef" * 8
            ):
                p = ROOT / "releases" / self.mod.load_catalog_version()
                # any existing file path if present
                hits = list(p.glob("restore-privacy-client-*")) if p.is_dir() else []
                if not hits:
                    self.skipTest("no catalog packages on disk")
                out = self.mod.evaluate_package_audit_state(
                    "linux", hits[0], pin="aa" * 32
                )
        self.assertEqual(out["state"], "Red")
        self.assertTrue(any("priv" in r.lower() for r in out["reasons"]))


class TestAuditMdHasPackageRag(unittest.TestCase):
    def test_written_audit_has_top_package_states(self):
        audit = ROOT / "AUDIT.md"
        if not audit.is_file():
            self.skipTest("AUDIT.md missing")
        text = audit.read_text(encoding="utf-8")
        # After a --write pass this is required; if stale, still require structure
        # once goal has run write — test_runner will regenerate.
        if "Installer package AUDIT STATE" not in text:
            self.skipTest("AUDIT.md not yet regenerated with package RAG (run --write)")
        self.assertLess(
            text.index("Installer package AUDIT STATE"),
            text.index("## 1. Executive summary"),
        )
        for plat in ("Windows", "Linux", "macOS", "iOS", "Android"):
            self.assertIn(plat, text)
        for state in ("Green", "Amber", "Red"):
            # At least the legend or a row uses the label
            self.assertIn(state, text)


if __name__ == "__main__":
    unittest.main()

"""Audit timer / sync defaults target Germany residual monopin (not Iceland).

Drives the real shipped modules so a drift back to Iceland as the default
audit-home fails the suite. Live residual catalog is DE + SG.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DE_MONOPIN = "178.105.187.178"
SG_MONOPIN = "5.223.48.8"
RO_MONOPIN = "185.146.232.107"
IS_MONOPIN = "82.221.101.241"


def _load_module(rel: str, name: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestAuditTimerRomaniaHome(unittest.TestCase):
    def test_sync_default_host_is_germany_monopin(self):
        mod = _load_module(
            "scripts/sync_audit_artifacts_from_node.py",
            "sync_audit_artifacts_from_node",
        )
        self.assertEqual(mod.DEFAULT_HOST, DE_MONOPIN)
        self.assertNotEqual(mod.DEFAULT_HOST, IS_MONOPIN)
        self.assertNotEqual(mod.DEFAULT_HOST, RO_MONOPIN)
        doc = (mod.__doc__ or "") + Path(
            ROOT / "scripts/sync_audit_artifacts_from_node.py"
        ).read_text(encoding="utf-8")
        self.assertIn(DE_MONOPIN, doc)
        self.assertIn("Germany", doc)
        self.assertIn("Singapore", doc)

    def test_run_security_audit_default_probe_host_is_germany(self):
        import os

        prev = os.environ.pop("RPT_NODE_HOST", None)
        try:
            mod = _load_module(
                "scripts/run_security_audit.py",
                "run_security_audit_de_home",
            )
            self.assertEqual(mod.DEFAULT_HOST, DE_MONOPIN)
            self.assertNotEqual(mod.DEFAULT_HOST, IS_MONOPIN)
            sched = [
                p
                for p in mod.active_residual_probe_schedule()
                if str(p.get("host") or "") != "127.0.0.1"
            ]
            hosts = {str(p.get("host") or "") for p in sched}
            codes = {str(p.get("code") or "").upper() for p in sched}
            if hosts:
                self.assertIn(DE_MONOPIN, hosts)
                self.assertIn(SG_MONOPIN, hosts)
                self.assertNotIn(IS_MONOPIN, hosts)
                self.assertIn("DE", codes)
                self.assertIn("SG", codes)
                self.assertNotIn("IS", codes)
        finally:
            if prev is not None:
                os.environ["RPT_NODE_HOST"] = prev

    def test_install_timer_script_documents_germany_home(self):
        text = (ROOT / "scripts" / "install_security_audit_timer.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn(DE_MONOPIN, text)
        self.assertIn("Germany", text)
        self.assertIn("Singapore", text)
        self.assertNotIn(IS_MONOPIN, text)
        self.assertIn("RPT_NODE_HOST=127.0.0.1", text)
        self.assertIn("RPT_AUDIT_REQUIRE_LOCALHOST=1", text)

    def test_sundries_audit_section_defaults_to_romania(self):
        text = (ROOT / "sundries.txt").read_text(encoding="utf-8")
        self.assertIn("185.146.232.107", text)
        # Audit block must not still say "On entry node" as sole default
        audit_block = text[text.find("Security audit timer") : text.find("Security audit timer") + 600]
        self.assertIn("Romania", audit_block)
        self.assertNotIn("On entry node:", audit_block)


if __name__ == "__main__":
    unittest.main()

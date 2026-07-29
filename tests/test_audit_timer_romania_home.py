"""Audit timer / sync defaults target Romania residual monopin (not Iceland).

Drives the real shipped modules so a drift back to Iceland as the default
audit-home fails the suite.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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
    def test_sync_default_host_is_romania_monopin(self):
        mod = _load_module(
            "scripts/sync_audit_artifacts_from_node.py",
            "sync_audit_artifacts_from_node",
        )
        self.assertEqual(mod.DEFAULT_HOST, RO_MONOPIN)
        self.assertNotEqual(mod.DEFAULT_HOST, IS_MONOPIN)
        # Docstring must name Romania as default audit home
        doc = (mod.__doc__ or "") + Path(
            ROOT / "scripts/sync_audit_artifacts_from_node.py"
        ).read_text(encoding="utf-8")
        self.assertIn(RO_MONOPIN, doc)
        self.assertIn("Romania", doc)

    def test_run_security_audit_default_probe_host_is_romania(self):
        # Import without clobbering env: clear RPT_NODE_HOST for this process
        import os

        prev = os.environ.pop("RPT_NODE_HOST", None)
        try:
            # Load fresh so module-level DEFAULT_HOST uses env default
            mod = _load_module(
                "scripts/run_security_audit.py",
                "run_security_audit_ro_home",
            )
            # Module stores env at import time; if empty env, default is RO
            self.assertEqual(
                os.environ.get("RPT_NODE_HOST", mod.DEFAULT_HOST)
                if False
                else (
                    mod.DEFAULT_HOST
                    if "RPT_NODE_HOST" not in os.environ
                    else os.environ["RPT_NODE_HOST"]
                ),
                RO_MONOPIN
                if "RPT_NODE_HOST" not in os.environ
                else os.environ["RPT_NODE_HOST"],
            )
            # Direct assertion on module default when env was unset at load
            self.assertEqual(mod.DEFAULT_HOST, RO_MONOPIN)
            self.assertNotEqual(mod.DEFAULT_HOST, IS_MONOPIN)
        finally:
            if prev is not None:
                os.environ["RPT_NODE_HOST"] = prev

    def test_install_timer_script_documents_romania_home(self):
        text = (ROOT / "scripts" / "install_security_audit_timer.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn(RO_MONOPIN, text)
        self.assertIn("Romania", text)
        # Oneshot still probes localhost only (no remote residual hardcode in unit env)
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

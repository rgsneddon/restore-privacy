"""Gates for security audit runner + public audit availability."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


class TestSecurityAuditArtifacts(unittest.TestCase):
    def test_runner_script_exists(self):
        p = ROOT / "scripts" / "run_security_audit.py"
        self.assertTrue(p.is_file())
        text = p.read_text(encoding="utf-8")
        self.assertIn("build_markdown", text)
        self.assertIn("probe_http_status", text)
        self.assertIn("82.221.101.241", text)
        self.assertIn("--write", text)

    def test_timer_install_script_four_hours(self):
        p = ROOT / "scripts" / "install_security_audit_timer.sh"
        self.assertTrue(p.is_file())
        text = p.read_text(encoding="utf-8")
        self.assertIn("4h", text)
        self.assertIn("rpt-security-audit", text)
        self.assertIn("run_security_audit.py", text)

    def test_audit_md_and_status_copy_present(self):
        audit = ROOT / "AUDIT.md"
        self.assertTrue(audit.is_file())
        text = audit.read_text(encoding="utf-8")
        self.assertGreater(len(text), 3000)
        self.assertIn("82.221.101.241", text)
        self.assertIn("residual_ip_capture", text)
        self.assertIn("Findings", text)
        # status page copy used for /AUDIT.md and /audit.md
        status_copy = ROOT / "status_page" / "AUDIT.md"
        self.assertTrue(status_copy.is_file())
        self.assertGreater(status_copy.stat().st_size, 2000)

    def test_status_page_serves_audit_paths(self):
        import sys

        sys.path.insert(0, str(ROOT / "status_page"))
        import app as status_app  # noqa: E402

        self.assertEqual(status_app.SECURITY_AUDIT_LOCAL_PATH, "/AUDIT.md")
        self.assertEqual(status_app.SECURITY_AUDIT_LOCAL_PATH_LOWER, "/audit.md")
        data = status_app.audit_document_bytes()
        self.assertIsNotNone(data)
        self.assertIn(b"Restore Privacy", data)
        self.assertIn(b"82.221.101.241", data)
        # Public GH host must be restore-privacy (not private RUST-IN-PRIVACY)
        self.assertIn("restore-privacy", status_app.GITHUB_BLOB_MAIN)
        self.assertNotIn("RUST-IN-PRIVACY", status_app.GITHUB_BLOB_MAIN)

    def test_build_markdown_uses_probe_results(self):
        import sys

        sys.path.insert(0, str(ROOT / "scripts"))
        # load as module
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "run_security_audit", ROOT / "scripts" / "run_security_audit.py"
        )
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)

        results = {
            "generated_at": "2026-07-21T00:00:00Z",
            "node_host": "82.221.101.241",
            "catalog_version": "0.2.9",
            "unit_suite": {
                "ran": True,
                "ok": True,
                "returncode": 0,
                "modules": ["tests.test_legal_links"],
            },
            "tcp_status": {"ok": True, "error": None},
            "http_status": {
                "ok": True,
                "status_code": 200,
                "body": {"title": "RESTORE PRIVACY"},
            },
            "udp": {"sent": True, "error": None},
            "no_priv": {"ok": True, "hits": []},
        }
        md = mod.build_markdown(results)
        self.assertIn("residual_ip_capture", md)
        self.assertIn("82.221.101.241", md)
        self.assertIn("0.2.9", md)
        self.assertIn("**PASS**", md)
        self.assertIn("title-only=True", md)
        self.assertNotIn("dpi-undetectable", md.lower())


if __name__ == "__main__":
    unittest.main()

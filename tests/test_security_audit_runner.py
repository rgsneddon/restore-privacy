"""Gates for security audit runner + public audit availability + section A privacy."""

from __future__ import annotations

import importlib.util
import json
import os
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


class TestSecurityAuditArtifacts(unittest.TestCase):
    def test_runner_script_exists(self):
        p = ROOT / "scripts" / "run_security_audit.py"
        self.assertTrue(p.is_file())
        text = p.read_text(encoding="utf-8")
        self.assertIn("build_markdown", text)
        self.assertIn("probe_http_status", text)
        self.assertIn("82.221.101.241", text)
        self.assertIn("--write", text)
        self.assertIn("redact_audit_text", text)
        self.assertIn("slim_results_for_public_json", text)

    def test_timer_install_script_four_hours(self):
        p = ROOT / "scripts" / "install_security_audit_timer.sh"
        self.assertTrue(p.is_file())
        text = p.read_text(encoding="utf-8")
        self.assertIn("4h", text)
        self.assertIn("rpt-security-audit", text)
        self.assertIn("run_security_audit.py", text)


class TestAuditTimerPrivacySectionA(unittest.TestCase):
    """Section A: audit run must not become a privacy leak."""

    def test_timer_unit_localhost_private_tmp_protect_jitter_no_exfil(self):
        text = (ROOT / "scripts" / "install_security_audit_timer.sh").read_text(
            encoding="utf-8"
        )
        # Local probes only
        self.assertIn("RPT_NODE_HOST=127.0.0.1", text)
        self.assertIn("RPT_AUDIT_REQUIRE_LOCALHOST=1", text)
        # No network exfil of audit artifacts (comments may say "do not git push")
        self.assertIn("no network exfil", text.lower().replace("-", " "))
        self.assertNotRegex(text, r"(?m)^\s*git\s+push\b")
        self.assertNotRegex(text, r"ExecStartPost=.*git\s+push")
        self.assertIn("do not", text.lower())
        self.assertIn("git push", text.lower())  # documented prohibition only
        # PrivateTmp + core + home/system protect + write scope
        self.assertIn("PrivateTmp=true", text)
        self.assertIn("LimitCORE=0", text)
        self.assertIn("ProtectHome=true", text)
        self.assertIn("ProtectSystem=strict", text)
        self.assertIn("ReadWritePaths=", text)
        self.assertIn("InaccessiblePaths=-${INSTALL_ROOT}/secrets", text)
        self.assertIn("LockPersonality=true", text)
        # Non-root identity when possible
        self.assertIn("rpt-audit", text)
        self.assertIn("useradd", text)
        # Outbound disabled on node
        self.assertIn("RPT_AUDIT_NO_OUTBOUND=1", text)
        self.assertIn("RPT_HOST_STATEMENTS_OFFLINE=1", text)
        # Schedule jitter
        self.assertIn("RandomizedDelaySec=", text)
        self.assertIn("JITTER_SEC", text)
        # Journal hygiene: wrapper one-line summary
        self.assertIn("rpt-security-audit: OK", text)
        self.assertIn("StandardOutput=journal", text)

    def test_redact_audit_text_strips_home_tokens_ssh(self):
        mod = _load_audit_mod()
        dirty = (
            "fail path /home/alice/.ssh/id_ed25519 "
            "token=gho_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456 "
            "Bearer supersecrettokenvaluehere "
            "deploy as bob@vps.example.com "
            "C:\\Users\\bob\\secrets\\key.pem "
            "-----BEGIN PRIVATE KEY-----\nMIIE\n-----END PRIVATE KEY-----"
        )
        clean = mod.redact_audit_text(dirty)
        self.assertNotIn("/home/alice", clean)
        self.assertIn("/home/[REDACTED_USER]", clean)
        self.assertNotIn("gho_ABCDEF", clean)
        self.assertIn("[REDACTED]", clean)
        self.assertNotIn("supersecrettokenvaluehere", clean)
        self.assertNotIn("bob@vps.example.com", clean)
        self.assertIn("[REDACTED_USER]@vps.example.com", clean)
        self.assertNotIn("BEGIN PRIVATE KEY", clean)
        self.assertIn("[REDACTED_PRIVATE_KEY]", clean)
        # Product public facts survive
        keep = mod.redact_audit_text("node 82.221.101.241 title RESTORE PRIVACY")
        self.assertIn("82.221.101.241", keep)
        self.assertIn("RESTORE PRIVACY", keep)

    def test_slim_json_drops_suite_tails(self):
        mod = _load_audit_mod()
        results = {
            "generated_at": "2026-07-21T00:00:00Z",
            "node_host": "127.0.0.1",
            "unit_suite": {
                "ran": True,
                "ok": False,
                "stdout_tail": "secret /home/x/.aws/credentials",
                "stderr_tail": "token=gho_LEAKEDVALUE1234567890",
            },
        }
        slim = mod.slim_results_for_public_json(results)
        us = slim["unit_suite"]
        self.assertNotIn("stdout_tail", us)
        self.assertNotIn("stderr_tail", us)
        self.assertTrue(slim["privacy"]["no_suite_tails"])
        self.assertTrue(slim["privacy"]["no_network_exfil"])

    def test_require_localhost_policy(self):
        mod = _load_audit_mod()
        self.assertTrue(mod.is_loopback_host("127.0.0.1"))
        self.assertTrue(mod.is_loopback_host("localhost"))
        self.assertFalse(mod.is_loopback_host("82.221.101.241"))
        with mock.patch.dict(os.environ, {"RPT_AUDIT_REQUIRE_LOCALHOST": "1"}, clear=False):
            with self.assertRaises(ValueError):
                mod.require_localhost_probe_host("82.221.101.241")
            self.assertEqual(mod.require_localhost_probe_host("127.0.0.1"), "127.0.0.1")
        with mock.patch.dict(os.environ, {"RPT_AUDIT_REQUIRE_LOCALHOST": "0"}, clear=False):
            self.assertEqual(
                mod.require_localhost_probe_host("82.221.101.241"), "82.221.101.241"
            )

    def test_write_outputs_redacts_and_drops_tails(self):
        """Drive real write_outputs entry point on a temp tree."""
        import shutil
        import tempfile

        mod = _load_audit_mod()
        td = Path(tempfile.mkdtemp(prefix="rpt-audit-write-"))
        try:
            # Point module ROOT at temp with minimal layout
            (td / "status_page" / "static").mkdir(parents=True)
            (td / "status_page" / "public").mkdir(parents=True)
            (td / "product").mkdir()
            old_root = mod.ROOT
            mod.ROOT = td
            results = {
                "generated_at": "2026-07-21T00:00:00Z",
                "node_host": "127.0.0.1",
                "catalog_version": "0.3.3",
                "unit_suite": {
                    "ran": True,
                    "ok": True,
                    "returncode": 0,
                    "modules": [],
                    "stdout_tail": "leak /home/eve/secret",
                    "stderr_tail": "token=gho_SHOULDNOTAPPEAR999",
                },
                "tcp_status": {"ok": True, "error": None, "host": "127.0.0.1", "port": 8080},
                "http_status": {
                    "ok": True,
                    "status_code": 200,
                    "body": {"title": "RESTORE PRIVACY"},
                    "error": "path /home/eve/x failed",
                },
                "udp": {"sent": True, "error": None},
                "no_priv": {"ok": True, "hits": []},
                "package_rag": {
                    "catalog_version": "0.3.3",
                    "overall": "Green",
                    "packages": [],
                    "legend": {"Green": "OK", "Amber": "P", "Red": "F"},
                },
            }
            out = td / "AUDIT.md"
            mod.write_outputs(results, out)
            md = out.read_text(encoding="utf-8")
            self.assertNotIn("/home/eve", md)
            self.assertNotIn("gho_SHOULDNOTAPPEAR", md)
            jpath = td / "status_page" / "static" / "security_audit_latest.json"
            self.assertTrue(jpath.is_file())
            data = json.loads(jpath.read_text(encoding="utf-8"))
            self.assertNotIn("stdout_tail", data.get("unit_suite") or {})
            self.assertNotIn("stderr_tail", data.get("unit_suite") or {})
            blob = jpath.read_text(encoding="utf-8")
            self.assertNotIn("gho_SHOULDNOTAPPEAR", blob)
            self.assertNotIn("/home/eve", blob)
            mod.ROOT = old_root
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_audit_md_and_status_copy_present(self):
        audit = ROOT / "AUDIT.md"
        self.assertTrue(audit.is_file())
        text = audit.read_text(encoding="utf-8")
        self.assertGreater(len(text), 3000)
        self.assertIn("82.221.101.241", text)
        self.assertIn("residual_ip_capture", text)
        self.assertIn("Findings", text)
        # VPN APP Shop copy used for /AUDIT.md and /audit.md
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
            "package_rag": {
                "catalog_version": "0.2.9",
                "overall": "Amber",
                "packages": [
                    {
                        "platform": "windows",
                        "label": "Windows",
                        "filename": "restore-privacy-client-0.2.9-windows-x64-setup.exe",
                        "state": "Green",
                        "reasons": ["pin ok"],
                    },
                    {
                        "platform": "linux",
                        "label": "Linux",
                        "filename": "restore-privacy-client-0.2.9-linux-x64.tar.gz",
                        "state": "Amber",
                        "reasons": ["soft"],
                    },
                    {
                        "platform": "macos",
                        "label": "macOS",
                        "filename": "x-macos.zip",
                        "state": "Red",
                        "reasons": ["missing"],
                    },
                    {
                        "platform": "ios",
                        "label": "iOS",
                        "filename": "x-ios.zip",
                        "state": "Green",
                        "reasons": [],
                    },
                    {
                        "platform": "android",
                        "label": "Android",
                        "filename": "x-android.apk",
                        "state": "Green",
                        "reasons": [],
                    },
                ],
                "legend": {
                    "Green": "OK",
                    "Amber": "Partial",
                    "Red": "Fail",
                },
            },
        }
        md = mod.build_markdown(results)
        self.assertIn("residual_ip_capture", md)
        self.assertIn("82.221.101.241", md)
        self.assertIn("0.2.9", md)
        self.assertIn("**PASS**", md)
        self.assertIn("title-only=True", md)
        self.assertNotIn("dpi-undetectable", md.lower())
        # Top package RAG section — solid colour cells (not bare **Green** words)
        self.assertIn("Installer package AUDIT STATE", md)
        self.assertIn("🟩", md)
        self.assertIn("🟧", md)
        self.assertIn("🟥", md)
        self.assertNotRegex(md, r"\| \*\*Green\*\* \|")
        self.assertIn("Windows", md)
        self.assertIn("Android", md)
        # Section appears before executive summary numbering body
        self.assertLess(
            md.index("Installer package AUDIT STATE"),
            md.index("## 1. Executive summary"),
        )


if __name__ == "__main__":
    unittest.main()

"""Local connection log: append/read/export with support diagnostics; no upload."""

from __future__ import annotations

import ast
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.connection_log import (  # noqa: E402
    LEGACY_LOG_FILENAME,
    LOG_FILENAME,
    ConnectionLogEvent,
    append_event,
    build_support_diagnostics,
    clear_events,
    default_log_path,
    export_to_file,
    format_export,
    is_hidden_log_filename,
    log_module_has_no_network_upload,
    migrate_legacy_log_if_needed,
    product_client_version,
    read_events,
    support_log_path_patterns,
)


class TestConnectionLogLocalStore(unittest.TestCase):
    def test_append_read_export_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "connection_log.jsonl"
            e1 = append_event("connect", "Connect started", path=path, ts=1_700_000_000.0)
            e2 = append_event(
                "session", "Residual capture active", path=path, ts=1_700_000_001.0
            )
            self.assertIsInstance(e1, ConnectionLogEvent)
            self.assertEqual(e1.kind, "connect")

            events = read_events(path=path)
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0].message, "Connect started")
            self.assertEqual(events[1].kind, "session")

            text = format_export(path=path)
            self.assertIn("Connect started", text)
            self.assertIn("Residual capture active", text)
            self.assertIn("local only", text.lower())
            self.assertIn("not uploaded", text.lower())

            dest = Path(td) / "export.txt"
            out = export_to_file(dest, source=path)
            self.assertTrue(out.is_file())
            body = out.read_text(encoding="utf-8")
            self.assertGreater(len(body), 40)
            self.assertIn("connect:", body.lower())

    def test_limit_keeps_newest(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "log.jsonl"
            for i in range(5):
                append_event("info", f"msg-{i}", path=path, ts=float(i))
            newest = read_events(path=path, limit=2)
            self.assertEqual(len(newest), 2)
            self.assertEqual(newest[0].message, "msg-3")
            self.assertEqual(newest[1].message, "msg-4")

    def test_trim_max_events(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "log.jsonl"
            for i in range(10):
                append_event("info", f"e{i}", path=path, max_events=3, ts=float(i))
            events = read_events(path=path)
            self.assertEqual(len(events), 3)
            self.assertEqual(events[0].message, "e7")

    def test_clear_events(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "log.jsonl"
            append_event("disconnect", "bye", path=path)
            self.assertTrue(path.is_file())
            clear_events(path=path)
            self.assertEqual(read_events(path=path), [])

    def test_missing_file_empty(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "missing.jsonl"
            self.assertEqual(read_events(path=path), [])
            self.assertIn("local only", format_export(path=path).lower())

    def test_default_path_is_hidden_local_product_dir(self):
        p = default_log_path()
        self.assertEqual(p.name, LOG_FILENAME)
        self.assertTrue(p.name.startswith("."), "default log must be a hidden filename")
        self.assertTrue(is_hidden_log_filename(p.name))
        self.assertNotEqual(LOG_FILENAME, LEGACY_LOG_FILENAME)
        s = str(p).replace("\\", "/").lower()
        self.assertTrue(
            "restoreprivacy" in s or "restore-privacy" in s,
            f"expected product-local path, got {p}",
        )

    def test_migrate_legacy_plain_name_to_hidden(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            legacy = d / LEGACY_LOG_FILENAME
            legacy.write_text(
                '{"ts":1,"kind":"info","message":"legacy"}\n', encoding="utf-8"
            )
            out = migrate_legacy_log_if_needed(directory=d)
            self.assertIsNotNone(out)
            hidden = d / LOG_FILENAME
            self.assertTrue(hidden.is_file())
            self.assertFalse(legacy.is_file())
            self.assertIn("legacy", hidden.read_text(encoding="utf-8"))


class TestConnectionLogNoUpload(unittest.TestCase):
    def test_helper_reports_no_network(self):
        self.assertTrue(log_module_has_no_network_upload())

    def test_ast_no_network_imports(self):
        src_path = ROOT / "client" / "connection_log.py"
        tree = ast.parse(src_path.read_text(encoding="utf-8"))
        banned = {"urllib", "requests", "httpx", "socket", "http", "aiohttp", "ftplib"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(alias.name.split(".", 1)[0], banned)
            elif isinstance(node, ast.ImportFrom) and node.module:
                self.assertNotIn(node.module.split(".", 1)[0], banned)

    def test_no_upload_calls_in_source(self):
        src = (ROOT / "client" / "connection_log.py").read_text(encoding="utf-8")
        for bad in (
            "urllib.request",
            "requests.post",
            "requests.put",
            "httpx.",
            "urlopen",
            "import webbrowser",
            "webbrowser.open",
        ):
            self.assertNotIn(bad, src)


class TestSupportDiagnosticsInExport(unittest.TestCase):
    """Shipped append + format_export include support diagnostic fields."""

    def test_build_support_diagnostics_has_version_platform(self):
        snap = build_support_diagnostics()
        self.assertEqual(snap.get("product"), "Restore Privacy")
        ver = product_client_version()
        self.assertEqual(snap.get("client_version"), ver)
        self.assertNotEqual(ver, "")
        self.assertIn("platform", snap)
        self.assertIn("os_name", snap)
        # No network keys
        self.assertNotIn("url", snap)

    def test_append_merges_diagnostics_and_caller_detail(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "connection_log.jsonl"
            ev = append_event(
                "error",
                "Connect failed: timeout",
                path=path,
                ts=1_700_000_100.0,
                detail={
                    "outcome": "fail",
                    "error": "timeout waiting for HELLO",
                    "residual_host": "82.221.101.241",
                    "residual_port": 44044,
                },
            )
            self.assertEqual(ev.detail.get("outcome"), "fail")
            self.assertEqual(ev.detail.get("error"), "timeout waiting for HELLO")
            self.assertIn("client_version", ev.detail)
            self.assertIn("platform", ev.detail)
            # Round-trip through JSONL
            events = read_events(path=path)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].detail.get("residual_host"), "82.221.101.241")
            self.assertEqual(events[0].detail.get("residual_port"), 44044)

    def test_export_body_contains_diagnostics_and_support_handoff(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "connection_log.jsonl"
            append_event(
                "connect",
                "Connect started",
                path=path,
                ts=1_700_000_000.0,
                detail={"outcome": "start"},
            )
            append_event(
                "error",
                "Connect failed: no reply",
                path=path,
                ts=1_700_000_001.0,
                detail={"outcome": "fail", "error": "no reply", "error_code": "timeout"},
            )
            dest = Path(td) / "support-export.txt"
            export_to_file(dest, source=path)
            body = dest.read_text(encoding="utf-8")
            self.assertIn("client_version=", body)
            self.assertIn("platform=", body)
            self.assertIn(product_client_version(), body)
            self.assertIn("outcome=fail", body)
            self.assertIn("error=no reply", body)
            self.assertIn("error_code=timeout", body)
            low = body.lower()
            self.assertIn("not uploaded", low)
            self.assertIn("support", low)
            self.assertIn("email", low)
            self.assertIn("local only", low)

    def test_windows_settings_export_uses_format_export(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("export_to_file", src)
        self.assertIn("format_export", src)
        self.assertIn("EXPORT_LOG_BUTTON", src)
        self.assertIn("SUPPORT_LOG_FIND_HINT", src)

    def test_export_documents_hidden_path_patterns(self):
        paths = support_log_path_patterns()
        self.assertIn(".rpt_support_log.jsonl", paths["windows"])
        self.assertIn(".rpt_support_log.jsonl", paths["linux"])
        body = format_export([])
        self.assertIn(paths["windows"], body)
        self.assertIn(paths["linux"], body)
        self.assertIn("hidden", body.lower())

    def test_docs_name_hidden_support_log_paths(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        privacy = (ROOT / "PRIVACY_POLICY.md").read_text(encoding="utf-8")
        for text in (readme, privacy):
            self.assertIn(".rpt_support_log.jsonl", text)
            self.assertIn("%LOCALAPPDATA%", text)
            self.assertIn(".local/share/restore-privacy", text)
            self.assertIn("email", text.lower())
        self.assertIn("Support logs", readme)
        copy = (ROOT / "client" / "transparency_copy.py").read_text(encoding="utf-8")
        self.assertIn("SUPPORT_LOG_PATH_WINDOWS", copy)
        self.assertIn("SUPPORT_LOG_FIND_HINT", copy)


if __name__ == "__main__":
    unittest.main()


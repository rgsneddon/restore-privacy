"""Local connection log: append/read/export; no network upload path."""

from __future__ import annotations

import ast
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.connection_log import (  # noqa: E402
    ConnectionLogEvent,
    append_event,
    clear_events,
    default_log_path,
    export_to_file,
    format_export,
    log_module_has_no_network_upload,
    read_events,
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

    def test_default_path_is_local_product_dir(self):
        p = default_log_path()
        self.assertEqual(p.name, "connection_log.jsonl")
        s = str(p).replace("\\", "/").lower()
        self.assertTrue(
            "restoreprivacy" in s or "restore-privacy" in s,
            f"expected product-local path, got {p}",
        )


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


if __name__ == "__main__":
    unittest.main()

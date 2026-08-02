"""Multi-node residual live probe schedule for security audit.

Drives shipped ``scripts/run_security_audit`` helpers: schedule membership,
markdown multi-peer table, and write-time stamp advance.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import tempfile
import time
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


class TestMultiNodeProbeSchedule(unittest.TestCase):
    def test_active_schedule_includes_all_catalog_peers_when_not_local(self) -> None:
        mod = _load_audit_mod()
        with mock.patch.dict(os.environ, {"RPT_AUDIT_REQUIRE_LOCALHOST": "0"}, clear=False):
            sched = mod.active_residual_probe_schedule()
        self.assertGreaterEqual(len(sched), 2, f"expected multi-node schedule, got {sched}")
        hosts = {str(p.get("host") or "") for p in sched}
        codes = {str(p.get("code") or "").upper() for p in sched}
        # Product residual catalog monopin peers (IS + DE)
        self.assertIn("IS", codes)
        self.assertIn("DE", codes)
        self.assertTrue(any(h.count(".") == 3 for h in hosts), hosts)
        # Not only a single DEFAULT_HOST
        self.assertGreater(len(hosts), 1)

    def test_localhost_timer_schedule_is_single_loopback(self) -> None:
        mod = _load_audit_mod()
        with mock.patch.dict(os.environ, {"RPT_AUDIT_REQUIRE_LOCALHOST": "1"}, clear=False):
            sched = mod.active_residual_probe_schedule()
        self.assertEqual(len(sched), 1)
        self.assertEqual(sched[0]["host"], "127.0.0.1")
        self.assertEqual(sched[0]["code"], "LOCAL")

    def test_render_live_table_multi_row_from_collector_fields(self) -> None:
        mod = _load_audit_mod()
        results = {
            "node_host": "178.105.187.178",
            "live_node_probes": [
                {
                    "code": "IS",
                    "label": "Iceland (IS)",
                    "tcp_status": {"ok": True, "error": None},
                    "http_status": {
                        "ok": True,
                        "status_code": 200,
                        "body": {"title": "RESTORE PRIVACY"},
                    },
                    "udp": {"sent": True, "error": None},
                },
                {
                    "code": "DE",
                    "label": "Germany (DE)",
                    "tcp_status": {"ok": False, "error": "timeout"},
                    "http_status": {"ok": False, "status_code": None, "body": None},
                    "udp": {"sent": False, "error": "refused"},
                },
            ],
        }
        table = mod.render_live_node_probe_table(results)
        self.assertIn("Iceland (IS)", table)
        self.assertIn("Germany (DE)", table)
        self.assertIn("ok=True", table)
        self.assertIn("ok=False", table)
        # Must not be a single-probe-only layout
        self.assertGreaterEqual(table.count("|"), 8)

    def test_build_markdown_includes_multi_node_section(self) -> None:
        mod = _load_audit_mod()
        results = {
            "generated_at": "2026-08-02T12:00:00Z",
            "node_host": "178.105.187.178",
            "catalog_version": "1.0.7",
            "unit_suite": {"ran": False, "ok": True, "modules": []},
            "tcp_status": {"ok": True, "error": None},
            "http_status": {
                "ok": True,
                "status_code": 200,
                "body": {"title": "RESTORE PRIVACY"},
            },
            "udp": {"sent": True, "error": None},
            "no_priv": {"ok": True, "hits": []},
            "package_rag": {
                "catalog_version": "1.0.7",
                "overall": "Green",
                "packages": [],
                "legend": {"Green": "OK", "Amber": "A", "Red": "R"},
            },
            "section_b": {"ok": True},
            "multihop_structure": {"ok": True},
            "live_node_probes": [
                {
                    "code": "IS",
                    "label": "Iceland (IS)",
                    "tcp_status": {"ok": True, "error": None},
                    "http_status": {"ok": True, "status_code": 200, "body": {}},
                    "udp": {"sent": True, "error": None},
                },
                {
                    "code": "DE",
                    "label": "Germany (DE)",
                    "tcp_status": {"ok": True, "error": None},
                    "http_status": {"ok": True, "status_code": 200, "body": {}},
                    "udp": {"sent": True, "error": None},
                },
            ],
        }
        md = mod.build_markdown(results)
        self.assertIn("Live residual node probe results", md)
        self.assertIn("Iceland (IS)", md)
        self.assertIn("Germany (DE)", md)
        self.assertIn("all active residual monopin peers", md.lower())

    def test_slim_json_drops_raw_hosts_from_live_probes(self) -> None:
        mod = _load_audit_mod()
        slim = mod.slim_results_for_public_json(
            {
                "generated_at": "2026-08-02T12:00:00Z",
                "node_host": "178.105.187.178",
                "unit_suite": {"ran": True, "ok": True, "stdout_tail": "x"},
                "live_node_probes": [
                    {
                        "code": "DE",
                        "label": "Germany (DE)",
                        "host": "178.105.187.178",
                        "tcp_status": {"ok": True, "host": "178.105.187.178", "port": 8080},
                        "http_status": {"ok": True, "status_code": 200, "body": {"title": "T"}},
                        "udp": {"sent": True, "port": 44044},
                        "ok": True,
                    }
                ],
            }
        )
        self.assertNotIn("stdout_tail", slim["unit_suite"])
        live = slim["live_node_probes"]
        self.assertEqual(len(live), 1)
        self.assertNotIn("host", live[0])
        self.assertEqual(live[0]["label"], "Germany (DE)")
        self.assertTrue(slim["privacy"].get("multi_node_probes"))


class TestWriteTimeStampAdvance(unittest.TestCase):
    def test_write_outputs_advances_generated_at_twice(self) -> None:
        """Two sequential write_outputs stamps advance (sticky last-run fix)."""
        mod = _load_audit_mod()
        td = Path(tempfile.mkdtemp(prefix="rpt-audit-stamp-"))
        try:
            (td / "status_page" / "static").mkdir(parents=True)
            (td / "status_page" / "public").mkdir(parents=True)
            old = mod.ROOT
            mod.ROOT = td
            base = {
                "generated_at": "2020-01-01T00:00:00Z",
                "node_host": "127.0.0.1",
                "catalog_version": "1.0.7",
                "unit_suite": {"ran": False, "ok": True, "modules": []},
                "tcp_status": {"ok": True, "error": None},
                "http_status": {
                    "ok": True,
                    "status_code": 200,
                    "body": {"title": "RESTORE PRIVACY"},
                },
                "udp": {"sent": True, "error": None},
                "no_priv": {"ok": True, "hits": []},
                "package_rag": {
                    "catalog_version": "1.0.7",
                    "overall": "Green",
                    "packages": [],
                    "legend": {"Green": "OK", "Amber": "A", "Red": "R"},
                },
                "section_b": {"ok": True},
                "multihop_structure": {"ok": True},
                "live_node_probes": [
                    {
                        "label": "localhost (node timer)",
                        "code": "LOCAL",
                        "tcp_status": {"ok": True, "error": None},
                        "http_status": {"ok": True, "status_code": 200, "body": {}},
                        "udp": {"sent": True, "error": None},
                    }
                ],
            }
            out = td / "AUDIT.md"
            mod.write_outputs(dict(base), out)
            jpath = td / "status_page" / "static" / "security_audit_latest.json"
            a1 = json.loads(jpath.read_text(encoding="utf-8"))["generated_at"]
            time.sleep(1.1)
            mod.write_outputs(dict(base), out)
            a2 = json.loads(jpath.read_text(encoding="utf-8"))["generated_at"]
            self.assertNotEqual(a1, a2, "generated_at must advance on each write")
            self.assertGreater(a2, a1)
            md = out.read_text(encoding="utf-8")
            self.assertIn(a2, md)
            sp = (td / "status_page" / "AUDIT.md").read_text(encoding="utf-8")
            self.assertIn(a2, sp)
            # UK display helper
            sys_path_status = ROOT / "status_page"
            import sys

            if str(sys_path_status) not in sys.path:
                sys.path.insert(0, str(sys_path_status))
            from audit_countdown import format_last_audit_run_display

            disp = format_last_audit_run_display(a2)
            self.assertTrue(
                disp.endswith(" GMT") or disp.endswith(" BST"),
                f"UK zone expected, got {disp!r}",
            )
            mod.ROOT = old
        finally:
            shutil.rmtree(td, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

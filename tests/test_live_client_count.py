"""Internal session registry: size up/down for routing (not a public count)."""

from __future__ import annotations

import json
import sys
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from node.sessions import (  # noqa: E402
    DEFAULT_SESSION_IDLE_SEC,
    Session,
    SessionRegistry,
)
from node.ui import make_handler  # noqa: E402


def _sess(sid: bytes, ip: str, last_seen: float, addr=("1.1.1.1", 9)) -> Session:
    return Session(
        session_id=sid,
        crypto=object(),
        client_addr=addr,
        vpn_ip=ip,
        last_seen=last_seen,
    )


def time_module_time() -> float:
    import time

    return time.time()


class TestInternalSessionCount(unittest.TestCase):
    def test_count_up_on_add_down_on_remove(self):
        reg = SessionRegistry(idle_sec=120)
        now = time_module_time()
        self.assertEqual(reg.count(), 0)
        self.assertEqual(reg.status_payload(), {"title": "RESTORE PRIVACY"})

        reg.add(_sess(b"\x01" * 8, "10.88.0.2", last_seen=now, addr=("1.1.1.1", 1001)))
        self.assertEqual(reg.count(), 1)
        self.assertNotIn("clients_connected", reg.status_payload())

        reg.add(_sess(b"\x02" * 8, "10.88.0.3", last_seen=now, addr=("1.1.1.2", 1002)))
        self.assertEqual(reg.count(), 2)

        self.assertTrue(reg.remove(b"\x01" * 8))
        self.assertEqual(reg.count(), 1)

        self.assertTrue(reg.remove(b"\x02" * 8))
        self.assertEqual(reg.count(), 0)

    def test_expire_stale_lowers_count_not_cumulative(self):
        reg = SessionRegistry(idle_sec=60)
        now = time_module_time()
        reg.add(
            _sess(b"\x0a" * 8, "10.88.0.10", last_seen=now, addr=("9.9.9.9", 1111))
        )
        reg.add(
            _sess(b"\x0b" * 8, "10.88.0.11", last_seen=now, addr=("8.8.8.8", 2222))
        )
        peak = reg.count()
        self.assertEqual(peak, 2)

        reg.add(
            _sess(
                b"\x0a" * 8, "10.88.0.10", last_seen=now - 200, addr=("9.9.9.9", 1111)
            )
        )
        live = reg.get(b"\x0b" * 8)
        self.assertIsNotNone(live)
        live.last_seen = now  # type: ignore[union-attr]

        removed = reg.expire_stale(now=now, idle_sec=60)
        self.assertEqual(removed, 1)
        self.assertEqual(reg.count(), 1)
        self.assertLess(reg.count(), peak)
        payload = reg.status_payload()
        self.assertEqual(payload, {"title": "RESTORE PRIVACY"})
        self.assertNotIn("clients_connected", payload)

    def test_status_payload_prunes_without_publishing_count(self):
        reg = SessionRegistry(idle_sec=30)
        old = time_module_time() - 500
        reg.add(_sess(b"\xcc" * 8, "10.88.0.20", last_seen=old))
        payload = reg.status_payload()
        self.assertEqual(payload, {"title": "RESTORE PRIVACY"})
        self.assertEqual(reg.count(), 0)

    def test_two_concurrent_live_sessions_internal_count_two(self):
        reg = SessionRegistry()
        t = time_module_time()
        reg.add(_sess(b"\x01" * 8, "10.88.0.2", last_seen=t, addr=("1.0.0.1", 1)))
        reg.add(_sess(b"\x02" * 8, "10.88.0.3", last_seen=t, addr=("1.0.0.2", 2)))
        self.assertEqual(reg.count(), 2)
        self.assertNotIn("clients_connected", reg.status_payload())

    def test_default_idle_constant_reasonable(self):
        self.assertGreaterEqual(DEFAULT_SESSION_IDLE_SEC, 30)
        self.assertLessEqual(DEFAULT_SESSION_IDLE_SEC, 120)

    def test_reconnect_same_addr_replaces_orphan_session(self):
        reg = SessionRegistry(idle_sec=600)
        now = time_module_time()
        addr = ("203.0.113.9", 54321)
        reg.add(_sess(b"\xaa" * 8, "10.88.0.2", last_seen=now, addr=addr))
        self.assertEqual(reg.count(), 1)
        reg.add(_sess(b"\xbb" * 8, "10.88.0.3", last_seen=now, addr=addr))
        self.assertEqual(reg.count(), 1)
        self.assertIsNone(reg.get(b"\xaa" * 8))
        self.assertIsNotNone(reg.get(b"\xbb" * 8))


class TestServeLoopWiresExpiry(unittest.TestCase):
    def test_server_source_calls_expire_stale(self):
        src = (ROOT / "node" / "server.py").read_text(encoding="utf-8")
        self.assertIn("expire_stale", src)
        self.assertIn("last_prune", src)
        self.assertIn("registry.touch", src)

    def test_sessions_module_has_expire_and_remove_no_public_count(self):
        src = (ROOT / "node" / "sessions.py").read_text(encoding="utf-8")
        self.assertIn("def expire_stale", src)
        self.assertIn("def remove", src)
        self.assertIn("DEFAULT_SESSION_IDLE_SEC", src)
        # status_payload must not publish clients_connected
        self.assertIn("def status_payload", src)
        self.assertNotIn('"clients_connected"', src)


class TestStatusApiTitleOnly(unittest.TestCase):
    def test_ui_handler_exposes_title_only(self):
        reg = SessionRegistry(idle_sec=60)
        t = time_module_time()
        reg.add(_sess(b"\x01" * 8, "10.88.0.2", last_seen=t, addr=("5.5.5.5", 50)))
        reg.add(
            _sess(b"\x02" * 8, "10.88.0.3", last_seen=t - 9999, addr=("6.6.6.6", 60))
        )
        Handler = make_handler(reg.status_payload)
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/status", timeout=5
            ) as resp:
                data = json.loads(resp.read().decode())
            self.assertEqual(set(data.keys()), {"title"})
            self.assertNotIn("clients_connected", data)
            self.assertNotIn("ip", data)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_status_page_normalize_strips_count(self):
        sys.path.insert(0, str(ROOT / "status_page"))
        import app as status_app  # noqa: E402

        out = status_app.normalize_status(
            {
                "clients_connected": 2,
                "total_clients": 999,
                "lifetime": 999,
                "clients_total": 999,
            }
        )
        self.assertEqual(out, {"title": "RESTORE PRIVACY VPN"})
        self.assertNotIn("clients_connected", out)


if __name__ == "__main__":
    unittest.main()

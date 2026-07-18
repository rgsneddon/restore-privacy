"""Live clients_connected: up on connect, down on remove/idle expiry (not cumulative)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from node.sessions import (  # noqa: E402
    DEFAULT_SESSION_IDLE_SEC,
    Session,
    SessionRegistry,
)
from node.ui import make_handler  # noqa: E402
from http.server import ThreadingHTTPServer  # noqa: E402
import threading  # noqa: E402
import json  # noqa: E402
import urllib.request  # noqa: E402


def _sess(sid: bytes, ip: str, last_seen: float, addr=("1.1.1.1", 9)) -> Session:
    return Session(
        session_id=sid,
        crypto=object(),
        client_addr=addr,
        vpn_ip=ip,
        last_seen=last_seen,
    )


class TestLiveClientCount(unittest.TestCase):
    def test_count_up_on_add_down_on_remove(self):
        reg = SessionRegistry(idle_sec=120)
        now = time_module_time()
        self.assertEqual(reg.count(), 0)
        self.assertEqual(reg.status_payload()["clients_connected"], 0)

        reg.add(_sess(b"\x01" * 8, "10.88.0.2", last_seen=now, addr=("1.1.1.1", 1001)))
        self.assertEqual(reg.count(), 1)
        self.assertEqual(reg.status_payload()["clients_connected"], 1)

        reg.add(_sess(b"\x02" * 8, "10.88.0.3", last_seen=now, addr=("1.1.1.2", 1002)))
        self.assertEqual(reg.count(), 2)
        self.assertEqual(reg.status_payload()["clients_connected"], 2)

        self.assertTrue(reg.remove(b"\x01" * 8))
        self.assertEqual(reg.count(), 1)
        self.assertEqual(reg.status_payload()["clients_connected"], 1)

        self.assertTrue(reg.remove(b"\x02" * 8))
        self.assertEqual(reg.count(), 0)
        self.assertEqual(reg.status_payload()["clients_connected"], 0)

    def test_expire_stale_lowers_count_not_cumulative(self):
        reg = SessionRegistry(idle_sec=60)
        now = time_module_time()
        # Two "connects" (distinct client endpoints)
        reg.add(
            _sess(b"\x0a" * 8, "10.88.0.10", last_seen=now, addr=("9.9.9.9", 1111))
        )
        reg.add(
            _sess(b"\x0b" * 8, "10.88.0.11", last_seen=now, addr=("8.8.8.8", 2222))
        )
        peak = reg.count()
        self.assertEqual(peak, 2)

        # One goes idle past timeout (simulates disconnect/silence)
        reg.add(
            _sess(
                b"\x0a" * 8, "10.88.0.10", last_seen=now - 200, addr=("9.9.9.9", 1111)
            )
        )
        # Other stays live
        live = reg.get(b"\x0b" * 8)
        self.assertIsNotNone(live)
        live.last_seen = now  # type: ignore[union-attr]

        removed = reg.expire_stale(now=now, idle_sec=60)
        self.assertEqual(removed, 1)
        self.assertEqual(reg.count(), 1)
        self.assertLess(reg.count(), peak)
        # Refresh remaining session before status_payload (uses real clock prune)
        live2 = reg.get(b"\x0b" * 8)
        self.assertIsNotNone(live2)
        live2.last_seen = time_module_time()  # type: ignore[union-attr]
        payload = reg.status_payload()
        self.assertEqual(payload["clients_connected"], 1)
        self.assertEqual(reg.count(), 1)
        self.assertNotIn("total", payload)
        self.assertNotIn("lifetime", payload)

    def test_status_payload_prunes_before_count(self):
        reg = SessionRegistry(idle_sec=30)
        old = time_module_time() - 500
        reg.add(_sess(b"\xcc" * 8, "10.88.0.20", last_seen=old))
        # Without prune this would be 1 forever; payload must drop to 0
        payload = reg.status_payload()
        self.assertEqual(payload["clients_connected"], 0)
        self.assertEqual(reg.count(), 0)

    def test_two_concurrent_live_sessions_count_two(self):
        reg = SessionRegistry()
        t = time_module_time()
        reg.add(_sess(b"\x01" * 8, "10.88.0.2", last_seen=t, addr=("1.0.0.1", 1)))
        reg.add(_sess(b"\x02" * 8, "10.88.0.3", last_seen=t, addr=("1.0.0.2", 2)))
        self.assertEqual(reg.status_payload()["clients_connected"], 2)

    def test_default_idle_constant_reasonable(self):
        self.assertGreaterEqual(DEFAULT_SESSION_IDLE_SEC, 30)
        self.assertLessEqual(DEFAULT_SESSION_IDLE_SEC, 120)

    def test_reconnect_same_addr_replaces_orphan_session(self):
        """Same client UDP endpoint reconnecting must not accumulate count."""
        reg = SessionRegistry(idle_sec=600)
        now = time_module_time()
        addr = ("203.0.113.9", 54321)
        reg.add(_sess(b"\xaa" * 8, "10.88.0.2", last_seen=now, addr=addr))
        self.assertEqual(reg.count(), 1)
        # New session_id, same client_addr (reconnect)
        reg.add(_sess(b"\xbb" * 8, "10.88.0.3", last_seen=now, addr=addr))
        self.assertEqual(reg.count(), 1)
        self.assertIsNone(reg.get(b"\xaa" * 8))
        self.assertIsNotNone(reg.get(b"\xbb" * 8))
        self.assertEqual(reg.status_payload()["clients_connected"], 1)


class TestServeLoopWiresExpiry(unittest.TestCase):
    def test_server_source_calls_expire_stale(self):
        src = (ROOT / "node" / "server.py").read_text(encoding="utf-8")
        self.assertIn("expire_stale", src)
        self.assertIn("last_prune", src)
        self.assertIn("registry.touch", src)

    def test_sessions_module_has_expire_and_remove(self):
        src = (ROOT / "node" / "sessions.py").read_text(encoding="utf-8")
        self.assertIn("def expire_stale", src)
        self.assertIn("def remove", src)
        self.assertIn("clients_connected", src)
        self.assertIn("DEFAULT_SESSION_IDLE_SEC", src)


class TestStatusApiCurrentOnly(unittest.TestCase):
    def test_ui_handler_exposes_only_current_count(self):
        reg = SessionRegistry(idle_sec=60)
        t = time_module_time()
        reg.add(_sess(b"\x01" * 8, "10.88.0.2", last_seen=t, addr=("5.5.5.5", 50)))
        reg.add(
            _sess(b"\x02" * 8, "10.88.0.3", last_seen=t - 9999, addr=("6.6.6.6", 60))
        )
        # Payload callback uses real registry.status_payload
        Handler = make_handler(reg.status_payload)
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/status", timeout=5
            ) as resp:
                data = json.loads(resp.read().decode())
            self.assertEqual(set(data.keys()), {"title", "clients_connected"})
            # Stale session pruned → only 1 live
            self.assertEqual(data["clients_connected"], 1)
            self.assertNotIn("ip", data)
            self.assertNotIn("clients", data)
            self.assertNotIn("total", data)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_status_page_normalize_rejects_lifetime_as_metric(self):
        sys.path.insert(0, str(ROOT / "status_page"))
        import app as status_app  # noqa: E402

        # Upstream must not be allowed to feed a cumulative total as the display field
        out = status_app.normalize_status(
            {
                "clients_connected": 2,
                "total_clients": 999,
                "lifetime": 999,
                "clients_total": 999,
            }
        )
        self.assertEqual(out["clients_connected"], 2)
        self.assertNotIn("total_clients", out)
        self.assertNotIn("lifetime", out)


def time_module_time() -> float:
    import time

    return time.time()


if __name__ == "__main__":
    unittest.main()

"""Windows residual auto-reconnect after idle drop (Settings opt-in)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.windows.idle_auto_reconnect import (  # noqa: E402
    MAX_IDLE_RECONNECT_ATTEMPTS,
    idle_reconnect_backoff_s,
    may_auto_reconnect_after_idle_drop,
)
from client.windows.settings_store import (  # noqa: E402
    AUTO_CONNECT_IF_IDLE_BLURB,
    AUTO_CONNECT_IF_IDLE_LABEL,
    KEY_AUTO_CONNECT_IF_IDLE,
    default_settings,
    load_settings,
    save_settings,
)


class TestIdleAutoReconnectPref(unittest.TestCase):
    def test_default_off(self):
        s = default_settings()
        self.assertFalse(s.auto_connect_if_idle)
        self.assertEqual(AUTO_CONNECT_IF_IDLE_LABEL, "auto connect if idle")
        self.assertIn("idle", AUTO_CONNECT_IF_IDLE_BLURB.lower())
        self.assertIn("disconnect", AUTO_CONNECT_IF_IDLE_BLURB.lower())

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "settings.json"
            s = default_settings()
            s.auto_connect_if_idle = True
            save_settings(s, path=path)
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(raw.get(KEY_AUTO_CONNECT_IF_IDLE))
            loaded = load_settings(path=path)
            self.assertTrue(loaded.auto_connect_if_idle)
            s.auto_connect_if_idle = False
            save_settings(s, path=path)
            self.assertFalse(load_settings(path=path).auto_connect_if_idle)

    def test_missing_key_defaults_off(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "settings.json"
            path.write_text('{"run_at_startup": false}\n', encoding="utf-8")
            self.assertFalse(load_settings(path=path).auto_connect_if_idle)


class TestMayAutoReconnectGate(unittest.TestCase):
    def test_default_off_blocks(self):
        d = may_auto_reconnect_after_idle_drop(
            pref_on=False,
            app_open=True,
            user_requested_disconnect=False,
            drop_was_idle_timeout=True,
        )
        self.assertFalse(d.allow)
        self.assertEqual(d.reason, "pref_off")

    def test_on_allows_idle_drop_while_app_open(self):
        d = may_auto_reconnect_after_idle_drop(
            pref_on=True,
            app_open=True,
            user_requested_disconnect=False,
            drop_was_idle_timeout=True,
        )
        self.assertTrue(d.allow)
        self.assertEqual(d.reason, "schedule_reconnect")

    def test_user_disconnect_never_reconnects(self):
        d = may_auto_reconnect_after_idle_drop(
            pref_on=True,
            app_open=True,
            user_requested_disconnect=True,
            drop_was_idle_timeout=True,
        )
        self.assertFalse(d.allow)
        self.assertEqual(d.reason, "user_disconnect")

    def test_app_closed_blocks(self):
        d = may_auto_reconnect_after_idle_drop(
            pref_on=True,
            app_open=False,
            user_requested_disconnect=False,
            drop_was_idle_timeout=True,
        )
        self.assertFalse(d.allow)

    def test_non_idle_drop_blocks(self):
        d = may_auto_reconnect_after_idle_drop(
            pref_on=True,
            app_open=True,
            user_requested_disconnect=False,
            drop_was_idle_timeout=False,
        )
        self.assertFalse(d.allow)
        self.assertEqual(d.reason, "not_idle_timeout_drop")

    def test_already_reconnecting_and_max_attempts(self):
        d = may_auto_reconnect_after_idle_drop(
            pref_on=True,
            app_open=True,
            user_requested_disconnect=False,
            drop_was_idle_timeout=True,
            already_reconnecting=True,
        )
        self.assertFalse(d.allow)
        d2 = may_auto_reconnect_after_idle_drop(
            pref_on=True,
            app_open=True,
            user_requested_disconnect=False,
            drop_was_idle_timeout=True,
            attempt_count=MAX_IDLE_RECONNECT_ATTEMPTS,
        )
        self.assertFalse(d2.allow)
        self.assertEqual(d2.reason, "max_attempts")

    def test_backoff_bounded_and_increasing(self):
        a0 = idle_reconnect_backoff_s(0)
        a1 = idle_reconnect_backoff_s(1)
        a2 = idle_reconnect_backoff_s(2)
        self.assertGreaterEqual(a0, 2.0)
        self.assertGreater(a1, a0)
        self.assertGreater(a2, a1)
        self.assertLessEqual(idle_reconnect_backoff_s(20), 30.0)


class TestIdleAutoReconnectWiring(unittest.TestCase):
    def test_app_and_tunnel_wire_idle_drop(self):
        app = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("auto_connect_if_idle", app)
        self.assertIn("AUTO_CONNECT_IF_IDLE_LABEL", app)
        self.assertIn("AUTO_CONNECT_IF_IDLE_BLURB", app)
        self.assertIn("_on_idle_session_drop", app)
        self.assertIn("on_idle_session_drop", app)
        self.assertIn("_user_requested_disconnect", app)
        # Distinct from cold-start autoconnect
        self.assertIn("Autoconnect on launch", app)
        self.assertIn("AUTO_CONNECT_IF_IDLE_LABEL", app)
        self.assertIn("auto_connect_if_idle", app)
        # Skeptic: must tear down + force re-HELLO on idle reconnect
        self.assertIn("perform_idle_drop_session_teardown", app)
        self.assertIn("force_reconnect=True", app)
        self.assertIn("force_reconnect: bool = False", app)

        tw = (ROOT / "client" / "windows" / "tunnel_win.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("on_idle_session_drop", tw)
        self.assertIn("_on_residual_liveness_lost", tw)

    def test_start_full_tunnel_accepts_idle_drop_callback(self):
        import inspect

        from client.windows.tunnel_win import start_full_tunnel

        sig = inspect.signature(start_full_tunnel)
        self.assertIn("on_idle_session_drop", sig.parameters)

    def test_start_connect_accepts_force_reconnect(self):
        import inspect

        # Source signature on method (avoid constructing full Tk app)
        app_src = (ROOT / "client" / "windows" / "app.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "def _start_connect(self, *, force_reconnect: bool = False)",
            app_src,
        )
        # connect() call site must pass force_reconnect through
        self.assertIn(
            "force_reconnect=bool(force_reconnect)",
            app_src,
        )


class TestIdleDropSessionTeardown(unittest.TestCase):
    """Honest path: liveness-lost teardown clears CONNECTED so re-HELLO can run."""

    def test_teardown_calls_disconnect_full_tunnel_and_client_disconnect(self):
        from client.windows.idle_auto_reconnect import (
            perform_idle_drop_session_teardown,
        )

        calls: list[tuple] = []
        client = mock.Mock()
        tunnel = mock.Mock()

        def fake_dft(t, c):
            calls.append(("disconnect_full_tunnel", t, c))
            # Real disconnect_full_tunnel also ends the session
            c.disconnect()

        steps = perform_idle_drop_session_teardown(
            tunnel=tunnel,
            client=client,
            disconnect_full_tunnel_fn=fake_dft,
        )
        self.assertIn("disconnect_full_tunnel", steps)
        self.assertIn("client_disconnect", steps)
        self.assertEqual(calls[0][0], "disconnect_full_tunnel")
        self.assertIs(calls[0][1], tunnel)
        self.assertIs(calls[0][2], client)
        # disconnect_full_tunnel path + belt-and-suspenders client.disconnect
        self.assertGreaterEqual(client.disconnect.call_count, 2)

    def test_teardown_with_none_tunnel_still_disconnects_client(self):
        from client.windows.idle_auto_reconnect import (
            perform_idle_drop_session_teardown,
        )

        client = mock.Mock()
        seen: list = []

        def fake_dft(t, c):
            seen.append(t)
            # tunnel may already be None after UI cleared the handle

        steps = perform_idle_drop_session_teardown(
            tunnel=None,
            client=client,
            disconnect_full_tunnel_fn=fake_dft,
        )
        self.assertIsNone(seen[0])
        self.assertIn("client_disconnect", steps)
        client.disconnect.assert_called()

    def test_connected_client_short_circuits_without_teardown(self):
        """Documents the bug: CONNECTED + no force_reconnect → false success."""
        from client.connect import ConnectState, RptClient
        from client.full_tunnel import build_full_tunnel_plan

        client = RptClient()
        client.state = ConnectState.CONNECTED
        client.session = mock.Mock(vpn_ip="10.88.0.1")
        client.tunnel_plan = build_full_tunnel_plan("10.88.0.1")
        out = client.connect(timeout=1.0, force_reconnect=False)
        self.assertTrue(out.ok)
        self.assertIn("already connected", (out.message or "").lower())

    def test_teardown_then_connect_does_not_short_circuit_as_connected(self):
        """Shipped teardown must clear session so next connect is not a no-op."""
        from client.connect import ConnectState, RptClient
        from client.full_tunnel import build_full_tunnel_plan
        from client.windows.idle_auto_reconnect import (
            perform_idle_drop_session_teardown,
        )

        client = RptClient()
        client.state = ConnectState.CONNECTED
        client.session = mock.Mock(vpn_ip="10.88.0.1")
        client.tunnel_plan = build_full_tunnel_plan("10.88.0.1")

        def dft(tunnel, c):
            # Mimic stop_full_tunnel session end
            if c is not None:
                c.disconnect()

        steps = perform_idle_drop_session_teardown(
            tunnel=object(),
            client=client,
            disconnect_full_tunnel_fn=dft,
        )
        self.assertIn("disconnect_full_tunnel", steps)
        self.assertEqual(client.state, ConnectState.DISCONNECTED)
        self.assertIsNone(client.session)

        # Without force: no longer "already connected" (must attempt real connect)
        with mock.patch(
            "client.connect.ensure_device_admission_key",
            side_effect=FileNotFoundError("no secrets"),
        ):
            out = client.connect(timeout=1.0, force_reconnect=False)
        self.assertFalse(out.ok)
        self.assertNotIn("already connected", (out.message or "").lower())

    def test_force_reconnect_bypasses_connected_short_circuit(self):
        """Belt path used by app _start_connect(force_reconnect=True)."""
        from client.connect import ConnectState, RptClient
        from client.full_tunnel import build_full_tunnel_plan

        client = RptClient()
        client.state = ConnectState.CONNECTED
        client.session = mock.Mock(vpn_ip="10.88.0.1")
        client.tunnel_plan = build_full_tunnel_plan("10.88.0.1")

        with mock.patch(
            "client.connect.ensure_device_admission_key",
            side_effect=FileNotFoundError("no secrets"),
        ):
            out = client.connect(timeout=1.0, force_reconnect=True)
        self.assertFalse(out.ok)
        self.assertNotIn("already connected", (out.message or "").lower())

    def test_app_idle_drop_body_orders_teardown_before_force_reconnect(self):
        """Structural: _on_idle_session_drop must teardown then force_reconnect."""
        app = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        # Isolate the method body roughly
        start = app.find("def _on_idle_session_drop")
        self.assertGreater(start, 0)
        end = app.find("\n    def _start_disconnect", start)
        body = app[start:end] if end > start else app[start : start + 4000]
        i_teardown = body.find("perform_idle_drop_session_teardown")
        i_force = body.find("force_reconnect=True")
        self.assertGreater(i_teardown, 0, "teardown missing from idle drop")
        self.assertGreater(i_force, 0, "force_reconnect missing from idle drop")
        self.assertLess(
            i_teardown,
            i_force,
            "teardown must be ordered before force reconnect schedule",
        )


if __name__ == "__main__":
    unittest.main()

"""Windows Connect must force keygen unlock; map residual 10054 clearly."""

from __future__ import annotations

import os
import socket
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestNeedsKeygenUnlock(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.lic = Path(self._td.name) / "licence_acceptance.json"
        self.pay = Path(self._td.name) / "payment_entitlement.json"
        os.environ["RPT_REQUIRE_PAYMENT_ENTITLEMENT"] = "1"

    def tearDown(self) -> None:
        self._td.cleanup()
        os.environ.pop("RPT_REQUIRE_PAYMENT_ENTITLEMENT", None)

    def test_needs_keygen_after_licence_without_payment(self) -> None:
        from client.licence_gate import (
            accept_licence,
            needs_keygen_unlock,
            may_connect,
        )
        from client.payment_entitlement import (
            PaymentEntitlement,
            save_payment_entitlement,
        )

        self.assertFalse(needs_keygen_unlock(self.lic))
        accept_licence(self.lic)
        # empty payment file
        save_payment_entitlement(PaymentEntitlement(), path=self.pay)
        with mock.patch(
            "client.payment_entitlement.default_entitlement_path",
            return_value=self.pay,
        ):
            with mock.patch(
                "client.licence_gate.has_accepted_licence",
                return_value=True,
            ):
                # drive real needs_keygen_unlock + payment_allows_connect
                from client import licence_gate as lg

                # Patch path used by has_accepted via real file
                with mock.patch.object(lg, "has_accepted_licence", return_value=True):
                    with mock.patch(
                        "client.payment_entitlement.payment_allows_connect",
                        return_value=False,
                    ):
                        self.assertTrue(lg.needs_keygen_unlock(self.lic))
                    with mock.patch(
                        "client.payment_entitlement.payment_allows_connect",
                        return_value=True,
                    ):
                        self.assertFalse(lg.needs_keygen_unlock(self.lic))

    def test_active_session_without_keygen_still_needs_unlock(self) -> None:
        """Thank-you discovery / session-only active file must not skip keygen."""
        from client.licence_gate import accept_licence, assert_may_connect, needs_keygen_unlock
        from client.payment_entitlement import (
            CONNECT_BLOCKED_KEYGEN_MSG,
            has_keygen_unlock,
            payment_allows_connect,
            record_payment_success,
        )

        accept_licence(self.lic)
        record_payment_success("cs_session_only", path=self.pay, platform="windows")
        self.assertFalse(has_keygen_unlock(path=self.pay))
        with mock.patch(
            "client.payment_entitlement.default_entitlement_path",
            return_value=self.pay,
        ):
            self.assertTrue(needs_keygen_unlock(self.lic))
            self.assertFalse(payment_allows_connect(path=self.pay, require=True))
            with mock.patch(
                "client.payment_entitlement.ensure_entitlement_for_connect",
                side_effect=lambda **kw: record_payment_success(
                    "cs_session_only", path=self.pay
                ),
            ):
                ok, msg = assert_may_connect(self.lic)
            self.assertFalse(ok)
            self.assertEqual(msg, CONNECT_BLOCKED_KEYGEN_MSG)

    def test_keygen_unlock_allows_connect(self) -> None:
        from client.licence_gate import accept_licence, assert_may_connect, needs_keygen_unlock
        from client.payment_entitlement import (
            import_keygen_and_verify,
            payment_allows_connect,
        )

        accept_licence(self.lic)

        def fake_fetch(sid: str = "", keygen: str = "", **_k):
            return {
                "status": "active",
                "connect_allowed": True,
                "session_id": "cs_keygen_ok",
                "keygen": keygen or "RPT-KEY-DEAD-BEEF-CAFE",
            }

        with mock.patch(
            "client.payment_entitlement.default_entitlement_path",
            return_value=self.pay,
        ):
            ent = import_keygen_and_verify(
                "RPT-KEY-DEAD-BEEF-CAFE",
                path=self.pay,
                fetch=fake_fetch,
                bind_device=False,
            )
            self.assertEqual(ent.status, "active")
            self.assertTrue(payment_allows_connect(path=self.pay, require=True))
            self.assertFalse(needs_keygen_unlock(self.lic))
            with mock.patch(
                "client.payment_entitlement.ensure_entitlement_for_connect",
                side_effect=lambda **kw: ent,
            ):
                ok, msg = assert_may_connect(self.lic)
            self.assertTrue(ok)
            self.assertEqual(msg, "")

    def test_session_only_remote_keygen_does_not_unlock(self) -> None:
        """Honest path: session-only active + remote returns keygen must NOT unlock.

        Status host always knows the keygen for a paid session. Writing that
        field into local cache on session lookup would skip the user keygen
        step — refresh must leave keygen empty until import_keygen_and_verify.
        """
        from client.licence_gate import accept_licence, needs_keygen_unlock
        from client.payment_entitlement import (
            ensure_entitlement_for_connect,
            has_keygen_unlock,
            import_keygen_and_verify,
            load_payment_entitlement,
            payment_allows_connect,
            record_payment_success,
            refresh_entitlement_from_remote,
        )

        accept_licence(self.lic)
        # Simulate thank-you / discovery: active session, no keygen on disk
        record_payment_success(
            "cs_session_only", path=self.pay, platform="windows"
        )
        self.assertFalse(has_keygen_unlock(path=self.pay))

        def remote_with_keygen(sid: str = "", keygen: str = "", **_k):
            return {
                "status": "active",
                "connect_allowed": True,
                "session_id": sid or "cs_session_only",
                "keygen": "RPT-KEY-FROM-STATUS-HOST",
                "platform": "windows",
            }

        with mock.patch(
            "client.payment_entitlement.default_entitlement_path",
            return_value=self.pay,
        ):
            refreshed = refresh_entitlement_from_remote(
                path=self.pay, fetch=remote_with_keygen
            )
            self.assertEqual(refreshed.status, "active")
            self.assertEqual(refreshed.keygen, "")
            self.assertFalse(has_keygen_unlock(refreshed))
            self.assertFalse(payment_allows_connect(path=self.pay, require=True))
            self.assertTrue(needs_keygen_unlock(self.lic))

            # ensure_entitlement_for_connect (launch bootstrap path) same rule
            ensure_entitlement_for_connect(
                path=self.pay, fetch=remote_with_keygen, bind_device=False
            )
            after_ensure = load_payment_entitlement(self.pay)
            self.assertEqual(after_ensure.keygen, "")
            self.assertFalse(payment_allows_connect(path=self.pay, require=True))
            self.assertTrue(needs_keygen_unlock(self.lic))

            # Only user keygen import path unlocks
            unlocked = import_keygen_and_verify(
                "RPT-KEY-FROM-STATUS-HOST",
                path=self.pay,
                fetch=remote_with_keygen,
                bind_device=False,
            )
            self.assertEqual(unlocked.keygen, "RPT-KEY-FROM-STATUS-HOST")
            self.assertTrue(payment_allows_connect(path=self.pay, require=True))
            self.assertFalse(needs_keygen_unlock(self.lic))

    def test_windows_app_has_keygen_prompt_hook(self) -> None:
        """Structural: shipped Windows app exposes forced keygen modal on Connect."""
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("def _show_keygen_prompt", src)
        self.assertIn("needs_keygen_unlock", src)
        self.assertIn("Enter licence keygen", src)
        self.assertIn("_show_keygen_prompt()", src)
        # Connect path must prefer keygen modal over Settings-only when unlock needed
        self.assertIn("if needs_keygen_unlock():", src)
        self.assertIn("import_keygen_and_verify", src)
        # Local-first gate: keygen checked before residual / status-host work
        self.assertIn("CONNECT_BLOCKED_KEYGEN_MSG", src)
        # Network bootstrap must not block the Tk UI thread on Connect start
        connect_fn = src.split("def _start_connect")[1].split("def _disconnect")[0]
        # First gate is local needs_keygen (not bootstrap on UI thread before gate)
        idx_keygen = connect_fn.find("if needs_keygen_unlock()")
        idx_bootstrap = connect_fn.find("bootstrap_payment_entitlement")
        self.assertGreater(idx_keygen, 0)
        self.assertGreater(idx_bootstrap, idx_keygen)
        # bootstrap runs inside work() worker thread
        self.assertIn("def work() -> None:", connect_fn)
        self.assertLess(
            connect_fn.find("def work() -> None:"),
            idx_bootstrap,
        )
        # Cold-start / autoconnect must not call assert_may_connect on UI thread
        auto = src.split("def _cold_start_first_run")[1].split("app.root.after")[0]
        self.assertNotIn("assert_may_connect()", auto)
        self.assertIn("needs_keygen_unlock()", auto)
        self.assertIn("_start_connect()", auto)
        self.assertIn("first_run_next_surface", auto)

    def test_linux_app_has_keygen_prompt_hook(self) -> None:
        """Structural: Linux desktop mirrors Windows forced keygen modal."""
        src = (ROOT / "client" / "linux" / "app.py").read_text(encoding="utf-8")
        self.assertIn("def _show_keygen_prompt", src)
        self.assertIn("needs_keygen_unlock", src)
        self.assertIn("Enter licence keygen", src)
        self.assertIn("if needs_keygen_unlock():", src)
        self.assertIn("import_keygen_and_verify", src)

    def test_flutter_shell_has_keygen_unlock_surface(self) -> None:
        """Structural: Flutter product shell forces keygen sheet (not Settings-only)."""
        main = (ROOT / "client_app" / "lib" / "main.dart").read_text(encoding="utf-8")
        gate = (ROOT / "client_app" / "lib" / "licence_gate.dart").read_text(
            encoding="utf-8"
        )
        status = (ROOT / "client_app" / "lib" / "connect_status.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("needsKeygenUnlock", gate)
        self.assertIn("_showKeygenSheet", main)
        self.assertIn("kKeygenPromptTitle", main)
        self.assertIn("importKeygenAndVerify", main)
        self.assertIn("keygen", status.lower())
        # Bind path must exist (node payment HELLO gate parity with desktop)
        self.assertIn("bindDeviceEntitlement", gate)
        self.assertIn("bind-device-entitlement", gate)
        self.assertIn("devicePubHex", gate)
        self.assertTrue(
            (ROOT / "client_app" / "test" / "keygen_bind_device_test.dart").is_file()
        )
        android = (
            ROOT
            / "client_app"
            / "android"
            / "app"
            / "src"
            / "main"
            / "kotlin"
            / "com"
            / "restoreprivacy"
            / "restore_privacy_client"
            / "MainActivity.kt"
        ).read_text(encoding="utf-8")
        self.assertIn('"devicePubHex"', android)
        self.assertIn("devicePubHexMap", android)


class TestFormatConnectFailure10054(unittest.TestCase):
    def test_maps_winerror_10054(self) -> None:
        from client.connect import format_connect_failure

        exc = ConnectionResetError(
            10054, "An existing connection was forcibly closed by the remote host"
        )
        # Windows often strings the OSError like this:
        try:
            raise ConnectionResetError(
                "[WinError 10054] An existing connection was forcibly closed by the remote host"
            )
        except ConnectionResetError as e:
            msg = format_connect_failure(
                e, host="82.221.101.241", port=44044, timeout_s=20
            )
        self.assertIn("82.221.101.241:44044", msg)
        self.assertIn("keygen", msg.lower())
        self.assertNotEqual(msg.strip(), str(exc))

    def test_timeout_mentions_keygen(self) -> None:
        from client.connect import format_connect_failure

        msg = format_connect_failure(
            TimeoutError("timed out"),
            host="82.221.101.241",
            port=44044,
            timeout_s=20,
        )
        self.assertIn("82.221.101.241:44044", msg)
        self.assertIn("keygen", msg.lower())


class TestImportKeygenBindsDevice(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.pay = Path(self._td.name) / "payment_entitlement.json"
        os.environ["RPT_REQUIRE_PAYMENT_ENTITLEMENT"] = "1"

    def tearDown(self) -> None:
        self._td.cleanup()
        os.environ.pop("RPT_REQUIRE_PAYMENT_ENTITLEMENT", None)

    def test_import_keygen_calls_bind_when_active(self) -> None:
        from client.payment_entitlement import import_keygen_and_verify

        bound: list[str] = []

        def fake_fetch(sid: str = "", keygen: str = "", **_k):
            return {
                "status": "active",
                "connect_allowed": True,
                "session_id": "cs_test_bind_me",
                "keygen": keygen or "RPT-KEY-AAAA-BBBB-CCCC",
            }

        def fake_bind(session_id: str, **_k):
            bound.append(session_id)
            return {"ok": True}

        with mock.patch(
            "client.payment_entitlement.default_entitlement_path",
            return_value=self.pay,
        ):
            with mock.patch(
                "client.payment_entitlement.fetch_remote_entitlement_status",
                side_effect=lambda sid="", keygen="", **k: fake_fetch(
                    sid, keygen=keygen
                ),
            ):
                with mock.patch(
                    "client.payment_entitlement.bind_device_to_remote",
                    side_effect=fake_bind,
                ):
                    ent = import_keygen_and_verify(
                        "RPT-KEY-AAAA-BBBB-CCCC",
                        path=self.pay,
                        bind_device=True,
                    )
        self.assertEqual(ent.status, "active")
        self.assertEqual(bound, ["cs_test_bind_me"])


class TestStatusHostTimeoutBounds(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop("RPT_STATUS_HOST_TIMEOUT", None)

    def test_default_timeout_is_short(self) -> None:
        from client.payment_entitlement import status_host_timeout_s

        os.environ.pop("RPT_STATUS_HOST_TIMEOUT", None)
        self.assertLessEqual(status_host_timeout_s(), 3.0)
        self.assertGreaterEqual(status_host_timeout_s(), 1.0)

    def test_timeout_clamped(self) -> None:
        from client.payment_entitlement import status_host_timeout_s

        os.environ["RPT_STATUS_HOST_TIMEOUT"] = "999"
        self.assertEqual(status_host_timeout_s(), 15.0)
        os.environ["RPT_STATUS_HOST_TIMEOUT"] = "0.1"
        self.assertEqual(status_host_timeout_s(), 1.0)

    def test_fetch_respects_timeout_wall_clock(self) -> None:
        """Dead host must fail within configured timeout + small slack (no multi-minute hang)."""
        from client.payment_entitlement import fetch_remote_entitlement_status

        # 127.0.0.1:9 is almost always closed/refused quickly; use a blackhole IP
        # with a tiny timeout to prove urlopen is bounded.
        os.environ["RPT_STATUS_HOST_TIMEOUT"] = "1"
        t0 = time.monotonic()
        out = fetch_remote_entitlement_status(
            "cs_timeout_probe",
            base_url="http://172.16.0.1:9",  # non-routable, will hang until timeout
            timeout=1.0,
            keygen="",
        )
        elapsed = time.monotonic() - t0
        self.assertIn(out.get("status"), ("unknown", "active", "failed", "revoked"))
        # Must not hang for 8s+ stacks; allow OS scheduling slack
        self.assertLess(elapsed, 4.0, f"fetch hung {elapsed:.2f}s (bound 1s + slack)")


if __name__ == "__main__":
    unittest.main()

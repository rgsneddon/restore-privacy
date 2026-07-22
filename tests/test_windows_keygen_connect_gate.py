"""Windows Connect must force keygen unlock; map residual 10054 clearly."""

from __future__ import annotations

import os
import socket
import sys
import tempfile
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

    def test_windows_app_has_keygen_prompt_hook(self) -> None:
        """Structural: shipped Windows app exposes forced keygen modal on Connect."""
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("def _show_keygen_prompt", src)
        self.assertIn("needs_keygen_unlock", src)
        self.assertIn("Enter licence keygen", src)
        self.assertIn("_show_keygen_prompt()", src)
        # Connect path must prefer keygen modal over Settings-only when unlock needed
        self.assertIn("elif needs_keygen_unlock():", src)
        self.assertIn("import_keygen_and_verify", src)

    def test_linux_app_has_keygen_prompt_hook(self) -> None:
        """Structural: Linux desktop mirrors Windows forced keygen modal."""
        src = (ROOT / "client" / "linux" / "app.py").read_text(encoding="utf-8")
        self.assertIn("def _show_keygen_prompt", src)
        self.assertIn("needs_keygen_unlock", src)
        self.assertIn("Enter licence keygen", src)
        self.assertIn("elif needs_keygen_unlock():", src)
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


if __name__ == "__main__":
    unittest.main()

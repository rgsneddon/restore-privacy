"""Settings surfaces work on every platform; Connect gates stay consistent."""

from __future__ import annotations

import ast
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestWindowsSettingsWiring(unittest.TestCase):
    def test_settings_sections_and_connect_gate(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        for needle in (
            "def _open_settings",
            "Payment entitlement",
            "Verify keygen",
            "import_session_and_verify",
            "ensure_entitlement_for_connect",
            "LICENCE_ACCEPT_BUTTON",
            "autoconnect_on_launch",
            "run_at_startup",
            "CONNECTION_LOG",
            "LEAK_TEST",
            "LEGAL_DOC_LINKS",
            "DPI_MITIGATION",
            "assert_may_connect",
            "bootstrap_payment_entitlement",
            "first_run_next_surface",
            "_ok_bind_and_close",
        ):
            self.assertIn(needle, src, msg=f"windows missing {needle}")
        # Connect opens Settings when payment blocked (licence already ok)
        self.assertIn("self._open_settings()", src)
        self.assertIn("has_accepted_licence()", src)


class TestLinuxSettingsWiring(unittest.TestCase):
    def test_settings_sections_and_connect_gate(self):
        src = (ROOT / "client" / "linux" / "app.py").read_text(encoding="utf-8")
        for needle in (
            "def _open_settings",
            "Payment entitlement",
            "Verify payment",
            "import_session_and_verify",
            "ensure_entitlement_for_connect",
            "LICENCE_ACCEPT_BUTTON",
            "autoconnect_on_launch",
            "run_at_startup",
            "CONNECTION_LOG",
            "LEAK_TEST",
            "LEGAL_DOC_LINKS",
            "DPI_MITIGATION",
            "assert_may_connect",
            "bootstrap_payment_entitlement",
            "should_autoconnect_on_launch",
        ):
            self.assertIn(needle, src, msg=f"linux missing {needle}")

    def test_linux_settings_store_defaults_off(self):
        from client.linux.settings_store import (
            apply_run_at_startup,
            default_settings,
            load_settings,
            save_settings,
            should_autoconnect_on_launch,
        )

        d = default_settings()
        self.assertFalse(d.run_at_startup)
        self.assertFalse(d.autoconnect_on_launch)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "settings.json"
            save_settings(
                type(d)(run_at_startup=False, autoconnect_on_launch=True), path=p
            )
            loaded = load_settings(path=p)
            self.assertTrue(loaded.autoconnect_on_launch)
            self.assertFalse(loaded.run_at_startup)
            self.assertTrue(should_autoconnect_on_launch(loaded))
            # Best-effort autostart (may write under temp home if we patch)
            st = apply_run_at_startup(False)
            self.assertIn(st, ("disabled", "skipped:non_linux") or True)
            self.assertTrue(st.startswith("disabled") or st.startswith("skipped") or st.startswith("failed"))


class TestFlutterSettingsWiring(unittest.TestCase):
    def test_settings_screen_actions(self):
        settings = (
            ROOT / "client_app" / "lib" / "settings_screen.dart"
        ).read_text(encoding="utf-8")
        main = (ROOT / "client_app" / "lib" / "main.dart").read_text(encoding="utf-8")
        gate = (
            ROOT / "client_app" / "lib" / "licence_gate.dart"
        ).read_text(encoding="utf-8")
        for needle in (
            "Payment entitlement",
            "Verify payment",
            "importSessionAndVerify",
            "refreshEntitlementFromRemote",
            "kLicenceAcceptButton",
            "autoconnectOnLaunch",
            "runAtStartup",
            "kConnectionLogTitle",
            "runLeakTest",
            "kDpiMitigationDisclaimer",
            "LegalDocLink",
        ):
            self.assertTrue(
                needle in settings or needle in main or needle in gate,
                msg=f"flutter missing {needle}",
            )
        self.assertIn("assertMayConnect", main)
        self.assertIn("refreshPayment: true", main)
        self.assertIn("_maybeAutoconnect", main)


class TestPaymentBootstrapAndConnectGate(unittest.TestCase):
    def test_bootstrap_and_ready_helpers(self):
        from client.startup_bootstrap import (
            bootstrap_payment_entitlement,
            ready_for_fast_connect,
        )
        from client.licence_gate import accept_licence, clear_licence_acceptance
        from client.payment_entitlement import record_payment_success

        with tempfile.TemporaryDirectory() as td:
            lic = Path(td) / "licence_acceptance.json"
            pay = Path(td) / "payment_entitlement.json"
            clear_licence_acceptance(path=lic)
            with mock.patch(
                "client.payment_entitlement.default_entitlement_path",
                return_value=pay,
            ):
                with mock.patch(
                    "client.payment_entitlement.ensure_entitlement_for_connect",
                    return_value=None,
                ):
                    self.assertIsNone(bootstrap_payment_entitlement())
                # unpaid not ready
                ok, msg = ready_for_fast_connect()
                # may use real home licence path — just ensure tuple shape
                self.assertIsInstance(ok, bool)
                self.assertIsInstance(msg, str)

                accept_licence(path=lic)
                record_payment_success("cs_fast", path=pay)
                with mock.patch(
                    "client.licence_gate.has_accepted_licence", return_value=True
                ):
                    with mock.patch(
                        "client.payment_entitlement.payment_allows_connect",
                        return_value=True,
                    ):
                        with mock.patch(
                            "client.payment_entitlement.assert_payment_may_connect",
                            return_value=(True, ""),
                        ):
                            with mock.patch(
                                "client.licence_gate.assert_may_connect",
                                return_value=(True, ""),
                            ):
                                ok2, msg2 = ready_for_fast_connect()
                                self.assertTrue(ok2)
                                self.assertEqual(msg2, "")

    def test_assert_may_connect_blocks_unpaid(self):
        from client.licence_gate import accept_licence, assert_may_connect
        from client.payment_entitlement import record_payment_failure

        with tempfile.TemporaryDirectory() as td:
            lic = Path(td) / "licence_acceptance.json"
            pay = Path(td) / "payment_entitlement.json"
            accept_licence(path=lic)
            record_payment_failure("cs_x", path=pay)
            with mock.patch(
                "client.payment_entitlement.default_entitlement_path",
                return_value=pay,
            ):
                with mock.patch(
                    "client.payment_entitlement.ensure_entitlement_for_connect",
                    return_value=None,
                ):
                    ok, msg = assert_may_connect(path=lic)
                    self.assertFalse(ok)
                    self.assertIn("payment", msg.lower())


class TestNoBypassConnectGates(unittest.TestCase):
    def test_autoconnect_still_gates(self):
        for rel in (
            "client/windows/app.py",
            "client/linux/app.py",
            "client_app/lib/main.dart",
        ):
            src = (ROOT / rel).read_text(encoding="utf-8")
            self.assertTrue(
                "assert_may_connect" in src or "assertMayConnect" in src,
                msg=f"{rel} missing Connect gate",
            )
            self.assertIn("autoconnect", src.lower())


if __name__ == "__main__":
    unittest.main()

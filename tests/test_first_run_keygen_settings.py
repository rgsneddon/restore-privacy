"""First-run: demand keygen unlock → settings OK → main Connect (real gates)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestFirstRunNextSurface(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.lic = Path(self._td.name) / "licence_acceptance.json"
        self.pay = Path(self._td.name) / "payment_entitlement.json"
        self.settings = Path(self._td.name) / "settings.json"
        os.environ["RPT_REQUIRE_PAYMENT_ENTITLEMENT"] = "1"

    def tearDown(self) -> None:
        self._td.cleanup()
        os.environ.pop("RPT_REQUIRE_PAYMENT_ENTITLEMENT", None)

    def test_cold_start_without_licence_is_licence(self) -> None:
        from client.first_run_flow import first_run_next_surface
        from client.licence_gate import clear_licence_acceptance

        clear_licence_acceptance(self.lic)
        self.assertEqual(first_run_next_surface(licence_path=self.lic), "licence")

    def test_licence_accepted_without_keygen_shows_step2(self) -> None:
        """After licence: step 2 (trial/KEYGEN). KEYGEN not mandatory while trial open."""
        from client.first_run_flow import (
            first_run_demands_keygen,
            first_run_next_surface,
        )
        from client.licence_gate import accept_licence, needs_keygen_unlock
        from client.payment_entitlement import (
            PaymentEntitlement,
            payment_allows_connect,
            save_payment_entitlement,
        )
        from client.device_trial import clear_device_trial

        accept_licence(self.lic)
        save_payment_entitlement(PaymentEntitlement(), path=self.pay)
        trial_path = Path(self._td.name) / "device_trial.json"
        clear_device_trial(trial_path)
        with mock.patch(
            "client.payment_entitlement.default_entitlement_path",
            return_value=self.pay,
        ), mock.patch(
            "client.device_trial.default_trial_path",
            return_value=trial_path,
        ):
            self.assertFalse(payment_allows_connect(path=self.pay, require=True))
            # Trial not expired → KEYGEN not mandatory
            self.assertFalse(needs_keygen_unlock(self.lic))
            # Still land on step 2 surface
            self.assertTrue(first_run_demands_keygen(licence_path=self.lic))
            self.assertEqual(
                first_run_next_surface(licence_path=self.lic), "keygen"
            )

    def test_session_only_active_still_shows_step2(self) -> None:
        from client.first_run_flow import first_run_next_surface
        from client.licence_gate import accept_licence
        from client.payment_entitlement import record_payment_success
        from client.device_trial import clear_device_trial

        accept_licence(self.lic)
        record_payment_success("cs_session_only", path=self.pay, platform="windows")
        trial_path = Path(self._td.name) / "device_trial.json"
        clear_device_trial(trial_path)
        with mock.patch(
            "client.payment_entitlement.default_entitlement_path",
            return_value=self.pay,
        ), mock.patch(
            "client.device_trial.default_trial_path",
            return_value=trial_path,
        ):
            self.assertEqual(
                first_run_next_surface(licence_path=self.lic), "keygen"
            )

    def test_keygen_unlock_goes_straight_to_main(self) -> None:
        """Post-keygen: lean residual path opens main Connect (not blocking Settings)."""
        from client.first_run_flow import (
            first_run_next_surface,
            post_keygen_next_surface,
        )
        from client.licence_gate import accept_licence, needs_keygen_unlock
        from client.payment_entitlement import import_keygen_and_verify

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
            import_keygen_and_verify(
                "RPT-KEY-DEAD-BEEF-CAFE",
                path=self.pay,
                fetch=fake_fetch,
                bind_device=False,
            )
            self.assertFalse(needs_keygen_unlock(self.lic))
            self.assertEqual(
                first_run_next_surface(
                    licence_path=self.lic, settings_path=self.settings
                ),
                "main",
            )
            self.assertEqual(
                post_keygen_next_surface(
                    licence_path=self.lic, settings_path=self.settings
                ),
                "main",
            )

    def test_connect_allowed_on_free_trial_without_keygen(self) -> None:
        """Trial window allows Connect without KEYGEN (clock starts on first Connect)."""
        from client.licence_gate import accept_licence, assert_may_connect
        from client.payment_entitlement import (
            PaymentEntitlement,
            save_payment_entitlement,
        )
        from client.device_trial import clear_device_trial, default_trial_path

        accept_licence(self.lic)
        save_payment_entitlement(PaymentEntitlement(), path=self.pay)
        trial_path = Path(self._td.name) / "device_trial.json"
        clear_device_trial(trial_path)
        with mock.patch(
            "client.payment_entitlement.default_entitlement_path",
            return_value=self.pay,
        ), mock.patch(
            "client.device_trial.default_trial_path",
            return_value=trial_path,
        ), mock.patch(
            "client.payment_entitlement.ensure_entitlement_for_connect",
            side_effect=lambda **kw: PaymentEntitlement(),
        ), mock.patch(
            "client.payment_entitlement.connect_status_host_refresh_needed",
            return_value=False,
        ):
            ok, msg = assert_may_connect(self.lic)
        self.assertTrue(ok, msg)


class TestFirstRunWindowsEntryStructural(unittest.TestCase):
    def test_app_cold_start_uses_first_run_surface(self) -> None:
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("first_run_next_surface", src)
        self.assertIn("_present_first_run_surface", src)
        self.assertIn("_open_settings(first_run=True)", src)
        self.assertIn("post_keygen_next_surface", src)
        self.assertIn("Unlock with KEYGEN", src)
        self.assertIn("Continue trial", src)
        # Must not gate cold-start solely on may_connect (that skipped keygen)
        self.assertIn("_cold_start_first_run", src)
        self.assertNotIn(
            "elif not may_connect():",
            src,
        )
        # Demand KEYGEN when trial expired; continue trial when open
        self.assertIn("needs_keygen_unlock()", src)
        self.assertIn("fulfilment email", src)
        self.assertIn("Buy KEYGEN", src)

    def test_settings_ok_and_geometry(self) -> None:
        from client.first_run_flow import (
            FIRST_RUN_SETTINGS_GEOMETRY,
            FIRST_RUN_SETTINGS_MINSIZE,
            MAIN_CONNECT_GEOMETRY,
        )

        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("FIRST_RUN_SETTINGS_GEOMETRY", src)
        self.assertIn("_ok_bind_and_close", src)
        self.assertIn('text="OK"', src)
        # Geometry large enough for primary controls
        w, h = FIRST_RUN_SETTINGS_GEOMETRY.lower().split("x")
        self.assertGreaterEqual(int(w), 560)
        self.assertGreaterEqual(int(h), 800)
        self.assertGreaterEqual(FIRST_RUN_SETTINGS_MINSIZE[0], 480)
        mw, mh = MAIN_CONNECT_GEOMETRY.lower().split("x")
        self.assertGreaterEqual(int(mw), 520)

    def test_no_bypass_scripts_in_windows_client(self) -> None:
        """Do not ship scripts that skip keygen unlock."""
        win_dir = ROOT / "client" / "windows"
        for p in win_dir.rglob("*"):
            if not p.is_file():
                continue
            name = p.name.lower()
            if name.endswith((".py", ".ps1", ".bat", ".cmd", ".vbs")):
                # product code may mention keygen; forbid bypass installers
                if "bypass" in name or "skip_keygen" in name or "unlock_free" in name:
                    self.fail(f"bypass-like file not allowed: {p}")


if __name__ == "__main__":
    unittest.main()

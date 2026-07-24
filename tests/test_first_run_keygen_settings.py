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

    def test_licence_accepted_without_keygen_demands_keygen(self) -> None:
        """Core product rule: unlock-absent after licence → keygen surface."""
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

        accept_licence(self.lic)
        save_payment_entitlement(PaymentEntitlement(), path=self.pay)
        with mock.patch(
            "client.payment_entitlement.default_entitlement_path",
            return_value=self.pay,
        ):
            self.assertFalse(payment_allows_connect(path=self.pay, require=True))
            self.assertTrue(needs_keygen_unlock(self.lic))
            self.assertTrue(first_run_demands_keygen(licence_path=self.lic))
            self.assertEqual(
                first_run_next_surface(licence_path=self.lic), "keygen"
            )

    def test_session_only_active_still_demands_keygen(self) -> None:
        from client.first_run_flow import first_run_next_surface
        from client.licence_gate import accept_licence, needs_keygen_unlock
        from client.payment_entitlement import record_payment_success

        accept_licence(self.lic)
        record_payment_success("cs_session_only", path=self.pay, platform="windows")
        with mock.patch(
            "client.payment_entitlement.default_entitlement_path",
            return_value=self.pay,
        ):
            self.assertTrue(needs_keygen_unlock(self.lic))
            self.assertEqual(
                first_run_next_surface(licence_path=self.lic), "keygen"
            )

    def test_keygen_unlock_then_settings_then_main(self) -> None:
        """Post-keygen: settings until OK; after mark complete → main."""
        from client.first_run_flow import (
            first_run_next_surface,
            mark_first_run_settings_completed,
            post_keygen_next_surface,
        )
        from client.licence_gate import accept_licence, needs_keygen_unlock
        from client.payment_entitlement import import_keygen_and_verify
        from client.windows.settings_store import (
            ProductSettings,
            load_settings,
            save_settings,
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
            import_keygen_and_verify(
                "RPT-KEY-DEAD-BEEF-CAFE",
                path=self.pay,
                fetch=fake_fetch,
                bind_device=False,
            )
            self.assertFalse(needs_keygen_unlock(self.lic))
            # No settings OK yet → settings surface
            save_settings(ProductSettings(), path=self.settings)
            self.assertEqual(
                first_run_next_surface(
                    licence_path=self.lic, settings_path=self.settings
                ),
                "settings",
            )
            self.assertEqual(
                post_keygen_next_surface(
                    licence_path=self.lic, settings_path=self.settings
                ),
                "settings",
            )
            # User presses OK — bind settings complete
            mark_first_run_settings_completed(path=self.settings)
            loaded = load_settings(path=self.settings)
            self.assertTrue(loaded.first_run_settings_completed)
            self.assertEqual(
                first_run_next_surface(
                    licence_path=self.lic, settings_path=self.settings
                ),
                "main",
            )

    def test_connect_blocked_without_keygen_message(self) -> None:
        from client.licence_gate import accept_licence, assert_may_connect
        from client.payment_entitlement import (
            CONNECT_BLOCKED_KEYGEN_MSG,
            PaymentEntitlement,
            save_payment_entitlement,
        )

        accept_licence(self.lic)
        save_payment_entitlement(PaymentEntitlement(), path=self.pay)
        with mock.patch(
            "client.payment_entitlement.default_entitlement_path",
            return_value=self.pay,
        ), mock.patch(
            "client.payment_entitlement.ensure_entitlement_for_connect",
            side_effect=lambda **kw: PaymentEntitlement(),
        ):
            ok, msg = assert_may_connect(self.lic)
        self.assertFalse(ok)
        self.assertEqual(msg, CONNECT_BLOCKED_KEYGEN_MSG)


class TestFirstRunWindowsEntryStructural(unittest.TestCase):
    def test_app_cold_start_uses_first_run_surface(self) -> None:
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("first_run_next_surface", src)
        self.assertIn("_present_first_run_surface", src)
        self.assertIn("_open_settings(first_run=True)", src)
        self.assertIn("post_keygen_next_surface", src)
        self.assertIn("Unlock installation", src)
        # Must not gate cold-start solely on may_connect (that skipped keygen)
        self.assertIn("_cold_start_first_run", src)
        self.assertNotIn(
            "elif not may_connect():",
            src,
        )
        # Demand keygen — refuse dismiss while unlock required
        self.assertIn("needs_keygen_unlock()", src)
        self.assertIn("Enter the keygen from your fulfilment email", src)

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

"""72h device trial + first-run surface order (shipped pure gates)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestDeviceTrialClock(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.path = Path(self._td.name) / "device_trial.json"
        os.environ["RPT_REQUIRE_PAYMENT_ENTITLEMENT"] = "1"

    def tearDown(self) -> None:
        self._td.cleanup()
        os.environ.pop("RPT_REQUIRE_PAYMENT_ENTITLEMENT", None)

    def test_not_started_allows_connect_and_full_remaining(self) -> None:
        from client.device_trial import (
            TRIAL_SECONDS,
            mark_first_successful_connect,
            trial_allows_residual_connect,
            trial_phase,
            trial_remaining_sec,
            DeviceTrialState,
            save_device_trial,
        )

        st = DeviceTrialState()
        save_device_trial(st, path=self.path)
        self.assertEqual(trial_phase(path=self.path, now=1_000.0), "not_started")
        self.assertTrue(trial_allows_residual_connect(path=self.path, now=1_000.0))
        rem = trial_remaining_sec(path=self.path, now=1_000.0)
        self.assertEqual(rem, float(TRIAL_SECONDS))
        self.assertEqual(TRIAL_SECONDS, 72 * 3600)

    def test_starts_only_on_first_successful_connect(self) -> None:
        from client.device_trial import (
            mark_first_successful_connect,
            trial_phase,
            trial_remaining_sec,
            load_device_trial,
        )

        t0 = 2_000_000.0
        mark_first_successful_connect(now=t0, path=self.path)
        st = load_device_trial(self.path)
        self.assertEqual(st.first_connect_at, t0)
        self.assertEqual(trial_phase(path=self.path, now=t0 + 10), "active")
        # Second connect does not move clock
        mark_first_successful_connect(now=t0 + 500, path=self.path)
        st2 = load_device_trial(self.path)
        self.assertEqual(st2.first_connect_at, t0)
        rem = trial_remaining_sec(path=self.path, now=t0 + 3600)
        self.assertAlmostEqual(rem, 72 * 3600 - 3600, places=0)

    def test_expired_blocks_trial_connect(self) -> None:
        from client.device_trial import (
            TRIAL_SECONDS,
            DeviceTrialState,
            save_device_trial,
            trial_allows_residual_connect,
            trial_phase,
        )

        t0 = 1_000_000.0
        save_device_trial(
            DeviceTrialState(first_connect_at=t0), path=self.path
        )
        after = t0 + TRIAL_SECONDS + 1
        self.assertEqual(trial_phase(path=self.path, now=after), "expired")
        self.assertFalse(trial_allows_residual_connect(path=self.path, now=after))


class TestFirstRunSurfacesWithTrial(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.lic = Path(self._td.name) / "licence_acceptance.json"
        self.pay = Path(self._td.name) / "payment_entitlement.json"
        self.trial = Path(self._td.name) / "device_trial.json"
        os.environ["RPT_REQUIRE_PAYMENT_ENTITLEMENT"] = "1"

    def tearDown(self) -> None:
        self._td.cleanup()
        os.environ.pop("RPT_REQUIRE_PAYMENT_ENTITLEMENT", None)

    def _patch_paths(self):
        return mock.patch.multiple(
            "client.payment_entitlement",
            default_entitlement_path=mock.Mock(return_value=self.pay),
        ), mock.patch(
            "client.device_trial.default_trial_path",
            return_value=self.trial,
        )

    def test_no_licence_is_licence(self) -> None:
        from client.first_run_flow import first_run_next_surface
        from client.licence_gate import clear_licence_acceptance

        clear_licence_acceptance(self.lic)
        self.assertEqual(first_run_next_surface(licence_path=self.lic), "licence")

    def test_licence_no_keygen_shows_step2(self) -> None:
        from client.first_run_flow import first_run_next_surface
        from client.licence_gate import accept_licence, needs_keygen_unlock
        from client.payment_entitlement import (
            PaymentEntitlement,
            save_payment_entitlement,
        )
        from client.device_trial import clear_device_trial

        accept_licence(self.lic)
        save_payment_entitlement(PaymentEntitlement(), path=self.pay)
        clear_device_trial(self.trial)
        with mock.patch(
            "client.payment_entitlement.default_entitlement_path",
            return_value=self.pay,
        ), mock.patch(
            "client.device_trial.default_trial_path",
            return_value=self.trial,
        ):
            # Trial not expired → KEYGEN not mandatory, but step 2 still shown
            self.assertFalse(needs_keygen_unlock(self.lic))
            self.assertEqual(
                first_run_next_surface(licence_path=self.lic), "keygen"
            )

    def test_trial_expired_keygen_mandatory(self) -> None:
        from client.device_trial import (
            TRIAL_SECONDS,
            DeviceTrialState,
            save_device_trial,
        )
        from client.licence_gate import accept_licence, needs_keygen_unlock
        from client.payment_entitlement import (
            PaymentEntitlement,
            save_payment_entitlement,
        )

        accept_licence(self.lic)
        save_payment_entitlement(PaymentEntitlement(), path=self.pay)
        save_device_trial(
            DeviceTrialState(first_connect_at=1.0), path=self.trial
        )
        with mock.patch(
            "client.payment_entitlement.default_entitlement_path",
            return_value=self.pay,
        ), mock.patch(
            "client.device_trial.default_trial_path",
            return_value=self.trial,
        ), mock.patch(
            "client.device_trial.time.time",
            return_value=1.0 + TRIAL_SECONDS + 10,
        ):
            self.assertTrue(needs_keygen_unlock(self.lic))

    def test_keygen_unlock_goes_to_main(self) -> None:
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
                first_run_next_surface(licence_path=self.lic), "main"
            )
            self.assertEqual(
                post_keygen_next_surface(licence_path=self.lic), "main"
            )

    def test_assert_may_connect_allows_trial(self) -> None:
        from client.licence_gate import accept_licence, assert_may_connect
        from client.payment_entitlement import (
            PaymentEntitlement,
            save_payment_entitlement,
        )
        from client.device_trial import clear_device_trial

        accept_licence(self.lic)
        save_payment_entitlement(PaymentEntitlement(), path=self.pay)
        clear_device_trial(self.trial)
        with mock.patch(
            "client.payment_entitlement.default_entitlement_path",
            return_value=self.pay,
        ), mock.patch(
            "client.device_trial.default_trial_path",
            return_value=self.trial,
        ), mock.patch(
            "client.payment_entitlement.ensure_entitlement_for_connect",
            side_effect=lambda **kw: PaymentEntitlement(),
        ), mock.patch(
            "client.payment_entitlement.connect_status_host_refresh_needed",
            return_value=False,
        ):
            ok, msg = assert_may_connect(self.lic)
        self.assertTrue(ok, msg)

    def test_assert_may_connect_refuses_revoked_even_with_open_trial(self) -> None:
        """Revoked/failed entitlement must not fall through to free trial."""
        from client.device_trial import clear_device_trial
        from client.licence_gate import accept_licence, assert_may_connect, may_connect
        from client.payment_entitlement import (
            STATUS_FAILED,
            STATUS_REVOKED,
            PaymentEntitlement,
            record_payment_failure,
            save_payment_entitlement,
        )

        accept_licence(self.lic)
        clear_device_trial(self.trial)
        for st in (STATUS_REVOKED, STATUS_FAILED):
            save_payment_entitlement(
                PaymentEntitlement(status=st, session_id="cs_dead", reason=st),
                path=self.pay,
            )
            with mock.patch(
                "client.payment_entitlement.default_entitlement_path",
                return_value=self.pay,
            ), mock.patch(
                "client.device_trial.default_trial_path",
                return_value=self.trial,
            ), mock.patch(
                "client.payment_entitlement.connect_status_host_refresh_needed",
                return_value=False,
            ):
                ok, msg = assert_may_connect(self.lic)
                self.assertFalse(
                    ok,
                    f"status={st} must block Connect (got ok with {msg!r})",
                )
                self.assertFalse(
                    may_connect(self.lic),
                    f"status={st} may_connect must be False",
                )

    def test_session_only_path_must_not_mark_trial_clock_in_app_source(self) -> None:
        """Structural: mark_first_successful_connect only under residual capture."""
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        # Isolate residual-success vs session-only branches
        i_resid = src.find("residual public IP uses the VPN node")
        i_session = src.find("session only (residual IPv4 off in Settings)")
        self.assertGreater(i_resid, 0)
        self.assertGreater(i_session, 0)
        # Between residual log and session-only branch: clock start present
        mid = src[i_resid:i_session]
        self.assertIn(
            "mark_first_successful_connect",
            mid,
            "trial clock must start on residual capture success",
        )
        # Session-only branch until next else: no clock start
        i_else = src.find("\n                    else:", i_session)
        session_branch = src[i_session:i_else if i_else > i_session else i_session + 800]
        self.assertNotIn(
            "mark_first_successful_connect",
            session_branch,
            "session-only Connect must not start 72h trial clock",
        )


class TestStep2UiWiring(unittest.TestCase):
    def test_app_step2_controls(self) -> None:
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("Continue trial", src)
        self.assertIn("Buy KEYGEN", src)
        self.assertIn("trial_status_blurb", src)
        self.assertIn("mark_first_successful_connect", src)
        self.assertIn("Unlock with KEYGEN", src)
        # Post-keygen lean path: main, not forced first-run Settings
        self.assertIn("post_keygen_next_surface", src)
        self.assertNotIn(
            "Keygen verified. Review Settings, then OK to open Connect.",
            src,
        )


if __name__ == "__main__":
    unittest.main()

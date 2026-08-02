"""KEYGEN-free 72h device trial: pure rules + host registry + paid isolation."""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

from device_trial import (  # noqa: E402
    TRIAL_SECONDS,
    claim_device_trial,
    connect_allowed_trial_or_paid,
    decide_trial_claim,
    get_device_trial_row,
    trial_is_active,
)


def _fake_pub(n: int = 1) -> str:
    return (f"{n:02x}" * 32)[:64]


class TestTrialPureRules(unittest.TestCase):
    def test_active_window_and_expiry(self) -> None:
        start = 1_000_000.0
        ends = start + TRIAL_SECONDS
        self.assertTrue(
            trial_is_active(
                started_at=start, ends_at=ends, status="active", now=start + 60
            )
        )
        self.assertFalse(
            trial_is_active(
                started_at=start, ends_at=ends, status="active", now=ends
            )
        )
        self.assertFalse(
            trial_is_active(
                started_at=start, ends_at=ends, status="expired", now=start + 1
            )
        )
        self.assertAlmostEqual(TRIAL_SECONDS, 72 * 3600)

    def test_decide_claim_create_reuse_deny(self) -> None:
        t0 = 2_000_000.0
        c = decide_trial_claim(None, now=t0)
        self.assertEqual(c["action"], "create")
        self.assertTrue(c["connect_allowed"])
        self.assertEqual(c["ends_at"], t0 + TRIAL_SECONDS)

        row = {
            "started_at": c["started_at"],
            "ends_at": c["ends_at"],
            "status": "active",
        }
        r = decide_trial_claim(row, now=t0 + 3600)
        self.assertEqual(r["action"], "reuse")
        self.assertTrue(r["connect_allowed"])
        self.assertEqual(r["ends_at"], c["ends_at"])  # no extension

        d = decide_trial_claim(row, now=c["ends_at"] + 1)
        self.assertEqual(d["action"], "deny")
        self.assertFalse(d["connect_allowed"])
        self.assertEqual(d["error"], "trial_exhausted")

    def test_paid_or_trial_decision(self) -> None:
        self.assertTrue(
            connect_allowed_trial_or_paid(
                keygen_connect_allowed=False, trial_connect_allowed=True
            )
        )
        self.assertTrue(
            connect_allowed_trial_or_paid(
                keygen_connect_allowed=True, trial_connect_allowed=False
            )
        )
        self.assertFalse(
            connect_allowed_trial_or_paid(
                keygen_connect_allowed=False, trial_connect_allowed=False
            )
        )


class TestTrialHostRegistry(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self._prev = os.environ.get("RPT_PAYMENT_DATA_DIR")
        os.environ["RPT_PAYMENT_DATA_DIR"] = self._td.name
        import payments

        payments.init_db()

    def tearDown(self) -> None:
        if self._prev is None:
            os.environ.pop("RPT_PAYMENT_DATA_DIR", None)
        else:
            os.environ["RPT_PAYMENT_DATA_DIR"] = self._prev
        self._td.cleanup()

    def test_claim_reuse_and_anti_reinstall(self) -> None:
        pub = _fake_pub(7)
        t0 = time.time()
        a = claim_device_trial(pub, now=t0)
        self.assertTrue(a["ok"], a)
        self.assertTrue(a["connect_allowed"])
        self.assertEqual(a["action"], "create")
        ends = float(a["ends_at"])

        # Same device_pub re-claim (sim reinstall prefs wipe, same keystore pub)
        b = claim_device_trial(pub, now=t0 + 100)
        self.assertTrue(b["connect_allowed"])
        self.assertEqual(b["action"], "reuse")
        self.assertEqual(float(b["ends_at"]), ends)

        # After expiry — no second full 72h
        c = claim_device_trial(pub, now=ends + 5)
        self.assertFalse(c["connect_allowed"])
        self.assertEqual(c.get("error"), "trial_exhausted")
        self.assertTrue(c.get("requires_keygen"))

        row = get_device_trial_row(pub, now=ends + 5)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertFalse(row["connect_allowed"])

    def test_get_device_entitlement_trial_and_paid_isolation(self) -> None:
        import payments

        pub = _fake_pub(9)
        t0 = time.time()
        claim_device_trial(pub, now=t0)
        ent = payments.get_device_entitlement(pub, now=t0 + 10)
        self.assertTrue(ent.get("connect_allowed"), ent)
        self.assertEqual(ent.get("kind"), "device_trial")
        self.assertEqual(ent.get("keygen") or "", "")

        # Paid bind present but not active must not fall through to free trial.
        sid = "cs_test_paid_only"
        conn = payments._connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO connect_entitlements"
                "(session_id, status, platform, reason, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?)",
                (sid, "failed", "macos", "test_fail", t0, t0),
            )
            conn.execute(
                "INSERT OR REPLACE INTO device_entitlements"
                "(device_pub_hex, session_id, created_at, updated_at) VALUES (?,?,?,?)",
                (pub, sid, t0, t0),
            )
        finally:
            conn.close()
        ent2 = payments.get_device_entitlement(pub, now=t0 + 20)
        self.assertFalse(ent2.get("connect_allowed"), ent2)
        self.assertEqual(ent2.get("kind"), "paid")


class TestTrialPrivacySurface(unittest.TestCase):
    def test_claim_api_fields_have_no_email_card(self) -> None:
        src = (ROOT / "status_page" / "device_trial.py").read_text(encoding="utf-8")
        self.assertNotIn("customer_email", src)
        self.assertIn("device_pub_hex", src)
        self.assertIn("TRIAL_SECONDS", src)
        self.assertIn("no email", src.lower())
        app = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("/api/device-trial/claim", app)
        self.assertIn("device-trial", app)


if __name__ == "__main__":
    unittest.main()

"""Success-page recovery when Stripe webhook grant is missing."""

from __future__ import annotations

import json
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

from downloads import RELEASE_VERSION  # noqa: E402
from payments import (  # noqa: E402
    PRICE_CURRENCY,
    PRICE_PENCE,
    ensure_download_grant_for_paid_session,
    find_grant_by_session,
    paid_session_needs_platform_picker,
    platform_from_stripe_checkout_session,
    resolve_platform_from_checkout_session,
)


def _paid_session(
    *,
    session_id: str = "cs_test_recovery_1",
    platform: str = "windows",
    amount: int | None = None,
) -> dict:
    return {
        "id": session_id,
        "payment_status": "paid",
        "amount_total": PRICE_PENCE if amount is None else amount,
        "currency": PRICE_CURRENCY,
        "client_reference_id": platform,
        "metadata": {},
    }


class TestEnsureGrantFromStripeSession(unittest.TestCase):
    def test_mints_when_webhook_missed(self):
        sid = f"cs_test_recovery_mint_{uuid.uuid4().hex[:12]}"
        sess = _paid_session(session_id=sid, platform="linux")

        def fake_get(url: str, headers: dict) -> tuple[int, bytes]:
            self.assertIn(sid, url)
            self.assertIn("Bearer", headers.get("Authorization", ""))
            return 200, json.dumps(sess).encode("utf-8")

        with mock.patch("payments.stripe_secret_key", return_value="sk_test_x"):
            self.assertIsNone(find_grant_by_session(sid))
            grant = ensure_download_grant_for_paid_session(
                sid, http_get=fake_get, secret_key="sk_test_x"
            )
        self.assertIsNotNone(grant)
        assert grant is not None
        self.assertEqual(grant["platform"], "linux")
        self.assertIn(RELEASE_VERSION, grant["filename"])
        self.assertTrue(grant["token"])

    def test_platform_hint_when_reference_empty(self):
        sid = f"cs_test_recovery_hint_{uuid.uuid4().hex[:12]}"
        sess = _paid_session(session_id=sid, platform="")
        sess["client_reference_id"] = ""

        def fake_get(url: str, headers: dict) -> tuple[int, bytes]:
            return 200, json.dumps(sess).encode("utf-8")

        with mock.patch("payments.stripe_secret_key", return_value="sk_test_x"):
            grant = ensure_download_grant_for_paid_session(
                sid,
                platform_hint="android",
                http_get=fake_get,
                secret_key="sk_test_x",
            )
        self.assertIsNotNone(grant)
        assert grant is not None
        self.assertEqual(grant["platform"], "android")

    def test_unpaid_does_not_mint(self):
        sid = f"cs_test_recovery_unpaid_{uuid.uuid4().hex[:12]}"
        sess = _paid_session(session_id=sid)
        sess["payment_status"] = "unpaid"

        def fake_get(url: str, headers: dict) -> tuple[int, bytes]:
            return 200, json.dumps(sess).encode("utf-8")

        with mock.patch("payments.stripe_secret_key", return_value="sk_test_x"):
            grant = ensure_download_grant_for_paid_session(
                sid, http_get=fake_get, secret_key="sk_test_x"
            )
        self.assertIsNone(grant)

    def test_needs_platform_picker(self):
        sid = f"cs_test_picker_{uuid.uuid4().hex[:12]}"
        sess = _paid_session(session_id=sid, platform="")
        sess["client_reference_id"] = ""

        def fake_get(url: str, headers: dict) -> tuple[int, bytes]:
            return 200, json.dumps(sess).encode("utf-8")

        with mock.patch("payments.stripe_secret_key", return_value="sk_test_x"):
            self.assertTrue(
                paid_session_needs_platform_picker(
                    sid, http_get=fake_get, secret_key="sk_test_x"
                )
            )

    def test_platform_from_session_client_reference(self):
        sess = _paid_session(platform="macos")
        self.assertEqual(platform_from_stripe_checkout_session(sess), "macos")
        sess["client_reference_id"] = ""
        sess["metadata"] = {"platform": "ios"}
        self.assertEqual(platform_from_stripe_checkout_session(sess), "ios")
        sess["metadata"] = {}
        self.assertEqual(platform_from_stripe_checkout_session(sess), "")

    def test_resolve_platform_from_checkout_session(self):
        sid = f"cs_test_resolve_plat_{uuid.uuid4().hex[:12]}"
        sess = _paid_session(session_id=sid, platform="linux")

        def fake_get(url: str, headers: dict) -> tuple[int, bytes]:
            return 200, json.dumps(sess).encode("utf-8")

        with mock.patch("payments.stripe_secret_key", return_value="sk_test_x"):
            self.assertEqual(
                resolve_platform_from_checkout_session(
                    sid, http_get=fake_get, secret_key="sk_test_x"
                ),
                "linux",
            )


if __name__ == "__main__":
    unittest.main()

"""Time-limited (1 hour) download grants: multi-fetch within TTL, deny after expiry.

Drives shipped mint/lookup/consume and thank-you / how-to-buy buyer copy.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

import payments as pay  # noqa: E402
from public_docs import render_how_to_buy_html  # noqa: E402


class TestDownloadTokenTtlReuse(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        os.environ["RPT_PAYMENT_DATA_DIR"] = self._td.name
        pay.init_db()
        self._t0 = 1_700_000_000.0

    def tearDown(self) -> None:
        self._td.cleanup()
        os.environ.pop("RPT_PAYMENT_DATA_DIR", None)

    def _mint(self) -> str:
        assets = pay.available_downloads()
        a = assets[0]
        return pay.mint_download_token(
            filename=a.filename,
            platform=a.platform,
            session_id="cs_ttl_reuse",
            ttl_sec=pay.TOKEN_TTL_SEC,
            now=self._t0,
        )

    def test_default_ttl_is_one_hour(self):
        self.assertEqual(pay.TOKEN_TTL_SEC, 3600)
        self.assertEqual(pay.DOWNLOAD_LINK_TTL_HOURS, 1)

    def test_multi_lookup_and_consume_within_ttl(self):
        tok = self._mint()
        g1 = pay.lookup_download_token(tok, now=self._t0 + 1)
        self.assertIsNotNone(g1)
        self.assertTrue(pay.consume_download_token(tok, now=self._t0 + 2))
        # Second allow after "use" — still within 1 hour of mint
        g2 = pay.lookup_download_token(tok, now=self._t0 + 60)
        self.assertIsNotNone(g2)
        self.assertTrue(pay.consume_download_token(tok, now=self._t0 + 61))
        r3 = pay.redeem_download_token(tok, now=self._t0 + 120)
        self.assertIsNotNone(r3)
        # Just before expiry still ok
        near = self._t0 + pay.TOKEN_TTL_SEC - 1
        self.assertIsNotNone(pay.lookup_download_token(tok, now=near))

    def test_deny_after_expires_at(self):
        tok = self._mint()
        self.assertTrue(pay.consume_download_token(tok, now=self._t0 + 1))
        past = self._t0 + pay.TOKEN_TTL_SEC + 1
        self.assertIsNone(pay.lookup_download_token(tok, now=past))
        self.assertFalse(pay.consume_download_token(tok, now=past))
        self.assertIsNone(pay.redeem_download_token(tok, now=past))

    def test_thankyou_and_howto_advise_one_hour_retry_not_once(self):
        html = pay.render_post_payment_thankyou_html(
            download_path="/download?token=tok_ttl_copy",
            filename="restore-privacy-client-0.5.7-windows-x64-setup.exe",
            platform="windows",
            session_id="cs_ttl_copy",
            purchase_id="RPT-TEST-TTTT-TTTT",
            keygen="RPT-KEY-TEST-TTL",
        )
        self.assertIn("download-lifetime-note", html)
        self.assertIn("1 hour", html)
        self.assertIn("connection drops", html.lower())
        self.assertIn(str(pay.DOWNLOAD_LINK_TTL_HOURS), html)
        self.assertNotIn("grant is one-time", html.lower())
        self.assertNotIn("one-time (security)", html.lower())
        low = html.lower()
        # Must not claim single-use after successful download
        self.assertNotIn("after a successful download the grant is one-time", low)

        howto = render_how_to_buy_html().decode("utf-8")
        self.assertIn("1 hour", howto)
        self.assertIn("connection drops", howto.lower())
        self.assertNotIn("works\n      <strong>once</strong>", howto)
        self.assertNotIn("The link works\n      <strong>once</strong>", howto)
        # Residual "once" from "subscription starts when you pay" style is ok;
        # explicit single-use download claim must be gone.
        self.assertNotIn("works <strong>once</strong>", howto.replace("\n", " "))

    def test_denied_copy_omits_already_used(self):
        self.assertNotIn("already-used", pay.DOWNLOAD_DENIED_MSG.lower())
        self.assertNotIn("already used", pay.DOWNLOAD_DENIED_MSG.lower())
        self.assertIn("hour", pay.DOWNLOAD_DENIED_MSG.lower())
        self.assertIn(pay.DOWNLOAD_LINK_VALIDITY_ADVICE[:20], pay.DOWNLOAD_LINK_VALIDITY_ADVICE)

    def test_product_docs_drop_one_time_download_claims(self):
        """Shipped product docs no longer describe download tokens as one-time."""
        root = Path(__file__).resolve().parents[1]
        howto = (root / "status_page" / "docs" / "PAID_DOWNLOADS_HOWTO.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("1-hour reusable", howto)
        self.assertNotIn("Shows a **one-time** link", howto)
        self.assertNotIn("Single-use **proxy** download", howto)
        self.assertIn("1-hour reusable proxy", howto.lower().replace("**", ""))
        readme = (root / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("one-time link after payment", readme)
        self.assertIn("1-hour download link after payment", readme)
        public_readme = (
            root / "status_page" / "public" / "README.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn("one-time link after payment", public_readme)
        admin = (root / "status_page" / "admin_panel.py").read_text(encoding="utf-8")
        self.assertIn("1-hour reusable", admin)
        self.assertNotIn("Pass this <strong>one-time</strong> link", admin)
        self.assertNotIn("open the one-time URL", admin)
        self.assertNotIn("One-time paid download", admin)
        self.assertNotIn("after consuming the token", admin)
        privacy = (root / "PRIVACY_POLICY.md").read_text(encoding="utf-8")
        self.assertNotIn("One-time download links will not reappear", privacy)
        self.assertIn("Time-limited (1 hour) download links", privacy)
        pub_privacy = (
            root / "status_page" / "public" / "PRIVACY_POLICY.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn("One-time download links will not reappear", pub_privacy)
        self.assertIn("Time-limited (1 hour) download links", pub_privacy)


if __name__ == "__main__":
    unittest.main()

"""Status-host security headers: real Handler responses + CSP / download contracts."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

import app as status_app  # noqa: E402
import security_headers as sh  # noqa: E402


EXPECTED = {
    "Strict-Transport-Security": sh.STRICT_TRANSPORT_SECURITY,
    "Content-Security-Policy": sh.CONTENT_SECURITY_POLICY,
    "X-Frame-Options": sh.X_FRAME_OPTIONS,
    "X-Content-Type-Options": sh.X_CONTENT_TYPE_OPTIONS,
    "Referrer-Policy": sh.REFERRER_POLICY,
    "Permissions-Policy": sh.PERMISSIONS_POLICY,
}


class TestSecurityHeaderConstants(unittest.TestCase):
    def test_six_document_headers_match_probe(self):
        pairs = dict(sh.security_headers(allow_framing=False))
        for name, value in EXPECTED.items():
            self.assertEqual(pairs[name], value, msg=name)
        self.assertEqual(set(pairs.keys()), set(EXPECTED.keys()))

    def test_form_action_allows_stripe_checkout_redirect_hosts(self):
        """Buy now POST → 302 Checkout needs Stripe hosts in form-action (Chrome)."""
        csp = sh.CONTENT_SECURITY_POLICY
        frameable = sh.CONTENT_SECURITY_POLICY_FRAMEABLE
        for policy in (csp, frameable, sh.FORM_ACTION_DIRECTIVE):
            self.assertIn("form-action", policy)
            self.assertIn("'self'", policy)
            self.assertIn("https://pay.restoreprivacy.online", policy)
            self.assertIn("https://checkout.stripe.com", policy)
            self.assertIn("https://buy.stripe.com", policy)
        # Still not a wildcard form-action
        self.assertNotIn("form-action *", csp)
        self.assertNotIn("form-action 'self' *", csp)
        # Checkout hosts must appear only in form-action, not as script/connect widen
        self.assertNotIn("script-src 'self' https://checkout.stripe.com", csp)
        self.assertIn(sh.FORM_ACTION_DIRECTIVE, csp)
        self.assertIn(sh.FORM_ACTION_DIRECTIVE, frameable)

    def test_frameable_omits_xfo_deny_uses_self_ancestors(self):
        pairs = dict(sh.security_headers(allow_framing=True))
        self.assertNotIn("X-Frame-Options", pairs)
        self.assertIn("frame-ancestors 'self'", pairs["Content-Security-Policy"])
        self.assertNotIn(
            "frame-ancestors 'none'", pairs["Content-Security-Policy"]
        )
        self.assertEqual(
            pairs["Strict-Transport-Security"], EXPECTED["Strict-Transport-Security"]
        )
        self.assertIn(
            "https://pay.restoreprivacy.online",
            pairs["Content-Security-Policy"],
        )


class TestHandlerSecurityHeaders(unittest.TestCase):
    def setUp(self):
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), status_app.Handler)
        self._port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def tearDown(self):
        self._httpd.shutdown()
        self._httpd.server_close()

    def _open(self, path: str):
        url = f"http://127.0.0.1:{self._port}{path}"
        return urllib.request.urlopen(url, timeout=8)

    def _assert_document_headers(self, headers) -> None:
        for name, value in EXPECTED.items():
            got = headers.get(name)
            self.assertEqual(
                got,
                value,
                msg=f"{name}: got {got!r} want {value!r}",
            )

    def test_public_html_has_six_headers(self):
        with mock.patch.object(
            status_app,
            "fetch_upstream_status",
            return_value={"title": "RESTORE PRIVACY VPN", "upstream_ok": True},
        ):
            with self._open("/") as resp:
                body = resp.read().decode("utf-8")
                self._assert_document_headers(resp.headers)
                self.assertIn("RESTORE PRIVACY", body)
                # CSP script-src 'self' only (no unsafe-inline scripts)
                csp = resp.headers.get("Content-Security-Policy") or ""
                self.assertIn("script-src 'self'", csp)
                self.assertNotIn("script-src 'self' 'unsafe-inline'", csp)
                self.assertIn('src="/static/public_theme.js"', body)

    def test_admin_login_html_has_six_headers(self):
        # Admin may be disabled without credentials — still HTML login or plain.
        os.environ.setdefault("RPT_ADMIN_PASSWORD", "test-security-headers-pw")
        os.environ.setdefault("RPT_ADMIN_SESSION_SECRET", "test-sec-headers-session")
        with self._open("/admin") as resp:
            self._assert_document_headers(resp.headers)
            ctype = resp.headers.get("Content-Type") or ""
            self.assertIn("text/html", ctype)
            body = resp.read().decode("utf-8")
            self.assertTrue(
                "admin-theme-script" in body or "admin" in body.lower(),
                msg="admin HTML path",
            )

    def test_static_theme_js_served_same_origin(self):
        with self._open("/static/public_theme.js") as resp:
            self.assertEqual(resp.status, 200)
            ctype = resp.headers.get("Content-Type") or ""
            self.assertIn("javascript", ctype.lower())
            body = resp.read().decode("utf-8")
            self.assertIn("localStorage", body)
            self.assertIn("data-theme", body)
            # Static also gets security headers (document framing deny ok)
            self.assertEqual(
                resp.headers.get("X-Content-Type-Options"),
                "nosniff",
            )
            csp = resp.headers.get("Content-Security-Policy") or ""
            self.assertIn("script-src 'self'", csp)

    def test_thankyou_html_manual_download_and_external_scripts(self):
        from payments import render_post_payment_thankyou_html

        html = render_post_payment_thankyou_html(
            download_path="/download?token=tok_sec_hdr",
            filename="restore-privacy-client-0.5.1-windows-x64-setup.exe",
            platform="windows",
            session_id="cs_sec_hdr",
            purchase_id="RPT-SECH-EADR-TEST",
            keygen="RPT-KEY-SECH-EADR-TEST",
        )
        self.assertIn('id="success-download-link"', html)
        self.assertIn('href="/download?token=tok_sec_hdr"', html)
        self.assertIn('data-manual-download="1"', html)
        self.assertIn('id="auto-download-frame"', html)
        self.assertIn('src="/download?token=tok_sec_hdr"', html)
        self.assertIn("/static/thankyou_keygen_copy.js", html)
        self.assertNotIn("<script>\n", html)
        self.assertNotIn("<script>", html.replace(
            '<script id="thankyou-keygen-copy-script"', ""
        ).replace('<script id="thankyou-entitlement-script"', ""))

    def test_paid_download_response_allows_same_origin_framing(self):
        """Binary /download must not send X-Frame-Options DENY (iframe auto-start)."""
        from downloads import RELEASE_VERSION

        tok = "tok_frame_allow_test"
        fname = f"restore-privacy-client-{RELEASE_VERSION}-windows-x64-setup.exe"
        payload = b"MZ-fake-installer-for-header-test"
        grant = {
            "token": tok,
            "filename": fname,
            "platform": "windows",
            "session_id": "cs_frame_test",
        }
        asset = {
            "body": payload,
            "content_type": "application/octet-stream",
            "content_length": len(payload),
            "source": "test",
        }
        with mock.patch.object(
            status_app, "lookup_download_token", return_value=grant
        ), mock.patch.object(
            status_app, "open_release_asset", return_value=asset
        ), mock.patch.object(
            status_app, "consume_download_token", return_value=True
        ):
            url = f"http://127.0.0.1:{self._port}/download?token={tok}"
            with urllib.request.urlopen(url, timeout=8) as resp:
                headers = resp.headers
                body = resp.read()
            self.assertIsNone(headers.get("X-Frame-Options"))
            csp = headers.get("Content-Security-Policy") or ""
            self.assertIn("frame-ancestors 'self'", csp)
            self.assertNotIn("frame-ancestors 'none'", csp)
            self.assertEqual(
                headers.get("Strict-Transport-Security"),
                EXPECTED["Strict-Transport-Security"],
            )
            self.assertEqual(
                headers.get("X-Content-Type-Options"),
                EXPECTED["X-Content-Type-Options"],
            )
            self.assertEqual(body, payload)


if __name__ == "__main__":
    unittest.main()

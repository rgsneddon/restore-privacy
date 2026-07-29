"""Admin authenticator (TOTP) 2FA: enroll, verify, no password-only full session."""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib import error, parse, request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestTotpPure(unittest.TestCase):
    def test_totp_rfc_known_vector_shape_and_roundtrip(self) -> None:
        from admin_2fa import (
            generate_totp_secret,
            totp_code_at,
            verify_totp,
            otpauth_uri,
        )

        secret = generate_totp_secret()
        self.assertGreaterEqual(len(secret), 16)
        t = 1_700_000_000.0
        code = totp_code_at(secret, t)
        self.assertRegex(code, r"^\d{6}$")
        self.assertTrue(verify_totp(secret, code, now=t))
        self.assertFalse(verify_totp(secret, "000000", now=t))
        self.assertFalse(verify_totp(secret, "abcdef", now=t))
        uri = otpauth_uri(secret, account="admin")
        self.assertTrue(uri.startswith("otpauth://totp/"))
        self.assertIn(secret, uri)
        self.assertIn("period=30", uri)


class TestAdmin2faAuthPath(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self._prev = {
            k: os.environ.get(k)
            for k in (
                "RPT_PAYMENT_DATA_DIR",
                "RPT_ADMIN_PASSWORD",
                "RPT_ADMIN_USER",
                "RPT_ADMIN_SESSION_SECRET",
                "RPT_ADMIN_DISABLE_BOOTSTRAP",
                "RPT_PUBLIC_BASE_URL",
                "RPT_ADMIN_COOKIE_SECURE",
            )
        }
        os.environ["RPT_PAYMENT_DATA_DIR"] = self._td.name
        os.environ["RPT_ADMIN_PASSWORD"] = "test-2fa-password-not-real"
        os.environ["RPT_ADMIN_USER"] = "admin"
        os.environ["RPT_ADMIN_SESSION_SECRET"] = "test-session-secret-for-2fa-unit"
        os.environ["RPT_ADMIN_DISABLE_BOOTSTRAP"] = "1"
        os.environ["RPT_PUBLIC_BASE_URL"] = "https://restoreprivacy.online"
        os.environ.pop("RPT_ADMIN_COOKIE_SECURE", None)
        from admin_2fa import clear_totp_enrollment_for_tests

        clear_totp_enrollment_for_tests()

    def tearDown(self) -> None:
        for k, v in self._prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._td.cleanup()

    def test_enroll_then_password_requires_totp(self) -> None:
        from admin_2fa import (
            begin_login_after_password,
            complete_setup,
            complete_verify,
            is_totp_enrolled,
            totp_code_at,
            verify_pending_token,
        )
        from admin_panel import (
            is_authenticated,
            mint_session_token,
            verify_session_token,
            format_session_cookie,
            SESSION_COOKIE,
            ADMIN_2FA_SECURITY_BLURB,
            render_login_html,
            render_2fa_setup_html,
            render_2fa_verify_html,
        )

        self.assertFalse(is_totp_enrolled())
        step = begin_login_after_password(now=1_700_000_000.0)
        self.assertEqual(step["stage"], "setup")
        pending = step["pending_token"]
        secret = step["secret_b32"]
        self.assertTrue(secret)
        # Password path must not mint full session
        info = verify_pending_token(pending, now=1_700_000_000.0, expect_stage="setup")
        self.assertIsNotNone(info)
        self.assertFalse(verify_session_token(pending))

        code = totp_code_at(secret, 1_700_000_000.0)
        complete_setup(pending, code, now=1_700_000_000.0)
        self.assertTrue(is_totp_enrolled())

        # Second login: verify stage
        step2 = begin_login_after_password(now=1_700_000_100.0)
        self.assertEqual(step2["stage"], "verify")
        pending2 = step2["pending_token"]
        bad = complete_verify
        with self.assertRaises(ValueError):
            bad(pending2, "000000", now=1_700_000_100.0)
        # pending still valid after failed attempt? consume only on success — yes
        good_code = totp_code_at(
            __import__("admin_2fa", fromlist=["get_enrolled_secret"]).get_enrolled_secret(),
            1_700_000_100.0,
        )
        complete_verify(pending2, good_code, now=1_700_000_100.0)
        full = mint_session_token(now=1_700_000_100.0)
        self.assertTrue(verify_session_token(full, now=1_700_000_100.0))

        # Cookie hygiene
        sc = format_session_cookie(full)
        self.assertIn("HttpOnly", sc)
        self.assertIn("SameSite=Strict", sc)
        self.assertIn("Secure", sc)
        self.assertIn(SESSION_COOKIE + "=", sc)

        # HTML: blurb + no secret on login; setup has secret only when passed
        login = render_login_html().decode("utf-8")
        self.assertIn(ADMIN_2FA_SECURITY_BLURB[:40], login)
        self.assertIn("admin-2fa-security-blurb", login)
        self.assertNotIn(secret, login)
        setup = render_2fa_setup_html(secret_b32=secret).decode("utf-8")
        self.assertIn(secret, setup)
        self.assertIn("admin-2fa-setup-form", setup)
        self.assertIn("otpauth://", setup)
        verify_html = render_2fa_verify_html().decode("utf-8")
        self.assertIn("admin-2fa-verify-form", verify_html)
        self.assertNotIn(secret, verify_html)

    def test_http_login_does_not_grant_admin_without_2fa(self) -> None:
        import re
        from http.cookiejar import CookieJar

        import app as status_app
        from admin_2fa import (
            clear_totp_enrollment_for_tests,
            is_totp_enrolled,
            totp_code_at,
        )

        clear_totp_enrollment_for_tests()
        # Local HTTP: do not require Secure cookie for jar to keep session
        os.environ["RPT_PUBLIC_BASE_URL"] = "http://127.0.0.1"
        os.environ["RPT_ADMIN_COOKIE_SECURE"] = "0"

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), status_app.Handler)
        port = httpd.server_address[1]
        thr = Thread(target=httpd.serve_forever, daemon=True)
        thr.start()
        data = parse.urlencode(
            {
                "username": "admin",
                "password": "test-2fa-password-not-real",
            }
        ).encode()
        try:
            with request.urlopen(f"http://127.0.0.1:{port}/admin", timeout=5) as resp:
                body = resp.read().decode("utf-8")
            self.assertIn("admin-login-form", body)
            self.assertNotIn("admin-grants-table", body)

            jar = CookieJar()
            opener = request.build_opener(request.HTTPCookieProcessor(jar))
            r2 = opener.open(
                request.Request(
                    f"http://127.0.0.1:{port}/admin/login",
                    data=data,
                    method="POST",
                ),
                timeout=5,
            )
            setup_body = r2.read().decode("utf-8")
            self.assertIn("admin-2fa-setup-form", setup_body)
            names = {c.name for c in jar}
            self.assertIn("rpt_admin_pending", names)
            self.assertNotIn("rpt_admin_session", names)

            m = re.search(
                r'id="admin-2fa-secret"[^>]*>\s*([A-Z2-7]+)\s*<', setup_body
            )
            self.assertIsNotNone(m, setup_body[:800])
            secret = m.group(1)
            code = totp_code_at(secret, time.time())
            # May be 302 — HTTPRedirectHandler follows by default
            opener.open(
                request.Request(
                    f"http://127.0.0.1:{port}/admin/2fa/setup",
                    data=parse.urlencode({"totp_code": code}).encode(),
                    method="POST",
                ),
                timeout=5,
            )
            names2 = {c.name for c in jar}
            self.assertIn("rpt_admin_session", names2)
            self.assertTrue(is_totp_enrolled())

            home = opener.open(
                f"http://127.0.0.1:{port}/admin", timeout=5
            ).read().decode("utf-8")
            self.assertIn("admin-sidebar", home)
            self.assertNotIn("admin-login-form", home)

            # Wrong TOTP after re-login does not grant full session
            jar2 = CookieJar()
            op2 = request.build_opener(request.HTTPCookieProcessor(jar2))
            op2.open(
                request.Request(
                    f"http://127.0.0.1:{port}/admin/login",
                    data=data,
                    method="POST",
                ),
                timeout=5,
            )
            denied = False
            try:
                op2.open(
                    request.Request(
                        f"http://127.0.0.1:{port}/admin/2fa/verify",
                        data=parse.urlencode({"totp_code": "000000"}).encode(),
                        method="POST",
                    ),
                    timeout=5,
                )
            except error.HTTPError as e:
                denied = e.code == 401
                self.assertIn("admin-2fa-verify", e.read().decode("utf-8"))
            self.assertTrue(denied)
            self.assertNotIn("rpt_admin_session", {c.name for c in jar2})
            blocked = op2.open(
                f"http://127.0.0.1:{port}/admin", timeout=5
            ).read().decode("utf-8")
            self.assertIn("admin-login-form", blocked)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_structure_routes_and_cookie_helper(self) -> None:
        app = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("/admin/2fa/setup", app)
        self.assertIn("/admin/2fa/verify", app)
        self.assertIn("begin_login_after_password", app)
        self.assertIn("complete_setup", app)
        self.assertIn("complete_verify", app)
        self.assertIn("format_session_cookie", app)
        self.assertNotIn(
            'f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax',
            app,
        )
        from admin_panel import format_session_cookie, admin_cookie_secure

        os.environ["RPT_PUBLIC_BASE_URL"] = "https://example.com"
        self.assertTrue(admin_cookie_secure())
        c = format_session_cookie("tok")
        self.assertIn("HttpOnly", c)
        self.assertIn("Secure", c)
        self.assertIn("SameSite=Strict", c)


if __name__ == "__main__":
    unittest.main()

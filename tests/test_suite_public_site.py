"""Public Suite v1.0.0 website: branding, free/KEYGEN story, admin isolation."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestSuitePublicBrand(unittest.TestCase):
    def test_render_html_suite_identity_and_free_keygen(self) -> None:
        from app import render_html
        from public_chrome import (
            PUBLIC_BRAND_DISPLAY,
            PUBLIC_BRAND_TITLE,
            PUBLIC_BRAND_VERSION,
            SUITE_HOME_INTRO_BODY,
        )

        html = render_html({"title": PUBLIC_BRAND_TITLE}).decode("utf-8")
        # Dedicated VPN product — not multi-product Suite pitch
        self.assertIn("Restore Privacy", html)
        self.assertNotIn("Restore Privacy Suite", html)
        self.assertIn(PUBLIC_BRAND_VERSION, html)
        self.assertIn(PUBLIC_BRAND_DISPLAY.split()[0], html)  # Restore
        self.assertIn("suite-home-intro", html)
        self.assertIn(SUITE_HOME_INTRO_BODY[:40], html)
        self.assertIn("virtual private network", html.lower())
        self.assertNotIn("fun rewards token wallet", html)
        self.assertNotIn("Evolve analysis engine", html)
        self.assertNotIn("RPSuite extras", html)
        self.assertIn("£3", html)
        self.assertIn("£30", html)
        self.assertIn(".:WELCOME, ANON:.", html)
        self.assertIn("YOUR PRIVACY, RESTORED", html)
        self.assertNotIn("mothly sunscription", html)
        self.assertIn("suite-storefront", html)
        self.assertIn("data-free-download", html)
        self.assertIn("KEYGEN", html)
        self.assertNotIn(">RESTORE PRIVACY VPN<", html)
        self.assertNotIn("paywall", html.lower())
        # Homepage is not the operator console
        self.assertNotIn("admin-login-form", html)
        self.assertNotIn("OPERATOR ADMIN PAGES", html)

    def test_display_title_maps_legacy_vpn_to_suite(self) -> None:
        from public_chrome import PUBLIC_BRAND_TITLE, public_display_title

        self.assertEqual(public_display_title("RESTORE PRIVACY"), PUBLIC_BRAND_TITLE)
        self.assertEqual(public_display_title("RESTORE PRIVACY VPN"), PUBLIC_BRAND_TITLE)
        self.assertEqual(public_display_title(""), PUBLIC_BRAND_TITLE)


class TestPublicSiteCopyHuman(unittest.TestCase):
    def test_intro_not_mechanical_inventory(self) -> None:
        from public_chrome import (
            SUITE_HOME_INTRO_BODY,
            SUITE_HOME_INTRO_FOOT,
            SUITE_HOME_INTRO_HEADING,
            render_suite_home_intro_html,
        )

        body = render_suite_home_intro_html()
        self.assertIn(SUITE_HOME_INTRO_HEADING, body)
        self.assertIn(SUITE_HOME_INTRO_BODY, body)
        # Foot retired in favour of closing typewriter line
        self.assertEqual(SUITE_HOME_INTRO_FOOT, "")
        self.assertIn("YOUR PRIVACY, RESTORED", body)
        # Human VPN intro: personal use + free trial + subscription price once
        self.assertTrue(
            SUITE_HOME_INTRO_BODY.startswith("Restore Privacy is a virtual private network"),
            msg=f"intro open clause: {SUITE_HOME_INTRO_BODY!r}",
        )
        self.assertIn("personal use", SUITE_HOME_INTRO_BODY)
        self.assertIn("no obligation to pay", SUITE_HOME_INTRO_BODY)
        self.assertIn("subscription", SUITE_HOME_INTRO_BODY)
        self.assertIn("£3", SUITE_HOME_INTRO_BODY)
        self.assertIn("£30", SUITE_HOME_INTRO_BODY)
        self.assertIn("three days", SUITE_HOME_INTRO_BODY.lower())
        # Old lead wording must not remain
        self.assertNotIn(
            "Download free below, try three days with no card, then keep going",
            SUITE_HOME_INTRO_BODY,
        )
        # No multi-product pitch
        self.assertNotIn("fun rewards token wallet", SUITE_HOME_INTRO_BODY)
        self.assertNotIn("RPSuite extras", SUITE_HOME_INTRO_BODY)
        self.assertNotIn("The Restore Privacy Suite", SUITE_HOME_INTRO_BODY)
        self.assertNotIn("mothly sunscription", SUITE_HOME_INTRO_BODY)
        # Closing typewriter owns the all-caps tagline
        self.assertNotIn("your privacy, restored", SUITE_HOME_INTRO_BODY.lower())
        # Anti-patterns: dense residual laundry as lead voice
        for bad in (
            "178.105.187.178",
            "82.221.101.241",
            "RPT_MULTIHOP",
            "residual-via-exit",
            "monopin",
        ):
            self.assertNotIn(bad, SUITE_HOME_INTRO_BODY)
            self.assertNotIn(bad, SUITE_HOME_INTRO_HEADING)
        self.assertGreater(len(SUITE_HOME_INTRO_BODY), 40)
        self.assertTrue(
            "free" in SUITE_HOME_INTRO_BODY.lower()
            or "Download" in SUITE_HOME_INTRO_BODY
        )


class TestAdminNotOnPublicPages(unittest.TestCase):
    def test_build_public_pages_excludes_admin(self) -> None:
        script = ROOT / "scripts" / "build_public_pages.py"
        out = ROOT / "public_site"
        r = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((out / "index.html").is_file())
        idx = (out / "index.html").read_text(encoding="utf-8")
        self.assertIn("Restore Privacy", idx)
        self.assertNotIn("Restore Privacy Suite", idx)
        from public_chrome import PUBLIC_BRAND_VERSION

        self.assertIn(PUBLIC_BRAND_VERSION, idx)
        self.assertIn("KEYGEN", idx)
        self.assertIn("£3", idx)
        # No admin console artifacts
        for p in out.rglob("*"):
            if not p.is_file():
                continue
            name = p.name.lower()
            self.assertFalse(name.startswith("admin_"), p)
            raw = p.read_bytes().lower()
            self.assertNotIn(b"admin-login-form", raw)
            self.assertNotIn(b"operator admin pages", raw)
            self.assertNotIn(b"admin_sidebar.js", raw)

    def test_unauthenticated_admin_is_not_console(self) -> None:
        """GET /admin without session never returns operator console body."""
        from app import Handler
        from admin_panel import render_login_html

        prev = {
            k: os.environ.get(k)
            for k in (
                "RPT_ADMIN_PASSWORD",
                "RPT_ADMIN_USER",
                "RPT_ADMIN_SESSION_SECRET",
                "RPT_PAYMENT_DATA_DIR",
            )
        }
        td = tempfile.TemporaryDirectory()
        try:
            os.environ["RPT_PAYMENT_DATA_DIR"] = td.name
            os.environ["RPT_ADMIN_PASSWORD"] = "unit-test-admin-password-xx"
            os.environ["RPT_ADMIN_USER"] = "admin"
            os.environ["RPT_ADMIN_SESSION_SECRET"] = "unit-test-session-secret-xx"
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            port = httpd.server_address[1]
            t = Thread(target=httpd.serve_forever, daemon=True)
            t.start()
            try:
                url = f"http://127.0.0.1:{port}/admin"
                try:
                    with request.urlopen(url, timeout=5) as resp:
                        code = resp.getcode()
                        body = resp.read().decode("utf-8", errors="replace")
                except error.HTTPError as e:
                    code = e.code
                    body = e.read().decode("utf-8", errors="replace")
                # Login surface or hard deny — never authenticated console
                self.assertIn(code, (200, 401, 403, 302, 503))
                self.assertNotIn("admin-sidebar", body)
                self.assertNotIn("admin-fleet", body)
                self.assertNotIn("Generate KEYGEN (admin failsafe)", body)
                # If HTML, should be login or disabled, not home console
                if code == 200 and "html" in body[:200].lower():
                    login = render_login_html().decode("utf-8")
                    # Login markers without console
                    self.assertTrue(
                        "admin-login" in body
                        or "login" in body.lower()
                        or "password" in body.lower()
                        or "disabled" in body.lower()
                        or body == login
                        or "OPERATOR ADMIN" in body
                        or "username" in body.lower()
                    )
                # Admin static JS denied anonymously
                try:
                    with request.urlopen(
                        f"http://127.0.0.1:{port}/static/admin_sidebar.js",
                        timeout=5,
                    ) as resp:
                        js_code = resp.getcode()
                        js_body = resp.read()
                except error.HTTPError as e:
                    js_code = e.code
                    js_body = e.read()
                self.assertEqual(js_code, 401)
                self.assertNotIn(b"function", js_body[:20] if js_body else b"")
            finally:
                httpd.shutdown()
        finally:
            for k, v in prev.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            td.cleanup()


class TestIsAdminStaticPath(unittest.TestCase):
    def test_admin_static_helpers(self) -> None:
        from app import is_admin_static_path

        self.assertTrue(is_admin_static_path("/static/admin_sidebar.js"))
        self.assertTrue(is_admin_static_path("/static/admin_theme.js"))
        self.assertFalse(is_admin_static_path("/static/public_theme.js"))
        self.assertFalse(is_admin_static_path("/static/logo.png"))


if __name__ == "__main__":
    unittest.main()

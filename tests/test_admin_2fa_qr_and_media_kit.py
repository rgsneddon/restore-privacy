"""2FA setup QR (real otpauth) + public media kit + Link Generation link."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
import zipfile
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib import request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestAdmin2faQr(unittest.TestCase):
    def test_setup_html_qr_encodes_real_otpauth(self) -> None:
        from admin_2fa import otpauth_uri
        from admin_panel import render_2fa_setup_html
        from qr_encode import qr_data_url_svg

        secret = "JBSWY3DPEHPK3PXP"
        uri = otpauth_uri(secret, account="admin")
        self.assertTrue(uri.startswith("otpauth://totp/"))
        self.assertIn(secret, uri)

        data_url = qr_data_url_svg(uri)
        self.assertTrue(data_url.startswith("data:image/svg+xml;base64,"))
        self.assertGreater(len(data_url), 200)

        html = render_2fa_setup_html(secret_b32=secret, otpauth=uri).decode("utf-8")
        self.assertIn('id="admin-2fa-qr"', html)
        self.assertIn("data-otpauth-qr", html)
        self.assertIn(data_url[:40], html)
        # URI is HTML-escaped in the page (&amp;) but same otpauth payload
        self.assertIn("data-otpauth-uri", html)
        self.assertIn("otpauth://totp/", html)
        self.assertIn(secret, html)
        self.assertNotIn("admin-2fa-setup-note", html)
        self.assertNotIn("admin-2fa-security-blurb", html)
        self.assertNotIn("admin-security-extra-advice", html)
        self.assertEqual(qr_data_url_svg(uri), data_url)
        self.assertNotIn("chart.googleapis", html)
        self.assertNotIn("api.qrserver", html)

    def test_login_has_password_and_totp_fields(self) -> None:
        from admin_panel import render_login_html

        html = render_login_html().decode("utf-8")
        self.assertIn("OPERATOR ADMIN PAGES", html)
        self.assertIn('id="admin-login-heading"', html)
        self.assertIn('name="username"', html)
        self.assertIn('name="password"', html)
        self.assertIn('name="totp_code"', html)
        self.assertIn("data-admin-login-totp", html)
        self.assertIn("admin-login-form", html)
        self.assertNotIn("admin-login-note", html)
        self.assertNotIn("admin-2fa-security-blurb", html)
        self.assertNotIn("admin-security-extra-advice", html)


class TestMediaKit(unittest.TestCase):
    def test_build_kit_contains_brand_assets(self) -> None:
        from media_kit import build_media_kit_bytes, ensure_media_kit_on_disk

        data = build_media_kit_bytes()
        self.assertGreater(len(data), 5000)
        with zipfile.ZipFile(__import__("io").BytesIO(data)) as zf:
            names = set(zf.namelist())
        self.assertIn("README.txt", names)
        brandish = [n for n in names if "favicon" in n.lower() or "logo" in n.lower()]
        self.assertGreaterEqual(len(brandish), 2, names)

        path = ensure_media_kit_on_disk()
        self.assertTrue(path.is_file())
        self.assertGreater(path.stat().st_size, 5000)

    def test_public_route_and_link_generation_placement(self) -> None:
        import app as status_app
        from admin_panel import (
            MEDIA_KIT_PUBLIC_PATH,
            render_admin_link_generation_html,
        )
        from media_kit import ensure_media_kit_on_disk

        ensure_media_kit_on_disk()
        app_src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("/media-kit/restore-privacy-media-kit.zip", app_src)
        self.assertIn("media_kit_file_path", app_src)

        page = render_admin_link_generation_html().decode("utf-8")
        self.assertIn("admin-media-kit-link", page)
        self.assertIn(MEDIA_KIT_PUBLIC_PATH, page)
        # Banner is above mint tools in main (sidebar may mention reissue earlier)
        kit_i = page.find('id="admin-media-kit-banner"')
        reissue_heading = page.find('id="admin-reissue-heading"')
        self.assertGreaterEqual(kit_i, 0)
        self.assertGreaterEqual(reissue_heading, 0)
        self.assertLess(kit_i, reissue_heading)

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), status_app.Handler)
        port = httpd.server_address[1]
        thr = Thread(target=httpd.serve_forever, daemon=True)
        thr.start()
        try:
            with request.urlopen(
                f"http://127.0.0.1:{port}/media-kit/restore-privacy-media-kit.zip",
                timeout=10,
            ) as resp:
                body = resp.read()
                code = resp.status
                ctype = resp.headers.get("Content-Type", "")
            self.assertEqual(code, 200)
            self.assertIn("zip", ctype.lower())
            self.assertGreater(len(body), 5000)
            self.assertEqual(body[:2], b"PK")
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_copy_to_downloads(self) -> None:
        from media_kit import KIT_FILENAME, copy_media_kit_to_downloads

        with tempfile.TemporaryDirectory() as td:
            dest = copy_media_kit_to_downloads(Path(td))
            self.assertEqual(dest.name, KIT_FILENAME)
            self.assertTrue(dest.is_file())
            self.assertGreater(dest.stat().st_size, 5000)


if __name__ == "__main__":
    unittest.main()

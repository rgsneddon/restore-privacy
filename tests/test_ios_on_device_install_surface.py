"""iPhone/iPad download surface must not serve a tap-inert .zip attachment."""

from __future__ import annotations

import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))
sys.path.insert(0, str(ROOT / "node"))

import app as status_app  # noqa: E402
from downloads import (  # noqa: E402
    ios_catalog_ipa_filename,
    render_ios_device_install_html,
    suite_free_direct_download_href,
)


class _FakeHandler(status_app.Handler):
    def __init__(self, path: str, *, command: str = "GET", headers: dict | None = None):
        self.path = path
        self.command = command
        self.headers = headers or {}
        self.wfile = BytesIO()
        self.rfile = BytesIO()
        self.code: int | None = None
        self.sent_headers: dict[str, str] = {}

    def send_response(self, code: int, message: str | None = None) -> None:
        self.code = code

    def send_header(self, key: str, value: str) -> None:
        self.sent_headers[key] = value

    def end_headers(self) -> None:
        return

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


class TestIosOnDeviceInstallSurface(unittest.TestCase):
    def test_ipa_filename_not_zip(self) -> None:
        name = ios_catalog_ipa_filename("1.2.7")
        self.assertTrue(name.endswith(".ipa"))
        self.assertFalse(name.endswith(".zip"))
        self.assertIn("1.2.7", name)

    def test_install_html_uses_testflight_not_sideload(self) -> None:
        html = render_ios_device_install_html(
            manifest_https_url="https://restoreprivacy.online/suite/ios-manifest.plist",
            ipa_href="/suite/ios.ipa",
            version="1.2.7",
        )
        self.assertNotIn("itms-services://", html)
        self.assertIn("testflight.apple.com/join/", html)
        self.assertIn("Install Restore Privacy", html)
        self.assertNotIn("/suite/ios.ipa", html)
        self.assertIn("cannot be installed", html)
        self.assertNotIn("rename", html.lower())
        self.assertNotIn(".zip →", html)

    def test_iphone_and_ipad_ua_get_install_page_not_zip(self) -> None:
        uas = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15",
            "Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15",
        )
        href = suite_free_direct_download_href("ios")
        self.assertIn("platform=ios", href)
        for ua in uas:
            h = _FakeHandler(
                href,
                headers={
                    "User-Agent": ua,
                    "Host": "restoreprivacy.online",
                    "X-Forwarded-Proto": "https",
                },
            )
            h.do_GET()
            self.assertEqual(h.code, 200, msg=ua)
            ctype = h.sent_headers.get("Content-Type") or ""
            self.assertIn("text/html", ctype, msg=ua)
            disp = h.sent_headers.get("Content-Disposition") or ""
            self.assertNotIn(".zip", disp)
            body = h.wfile.getvalue().decode("utf-8", "replace")
            self.assertNotIn("itms-services://", body, msg=ua)
            self.assertIn("testflight.apple.com/join/", body, msg=ua)
            self.assertNotIn("ios-manifest.plist", body, msg=ua)

    def test_desktop_ua_still_302s_catalog_zip_name(self) -> None:
        def fake_plan(filename: str, **_kwargs):
            return {
                "url": f"https://assets.example.test/paid-assets/1.2.7/{filename}?sig=1",
                "version": "1.2.7",
                "filename": filename,
                "source": "helsinki_host",
                "store_probed": True,
            }

        with mock.patch("host_delivery.suite_free_delivery_plan", side_effect=fake_plan):
            h = _FakeHandler(
                suite_free_direct_download_href("ios"),
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                    "Host": "restoreprivacy.online",
                },
            )
            h.do_GET()
        self.assertEqual(h.code, 302)
        loc = h.sent_headers.get("Location") or ""
        self.assertIn("ios.zip", loc)

    def test_manifest_endpoint_points_at_ipa(self) -> None:
        h = _FakeHandler(
            "/suite/ios-manifest.plist",
            headers={
                "Host": "restoreprivacy.online",
                "X-Forwarded-Proto": "https",
            },
        )
        h.do_GET()
        self.assertEqual(h.code, 200)
        body = h.wfile.getvalue()
        self.assertIn(b"software-package", body)
        self.assertIn(b"https://restoreprivacy.online/suite/ios.ipa", body)
        self.assertNotIn(b"-ios.zip", body)


if __name__ == "__main__":
    unittest.main()

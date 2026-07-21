"""Brand logo / favicon: VPN APP Shop wiring + platform icon slots from vpnlogo.jpg."""

from __future__ import annotations

import sys
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

import app as status_app  # noqa: E402


class TestBrandSourceAndDerivatives(unittest.TestCase):
    def test_master_brand_source_present(self):
        src = ROOT / "assets" / "brand" / "vpnlogo.jpg"
        self.assertTrue(src.is_file(), f"missing {src}")
        self.assertGreater(src.stat().st_size, 10_000)

    def test_status_static_favicon_and_logo(self):
        static = ROOT / "status_page" / "static"
        for name in ("favicon.ico", "favicon.png", "logo.png", "apple-touch-icon.png"):
            p = static / name
            self.assertTrue(p.is_file(), f"missing {p}")
            self.assertGreater(p.stat().st_size, 200)

    def test_android_launchers_updated(self):
        res = ROOT / "client_app" / "android" / "app" / "src" / "main" / "res"
        for density in (
            "mipmap-mdpi",
            "mipmap-hdpi",
            "mipmap-xhdpi",
            "mipmap-xxhdpi",
            "mipmap-xxxhdpi",
        ):
            p = res / density / "ic_launcher.png"
            self.assertTrue(p.is_file(), f"missing {p}")
            # Default Flutter placeholder icons were tiny (~500B); brand is larger
            self.assertGreater(p.stat().st_size, 2_000, f"still tiny default? {p}")

    def test_windows_flutter_and_python_icons(self):
        flutter_ico = (
            ROOT
            / "client_app"
            / "windows"
            / "runner"
            / "resources"
            / "app_icon.ico"
        )
        py_ico = ROOT / "client" / "windows" / "native" / "app_icon.ico"
        py_png = ROOT / "client" / "windows" / "native" / "app_icon.png"
        for p in (flutter_ico, py_ico, py_png):
            self.assertTrue(p.is_file(), f"missing {p}")
            self.assertGreater(p.stat().st_size, 1_000)

    def test_ios_macos_appicons_present(self):
        ios = (
            ROOT
            / "client_app"
            / "ios"
            / "Runner"
            / "Assets.xcassets"
            / "AppIcon.appiconset"
            / "Icon-App-1024x1024@1x.png"
        )
        mac = (
            ROOT
            / "client_app"
            / "macos"
            / "Runner"
            / "Assets.xcassets"
            / "AppIcon.appiconset"
            / "app_icon_1024.png"
        )
        self.assertTrue(ios.is_file())
        self.assertGreater(ios.stat().st_size, 5_000)
        self.assertTrue(mac.is_file())
        self.assertGreater(mac.stat().st_size, 5_000)

    def test_windows_client_sets_icon_hook(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("_set_window_icon", src)
        self.assertIn("app_icon.ico", src)
        self.assertIn("iconbitmap", src)


class TestStatusPageFavicon(unittest.TestCase):
    def test_render_html_links_favicon(self):
        html = status_app.render_html(
            {"title": "RESTORE PRIVACY", "clients_connected": 0}
        ).decode("utf-8")
        self.assertIn('rel="icon"', html)
        self.assertIn("/favicon.ico", html)
        self.assertIn("/favicon.png", html)
        self.assertIn("/logo.png", html)
        self.assertIn('class="brand-logo"', html)

    def test_static_resolution_and_bytes(self):
        for path in ("/favicon.ico", "/favicon.png", "/logo.png", "/apple-touch-icon.png"):
            resolved = status_app.static_file_path(path)
            self.assertIsNotNone(resolved, path)
            got = status_app.read_static_bytes(path)
            self.assertIsNotNone(got, path)
            data, ctype = got
            self.assertGreater(len(data), 200, path)
            self.assertTrue(
                ctype.startswith("image/") or "icon" in ctype,
                f"{path} ctype={ctype}",
            )

    def test_handler_serves_favicon_twice(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), status_app.Handler)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            with mock.patch.object(
                status_app,
                "fetch_upstream_status",
                return_value={"title": "RESTORE PRIVACY", "clients_connected": 0},
            ):
                for _ in range(2):
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/", timeout=5
                    ) as resp:
                        html = resp.read().decode("utf-8")
                    self.assertIn("/favicon.ico", html)
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/favicon.ico", timeout=5
                    ) as resp:
                        data = resp.read()
                        ctype = resp.headers.get("Content-Type", "")
                    self.assertGreater(len(data), 200)
                    self.assertTrue("image" in ctype or "icon" in ctype)
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/logo.png", timeout=5
                    ) as resp:
                        logo = resp.read()
                    self.assertGreater(len(logo), 1000)
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()

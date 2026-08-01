"""Brand logo / favicon: current primary masters + status static + platform slots."""

from __future__ import annotations

import hashlib
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

# Pre-current Flutter brand plate (smaller file); must not reappear after regen.
_STALE_FLUTTER_APP_ICON_SHA256_PREFIX = "905639773aa76e20"


def _sha256_prefix(path: Path, n: int = 16) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:n]


class TestFillShieldInteriorHoles(unittest.TestCase):
    def test_fill_keeps_outer_transparent_and_fills_enclosed_holes(self) -> None:
        """Drive shipped fill_shield_interior_holes from generate_brand_icons."""
        import importlib.util

        from PIL import Image, ImageDraw

        gen_path = ROOT / "scripts" / "generate_brand_icons.py"
        spec = importlib.util.spec_from_file_location("generate_brand_icons", gen_path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Synthetic: opaque ring (alpha 255) around a transparent hole; outer transparent
        im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        solid = Image.new("RGBA", (64, 64), (10, 22, 40, 255))
        draw = ImageDraw.Draw(im)
        draw.ellipse((8, 8, 55, 55), fill=(0, 180, 255, 255))
        draw.ellipse((24, 24, 39, 39), fill=(0, 0, 0, 0))  # hole
        filled = mod.fill_shield_interior_holes(im, solid)
        self.assertEqual(filled.getpixel((0, 0))[3], 0)
        self.assertEqual(filled.getpixel((63, 63))[3], 0)
        # Center of hole should now be opaque dark blue from solid plate
        c = filled.getpixel((31, 31))
        self.assertEqual(c[3], 255)
        self.assertLess(c[0], 40)
        self.assertLess(c[1], 50)

    def test_shipped_logo_transparent_has_no_interior_holes(self) -> None:
        from PIL import Image, ImageDraw

        path = ROOT / "status_page" / "static" / "logo_transparent.png"
        self.assertTrue(path.is_file())
        im = Image.open(path).convert("RGBA")
        w, h = im.size
        px = im.load()
        outer = Image.new("L", (w, h), 0)
        op = outer.load()
        for y in range(h):
            for x in range(w):
                if px[x, y][3] == 0:
                    op[x, y] = 255
        for seed in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
            if outer.getpixel(seed) == 255:
                ImageDraw.floodfill(outer, seed, 128, thresh=0)
        holes = sum(
            1
            for y in range(h)
            for x in range(w)
            if px[x, y][3] == 0 and outer.getpixel((x, y)) != 128
        )
        self.assertEqual(holes, 0)


class TestBrandSourceAndDerivatives(unittest.TestCase):
    def test_master_brand_source_present(self):
        """Current brand masters live under assets/brand (primary_* preferred)."""
        primary = ROOT / "assets" / "brand" / "primary_dark_1024.png"
        transparent = ROOT / "assets" / "brand" / "primary_transparent_1024.png"
        self.assertTrue(primary.is_file(), f"missing current master {primary}")
        self.assertGreater(primary.stat().st_size, 50_000)
        self.assertTrue(transparent.is_file(), f"missing {transparent}")
        self.assertGreater(transparent.stat().st_size, 50_000)
        # Legacy jpg may remain for history but is not the status favicon source
        legacy = ROOT / "assets" / "brand" / "vpnlogo.jpg"
        if legacy.is_file():
            self.assertNotEqual(
                _sha256_prefix(primary),
                _sha256_prefix(legacy),
                "primary master must not be a rename of the legacy jpg plate",
            )

    def test_status_static_favicon_and_logo(self):
        static = ROOT / "status_page" / "static"
        brand = ROOT / "assets" / "brand"
        for name in (
            "favicon.ico",
            "favicon.png",
            "logo.png",
            "logo_transparent.png",
            "apple-touch-icon.png",
        ):
            p = static / name
            self.assertTrue(p.is_file(), f"missing {p}")
            self.assertGreater(p.stat().st_size, 200)
        # Favicons/logo plate are the regenerated current set (match assets/brand)
        self.assertEqual(
            (static / "favicon.ico").read_bytes(),
            (brand / "favicon.ico").read_bytes(),
        )
        self.assertEqual(
            (static / "favicon.png").read_bytes(),
            (brand / "favicon-32.png").read_bytes(),
        )
        self.assertEqual(
            (static / "logo.png").read_bytes(),
            (brand / "logo-256.png").read_bytes(),
        )
        # Public header cutout: interior-filled transparent master (not raw holes)
        self.assertEqual(
            (static / "logo_transparent.png").read_bytes(),
            (brand / "primary_transparent_filled_1024.png").read_bytes(),
        )
        self.assertNotEqual(
            (static / "logo_transparent.png").read_bytes(),
            (brand / "primary_transparent_1024.png").read_bytes(),
        )
        # Header transparent ≠ opaque plate
        self.assertNotEqual(
            (static / "logo_transparent.png").read_bytes(),
            (static / "logo.png").read_bytes(),
        )

    def test_flutter_brand_assets_match_current_logo_plate(self):
        """client_app brand slots must not keep the pre-current smaller plate."""
        flutter = ROOT / "client_app" / "assets" / "brand" / "app_icon.png"
        logo256 = ROOT / "assets" / "brand" / "logo-256.png"
        self.assertTrue(flutter.is_file())
        self.assertTrue(logo256.is_file())
        self.assertEqual(flutter.read_bytes(), logo256.read_bytes())
        self.assertNotEqual(
            _sha256_prefix(flutter),
            _STALE_FLUTTER_APP_ICON_SHA256_PREFIX,
            "Flutter app_icon still matches known-stale pre-current hash",
        )

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
        from public_chrome import PUBLIC_BRAND_LOGO_PATH, PUBLIC_BRAND_TITLE

        html = status_app.render_html(
            {"title": "RESTORE PRIVACY", "clients_connected": 0}
        ).decode("utf-8")
        self.assertIn('rel="icon"', html)
        self.assertIn("/favicon.ico", html)
        self.assertIn("/favicon.png", html)
        self.assertIn("/apple-touch-icon.png", html)
        # Header brand mark is banner-only (logos not in top box)
        self.assertIn('class="brand-mark"', html)
        self.assertIn('class="brand-banner"', html)
        self.assertIn("banner.jpg", html)
        self.assertIn(PUBLIC_BRAND_TITLE, html)
        brand_start = html.index('id="brand-panel"')
        brand_end = html.index("</header>", brand_start)
        brand = html[brand_start:brand_end]
        self.assertIn("brand-banner", brand)
        self.assertNotIn('class="brand-logo"', brand)
        self.assertNotIn("brand-logo-left", brand)
        self.assertNotIn("brand-logo-right", brand)
        self.assertNotIn("/logo_transparent.png", brand)
        self.assertNotIn('src="/logo.png"', brand)
        self.assertNotIn('src="/logo.png?', brand)
        # Logo static files still resolve for favicon/media-kit (not header)
        _ = PUBLIC_BRAND_LOGO_PATH

    def test_static_resolution_and_bytes(self):
        for path in (
            "/favicon.ico",
            "/favicon.png",
            "/logo.png",
            "/logo_transparent.png",
            "/apple-touch-icon.png",
        ):
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
                        f"http://127.0.0.1:{port}/logo_transparent.png", timeout=5
                    ) as resp:
                        logo = resp.read()
                    self.assertGreater(len(logo), 1000)
                    # Opaque plate still served if requested (legacy / solid plate)
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/logo.png", timeout=5
                    ) as resp:
                        self.assertGreater(len(resp.read()), 1000)
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()

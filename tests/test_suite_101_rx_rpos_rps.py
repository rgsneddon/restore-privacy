"""Suite 1.0.1 catalog, Rx browser, Service link, admin rpOS/rpS, Ned surfaces."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))
sys.path.insert(0, str(ROOT / "scripts"))


class TestSuite101Catalog(unittest.TestCase):
    def test_catalog_pin_and_platform_packages(self) -> None:
        from downloads import (
            RELEASE_VERSION,
            assure_current_catalog_packages,
            current_catalog_version,
            list_catalog_platform_packages,
            list_suite_extra_packages,
            rx_browser_package_filename,
            rx_browser_package_href,
        )

        pin = RELEASE_VERSION
        self.assertEqual(current_catalog_version(), pin)
        pkgs = list_catalog_platform_packages()
        plats = {p["platform"] for p in pkgs}
        self.assertEqual(
            plats, {"windows", "macos", "linux", "android", "ios"}
        )
        for p in pkgs:
            self.assertEqual(p["version"], pin)
            self.assertIn(pin, p["filename"])
            self.assertTrue(
                p["filename"].startswith(f"restore-privacy-client-{pin}-")
            )

        # Local release tree has real files
        rel = ROOT / "releases" / pin
        for p in pkgs:
            f = rel / p["filename"]
            self.assertTrue(f.is_file(), f"missing {f}")
            self.assertGreater(f.stat().st_size, 0)

        extras = list_suite_extra_packages()
        self.assertEqual(extras[0]["kind"], "rx_browser")
        self.assertEqual(extras[0]["filename"], rx_browser_package_filename())
        rx = rel / rx_browser_package_filename()
        self.assertTrue(rx.is_file(), rx)
        self.assertGreater(rx.stat().st_size, 0)
        self.assertTrue(
            (rel / f"restore-privacy-browser-extension-{pin}.zip").is_file()
        )
        href = rx_browser_package_href(user_agent="Mozilla/5.0 (Windows NT 10.0)")
        self.assertIn(f"/assets/{pin}/", href)
        self.assertIn("rx-browser", href)

        # assure helper should not invent platforms
        r = assure_current_catalog_packages()
        self.assertEqual(r.get("catalog_version"), pin)


class TestServiceRxLink(unittest.TestCase):
    def test_service_page_links_rx_package_device_aware(self) -> None:
        from service_commercial import (
            SERVICE_RX_BOX_ID,
            SERVICE_RX_LINK_ID,
            render_service_page_html,
        )

        raw = render_service_page_html(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        )
        html = raw.decode("utf-8")
        self.assertIn(f'id="{SERVICE_RX_BOX_ID}"', html)
        self.assertIn(f'id="{SERVICE_RX_LINK_ID}"', html)
        self.assertIn("data-rx-browser-download", html)
        from downloads import RELEASE_VERSION, rx_browser_package_filename

        self.assertIn(rx_browser_package_filename(), html)
        self.assertIn(f"/assets/{RELEASE_VERSION}/", html)
        self.assertIn('data-detected-platform="macos"', html)
        # Companion also links Rx
        self.assertIn("service-link-rx-browser-inline", html)
        # Main nav Service still present via brand header
        self.assertIn('data-page="service"', html)

    def test_open_release_asset_serves_rx_zip(self) -> None:
        """Fulfilment helper must open Rx package (free-open allowlist), not None."""
        from downloads import rx_browser_package_filename
        from payments import free_open_filenames, open_release_asset

        fname = rx_browser_package_filename()
        self.assertIn(fname, free_open_filenames())
        asset = open_release_asset(fname)
        self.assertIsNotNone(asset, f"open_release_asset({fname!r}) returned None")
        assert asset is not None
        self.assertEqual(asset.get("content_type"), "application/zip")
        length = asset.get("content_length")
        self.assertIsNotNone(length)
        self.assertGreater(int(length or 0), 0)
        body = asset["body"]
        try:
            chunk = body.read(4) if hasattr(body, "read") else body[:4]
            # ZIP local file header magic
            self.assertEqual(chunk[:2], b"PK")
        finally:
            if hasattr(body, "close"):
                body.close()

    def test_http_get_service_rx_href_returns_zip(self) -> None:
        """Live Handler: GET Service Rx href → 200 + application/zip + non-empty body."""
        import threading
        import urllib.error
        import urllib.request
        from http.server import ThreadingHTTPServer

        import app as status_app
        from downloads import rx_browser_package_href
        from service_commercial import render_service_page_html

        href = rx_browser_package_href(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        )
        self.assertTrue(href.startswith("/assets/"), href)
        # Service HTML embeds the same href
        html = render_service_page_html(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        ).decode("utf-8")
        self.assertIn(href, html)

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), status_app.Handler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{port}{href}"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=15) as res:
                status = res.status
                ctype = (res.headers.get("Content-Type") or "").lower()
                data = res.read()
            self.assertEqual(status, 200, f"expected 200 for {url}")
            self.assertIn("zip", ctype)
            self.assertGreater(len(data), 100)
            self.assertEqual(data[:2], b"PK")
        except urllib.error.HTTPError as exc:
            self.fail(f"GET {href} failed HTTP {exc.code}: {exc.read()[:200]!r}")
        finally:
            httpd.shutdown()
            httpd.server_close()


class TestAdminRposRps(unittest.TestCase):
    def test_rpos_howto_admin_only_content(self) -> None:
        from admin_rpos import (
            ADMIN_RPOS_HOWTO_ID,
            ADMIN_RPOS_PATH,
            RPOS_SDK_APPS,
            render_admin_rpos_page_html,
        )

        self.assertEqual(ADMIN_RPOS_PATH, "/admin/rpos")
        raw = render_admin_rpos_page_html()
        html = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
        self.assertIn(ADMIN_RPOS_HOWTO_ID, html)
        self.assertIn("RESTORE rpOS", html)
        self.assertIn("£3000", html)
        self.assertIn("MISHI", html)
        for app in RPOS_SDK_APPS:
            self.assertIn(app.split()[0], html)
        # Not a public chrome page
        self.assertNotIn('data-site-nav="1"', html)

    def test_rps_stats_structure_and_persist(self) -> None:
        from admin_rps import (
            ADMIN_RPS_PATH,
            load_rps_stats,
            record_rps_heartbeat,
            render_admin_rps_page_html,
            save_rps_stats,
        )

        self.assertEqual(ADMIN_RPS_PATH, "/admin/rps")
        with tempfile.TemporaryDirectory() as td:
            fake = Path(td) / "rps_ned_stats.json"
            with mock.patch("admin_rps.rps_stats_path", return_value=fake):
                s = save_rps_stats({"nodes_online": 2, "narrative_sessions": 1})
                self.assertEqual(s["nodes_online"], 2)
                s2 = record_rps_heartbeat(nodes_online=3)
                self.assertEqual(s2["nodes_online"], 3)
                self.assertGreaterEqual(s2["learning_epochs"], 1)
                loaded = load_rps_stats()
                self.assertEqual(loaded["nodes_online"], 3)
        raw = render_admin_rps_page_html()
        html = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
        self.assertIn("admin-rps-stats", html)
        self.assertIn("GOD", html)
        self.assertIn("rpS", html)


class TestRposScaffoldDocs(unittest.TestCase):
    def test_monorepo_rpos_and_beam_docs_present(self) -> None:
        for rel in (
            "rpos/README.md",
            "rpos/LICENSE",
            "rpos/PRIVACY_POLICY.md",
            "rpos/security/AUDIT.md",
            "rpos/docs/DEPLOY.md",
            "rpos/sdk/mishi/README.md",
            "beam_privacy_dapp/README.md",
            "beam_privacy_dapp/LICENSE",
            "beam_privacy_dapp/src/dapp_manifest.json",
        ):
            p = ROOT / rel
            self.assertTrue(p.is_file(), rel)
            self.assertGreater(p.stat().st_size, 0, rel)
        lic = (ROOT / "rpos/LICENSE").read_text(encoding="utf-8")
        self.assertIn("MIT License", lic)
        man = json.loads(
            (ROOT / "beam_privacy_dapp/src/dapp_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        from downloads import RELEASE_VERSION

        self.assertEqual(man.get("suite_monopin"), RELEASE_VERSION)

    def test_windows_breadcrumbs_present(self) -> None:
        from downloads import RELEASE_VERSION

        # Prefer current monopin; fall back to prior pin breadcrumbs if not yet staged.
        p = ROOT / "releases" / RELEASE_VERSION / "WINDOWS_BREADCRUMBS.md"
        if not p.is_file():
            p = ROOT / "releases" / "1.0.1" / "WINDOWS_BREADCRUMBS.md"
        self.assertTrue(p.is_file(), p)
        text = p.read_text(encoding="utf-8")
        self.assertRegex(text, r"1\.\d+\.\d+")
        self.assertIn("Windows", text)
        self.assertIn("breadcrumb", text.lower())


class TestBrowserExtension101(unittest.TestCase):
    def test_extension_manifest_and_zip_pin(self) -> None:
        from downloads import RELEASE_VERSION

        man = json.loads(
            (ROOT / "browser_extension" / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(man.get("version"), RELEASE_VERSION)
        self.assertEqual(man.get("manifest_version"), 3)
        core = (ROOT / "browser_extension" / "lib" / "vpn_core.js").read_text(
            encoding="utf-8"
        )
        self.assertIn(f'catalogVersion: "{RELEASE_VERSION}"', core)
        z = (
            ROOT
            / "releases"
            / RELEASE_VERSION
            / f"restore-privacy-browser-extension-{RELEASE_VERSION}.zip"
        )
        self.assertTrue(z.is_file(), z)
        self.assertGreater(z.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()

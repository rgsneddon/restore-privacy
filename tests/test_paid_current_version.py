"""Paid downloads always bind and open the current catalog product version."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

from downloads import (  # noqa: E402
    RELEASE_VERSION,
    available_downloads,
    list_catalog_platform_packages,
    render_download_section_html,
)
import payments  # noqa: E402


class TestGrantBindsCurrentCatalogVersion(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        os.environ["RPT_PAYMENT_DATA_DIR"] = self._td.name
        payments.init_db()

    def _sign(self, payload: bytes, secret: str) -> str:
        t = int(time.time())
        signed = f"{t}.".encode() + payload
        sig = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
        return f"t={t},v1={sig}"

    def test_platform_filename_contains_current_version_all_devices(self):
        for a in available_downloads():
            fname = payments.platform_filename(a.platform)
            self.assertEqual(fname, a.filename)
            self.assertIn(RELEASE_VERSION, fname)
            self.assertTrue(
                fname.startswith(f"restore-privacy-client-{RELEASE_VERSION}-")
            )

    def test_resolve_ignores_stale_metadata_filename(self):
        stale = f"restore-privacy-client-0.0.1-windows-x64-setup.exe"
        resolved = payments.resolve_paid_grant_filename(
            "windows", metadata_filename=stale
        )
        current = payments.platform_filename("windows")
        self.assertEqual(resolved, current)
        self.assertIn(RELEASE_VERSION, resolved)
        self.assertNotIn("0.0.1", resolved)

    def test_webhook_mints_current_filename_despite_stale_meta(self):
        secret = "whsec_version_bind"
        stale = "restore-privacy-client-0.2.9-linux-x64.tar.gz"
        payload = json.dumps(
            {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_ver_stale_meta",
                        "payment_status": "paid",
                        "amount_total": 300,
                        "currency": "gbp",
                        "client_reference_id": "linux",
                        "metadata": {
                            "platform": "linux",
                            "filename": stale,
                            "amount_pence": "300",
                            "currency": "gbp",
                        },
                    }
                },
            }
        ).encode()
        result = payments.handle_stripe_webhook(
            payload, self._sign(payload, secret), secret=secret
        )
        self.assertTrue(result.get("granted"), result)
        tok = result["token"]
        grant = payments.lookup_download_token(tok)
        self.assertIsNotNone(grant)
        assert grant is not None
        want = payments.platform_filename("linux")
        self.assertEqual(grant["filename"], want)
        self.assertIn(RELEASE_VERSION, grant["filename"])
        self.assertNotEqual(grant["filename"], stale)

    def test_webhook_each_platform_mints_current_catalog_name(self):
        secret = "whsec_each_plat"
        for a in available_downloads():
            with self.subTest(platform=a.platform):
                payload = json.dumps(
                    {
                        "type": "checkout.session.completed",
                        "data": {
                            "object": {
                                "id": f"cs_ver_{a.platform}",
                                "payment_status": "paid",
                                "amount_total": 300,
                                "currency": "gbp",
                                "client_reference_id": a.platform,
                                "metadata": {},
                            }
                        },
                    }
                ).encode()
                result = payments.handle_stripe_webhook(
                    payload, self._sign(payload, secret), secret=secret
                )
                self.assertTrue(result.get("granted"), result)
                grant = payments.lookup_download_token(result["token"])
                self.assertIsNotNone(grant)
                assert grant is not None
                self.assertEqual(grant["filename"], a.filename)
                self.assertIn(RELEASE_VERSION, grant["filename"])


class TestOpenPrefersCurrentVersionStore(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        for k in (
            "RPT_ASSET_DIR",
            "RPT_ASSET_FETCH_TOKEN",
            "RPT_VPS_ASSET_BASE",
            "RPT_GITHUB_TOKEN",
            "GITHUB_TOKEN",
            "GH_TOKEN",
        ):
            os.environ.pop(k, None)

    def test_open_current_filename_from_current_version_dir_not_old(self):
        """Temp tree: old version dir + current; open uses current catalog name/path."""
        root = Path(self._td.name)
        old_ver = "0.2.9"
        cur = RELEASE_VERSION
        old_dir = root / "paid_assets" / old_ver
        cur_dir = root / "paid_assets" / cur
        old_dir.mkdir(parents=True)
        cur_dir.mkdir(parents=True)
        fname = payments.platform_filename("windows")
        assert fname is not None
        # Stale-named file only under old dir (must not be openable as catalog)
        (old_dir / f"restore-privacy-client-{old_ver}-windows-x64-setup.exe").write_bytes(
            b"OLD-WINDOWS-BYTES"
        )
        # Current catalog name only under current version store
        payload = b"CURRENT-WINDOWS-PRODUCT-BYTES"
        (cur_dir / fname).write_bytes(payload)

        # Search: old dir first, then current — open must still find current by filename
        # and not open the old-named file as the current product.
        with mock.patch.object(
            payments,
            "asset_search_dirs",
            return_value=[old_dir, cur_dir],
        ):
            asset = payments.open_release_asset(fname)
        self.assertIsNotNone(asset)
        assert asset is not None
        body = asset["body"]
        try:
            data = body.read() if hasattr(body, "read") else body
        finally:
            if hasattr(body, "close"):
                body.close()
        self.assertEqual(data, payload)
        self.assertNotEqual(data, b"OLD-WINDOWS-BYTES")

    def test_open_rejects_stale_version_filename(self):
        root = Path(self._td.name)
        old_dir = root / "0.2.9"
        old_dir.mkdir()
        stale = "restore-privacy-client-0.2.9-android.apk"
        (old_dir / stale).write_bytes(b"STALE-APK")
        os.environ["RPT_ASSET_DIR"] = str(old_dir)
        self.assertIsNone(payments.open_release_asset(stale))
        # Current name is accepted only if present
        current = payments.platform_filename("android")
        self.assertIsNotNone(current)
        self.assertNotEqual(current, stale)

    def test_vps_url_uses_current_version_segment(self):
        for a in available_downloads():
            url = payments.vps_asset_url(a.filename)
            self.assertIn(f"/{RELEASE_VERSION}/", url)
            self.assertTrue(url.endswith(a.filename))
            self.assertNotIn("/0.2.9/", url)

    def test_ui_catalog_version_matches_grant_names(self):
        html = render_download_section_html()
        # Version remains in the h2 title (not the removed subtitle catalog-version span)
        self.assertIn(f"Download client v{RELEASE_VERSION}", html)
        self.assertNotIn('id="catalog-version"', html)
        self.assertNotIn("paid download only", html)
        # Homepage buy form lists each current-catalog platform (not free GH hrefs)
        for label in ("Windows", "Linux", "macOS", "iOS", "Android"):
            self.assertIn(label, html)
        for a in available_downloads():
            self.assertIn(a.filename, html)
            self.assertNotIn(f'href="{a.url}"', html)
        pkgs = list_catalog_platform_packages()
        self.assertEqual(len(pkgs), 5)
        for p in pkgs:
            self.assertEqual(p["version"], RELEASE_VERSION)


class TestLookupRebindsStaleGrantFilename(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        os.environ["RPT_PAYMENT_DATA_DIR"] = self._td.name
        payments.init_db()

    def test_lookup_delivers_current_filename_when_row_stale(self):
        """Active download tokens always open the live catalog package."""
        current = payments.platform_filename("windows")
        self.assertIsNotNone(current)
        assert current is not None
        stale = "restore-privacy-client-0.2.9-windows-x64-setup.exe"
        # Mint with correct binding first…
        tok = payments.mint_download_token(
            filename=current,
            platform="windows",
            session_id="cs_stale_row",
        )
        # …then corrupt the stored filename as if left from an older pin.
        conn = payments._connect()
        try:
            conn.execute(
                "UPDATE grants SET filename = ? WHERE token = ?",
                (stale, tok),
            )
            conn.commit()
            row = conn.execute(
                "SELECT filename FROM grants WHERE token = ?", (tok,)
            ).fetchone()
            self.assertEqual(row["filename"], stale)
        finally:
            conn.close()
        grant = payments.lookup_download_token(tok)
        self.assertIsNotNone(grant)
        assert grant is not None
        self.assertEqual(grant["filename"], current)
        self.assertIn(RELEASE_VERSION, grant["filename"])
        self.assertNotIn("0.2.9", grant["filename"])
        self.assertEqual(grant.get("stored_filename"), stale)
        # Delivery helper matches
        live = payments.grant_delivery_filename(
            platform="windows", stored_filename=stale
        )
        self.assertEqual(live, current)
        # open_release_asset still rejects the stale name itself
        self.assertIsNone(payments.open_release_asset(stale))

    def test_admin_mint_uses_current_filename(self):
        result = payments.admin_mint_download_for_platform("linux")
        self.assertTrue(result.get("token") or result.get("download_token") or result)
        # API shape varies — inspect DB via minted token when present
        tok = (
            result.get("token")
            or result.get("download_token")
            or (result.get("grant") or {}).get("token")
        )
        if not tok and isinstance(result, dict):
            # fall back: download_url may embed token=
            url = str(result.get("download_url") or result.get("url") or "")
            if "token=" in url:
                tok = url.split("token=", 1)[-1].split("&", 1)[0]
        self.assertTrue(tok, result)
        g = payments.lookup_download_token(str(tok))
        self.assertIsNotNone(g)
        assert g is not None
        self.assertEqual(g["filename"], payments.platform_filename("linux"))


class TestServePathCatalogPin(unittest.TestCase):
    def test_path_allowed_refuses_stale_version(self):
        # Load pure helper from serve script without starting HTTP server
        import importlib.util

        path = ROOT / "node" / "serve_paid_assets.py"
        spec = importlib.util.spec_from_file_location("serve_paid_assets", path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        pin = RELEASE_VERSION
        fname = f"restore-privacy-client-{pin}-windows-x64-setup.exe"
        self.assertTrue(
            mod.path_allowed_for_catalog(pin, fname, catalog_version=pin)
        )
        self.assertFalse(
            mod.path_allowed_for_catalog("0.2.9", fname, catalog_version=pin)
        )
        self.assertFalse(
            mod.path_allowed_for_catalog(
                pin,
                "restore-privacy-client-0.2.9-windows-x64-setup.exe",
                catalog_version=pin,
            )
        )


class TestStoreTidyCurrentOnly(unittest.TestCase):
    def test_tidy_removes_non_current_version_dirs(self):
        import importlib.util

        path = ROOT / "scripts" / "host_paid_assets_vps.py"
        spec = importlib.util.spec_from_file_location("host_paid_assets_vps", path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        (root / "0.2.9").mkdir()
        (root / "0.4.10").mkdir()
        (root / RELEASE_VERSION).mkdir()
        (root / RELEASE_VERSION / "keep.txt").write_text("ok", encoding="utf-8")
        (root / "0.2.9" / "old.bin").write_bytes(b"x")
        dry = mod.tidy_paid_assets_root(root, RELEASE_VERSION, dry_run=True)
        self.assertEqual(len(dry), 2)
        self.assertTrue((root / "0.2.9").is_dir())
        removed = mod.tidy_paid_assets_root(root, RELEASE_VERSION, dry_run=False)
        self.assertEqual(len(removed), 2)
        self.assertFalse((root / "0.2.9").exists())
        self.assertFalse((root / "0.4.10").exists())
        self.assertTrue((root / RELEASE_VERSION / "keep.txt").is_file())


if __name__ == "__main__":
    unittest.main()

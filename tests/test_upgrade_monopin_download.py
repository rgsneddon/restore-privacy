"""Platform-matched monopin upgrade download (not /pay) + mint resolver."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestCatalogInstallerBasename(unittest.TestCase):
    def test_five_platforms(self):
        from client.ui_theme import catalog_installer_filename

        for plat, needle in (
            ("windows", "windows-x64-setup.exe"),
            ("macos", "macos.zip"),
            ("ios", "ios.zip"),
            ("android", "android.apk"),
            ("linux", "linux-x64.tar.gz"),
        ):
            name = catalog_installer_filename(plat, version="0.5.7")
            self.assertEqual(name, f"restore-privacy-client-0.5.7-{needle}")
            self.assertIn("0.5.7", name)

    def test_unknown_platform(self):
        from client.ui_theme import catalog_installer_filename

        self.assertIsNone(catalog_installer_filename("amiga"))


class TestUpgradeDownloadPath(unittest.TestCase):
    def test_path_not_pay(self):
        from client.ui_theme import upgrade_download_path, upgrade_download_url

        path = upgrade_download_path("macos", keygen="RPT-KEY-TEST")
        self.assertTrue(path.startswith("/upgrade-download?"))
        self.assertIn("platform=macos", path)
        self.assertIn("keygen=", path)
        self.assertIn("filename=", path)
        self.assertNotIn("/pay", path)
        url = upgrade_download_url("android")
        self.assertIn("/upgrade-download", url)
        self.assertNotIn("/pay?", url)

    def test_token_path_is_download_grant(self):
        from client.ui_theme import upgrade_download_url

        url = upgrade_download_url("windows", token="abcXYZ")
        self.assertIn("/download?token=abcXYZ", url)
        self.assertNotIn("upgrade-download", url)


class TestResolveUpgradeDownloadMint(unittest.TestCase):
    def test_mint_fn_returns_direct_download(self):
        from client.ui_theme import resolve_upgrade_download_url

        def mint(**kwargs):
            self.assertEqual(kwargs["platform"], "macos")
            self.assertEqual(kwargs["keygen"], "RPT-KEY-ABCD")
            return {
                "ok": True,
                "token": "mintedTok",
                "download_url": "https://restoreprivacy.online/download?token=mintedTok",
            }

        url = resolve_upgrade_download_url(
            "macos", keygen="RPT-KEY-ABCD", mint_fn=mint
        )
        self.assertEqual(
            url, "https://restoreprivacy.online/download?token=mintedTok"
        )
        self.assertNotIn("/pay", url)

    def test_mint_failure_falls_soft_to_upgrade_download(self):
        from client.ui_theme import resolve_upgrade_download_url

        def mint(**kwargs):
            raise ValueError("entitlement_not_active")

        url = resolve_upgrade_download_url(
            "linux", keygen="RPT-KEY-X", mint_fn=mint
        )
        self.assertIn("/upgrade-download", url)
        self.assertIn("platform=linux", url)
        self.assertNotIn("/pay?", url)


class TestSubscriberUpgradeMintHelper(unittest.TestCase):
    def test_mint_subscriber_upgrade_requires_active(self):
        from payments import mint_subscriber_upgrade_download

        with self.assertRaises(ValueError) as ctx:
            mint_subscriber_upgrade_download(platform="macos", keygen="")
        self.assertIn("missing", str(ctx.exception).lower())

    def test_mint_with_mock_active_entitlement(self):
        import payments

        with mock.patch.object(
            payments,
            "get_connect_entitlement_by_keygen",
            return_value={
                "session_id": "cs_test_up",
                "connect_allowed": True,
                "status": "active",
                "keygen": "RPT-KEY-MOCK-0001",
            },
        ), mock.patch.object(
            payments,
            "mint_download_token",
            return_value="tok_upgrade_1",
        ), mock.patch.object(
            payments,
            "platform_filename",
            return_value="restore-privacy-client-0.5.7-macos.zip",
        ), mock.patch.object(
            payments,
            "public_base_url",
            return_value="https://restoreprivacy.online",
        ), mock.patch.object(payments, "init_db"), mock.patch.object(
            payments, "_connect"
        ) as c:
            conn = mock.MagicMock()
            conn.execute.return_value.fetchone.return_value = None
            c.return_value = conn
            out = payments.mint_subscriber_upgrade_download(
                platform="macos",
                keygen="RPT-KEY-MOCK-0001",
            )
        self.assertTrue(out.get("ok"))
        self.assertEqual(out["token"], "tok_upgrade_1")
        self.assertIn("/download?token=tok_upgrade_1", out["download_url"])
        self.assertEqual(out["platform"], "macos")
        self.assertTrue(out.get("subscriber_upgrade"))


class TestFlutterUpgradeBannerStructural(unittest.TestCase):
    def test_dart_not_pay_primary(self):
        banner = (ROOT / "client_app" / "lib" / "upgrade_banner.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("upgradeDownloadUrl", banner)
        self.assertIn("/upgrade-download", banner)
        self.assertIn("resolveUpgradeDownloadUrl", banner)
        self.assertIn("subscriber-upgrade-download", banner)
        # Must not hard-code /pay?platform= as primary CTA
        self.assertNotIn("/pay?platform=", banner)


class TestUpgradeDownloadFormNoCredential(unittest.TestCase):
    def test_form_html_no_unboundlocal_and_escapes_platform(self):
        """No-credential browser path: pure helper must not crash on html.escape."""
        # Import shipped status_page.app helper (real path).
        import importlib
        import sys

        sp = str(ROOT / "status_page")
        if sp not in sys.path:
            sys.path.insert(0, sp)
        app_mod = importlib.import_module("app")
        # Drive real function (regression for UnboundLocalError on html= shadow)
        out = app_mod.upgrade_download_form_html("macos")
        self.assertIn("<form", out)
        self.assertIn('name="platform" value="macos"', out)
        self.assertIn("Get update", out)
        self.assertIn("keygen", out.lower())
        # XSS-ish platform must be escaped
        evil = app_mod.upgrade_download_form_html('<script>x</script>')
        self.assertNotIn("<script>x</script>", evil)
        self.assertIn("&lt;script&gt;", evil)

    def test_handler_source_does_not_shadow_html_module(self):
        src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        # The no-credential branch must call the pure helper, not `html = (`
        self.assertIn("def upgrade_download_form_html", src)
        # Route handler (not the helper docstring) uses body_html assignment
        marker = 'path in (\n            "/upgrade-download"'
        self.assertIn(marker, src)
        block = src[src.index(marker) : src.index(marker) + 4000]
        self.assertNotIn("html = (", block)
        self.assertIn("body_html = upgrade_download_form_html", block)


class TestNativePrepEngineHasShapeAndCrypto(unittest.TestCase):
    def test_nativeprep_engines_embed_types_and_session_crypto(self):
        for rel in (
            "client_app/macos/NativePrep/Rpt2/RptClientEngine.swift",
            "client_app/ios/NativePrep/Rpt2/RptClientEngine.swift",
        ):
            src = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("public enum RptTrafficShape", src, rel)
            self.assertIn("public enum RptObfuscation", src, rel)
            self.assertIn("sessionCrypto", src, rel)
            self.assertIn("dataPlaneCrypto", src, rel)
            self.assertIn("RptUDPTransport", src, rel)


if __name__ == "__main__":
    unittest.main()

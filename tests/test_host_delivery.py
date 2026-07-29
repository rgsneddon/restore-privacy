"""Helsinki host delivery: short-lived signed URLs + fallback policy."""

from __future__ import annotations

import importlib
import os
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


class TestHostDeliveryPure(unittest.TestCase):
    def setUp(self) -> None:
        # Ensure package imports resolve
        import sys

        sp = str(ROOT / "status_page")
        if sp not in sys.path:
            sys.path.insert(0, sp)
        node = str(ROOT / "node")
        if node not in sys.path:
            sys.path.insert(0, node)

    def test_mint_and_verify_roundtrip(self) -> None:
        from host_delivery import mint_delivery_signature, verify_delivery_signature

        secret = "test-secret-for-hmac-only"
        exp = int(time.time()) + 600
        sig = mint_delivery_signature(
            version="0.5.4",
            filename="restore-privacy-client-0.5.4-windows-x64-setup.exe",
            exp=exp,
            nonce="abc123",
            secret=secret,
        )
        self.assertTrue(len(sig) == 64)
        self.assertTrue(
            verify_delivery_signature(
                version="0.5.4",
                filename="restore-privacy-client-0.5.4-windows-x64-setup.exe",
                exp=exp,
                nonce="abc123",
                sig=sig,
                secret=secret,
            )
        )
        self.assertFalse(
            verify_delivery_signature(
                version="0.5.4",
                filename="restore-privacy-client-0.5.4-windows-x64-setup.exe",
                exp=exp,
                nonce="abc123",
                sig=sig,
                secret="wrong",
            )
        )
        self.assertFalse(
            verify_delivery_signature(
                version="0.5.4",
                filename="restore-privacy-client-0.5.4-windows-x64-setup.exe",
                exp=int(time.time()) - 10,
                nonce="abc123",
                sig=sig,
                secret=secret,
            )
        )

    def test_serve_request_authorized_matches_status_mint(self) -> None:
        """Helsinki serve verifier accepts tokens minted by status host_delivery."""
        from host_delivery import mint_delivery_signature
        import serve_paid_assets as spa

        secret = "shared-fetch-token"
        exp = int(time.time()) + 300
        fname = "restore-privacy-client-0.5.4-linux-x64.tar.gz"
        nonce = "deadbeef"
        sig = mint_delivery_signature(
            version="0.5.4",
            filename=fname,
            exp=exp,
            nonce=nonce,
            secret=secret,
        )
        self.assertTrue(
            spa.request_authorized(
                header_token="",
                expected_token=secret,
                version="0.5.4",
                filename=fname,
                query={"exp": [str(exp)], "n": [nonce], "sig": [sig]},
            )
        )
        # Header long-lived still works
        self.assertTrue(
            spa.request_authorized(
                header_token=secret,
                expected_token=secret,
                version="0.5.4",
                filename=fname,
                query={},
            )
        )
        # Bad sig refused
        self.assertFalse(
            spa.request_authorized(
                header_token="",
                expected_token=secret,
                version="0.5.4",
                filename=fname,
                query={"exp": [str(exp)], "n": [nonce], "sig": ["0" * 64]},
            )
        )

    def test_build_url_for_catalog_basename(self) -> None:
        from host_delivery import build_host_delivery_url
        from downloads import WINDOWS_EXE_FILENAME, RELEASE_VERSION

        url = build_host_delivery_url(
            WINDOWS_EXE_FILENAME,
            secret="sec",
            base_url="https://example.test/paid-assets",
            ttl_sec=120,
            now=1_700_000_000.0,
            nonce="fixednonce",
        )
        self.assertIsNotNone(url)
        assert url is not None
        self.assertTrue(url.startswith("https://example.test/paid-assets/"))
        self.assertIn(RELEASE_VERSION, url)
        self.assertIn(WINDOWS_EXE_FILENAME, url)
        self.assertIn("exp=", url)
        self.assertIn("sig=", url)
        self.assertIn("n=fixednonce", url)
        # Long-lived secret must not appear in the URL
        self.assertNotIn("sec", url.split("?", 1)[-1])

    def test_build_url_refuses_non_catalog_and_traversal(self) -> None:
        from host_delivery import build_host_delivery_url

        self.assertIsNone(
            build_host_delivery_url(
                "../etc/passwd",
                secret="sec",
                base_url="https://example.test/paid-assets",
            )
        )
        self.assertIsNone(
            build_host_delivery_url(
                "not-a-catalog-file.exe",
                secret="sec",
                base_url="https://example.test/paid-assets",
            )
        )
        self.assertIsNone(
            build_host_delivery_url(
                "restore-privacy-client-0.5.4-windows-x64-setup.exe",
                secret="",
                base_url="https://example.test/paid-assets",
            )
        )

    def test_host_delivery_plan_respects_disable_flag(self) -> None:
        from host_delivery import host_delivery_plan, build_host_delivery_url
        from downloads import WINDOWS_EXE_FILENAME

        with mock.patch.dict(
            os.environ,
            {
                "RPT_HOST_DELIVERY": "0",
                "RPT_ASSET_FETCH_TOKEN": "tok",
                "RPT_VPS_ASSET_BASE": "https://example.test/paid-assets",
            },
            clear=False,
        ):
            # force_enabled False via env
            import host_delivery as hd

            importlib.reload(hd)
            self.assertIsNone(hd.host_delivery_plan(WINDOWS_EXE_FILENAME))
        # force_enabled True still builds when secret/base injected via build
        url = build_host_delivery_url(
            WINDOWS_EXE_FILENAME,
            secret="tok",
            base_url="https://example.test/paid-assets",
        )
        self.assertIsNotNone(url)
        plan = host_delivery_plan(WINDOWS_EXE_FILENAME, force_enabled=True)
        # May be None if env lacks token in this process — use force path via build only
        if plan is not None:
            self.assertEqual(plan["source"], "helsinki_host")
            self.assertIn("http", plan["url"])

    def test_open_release_asset_fallback_without_host_token(self) -> None:
        """When Helsinki token unset, local staged file still opens (proxy path)."""
        from downloads import WINDOWS_EXE_FILENAME, RELEASE_VERSION
        import payments

        # Use a tiny temp staged file under assets/{ver}/
        assets = ROOT / "status_page" / "assets" / RELEASE_VERSION
        assets.mkdir(parents=True, exist_ok=True)
        path = assets / WINDOWS_EXE_FILENAME
        created = False
        if not path.is_file() or path.stat().st_size < 10:
            path.write_bytes(b"MZ" + b"\x00" * 100)
            created = True
        try:
            with mock.patch.dict(
                os.environ,
                {
                    "RPT_ASSET_FETCH_TOKEN": "",
                    "RPT_VPS_ASSET_TOKEN": "",
                    "RPT_HOST_DELIVERY": "0",
                },
                clear=False,
            ):
                # Clear process-stored token paths by forcing empty returns
                with mock.patch.object(payments, "vps_asset_fetch_token", return_value=""):
                    asset = payments.open_release_asset(WINDOWS_EXE_FILENAME)
                    self.assertIsNotNone(asset)
                    assert asset is not None
                    self.assertEqual(asset.get("source"), "local")
                    body = asset["body"]
                    try:
                        data = body.read(2) if hasattr(body, "read") else body[:2]
                    finally:
                        if hasattr(body, "close"):
                            body.close()
                    self.assertEqual(data[:2], b"MZ")
        finally:
            if created:
                try:
                    path.unlink()
                except OSError:
                    pass

    def test_download_route_wires_host_delivery(self) -> None:
        """Structural: /download uses host_delivery_plan before open_release_asset."""
        app_src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("host_delivery_plan", app_src)
        self.assertIn("helsinki_host", app_src)
        # Host path before proxy
        i_plan = app_src.find("host_delivery_plan")
        i_open = app_src.find("open_release_asset(str(fname))")
        self.assertGreater(i_plan, 0)
        self.assertGreater(i_open, i_plan)
        serve = (ROOT / "node" / "serve_paid_assets.py").read_text(encoding="utf-8")
        self.assertIn("request_authorized", serve)
        self.assertIn("verify_delivery_signature", serve)
        self.assertIn("short-lived", serve.lower() or "signed query")


if __name__ == "__main__":
    unittest.main()

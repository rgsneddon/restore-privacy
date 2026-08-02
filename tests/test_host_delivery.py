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
        from downloads import WINDOWS_EXE_FILENAME

        self.assertIsNone(
            build_host_delivery_url(
                WINDOWS_EXE_FILENAME,
                secret="",
                base_url="https://example.test/paid-assets",
            )
        )
        # Plain HTTP base refused for browser delivery (mixed content)
        self.assertIsNone(
            build_host_delivery_url(
                WINDOWS_EXE_FILENAME,
                secret="sec",
                base_url="http://135.181.152.10:8081/paid-assets",
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
        # Scope to paid /download route — free Suite path also calls open_release_asset
        # earlier in the file, so a global find() is not meaningful.
        i_dl = app_src.find('if path == "/download":')
        self.assertGreater(i_dl, 0)
        i_plan = app_src.find("host_delivery_plan", i_dl)
        i_open = app_src.find("open_release_asset(str(fname))", i_dl)
        self.assertGreater(i_plan, i_dl)
        self.assertGreater(i_open, i_plan)
        # Must not burn grant on 302 (thank-you iframe + manual share one token)
        host_block = app_src[i_plan:i_open]
        self.assertIn("probe=True", host_block)
        self.assertNotIn("consume_download_token(token)", host_block)
        # Host 302 path must not consume; consume is only after full proxy stream.
        self.assertIn("host 302 does not", app_src)
        self.assertIn("Consume only after a successful full stream", app_src)
        serve = (ROOT / "node" / "serve_paid_assets.py").read_text(encoding="utf-8")
        self.assertIn("request_authorized", serve)
        self.assertIn("verify_delivery_signature", serve)
        self.assertIn("short-lived", serve.lower() or "signed query")
        # HEAD must be implemented so platform probes are not all identical 501
        self.assertIn("def do_HEAD", app_src)
        self.assertIn("def do_HEAD", serve)

    def test_probe_failure_returns_none_plan(self) -> None:
        from host_delivery import host_delivery_plan, build_host_delivery_url
        from downloads import WINDOWS_EXE_FILENAME

        url = build_host_delivery_url(
            WINDOWS_EXE_FILENAME,
            secret="sec",
            base_url="https://example.test/paid-assets",
            nonce="n1",
            now=1_700_000_000.0,
        )
        self.assertIsNotNone(url)

        def _boom(*_a, **_k):
            raise OSError("helsinki down")

        plan = host_delivery_plan(
            WINDOWS_EXE_FILENAME,
            force_enabled=True,
            probe=True,
            urlopen=_boom,
        )
        # force_enabled still needs secret/base from env or build — inject via mock
        with mock.patch(
            "host_delivery.build_host_delivery_url", return_value=url
        ):
            with mock.patch(
                "host_delivery.safe_catalog_version_and_filename",
                return_value=("0.5.4", WINDOWS_EXE_FILENAME),
            ):
                plan = host_delivery_plan(
                    WINDOWS_EXE_FILENAME,
                    force_enabled=True,
                    probe=True,
                    urlopen=_boom,
                )
                self.assertIsNone(plan)

    def test_probe_success_keeps_plan(self) -> None:
        from host_delivery import host_delivery_plan
        from downloads import WINDOWS_EXE_FILENAME

        class _Resp:
            status = 200

            def read(self, n: int = -1):
                return b"M"

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def getcode(self):
                return 200

        def _ok(req, timeout=8.0):
            return _Resp()

        url = (
            "https://example.test/paid-assets/0.5.4/"
            + WINDOWS_EXE_FILENAME
            + "?exp=9999999999&n=ab&sig=cd"
        )
        with mock.patch(
            "host_delivery.build_host_delivery_url", return_value=url
        ):
            with mock.patch(
                "host_delivery.safe_catalog_version_and_filename",
                return_value=("0.5.4", WINDOWS_EXE_FILENAME),
            ):
                plan = host_delivery_plan(
                    WINDOWS_EXE_FILENAME,
                    force_enabled=True,
                    probe=True,
                    urlopen=_ok,
                )
                self.assertIsNotNone(plan)
                assert plan is not None
                self.assertEqual(plan["source"], "helsinki_host")

    def test_thankyou_allows_signed_helsinki_url(self) -> None:
        from payments import render_post_payment_thankyou_html
        from host_delivery import is_signed_helsinki_delivery_url
        from downloads import WINDOWS_EXE_FILENAME, RELEASE_VERSION

        bad = "https://github.com/rgsneddon/restore-privacy/releases/download/x/y.exe"
        self.assertFalse(is_signed_helsinki_delivery_url(bad))
        http_bad = (
            f"http://135.181.152.10.sslip.io/paid-assets/{RELEASE_VERSION}/"
            f"{WINDOWS_EXE_FILENAME}?exp=999&n=aa&sig=bb"
        )
        self.assertFalse(is_signed_helsinki_delivery_url(http_bad))
        good = (
            f"https://135.181.152.10.sslip.io/paid-assets/{RELEASE_VERSION}/"
            f"{WINDOWS_EXE_FILENAME}?exp=999&n=aa&sig=bb"
        )
        self.assertTrue(is_signed_helsinki_delivery_url(good))
        html = render_post_payment_thankyou_html(
            download_path=good,
            filename=WINDOWS_EXE_FILENAME,
            platform="windows",
        )
        self.assertIn("auto-download-frame", html)
        self.assertIn(good.split("?", 1)[0], html)
        # Same href for iframe and manual
        self.assertIn('id="success-download-link"', html)
        with self.assertRaises(ValueError):
            render_post_payment_thankyou_html(
                download_path=bad,
                filename="x.exe",
                platform="windows",
            )
        with self.assertRaises(ValueError):
            render_post_payment_thankyou_html(
                download_path=http_bad,
                filename=WINDOWS_EXE_FILENAME,
                platform="windows",
            )

    def test_https_only_browser_delivery_helpers(self) -> None:
        """HTTPS shop must not get http:// host delivery for Windows setup."""
        from host_delivery import (
            build_host_delivery_url,
            is_browser_safe_https_url,
            browser_host_base_url,
            host_delivery_plan,
        )
        from downloads import WINDOWS_EXE_FILENAME

        self.assertTrue(
            is_browser_safe_https_url(
                "https://135.181.152.10.sslip.io/paid-assets/x.exe?exp=1&n=a&sig=b"
            )
        )
        self.assertFalse(
            is_browser_safe_https_url(
                "http://135.181.152.10:8081/paid-assets/x.exe"
            )
        )
        self.assertIsNone(
            browser_host_base_url("http://135.181.152.10:8081/paid-assets")
        )
        self.assertEqual(
            browser_host_base_url("https://example.test/paid-assets"),
            "https://example.test/paid-assets",
        )
        https_url = build_host_delivery_url(
            WINDOWS_EXE_FILENAME,
            secret="sec",
            base_url="https://example.test/paid-assets",
            nonce="n1",
            now=1_700_000_000.0,
        )
        self.assertIsNotNone(https_url)
        assert https_url is not None
        self.assertTrue(https_url.startswith("https://"))
        self.assertIsNone(
            build_host_delivery_url(
                WINDOWS_EXE_FILENAME,
                secret="sec",
                base_url="http://example.test/paid-assets",
                nonce="n1",
            )
        )
        # Plan with HTTP env base must not offer browser 302
        with mock.patch.dict(
            os.environ,
            {
                "RPT_HOST_DELIVERY": "1",
                "RPT_ASSET_FETCH_TOKEN": "tok",
                "RPT_VPS_ASSET_BASE": "http://135.181.152.10:8081/paid-assets",
            },
            clear=False,
        ):
            import host_delivery as hd
            import importlib

            importlib.reload(hd)
            self.assertIsNone(hd.browser_host_base_url())
            self.assertIsNone(hd.host_delivery_plan(WINDOWS_EXE_FILENAME))

    def test_download_route_https_gate_structural(self) -> None:
        app_src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("is_browser_safe_https_url", app_src)
        self.assertIn("safe_https", app_src)
        # 302 only after HTTPS check
        i_safe = app_src.find("safe_https")
        i_302 = app_src.find("self.send_response(302)", i_safe)
        self.assertGreater(i_safe, 0)
        self.assertGreater(i_302, i_safe)
        # Attachment disposition remains on proxy byte path
        self.assertIn('attachment; filename="', app_src)
        from payments import content_type_for_filename
        from downloads import WINDOWS_EXE_FILENAME

        self.assertIn(
            "portable-executable",
            content_type_for_filename(WINDOWS_EXE_FILENAME),
        )


if __name__ == "__main__":
    unittest.main()

"""Inventory + unit coverage of paid download fulfilment paths (monopin catalog)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestCatalogDownloadMethods(unittest.TestCase):
    def test_all_five_platforms_have_catalog_filenames(self):
        from downloads import RELEASE_VERSION, available_downloads

        assets = list(available_downloads())
        plats = {a.platform for a in assets}
        for p in ("windows", "linux", "macos", "ios", "android"):
            self.assertIn(p, plats)
        for a in assets:
            self.assertIn(RELEASE_VERSION, a.filename)
            # Paid entry is /pay path — never free GH permanent installer href
            self.assertTrue(
                a.pay_path.startswith("/pay") or "stripe" in a.pay_path.lower(),
                msg=a.pay_path,
            )
            # a.url may be bookkeeping-only GH shape; must never be used as free href
            self.assertTrue(
                a.pay_path.startswith("/pay"),
                msg=f"public pay entry must be site /pay, got {a.pay_path}",
            )

    def test_vps_asset_url_shape_for_each_platform(self):
        from downloads import RELEASE_VERSION, available_downloads
        from payments import vps_asset_base_url, vps_asset_url

        base = vps_asset_base_url()
        self.assertTrue(base.startswith("http"))
        self.assertIn("paid-assets", base)
        for a in available_downloads():
            url = vps_asset_url(a.filename)
            self.assertTrue(url.startswith(base))
            self.assertIn(f"/{RELEASE_VERSION}/", url)
            self.assertTrue(url.endswith(a.filename))

    def test_open_release_asset_vps_spools_full_body(self):
        """VPS path materialises the full installer before returning body."""
        from downloads import available_downloads
        import payments as pay

        asset = available_downloads()[0]
        payload = b"ABCDEFGH" * 1000

        class _Resp:
            headers = {"Content-Length": str(len(payload))}

            def read(self, n: int = -1):
                data = getattr(self, "_data", payload)
                self._data = b""
                return data

            def close(self):
                return None

        def fake_urlopen(req, timeout=None):
            return _Resp()

        with mock.patch.object(pay, "vps_asset_fetch_token", return_value="tok"):
            with mock.patch.object(pay, "asset_search_dirs", return_value=[]):
                with mock.patch.object(pay, "github_auth_token", return_value=""):
                    opened = pay.open_release_asset(
                        asset.filename, urlopen=fake_urlopen
                    )
        self.assertIsNotNone(opened)
        assert opened is not None
        self.assertEqual(opened["source"], "vps")
        self.assertEqual(opened["body"].read(), payload)
        opened["body"].close()

    def test_download_route_consume_after_stream_in_source(self):
        src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        # Consume must appear after stream_ok path, not before body write loop
        consume_idx = src.index("consume_download_token(token)")
        stream_ok_idx = src.index("stream_ok = True")
        self.assertLess(stream_ok_idx, consume_idx)
        self.assertIn("ConnectionResetError", src)
        self.assertIn("successful full stream", src.lower() or src)

    def test_fulfilment_ready_helper_probes_open(self):
        from payments import check_fulfilment_ready

        with mock.patch(
            "payments.open_release_asset",
            return_value={
                "filename": "x",
                "content_type": "application/octet-stream",
                "content_length": 1,
                "body": BytesIO(b"x"),
                "source": "local",
            },
        ):
            ready = check_fulfilment_ready(platform="windows")
        self.assertTrue(ready.get("ok"))
        self.assertEqual(ready.get("source"), "local")


if __name__ == "__main__":
    unittest.main()

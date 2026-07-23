"""Thank-you pending / packaging copy and download stream chunk size."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

from payments import (  # noqa: E402
    open_release_asset,
    render_post_payment_thankyou_html,
)


class TestThankYouPackagingCopy(unittest.TestCase):
    def test_success_thankyou_has_packaging_wait_copy(self):
        html = render_post_payment_thankyou_html(
            download_path="/download?token=abc_test_token_xyz",
            filename="restore-privacy-client-0.3.9-windows-x64-setup.exe",
            platform="windows",
            session_id="cs_test_packaging_1",
            purchase_id="RPT-PPI-TEST01",
            keygen="RPT-KEY-AAAA-BBBB-CCCC",
        )
        self.assertIn("please wait for your download.. packaging...", html)
        self.assertIn('id="auto-download-note"', html)
        self.assertIn('id="auto-download-frame"', html)
        self.assertIn("/download?token=", html)
        self.assertNotIn("If nothing appears after ~30s", html)
        self.assertNotIn("contact support with session id", html.lower())
        # Installer iframe has immediate src; entitlement deferred
        self.assertIn('id="auto-download-frame"', html)
        self.assertIn('data-src=', html)  # entitlement deferred
        self.assertIn("setTimeout", html)
        # KEYGEN prominent + copy control; under ready lines; no page auto-close
        self.assertIn('id="product-keygen"', html)
        self.assertIn("RPT-KEY-AAAA-BBBB-CCCC", html)
        self.assertIn('id="keygen-copy-btn"', html)
        self.assertIn("Copy keygen", html)
        self.assertIn('id="keygen-box"', html)
        self.assertIn('data-keygen-prominent="1"', html)
        self.assertIn('data-page-lifetime="until-tab-close"', html)
        self.assertIn('data-available-until-tab-close="1"', html)
        self.assertIn('id="success-download-link"', html)
        # KEYGEN appears after package-ready line, before PPI box
        ready_i = html.find('id="paid-package-name"')
        kg_i = html.find('id="keygen-box"')
        ppi_i = html.find('id="purchase-id-box"')
        self.assertGreater(kg_i, ready_i)
        self.assertGreater(ppi_i, kg_i)
        # No auto-navigation refresh header; download control stays in markup
        self.assertNotIn('http-equiv="refresh"', html.lower())
        self.assertNotIn("location.href", html.lower())
        self.assertNotIn('success-download-link").disabled', html)

    def test_pending_success_branch_copy_via_handler_source(self):
        """Pending branch lives in app.py — assert shipped source strings."""
        src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("please wait for your download.. packaging...", src)
        self.assertIn("pay-success-packaging", src)
        self.assertNotIn("If nothing appears after ~30s", src)
        self.assertNotIn("contact support with session id", src.lower())


class TestDownloadStreamLocalFastPath(unittest.TestCase):
    def test_open_release_asset_local_streams_file(self):
        from downloads import RELEASE_ASSETS

        a = RELEASE_ASSETS[0]
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            f = base / a.filename
            payload = b"RPT-INSTALLER-FAKE-" + b"x" * 4000
            f.write_bytes(payload)
            with mock.patch("payments.asset_search_dirs", return_value=[base]):
                asset = open_release_asset(a.filename)
            self.assertIsNotNone(asset)
            assert asset is not None
            self.assertEqual(asset["source"], "local")
            self.assertEqual(asset["content_length"], len(payload))
            body = asset["body"]
            try:
                data = body.read()
            finally:
                body.close()
            self.assertEqual(data, payload)

    def test_download_handler_uses_large_chunk(self):
        src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("256 * 1024", src)
        self.assertIn("wfile.flush", src)


if __name__ == "__main__":
    unittest.main()

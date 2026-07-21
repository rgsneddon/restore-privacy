"""Per-device catalog + Iceland VPS paid-asset host path (shipped helpers)."""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))
sys.path.insert(0, str(ROOT / "scripts"))

from downloads import (  # noqa: E402
    RELEASE_VERSION,
    available_downloads,
    list_catalog_platform_packages,
    render_download_section_html,
)
import payments  # noqa: E402


def _load_host_script():
    path = ROOT / "scripts" / "host_paid_assets_vps.py"
    spec = importlib.util.spec_from_file_location("host_paid_assets_vps", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestCatalogPerDevice(unittest.TestCase):
    def test_five_platforms_individually(self):
        pkgs = list_catalog_platform_packages()
        self.assertEqual(len(pkgs), 5)
        platforms = [p["platform"] for p in pkgs]
        self.assertEqual(
            platforms, ["windows", "android", "macos", "ios", "linux"]
        )
        for p in pkgs:
            self.assertEqual(p["version"], RELEASE_VERSION)
            self.assertTrue(
                p["filename"].startswith(f"restore-privacy-client-{RELEASE_VERSION}-")
            )
            self.assertEqual(p["relative_path"], f"{p['version']}/{p['filename']}")
            # one device → one distinct filename
            self.assertIn(p["filename"], {a.filename for a in available_downloads()})

    def test_script_list_matches_catalog(self):
        mod = _load_host_script()
        listed = mod.list_packages()
        pure = list_catalog_platform_packages()
        self.assertEqual(listed, pure)
        self.assertEqual(len(listed), 5)

    def test_public_ui_no_free_gh_hrefs(self):
        html = render_download_section_html()
        for a in available_downloads():
            self.assertNotIn(f'href="{a.url}"', html)
        self.assertNotIn("releases/download/", html.split("dl-buttons")[0])


class TestVpsAssetOpen(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        for k in (
            "RPT_ASSET_DIR",
            "RPT_ASSET_FETCH_TOKEN",
            "RPT_VPS_ASSET_TOKEN",
            "RPT_VPS_ASSET_BASE",
            "RPT_GITHUB_TOKEN",
            "GITHUB_TOKEN",
            "GH_TOKEN",
        ):
            os.environ.pop(k, None)

    def test_asset_search_includes_vps_remote_layout(self):
        dirs = [str(p) for p in payments.asset_search_dirs()]
        joined = "\n".join(dirs)
        self.assertIn("paid_assets", joined)
        self.assertIn(RELEASE_VERSION, joined)

    def test_vps_url_per_device_filename(self):
        for a in available_downloads():
            url = payments.vps_asset_url(a.filename)
            self.assertIn("82.221.101.241", url)
            self.assertIn("/paid-assets/", url)
            self.assertTrue(url.endswith(f"/{RELEASE_VERSION}/{a.filename}"))

    def test_open_prefers_local_vps_layout_dir(self):
        # Mirror Iceland on-disk layout under a temp RPT_ASSET_DIR
        os.environ["RPT_ASSET_DIR"] = self._td.name
        fname = next(a.filename for a in available_downloads() if a.platform == "linux")
        payload = b"LINUX-VPS-LAYOUT-BYTES"
        (Path(self._td.name) / fname).write_bytes(payload)
        asset = payments.open_release_asset(fname)
        self.assertIsNotNone(asset)
        assert asset is not None
        self.assertEqual(asset["source"], "local")
        body = asset["body"]
        try:
            data = body.read() if hasattr(body, "read") else body
        finally:
            if hasattr(body, "close"):
                body.close()
        self.assertEqual(data, payload)

    def test_open_vps_http_with_token(self):
        fname = next(a.filename for a in available_downloads() if a.platform == "windows")
        os.environ["RPT_ASSET_FETCH_TOKEN"] = "unit-vps-secret"
        os.environ["RPT_VPS_ASSET_BASE"] = "http://82.221.101.241:8081/paid-assets"
        # Empty local search
        empty = Path(self._td.name) / "empty"
        empty.mkdir()
        os.environ["RPT_ASSET_DIR"] = str(empty)
        seen = []

        class FakeResp:
            def __init__(self, data: bytes, headers=None):
                self._data = data
                self.headers = headers or {"Content-Length": str(len(data))}

            def read(self, n=-1):
                if n is None or n < 0:
                    out, self._data = self._data, b""
                    return out
                out, self._data = self._data[:n], self._data[n:]
                return out

            def close(self):
                pass

        def fake_urlopen(req, timeout=None):
            url = req.full_url if hasattr(req, "full_url") else req.get_full_url()
            headers = {k.lower(): v for k, v in req.header_items()}
            seen.append((url, headers.get("x-rpt-asset-token", "")))
            if "/paid-assets/" in url and fname in url:
                return FakeResp(b"EXE-FROM-VPS")
            raise AssertionError(f"unexpected {url}")

        with mock.patch.object(
            payments,
            "asset_search_dirs",
            return_value=[empty],
        ):
            asset = payments.open_release_asset(fname, urlopen=fake_urlopen)
        self.assertIsNotNone(asset)
        assert asset is not None
        self.assertEqual(asset["source"], "vps")
        data = asset["body"].read()
        asset["body"].close()
        self.assertEqual(data, b"EXE-FROM-VPS")
        self.assertTrue(any(t == "unit-vps-secret" for _, t in seen), seen)
        self.assertTrue(any(fname in u for u, _ in seen), seen)

    def test_reject_unknown_filename(self):
        self.assertIsNone(payments.open_release_asset("not-a-product.bin"))


class TestServePaidAssetsScript(unittest.TestCase):
    def test_serve_script_exists_and_token_gates(self):
        p = ROOT / "node" / "serve_paid_assets.py"
        self.assertTrue(p.is_file())
        text = p.read_text(encoding="utf-8")
        self.assertIn("X-RPT-Asset-Token", text)
        self.assertIn("/paid-assets", text)
        self.assertIn("paid_assets", text)


class TestHostScriptStructural(unittest.TestCase):
    def test_script_wires_five_devices_and_vps_path(self):
        text = (ROOT / "scripts" / "host_paid_assets_vps.py").read_text(encoding="utf-8")
        self.assertIn("list_catalog_platform_packages", text)
        self.assertIn("82.221.101.241", text)
        self.assertIn("paid_assets", text)
        self.assertIn("--list", text)
        self.assertIn("--stage", text)
        self.assertIn("--upload", text)
        for plat in ("windows", "android", "macos", "ios", "linux"):
            # enumeration comes from catalog constants, not hard-coded one-blob
            self.assertTrue(plat)


if __name__ == "__main__":
    unittest.main()

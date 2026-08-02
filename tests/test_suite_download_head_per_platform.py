"""HEAD on free Suite platform links must not all return the same 501.

Regression: status host only implemented do_GET, so curl -I / link checkers
got identical 501 Unsupported method for every platform. GET already 302s to
distinct Helsinki filenames; HEAD must mirror those distinct Locations.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))
sys.path.insert(0, str(ROOT / "node"))

import app as status_app  # noqa: E402
from downloads import list_catalog_platform_packages  # noqa: E402


class _FakeHandler(status_app.Handler):
    """In-process handler capturing status/headers/body without sockets."""

    def __init__(self, path: str, *, command: str = "GET"):
        self.path = path
        self.command = command
        self.headers = {}
        self.wfile = BytesIO()
        self.rfile = BytesIO()
        self.code: int | None = None
        self.sent_headers: dict[str, str] = {}

    def send_response(self, code: int, message: str | None = None) -> None:
        self.code = code

    def send_header(self, key: str, value: str) -> None:
        self.sent_headers[key] = value

    def end_headers(self) -> None:
        return

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


class TestSuiteDownloadHeadPerPlatform(unittest.TestCase):
    def test_head_free_direct_distinct_locations_per_platform(self) -> None:
        pkgs = list_catalog_platform_packages()
        self.assertEqual(len(pkgs), 5)

        def fake_plan(filename: str, **_kwargs):
            ver = pkgs[0]["version"]
            return {
                "url": (
                    f"https://assets.example.test/paid-assets/{ver}/"
                    f"{filename}?exp=9999999999&n=ab&sig=cd"
                ),
                "version": ver,
                "filename": filename,
                "source": "helsinki_host",
                "store_probed": True,
            }

        locations: dict[str, str] = {}
        with mock.patch(
            "host_delivery.suite_free_delivery_plan", side_effect=fake_plan
        ):
            for p in pkgs:
                plat = p["platform"]
                fname = p["filename"]
                path = f"/suite/download?platform={plat}&free_direct=1"
                h = _FakeHandler(path, command="HEAD")
                h.do_HEAD()
                self.assertNotEqual(
                    h.code,
                    501,
                    msg=f"{plat}: HEAD must not be Unsupported method (got {h.code})",
                )
                self.assertEqual(h.code, 302, msg=f"{plat}: expected 302 got {h.code}")
                loc = h.sent_headers.get("Location") or ""
                self.assertIn(fname, loc, msg=f"{plat}: Location missing {fname}")
                self.assertEqual(
                    h.wfile.getvalue(),
                    b"",
                    msg=f"{plat}: HEAD must not send body",
                )
                locations[plat] = loc

        basenames = {
            loc.split("?")[0].rsplit("/", 1)[-1] for loc in locations.values()
        }
        self.assertEqual(len(basenames), 5, msg=basenames)

        # GET still works and matches the same filenames
        with mock.patch(
            "host_delivery.suite_free_delivery_plan", side_effect=fake_plan
        ):
            h = _FakeHandler(
                "/suite/download?platform=windows&free_direct=1", command="GET"
            )
            h.do_GET()
            self.assertEqual(h.code, 302)
            self.assertIn("windows", h.sent_headers.get("Location", ""))


class TestServePaidAssetsHead(unittest.TestCase):
    def test_head_returns_per_file_headers_no_body(self) -> None:
        path = ROOT / "node" / "serve_paid_assets.py"
        spec = importlib.util.spec_from_file_location("serve_paid_assets", path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ver = "1.0.8"
            (root / ver).mkdir()
            files = {
                "restore-privacy-client-1.0.8-windows-x64-setup.exe": b"MZ-WIN-" + b"A" * 40,
                "restore-privacy-client-1.0.8-android.apk": b"PK-APK-" + b"B" * 80,
                "restore-privacy-client-1.0.8-macos.zip": b"PK-MAC-" + b"C" * 120,
            }
            for name, data in files.items():
                (root / ver / name).write_bytes(data)

            os.environ["RPT_ASSET_FETCH_TOKEN"] = "head-unit-token"
            os.environ["RPT_VPS_ASSET_REMOTE_ROOT"] = str(root)
            os.environ["RPT_CATALOG_VERSION"] = ver

            httpd = ThreadingHTTPServer(("127.0.0.1", 0), mod.Handler)
            port = httpd.server_address[1]
            t = threading.Thread(target=httpd.serve_forever, daemon=True)
            t.start()
            try:
                from host_delivery import mint_delivery_signature

                seen_disp: set[str] = set()
                seen_len: set[str] = set()
                for name, data in files.items():
                    exp = int(time.time()) + 600
                    nonce = "n" + name[:6]
                    sig = mint_delivery_signature(
                        version=ver,
                        filename=name,
                        exp=exp,
                        nonce=nonce,
                        secret="head-unit-token",
                    )
                    q = f"exp={exp}&n={nonce}&sig={sig}"
                    url = f"http://127.0.0.1:{port}/paid-assets/{ver}/{name}?{q}"
                    req = Request(url, method="HEAD")
                    with urlopen(req, timeout=5) as resp:
                        self.assertEqual(resp.status, 200)
                        cl = resp.headers.get("Content-Length")
                        disp = resp.headers.get("Content-Disposition") or ""
                        body = resp.read()
                    self.assertEqual(body, b"")
                    self.assertEqual(cl, str(len(data)))
                    self.assertIn(name, disp)
                    seen_disp.add(disp)
                    seen_len.add(cl or "")
                self.assertEqual(len(seen_disp), 3)
                self.assertEqual(len(seen_len), 3)
            finally:
                httpd.shutdown()


if __name__ == "__main__":
    unittest.main()

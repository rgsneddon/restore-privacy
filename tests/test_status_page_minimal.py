"""Public status page: title + legal links + downloads + Rust footer (no live count)."""

from __future__ import annotations

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
from downloads import (  # noqa: E402
    ANDROID_APK_FILENAME,
    RUST_REPO_URL,
    WINDOWS_ZIP_FILENAME,
    available_downloads,
)


class TestPublicPageWithDownloads(unittest.TestCase):
    def test_render_has_title_and_download_buttons_no_count(self):
        html = status_app.render_html(
            {"title": "RESTORE PRIVACY"}
        ).decode("utf-8")
        self.assertIn("RESTORE PRIVACY", html)
        self.assertNotIn("BETA - test phase - please report any bugs to", html)
        self.assertNotIn(
            "Download the client for your platform. No public live session counter",
            html,
        )
        self.assertNotIn("Windows setup needs no separate Python install", html)
        self.assertNotIn('class="dl-note"', html)
        self.assertIn("LICENCE", html)
        self.assertIn("PRIVACY POLICY", html)
        self.assertIn("SECURITY AUDIT", html)
        self.assertNotIn("Currently connected clients", html)
        self.assertNotIn('id="clients-connected"', html)
        self.assertNotIn("fetch('/api/status'", html)
        self.assertNotIn("setInterval(poll", html)
        self.assertIn("Download client v1.0.0", html)
        self.assertIn(WINDOWS_ZIP_FILENAME, html)
        self.assertIn(ANDROID_APK_FILENAME, html)
        for a in available_downloads():
            self.assertIn(a.url, html)
        self.assertIn(RUST_REPO_URL, html)
        self.assertIn("RUST-IN-PRIVACY", html)
        self.assertIn('id="rust-repo-link"', html)
        self.assertNotIn("connect-via-web", html)
        self.assertNotIn("Connect via web", html)
        self.assertNotIn("buymeacoffee.com", html)

    def test_handler_twice_has_downloads(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), status_app.Handler)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            with mock.patch.object(
                status_app,
                "fetch_upstream_status",
                return_value={"title": "RESTORE PRIVACY", "upstream_ok": True},
            ):
                for _ in range(2):
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/", timeout=5
                    ) as resp:
                        html = resp.read().decode("utf-8")
                    self.assertIn("RESTORE PRIVACY", html)
                    self.assertIn("LICENCE", html)
                    self.assertIn("PRIVACY POLICY", html)
                    self.assertIn("SECURITY AUDIT", html)
                    self.assertNotIn("BETA - test phase", html)
                    self.assertNotIn("clients-connected", html)
                    self.assertNotIn("fetch('/api/status'", html)
                    self.assertIn("Download client v1.0.0", html)
                    self.assertIn(WINDOWS_ZIP_FILENAME, html)
                    self.assertIn("/releases/download/v1.0.0/", html)
                    self.assertIn(RUST_REPO_URL, html)
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()

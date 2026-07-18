"""Public status page: title + live count + Windows .exe / Android .apk downloads."""

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
    WINDOWS_EXE_FILENAME,
    available_downloads,
)


class TestPublicPageWithDownloads(unittest.TestCase):
    def test_render_has_title_count_poll_and_download_buttons(self):
        html = status_app.render_html(
            {"title": "RESTORE PRIVACY", "clients_connected": 3}
        ).decode("utf-8")
        self.assertIn("RESTORE PRIVACY", html)
        self.assertIn("BETA - test phase - please report any bugs to", html)
        self.assertIn("https://x.com/rgsneddon", html)
        self.assertIn("Currently connected clients", html)
        self.assertIn('id="clients-connected"', html)
        self.assertIn(">3<", html)
        self.assertIn("fetch('/api/status'", html)
        self.assertIn("setInterval(poll", html)
        # Download buttons for v0.1.3 exe + apk
        self.assertIn("Download client v0.1.3", html)
        self.assertIn(WINDOWS_EXE_FILENAME, html)
        self.assertIn(ANDROID_APK_FILENAME, html)
        self.assertIn(".exe", html)
        self.assertIn(".apk", html)
        for a in available_downloads():
            self.assertIn(a.url, html)
        # No connect-via-web / coffee chrome
        self.assertNotIn("connect-via-web", html)
        self.assertNotIn("Connect via web", html)
        self.assertNotIn("buymeacoffee.com", html)
        self.assertNotIn("buy rus a coffee", html)

    def test_handler_twice_has_downloads(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), status_app.Handler)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            with mock.patch.object(
                status_app,
                "fetch_upstream_status",
                return_value={"title": "RESTORE PRIVACY", "clients_connected": 2},
            ):
                for _ in range(2):
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/", timeout=5
                    ) as resp:
                        html = resp.read().decode("utf-8")
                    self.assertIn("RESTORE PRIVACY", html)
                    self.assertIn(
                        "BETA - test phase - please report any bugs to", html
                    )
                    self.assertIn("https://x.com/rgsneddon", html)
                    self.assertIn("clients-connected", html)
                    self.assertIn("fetch('/api/status'", html)
                    self.assertIn("Download client v0.1.3", html)
                    self.assertIn(WINDOWS_EXE_FILENAME, html)
                    self.assertIn(ANDROID_APK_FILENAME, html)
                    self.assertIn("/releases/download/0.1.3/", html)
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()

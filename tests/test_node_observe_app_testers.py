"""Node public observe UI redirects browsers to app-testers; JSON stays title-only."""

from __future__ import annotations

import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from node.ui import (  # noqa: E402
    DEFAULT_OBSERVE_REDIRECT_URL,
    make_handler,
    observe_redirect_url,
    public_status_from_payload,
)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def _opener_no_redirect():
    return urllib.request.build_opener(_NoRedirect)


class TestObserveRedirectUrl(unittest.TestCase):
    def test_default_is_product_app_testers(self) -> None:
        self.assertEqual(
            DEFAULT_OBSERVE_REDIRECT_URL,
            "https://restoreprivacy.online/app-testers",
        )
        # Without env override, observe_redirect_url matches default
        import os

        old = os.environ.pop("RPT_NODE_OBSERVE_URL", None)
        try:
            self.assertEqual(
                observe_redirect_url(),
                "https://restoreprivacy.online/app-testers",
            )
        finally:
            if old is not None:
                os.environ["RPT_NODE_OBSERVE_URL"] = old


class TestNodeObserveRedirect(unittest.TestCase):
    def setUp(self) -> None:
        def get_status():
            return {"title": "RESTORE PRIVACY", "clients_connected": 99, "live": 3}

        self.Handler = make_handler(get_status)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), self.Handler)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.port}"

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    def _get_redirect(self, path: str) -> tuple[int, str, str]:
        """GET without following redirects; return (status, Location, body)."""
        req = urllib.request.Request(self.base + path, method="GET")
        try:
            with _opener_no_redirect().open(req, timeout=5) as resp:
                return (
                    int(resp.status),
                    resp.headers.get("Location") or "",
                    resp.read().decode("utf-8"),
                )
        except urllib.error.HTTPError as e:
            return (
                int(e.code),
                e.headers.get("Location") or "",
                e.read().decode("utf-8"),
            )

    def test_root_redirects_to_app_testers(self) -> None:
        status, loc, body = self._get_redirect("/")
        self.assertIn(status, (301, 302, 303, 307, 308))
        self.assertEqual(loc, "https://restoreprivacy.online/app-testers")
        self.assertIn("https://restoreprivacy.online/app-testers", body)
        # Old primary observe landing is gone
        self.assertNotIn("Node online. No public live session counter.", body)
        self.assertNotIn("Clients connected", body)
        self.assertNotIn("clients_connected", body)

    def test_index_html_same_redirect(self) -> None:
        status, loc, _body = self._get_redirect("/index.html")
        self.assertIn(status, (301, 302, 303, 307, 308))
        self.assertEqual(loc, "https://restoreprivacy.online/app-testers")

    def test_observe_path_redirects(self) -> None:
        status, loc, _body = self._get_redirect("/observe")
        self.assertIn(status, (301, 302, 303, 307, 308))
        self.assertEqual(loc, "https://restoreprivacy.online/app-testers")

    def test_api_status_title_only_not_redirect(self) -> None:
        with urllib.request.urlopen(self.base + "/api/status", timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            ctype = resp.headers.get("Content-Type") or ""
            self.assertIn("application/json", ctype)
            data = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(data, {"title": "RESTORE PRIVACY"})
        self.assertNotIn("clients_connected", data)
        self.assertNotIn("live", data)
        self.assertNotIn("sessions", data)

    def test_status_path_title_only(self) -> None:
        with urllib.request.urlopen(self.base + "/status", timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(data.get("title"), "RESTORE PRIVACY")
        for bad in ("clients_connected", "live", "utilization", "capacity"):
            self.assertNotIn(bad, data)

    def test_handler_observe_url_override(self) -> None:
        def get_status():
            return {"title": "RESTORE PRIVACY"}

        Handler = make_handler(
            get_status, observe_url="https://example.test/app-testers"
        )
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{port}/", method="GET")
            try:
                with _opener_no_redirect().open(req, timeout=5) as resp:
                    loc = resp.headers.get("Location") or ""
            except urllib.error.HTTPError as e:
                loc = e.headers.get("Location") or ""
            self.assertEqual(loc, "https://example.test/app-testers")
        finally:
            httpd.shutdown()
            httpd.server_close()


class TestPublicStatusHelper(unittest.TestCase):
    def test_filter_strips_counts(self) -> None:
        safe = public_status_from_payload(
            {"title": "RESTORE PRIVACY", "clients_connected": 4, "live": 2}
        )
        self.assertEqual(safe, {"title": "RESTORE PRIVACY"})


if __name__ == "__main__":
    unittest.main()

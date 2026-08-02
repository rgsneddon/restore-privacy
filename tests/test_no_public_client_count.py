"""Public status surfaces must not expose a live client count."""

from __future__ import annotations

import json
import sys
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))
sys.path.insert(0, str(ROOT))

import app as status_app  # noqa: E402
from node.sessions import Session, SessionRegistry  # noqa: E402
from node.ui import make_handler, public_status_from_payload  # noqa: E402


class TestStatusPageNoCount(unittest.TestCase):
    def test_normalize_and_public_payload_title_only(self):
        out = status_app.normalize_status(
            {"title": "RESTORE PRIVACY", "clients_connected": 99, "secret": "x"}
        )
        self.assertEqual(out, {"title": "RESTORE PRIVACY SUITE"})
        self.assertNotIn("clients_connected", out)
        pub = status_app.public_status_payload(
            {"title": "RESTORE PRIVACY", "clients_connected": 5}
        )
        self.assertEqual(set(pub.keys()), {"title"})
        self.assertNotIn("clients_connected", pub)

    def test_render_html_has_no_counter_ui(self):
        html = status_app.render_html(
            {"title": "RESTORE PRIVACY"}
        ).decode("utf-8")
        self.assertIn("RESTORE PRIVACY", html)
        self.assertIn("Download Suite client", html)
        self.assertNotIn("Currently connected clients", html)
        self.assertNotIn("clients-connected", html)
        self.assertNotIn("clients_connected", html)
        self.assertNotIn("Live count", html)
        self.assertNotIn("fetch('/api/status'", html)

    def test_api_status_json_title_only(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), status_app.Handler)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            with mock.patch.object(
                status_app,
                "fetch_upstream_status",
                return_value={"title": "RESTORE PRIVACY", "upstream_ok": True},
            ):
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/status", timeout=5
                ) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data, {"title": "RESTORE PRIVACY SUITE"})
            self.assertNotIn("clients_connected", data)
        finally:
            httpd.shutdown()
            httpd.server_close()


class TestNodePublicStatusNoCount(unittest.TestCase):
    def test_registry_status_payload_no_count(self):
        reg = SessionRegistry(idle_sec=120)
        reg.add(
            Session(
                session_id=b"\x01" * 8,
                crypto=object(),
                client_addr=("1.2.3.4", 9),
                vpn_ip="10.88.0.2",
            )
        )
        self.assertEqual(reg.count(), 1)  # internal routing size still works
        payload = reg.status_payload()
        self.assertEqual(payload, {"title": "RESTORE PRIVACY"})
        self.assertNotIn("clients_connected", payload)

    def test_node_ui_api_strips_count(self):
        def get_status():
            return {"title": "RESTORE PRIVACY", "clients_connected": 7}

        self.assertEqual(
            public_status_from_payload(get_status()),
            {"title": "RESTORE PRIVACY"},
        )
        Handler = make_handler(get_status)
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/status", timeout=5
            ) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            # Node UI public API still title-only (short product name from node)
            self.assertEqual(data, {"title": "RESTORE PRIVACY"})
            # Browser observe path redirects to app-testers (do not follow)
            class _NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    return None

            req = urllib.request.Request(f"http://127.0.0.1:{port}/", method="GET")
            try:
                with urllib.request.build_opener(_NoRedirect).open(
                    req, timeout=5
                ) as resp:
                    status = resp.status
                    loc = resp.headers.get("Location") or ""
                    html = resp.read().decode("utf-8")
            except urllib.error.HTTPError as e:
                status = e.code
                loc = e.headers.get("Location") or ""
                html = e.read().decode("utf-8")
            self.assertIn(status, (301, 302, 303, 307, 308))
            self.assertIn("restoreprivacy.online/app-testers", loc)
            self.assertNotIn("Clients connected", html)
            self.assertNotIn('id="n"', html)
            self.assertNotIn("Node online. No public live session counter.", html)
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()

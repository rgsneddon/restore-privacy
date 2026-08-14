"""Fleet /admin/fleet SG row: catalog peer + private capacity probe path."""

from __future__ import annotations

import io
import json
import sys
import urllib.error
from email.message import Message
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestAdminFleetSgCatalogAndProbe(TestCase):
    def test_product_catalog_peers_includes_sg_host(self) -> None:
        from client.multihop import PRODUCT_SG_HOST, product_country_catalog
        from status_page.admin_node_usage import product_catalog_peers

        shipped = [(n.code, n.host) for n in product_country_catalog()]
        self.assertIn(("SG", "5.223.48.8"), shipped)
        self.assertEqual(PRODUCT_SG_HOST, "5.223.48.8")

        peers = product_catalog_peers()
        sg = next(p for p in peers if p["code"] == "SG")
        self.assertEqual(sg["host"], "5.223.48.8")
        self.assertEqual(sg["name"], "Singapore")

    def test_fleet_probe_url_and_401_marks_sg_error(self) -> None:
        from status_page.admin_node_usage import (
            collect_live_fleet_usage_rows,
            private_capacity_url,
            probe_peer_private_capacity,
        )

        sg_host = "5.223.48.8"
        self.assertEqual(
            private_capacity_url(sg_host),
            "http://5.223.48.8:8080/api/private/capacity",
        )

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b"unauthorized")

            def log_message(self, fmt: str, *args: object) -> None:
                return

        httpd = HTTPServer(("127.0.0.1", 0), _Handler)
        thread = Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            port = httpd.server_address[1]
            payload, err = probe_peer_private_capacity(
                "127.0.0.1",
                token="test-token",
                timeout_s=2.0,
                ui_port=port,
            )
            self.assertIsNone(payload)
            self.assertEqual(err, "HTTP 401")
        finally:
            httpd.shutdown()
            httpd.server_close()

        def transport(url: str, headers: dict[str, str], timeout_s: float) -> str:
            if "5.223.48.8" in url:
                raise urllib.error.HTTPError(
                    url, 401, "Unauthorized", Message(), io.BytesIO(b"unauthorized")
                )
            if "178.105.187.178" in url:
                return json.dumps(
                    {
                        "live": 1,
                        "capacity": 1024,
                        "process_uptime_sec": 10,
                        "total_bytes_relayed": 100,
                        "private": True,
                    }
                )
            raise urllib.error.URLError("unexpected host")

        rows = collect_live_fleet_usage_rows(
            env={"RPT_CAPACITY_TOKEN": "test-token"},
            transport=transport,
        )
        by = {r.code: r for r in rows}
        self.assertIn("SG", by)
        self.assertEqual(by["SG"].host, "5.223.48.8")
        self.assertEqual(by["SG"].status, "error")
        self.assertEqual(by["SG"].detail, "HTTP 401")
        self.assertEqual(by["DE"].status, "ok")

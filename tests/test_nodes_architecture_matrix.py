"""Three-peer residual architecture matrix (shipped catalog + live optional).

Unit parts always run. Live HTTP/UDP probes run when RPT_LIVE_NODE_PROBE=1
(or always when hosts answer — fail soft to skip if offline).
"""

from __future__ import annotations

import json
import os
import random
import socket
import sys
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.endpoint import (  # noqa: E402
    product_de_node_elgamal_pub_path,
    product_exit_node_elgamal_pub_path,
    product_node_elgamal_pub_path,
)
from client.multihop import (  # noqa: E402
    COUNTRY_DE,
    COUNTRY_IS,
    COUNTRY_RO,
    PRODUCT_COUNTRY_CATALOG,
    PRODUCT_DE_HOST,
    PRODUCT_EXIT_HOST,
    PRODUCT_NODE_HOST,
    resolve_entry_exit,
)
from client.secrets_loader import load_node_elgamal_public_for_endpoint  # noqa: E402
from node.fleet_wipe import fleet_country_codes  # noqa: E402


class TestThreePeerArchitecture(unittest.TestCase):
    def test_catalog_hosts_and_pins(self):
        by_code = {n.code: n for n in PRODUCT_COUNTRY_CATALOG}
        self.assertEqual(set(by_code), {COUNTRY_IS, COUNTRY_RO, COUNTRY_DE})
        self.assertEqual(by_code[COUNTRY_IS].host, PRODUCT_NODE_HOST)
        self.assertEqual(by_code[COUNTRY_RO].host, PRODUCT_EXIT_HOST)
        self.assertEqual(by_code[COUNTRY_DE].host, PRODUCT_DE_HOST)
        self.assertEqual(by_code[COUNTRY_DE].host, "167.233.224.5")
        self.assertEqual(by_code[COUNTRY_IS].pub_name, "node_elgamal.pub")
        self.assertEqual(by_code[COUNTRY_RO].pub_name, "exit_node_elgamal.pub")
        self.assertEqual(by_code[COUNTRY_DE].pub_name, "de_node_elgamal.pub")
        for p in (
            product_node_elgamal_pub_path(),
            product_exit_node_elgamal_pub_path(),
            product_de_node_elgamal_pub_path(),
        ):
            self.assertTrue(p.is_file(), p)
            self.assertEqual(p.stat().st_size, 256)

    def test_fleet_order_is_ro_de(self):
        self.assertEqual(fleet_country_codes(), ["IS", "RO", "DE"])

    def test_multihop_exit_never_entry_host(self):
        for code in (COUNTRY_IS, COUNTRY_RO, COUNTRY_DE):
            for seed in range(8):
                e, x = resolve_entry_exit(
                    code, multihop_enabled=True, rng=random.Random(seed)
                )
                self.assertEqual(e.code, code)
                self.assertIsNotNone(x)
                assert x is not None
                self.assertNotEqual(e.host, x.host)
                self.assertNotEqual(e.code, x.code)

    def test_load_pub_for_each_peer_endpoint(self):
        for n in PRODUCT_COUNTRY_CATALOG:
            pub = load_node_elgamal_public_for_endpoint(n.as_endpoint())
            self.assertGreater(pub.y.bit_length(), 2000)


class TestLivePeerSurfaces(unittest.TestCase):
    """Best-effort live probes — skip entire class if RPT_LIVE_NODE_PROBE=0."""

    @classmethod
    def setUpClass(cls):
        # Default: run live probes (goal is operational verification). Set
        # RPT_LIVE_NODE_PROBE=0 to skip in offline CI.
        cls.enabled = os.environ.get("RPT_LIVE_NODE_PROBE", "1").strip().lower() not in (
            "0",
            "false",
            "no",
            "off",
        )

    def test_public_status_title_only_all_peers(self):
        if not self.enabled:
            self.skipTest("RPT_LIVE_NODE_PROBE=0")
        for n in PRODUCT_COUNTRY_CATALOG:
            url = f"http://{n.host}:8080/api/status"
            try:
                with urllib.request.urlopen(url, timeout=6) as r:  # noqa: S310
                    raw = r.read().decode()
                data = json.loads(raw)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
                self.fail(f"{n.code} status unreachable: {exc}")
            self.assertEqual(
                set(data.keys()),
                {"title"},
                f"{n.code} not title-only: {data!r}",
            )
            self.assertNotIn("clients_connected", data)
            self.assertNotIn("active_sessions", data)
            self.assertNotIn("utilization", data)

    def test_udp_44044_send_all_peers(self):
        if not self.enabled:
            self.skipTest("RPT_LIVE_NODE_PROBE=0")
        for n in PRODUCT_COUNTRY_CATALOG:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(3)
            try:
                sock.sendto(b"RPT2", (n.host, int(n.port)))
            except OSError as exc:
                self.fail(f"{n.code} udp send fail: {exc}")
            finally:
                sock.close()


if __name__ == "__main__":
    unittest.main()

"""Three-peer residual architecture matrix (shipped catalog + live optional).

Unit parts always run. Live HTTP/UDP probes run when RPT_LIVE_NODE_PROBE=1
(or always when hosts answer — fail soft to skip if offline).
Germany residual peer remains retired from the product catalog.
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
    product_exit_node_elgamal_pub_path,
    product_node_elgamal_pub_path,
    product_us_node_elgamal_pub_path,
)
from client.multihop import (  # noqa: E402
    COUNTRY_IS,
    COUNTRY_RO,
    COUNTRY_US,
    PRODUCT_COUNTRY_CATALOG,
    PRODUCT_EXIT_HOST,
    PRODUCT_NODE_HOST,
    PRODUCT_US_HOST,
    resolve_entry_exit,
)
from client.secrets_loader import load_node_elgamal_public_for_endpoint  # noqa: E402
from node.fleet_wipe import fleet_country_codes  # noqa: E402


class TestThreePeerArchitecture(unittest.TestCase):
    def test_catalog_hosts_and_pins(self):
        by_code = {n.code: n for n in PRODUCT_COUNTRY_CATALOG}
        self.assertEqual(set(by_code), {COUNTRY_IS, COUNTRY_RO, COUNTRY_US})
        self.assertNotIn("DE", by_code)
        self.assertEqual(by_code[COUNTRY_IS].host, PRODUCT_NODE_HOST)
        self.assertEqual(by_code[COUNTRY_RO].host, PRODUCT_EXIT_HOST)
        self.assertEqual(by_code[COUNTRY_US].host, PRODUCT_US_HOST)
        self.assertEqual(by_code[COUNTRY_US].host, "5.161.242.85")
        self.assertEqual(by_code[COUNTRY_IS].pub_name, "node_elgamal.pub")
        self.assertEqual(by_code[COUNTRY_RO].pub_name, "exit_node_elgamal.pub")
        self.assertEqual(by_code[COUNTRY_US].pub_name, "us_node_elgamal.pub")
        for p in (
            product_node_elgamal_pub_path(),
            product_exit_node_elgamal_pub_path(),
            product_us_node_elgamal_pub_path(),
        ):
            self.assertTrue(p.is_file(), p)
            self.assertEqual(p.stat().st_size, 256)

    def test_fleet_order_is_ro_us(self):
        codes = fleet_country_codes()
        self.assertEqual(codes, ["IS", "RO", "US"])
        self.assertNotIn("DE", codes)

    def test_multihop_exit_never_entry_host(self):
        for code in (COUNTRY_IS, COUNTRY_RO, COUNTRY_US):
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


class TestLiveNodeOptional(unittest.TestCase):
    """Optional live probes — skip unless env set or fail soft."""

    def test_status_title_when_reachable(self):
        if os.environ.get("RPT_LIVE_NODE_PROBE", "").strip() not in (
            "1",
            "true",
            "yes",
            "on",
        ):
            self.skipTest("set RPT_LIVE_NODE_PROBE=1 for live status checks")
        for host in (PRODUCT_NODE_HOST, PRODUCT_EXIT_HOST, PRODUCT_US_HOST):
            url = f"http://{host}:8080/status"
            try:
                with urllib.request.urlopen(url, timeout=3) as resp:
                    body = resp.read().decode("utf-8", errors="replace")
                data = json.loads(body)
                self.assertIn("title", data)
            except (
                urllib.error.URLError,
                TimeoutError,
                socket.timeout,
                json.JSONDecodeError,
            ):
                self.skipTest(f"live status unreachable for {host}")


if __name__ == "__main__":
    unittest.main()

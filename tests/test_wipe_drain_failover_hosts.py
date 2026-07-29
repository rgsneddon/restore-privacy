"""Wipe-drain Connect failover hosts (shipped Flutter catalog helpers).

Proves preferred DE down → alternate residual hosts are IS and/or US from the
same catalog path Connect uses (not a reimplementation of native selection).
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestDartAlternateResidualHosts(unittest.TestCase):
    def test_country_select_exports_alternate_hosts(self):
        src = (ROOT / "client_app" / "lib" / "country_select.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("List<String> alternateResidualHosts", src)
        self.assertIn("kProductCountryCatalog", src)

    def test_rpt_config_exposes_alternate_hosts_for_connect(self):
        src = (ROOT / "client_app" / "lib" / "rpt_config.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("alternateHosts", src)
        self.assertIn("alternateResidualHosts", src)

    def test_vpn_controller_passes_alternate_hosts_to_native(self):
        src = (ROOT / "client_app" / "lib" / "vpn_controller.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("'alternateHosts': RptConfig.alternateHosts", src)

    def test_catalog_hosts_is_de_us(self):
        src = (ROOT / "client_app" / "lib" / "country_select.dart").read_text(
            encoding="utf-8"
        )
        hosts = re.findall(r"host: '([0-9.]+)'", src)
        self.assertEqual(
            hosts,
            ["82.221.101.241", "178.105.187.178", "5.161.242.85"],
        )
        self.assertNotIn("185.146.232.107", hosts)


class TestSwiftWipeDrainFailover(unittest.TestCase):
    def test_rpt_endpoint_catalog_and_unreachable_classifier(self):
        src = (
            ROOT
            / "client_app"
            / "macos"
            / "NativePrep"
            / "Rpt2"
            / "RptEndpoint.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("alternateHosts(excluding", src)
        self.assertIn("connectHostOrder", src)
        self.assertIn("isResidualUnreachableFailure", src)
        self.assertIn("82.221.101.241", src)
        self.assertIn("178.105.187.178", src)
        self.assertIn("5.161.242.85", src)
        self.assertIn("udp receive timeout", src)

    def test_vpn_channel_attempts_failover_sequence(self):
        src = (
            ROOT / "client_app" / "macos" / "NativePrep" / "RptVpnChannel.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("attemptTunnelConnectHosts", src)
        self.assertIn("wipe_drain_failover", src)
        self.assertIn("wipeDrainFailover", src)

    def test_packet_tunnel_hello_failover(self):
        src = (
            ROOT
            / "client_app"
            / "macos"
            / "NativePrep"
            / "PacketTunnelProvider.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("connectHostOrder", src)
        self.assertIn("isResidualUnreachableFailure", src)

    def test_orchestrator_connect_with_wipe_failover(self):
        src = (
            ROOT
            / "client_app"
            / "macos"
            / "NativePrep"
            / "Rpt2"
            / "RptConnectOrchestrator.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("connectWithWipeFailover", src)
        self.assertIn("wipe_drain_failover", src)


class TestPythonSelectStillDrainsDe(unittest.TestCase):
    """Shipped wipe_hop path for DE preferred still hops to IS/US."""

    def test_de_drain_select(self):
        sys.path.insert(0, str(ROOT))
        import random

        from client.multihop import (
            PRODUCT_DE_HOST,
            PRODUCT_NODE_HOST,
            PRODUCT_US_HOST,
            multihop_config_for_entry_country,
        )
        from client.wipe_hop import REASON_WIPE_DRAIN_FAILOVER, select_wipe_aware_residual

        cfg = multihop_config_for_entry_country("DE", multihop_enabled=False)
        sel = select_wipe_aware_residual(
            cfg,
            preferred_draining=True,
            preferred_healthy=True,
            peer_health={
                PRODUCT_NODE_HOST: True,
                PRODUCT_DE_HOST: True,
                PRODUCT_US_HOST: True,
            },
            rng=random.Random(1),
        )
        self.assertEqual(sel.reason, REASON_WIPE_DRAIN_FAILOVER)
        self.assertIn(sel.endpoint.host, {PRODUCT_NODE_HOST, PRODUCT_US_HOST})
        self.assertNotEqual(sel.endpoint.host, PRODUCT_DE_HOST)


if __name__ == "__main__":
    unittest.main()

"""rpOS flyclient hidden-node agent + multi-hop integration (not Connect HELLO-skip)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.flyclient_hidden_node import (  # noqa: E402
    AGENT_NAME,
    FORBIDDEN_SELFHOST_MARKERS,
    ROLE_HIDDEN,
    USES_DISK_CRYPTO_INSTALL,
    USES_SELFHOST_STACK,
    USES_ZRAM_LUKS,
    FlyclientHiddenAgent,
    assert_not_public_catalog,
    enable_for_rpos_install,
    hidden_hops_from_records,
    is_public_catalog_peer_host,
    list_enabled_hidden_nodes,
    load_registry,
    register_instance,
    synthetic_hidden_host,
)
from client.multihop import (  # noqa: E402
    PRODUCT_DE_HOST,
    PRODUCT_NODE_HOST,
    PRODUCT_COUNTRY_CATALOG,
    Hop,
    MultiHopConfig,
    build_multihop_path_with_hidden,
    is_hidden_hop,
    is_multihop_active,
    multihop_config_with_hidden_registry,
    multihop_status_text,
    product_country_catalog,
    public_catalog_hosts,
    public_dialable_peers,
    residual_endpoint,
)
from rpos.installer.pipeline import RestorePipeline  # noqa: E402
from rpos.installer.wipe_adapter import DryRunWipeAdapter  # noqa: E402


class TestFlyclientHiddenAgent(unittest.TestCase):
    def test_resource_posture_no_selfhost_stack(self) -> None:
        self.assertFalse(USES_SELFHOST_STACK)
        self.assertFalse(USES_ZRAM_LUKS)
        self.assertFalse(USES_DISK_CRYPTO_INSTALL)
        with tempfile.TemporaryDirectory() as td:
            rec = register_instance(td, install_id="rpos-test-1", start=True)
            agent = FlyclientHiddenAgent(record=rec)
            start = agent.start()
            stop = agent.stop()
            self.assertTrue(start["ok"])
            self.assertTrue(stop["ok"])
            self.assertFalse(start["uses_selfhost"])
            self.assertFalse(start["uses_zram_luks"])
            self.assertFalse(start["public_catalog"])
            posture = agent.resource_posture()
            self.assertLessEqual(posture["max_rss_mb"], 128)
            self.assertLessEqual(posture["max_cpu_percent"], 15)
            self.assertFalse(posture["uses_selfhost"])
            # Must not have invoked selfhost scripts
            blob = " ".join(agent.invocations)
            for m in FORBIDDEN_SELFHOST_MARKERS:
                self.assertNotIn(m, blob)
            # Agent start/stop path does not shell out
            src = (ROOT / "client" / "flyclient_hidden_node.py").read_text(
                encoding="utf-8"
            )
            self.assertNotIn("subprocess", src)
            self.assertNotIn("os.system", src)
            self.assertNotIn("Popen", src)
            # Forbid list documents markers; agent must never call them
            self.assertIn("FORBIDDEN_SELFHOST_MARKERS", src)
            self.assertTrue(start.get("uses_selfhost") is False)

    def test_register_not_public_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            rec = register_instance(
                td,
                install_id="rpos-hid-2",
                host=synthetic_hidden_host(seed="aa"),
            )
            assert_not_public_catalog(rec)
            self.assertEqual(rec.role, ROLE_HIDDEN)
            self.assertEqual(rec.visibility, "hidden")
            self.assertFalse(rec.public_catalog)
            self.assertFalse(is_public_catalog_peer_host(rec.host))
            nodes = load_registry(td)
            self.assertEqual(len(nodes), 1)
            self.assertEqual(nodes[0].install_id, "rpos-hid-2")


class TestRposInstallEnablesHiddenNode(unittest.TestCase):
    def test_pipeline_restore_enables_hidden_flyclient(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            prefix = Path(td) / "root"
            pipe = RestorePipeline(
                prefix=prefix,
                source_rpos=ROOT / "rpos",
                wipe=DryRunWipeAdapter(),
            )
            r = pipe.run("RESTORE", skip_wipe=True)
            self.assertTrue(r["proceeded"])
            self.assertIn("hidden_node_enable", r["stages"])
            hn = r["hidden_node"]
            self.assertTrue(hn["ok"])
            self.assertTrue(hn["enabled"])
            self.assertEqual(hn["agent"], AGENT_NAME)
            self.assertFalse(hn["public_catalog"])
            self.assertFalse(hn["uses_selfhost"])
            self.assertFalse(hn["uses_zram_luks"])
            marker = Path(r["install"]["marker"])
            data = json.loads(marker.read_text(encoding="utf-8"))
            self.assertTrue(data["hidden_node_enabled"])
            self.assertTrue(data["flyclient_hidden_node"])
            self.assertFalse(data["hidden_node_public_catalog"])
            self.assertFalse(data["hidden_node_uses_selfhost"])
            self.assertTrue(data.get("install_id"))
            # Registry file on disk
            reg = list_enabled_hidden_nodes(single_prefix=prefix)
            self.assertEqual(len(reg), 1)
            self.assertEqual(reg[0].install_id, data["install_id"])

    def test_enable_for_rpos_install_entry_point(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            # Pre-create marker as pipeline does
            pref = Path(td)
            (pref / "RPOS_INSTALLED.json").write_text(
                json.dumps({"product": "rpOS", "oobe_pending": True}) + "\n",
                encoding="utf-8",
            )
            out = enable_for_rpos_install(pref)
            self.assertTrue(out["enabled"])
            data = json.loads((pref / "RPOS_INSTALLED.json").read_text(encoding="utf-8"))
            self.assertTrue(data["flyclient_hidden_node"])


class TestMultihopHiddenPath(unittest.TestCase):
    def test_path_includes_hidden_not_public(self) -> None:
        hid_host = synthetic_hidden_host(seed="bb")
        hidden = [Hop(hid_host, 44051, role=ROLE_HIDDEN)]
        cfg = build_multihop_path_with_hidden(
            Hop(PRODUCT_NODE_HOST, role="entry"),
            Hop(PRODUCT_DE_HOST, role="exit"),
            hidden,
            enabled=True,
        )
        self.assertTrue(is_multihop_active(cfg))
        self.assertGreaterEqual(len(cfg.hops), 3)
        roles = [h.role for h in cfg.hops]
        self.assertEqual(roles[0], "entry")
        self.assertEqual(roles[-1], "exit")
        self.assertIn(ROLE_HIDDEN, roles)
        mid = [h for h in cfg.hops if h.is_hidden()]
        self.assertEqual(len(mid), 1)
        self.assertTrue(is_hidden_hop(mid[0]))
        # Residual still via exit (not hidden host)
        self.assertEqual(residual_endpoint(cfg).host, PRODUCT_DE_HOST)
        self.assertNotEqual(residual_endpoint(cfg).host, hid_host)
        text = multihop_status_text(cfg)
        self.assertIn("multi-hop active", text)
        self.assertIn("hidden hop", text)
        self.assertIn("residual via", text)
        self.assertNotIn("full onion", text.lower().replace("not full onion", "x"))
        self.assertIn("not full onion", text.lower())

    def test_multihop_off_ignores_hidden(self) -> None:
        hid = [Hop(synthetic_hidden_host(seed="cc"), 44052, role=ROLE_HIDDEN)]
        cfg = multihop_config_with_hidden_registry(
            "DE",
            multihop_enabled=False,
            hidden_hops=hid,
        )
        self.assertFalse(cfg.enabled)
        self.assertFalse(is_multihop_active(cfg))
        self.assertEqual(len(cfg.hops), 1)
        self.assertFalse(any(h.is_hidden() for h in cfg.hops))

    def test_public_catalog_excludes_hidden_hosts(self) -> None:
        pub = public_catalog_hosts()
        self.assertIn(PRODUCT_NODE_HOST, pub)
        self.assertIn(PRODUCT_DE_HOST, pub)
        hid = synthetic_hidden_host(seed="dd")
        self.assertNotIn(hid, pub)
        peers = public_dialable_peers(hidden_hosts=[hid, PRODUCT_NODE_HOST])
        hosts = {p.host for p in peers}
        # PRODUCT_NODE_HOST denied via hidden_hosts denylist
        self.assertNotIn(PRODUCT_NODE_HOST, hosts)
        # Catalog itself never lists synthetic hidden
        for n in product_country_catalog():
            self.assertNotEqual(n.host, hid)
            self.assertIn(n.code, ("IS", "DE"))
        for n in PRODUCT_COUNTRY_CATALOG:
            self.assertFalse(
                n.host.startswith("10.77."),
                msg="public catalog must not include flyclient RFC1918 hosts",
            )

    def test_hidden_records_to_hops(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            rec = register_instance(
                td,
                install_id="rpos-path",
                host=synthetic_hidden_host(seed="ee"),
            )
            hops = hidden_hops_from_records([rec])
            self.assertEqual(len(hops), 1)
            self.assertTrue(hops[0].is_hidden())
            cfg = build_multihop_path_with_hidden(
                Hop(PRODUCT_NODE_HOST, role="entry"),
                Hop(PRODUCT_DE_HOST, role="exit"),
                hops,
            )
            self.assertTrue(is_multihop_active(cfg))
            self.assertEqual(residual_endpoint(cfg).host, PRODUCT_DE_HOST)

    def test_refuse_public_host_as_hidden_middle(self) -> None:
        """Public monopin must not be re-tagged hidden in path builder."""
        cfg = build_multihop_path_with_hidden(
            Hop(PRODUCT_NODE_HOST, role="entry"),
            Hop(PRODUCT_DE_HOST, role="exit"),
            [Hop(PRODUCT_NODE_HOST, 44044, role=ROLE_HIDDEN)],
            enabled=True,
        )
        # Public host stripped from middle — path is entry→exit only
        hidden_mids = [h for h in cfg.hops if h.is_hidden()]
        self.assertEqual(hidden_mids, [])
        self.assertEqual(len(cfg.hops), 2)


class TestNoConnectHelloSkipRegression(unittest.TestCase):
    def test_flyclient_connect_still_gone(self) -> None:
        self.assertFalse((ROOT / "client" / "flyclient_connect.py").is_file())
        # New agent module is allowed and distinct
        self.assertTrue((ROOT / "client" / "flyclient_hidden_node.py").is_file())
        connect = (ROOT / "client" / "connect.py").read_text(encoding="utf-8")
        self.assertNotIn("flyclient_connect", connect)
        self.assertNotIn("flyclient_decide", connect)
        # Hidden agent must not wire into connect residual skip
        agent_src = (ROOT / "client" / "flyclient_hidden_node.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("flyclient_connect", agent_src)
        self.assertNotIn("force_reconnect", agent_src)
        self.assertNotIn("flyclient_decide", agent_src)
        # Docs state HELLO is not skipped
        self.assertIn("HELLO", agent_src)


if __name__ == "__main__":
    unittest.main()

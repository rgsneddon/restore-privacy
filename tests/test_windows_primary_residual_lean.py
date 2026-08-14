"""Windows primary residual attach + lean residual when privacy-scale is all off.

Primary residual failure that self-inflicted from a missing US ElGamal pin
(product default entry) is a packaging/secrets bug, not genuine HELLO refusal.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.connect import RptClient  # noqa: E402
from client.endpoint import Endpoint  # noqa: E402
from client.multihop import (  # noqa: E402
    PRODUCT_DE_HOST,
    PRODUCT_EXIT_HOST,
    PRODUCT_NODE_HOST,
    PRODUCT_SG_HOST,
    PRODUCT_US_HOST,
    MultiHopConfig,
    multihop_config_for_entry_country,
    residual_try_order,
    select_residual_endpoint,
)
from client.product_policy import (  # noqa: E402
    PrivacyScalePrefs,
    product_dataplane_traffic_shape,
    resolve_privacy_policy,
)
from client.secrets_loader import (  # noqa: E402
    CATALOG_NODE_PUB_NAMES,
    US_NODE_PUB_NAME,
    ensure_device_admission_key,
    load_node_elgamal_public_for_endpoint,
    sync_catalog_public_pubs_into,
)
from node.traffic_shape import DEFAULT_TRAFFIC_SHAPE  # noqa: E402


class TestPrimaryResidualTryOrder(unittest.TestCase):
    def test_us_entry_primary_is_first_when_healthy(self) -> None:
        cfg = multihop_config_for_entry_country("US", multihop_enabled=False)
        sel = select_residual_endpoint(
            cfg,
            entry_healthy=True,
            exit_healthy=True,
            entry_draining=False,
        )
        # Stale US heals to DE; catalog failover is Singapore, never Iceland.
        self.assertEqual(sel.endpoint.host, PRODUCT_DE_HOST)
        self.assertNotEqual(sel.endpoint.host, PRODUCT_NODE_HOST)
        self.assertEqual(sel.reason, "entry_primary")
        self.assertFalse(sel.failover_active)

        order = residual_try_order(
            cfg,
            entry_healthy=True,
            exit_healthy=True,
            entry_draining=False,
        )
        self.assertEqual(
            [e.host for e in order], [PRODUCT_DE_HOST, PRODUCT_SG_HOST]
        )
        self.assertNotIn(PRODUCT_NODE_HOST, [e.host for e in order])

    def test_forced_primary_fail_try_order_failover_to_alternate(self) -> None:
        cfg = multihop_config_for_entry_country("US", multihop_enabled=False)
        order = residual_try_order(
            cfg,
            entry_healthy=True,
            exit_healthy=True,
            entry_draining=False,
        )
        self.assertEqual(order[0].host, PRODUCT_DE_HOST)
        self.assertNotIn(PRODUCT_NODE_HOST, [e.host for e in order])

    def test_both_unhealthy_fail_closed(self) -> None:
        cfg = multihop_config_for_entry_country("US", multihop_enabled=False)
        from client.multihop import ResidualUnavailable

        with self.assertRaises(ResidualUnavailable):
            select_residual_endpoint(
                cfg,
                entry_healthy=False,
                exit_healthy=False,
                entry_draining=False,
            )

    def test_connect_primary_success_not_hello_failover(self) -> None:
        """Healthy primary HELLO success leaves selection reason != hello_failover."""
        cfg = multihop_config_for_entry_country("US", multihop_enabled=False)
        client = RptClient(multihop=cfg)
        statuses: list[str] = []
        client.status_cb = statuses.append

        ok = object()

        def _fake_hello(ep, **_kw):
            from client.connect import ConnectResult, ConnectState

            client.endpoint = ep
            client.state = ConnectState.CONNECTED
            return ConnectResult(ok=True, state=ConnectState.CONNECTED, message="ok")

        with mock.patch.object(client, "_hello_to_endpoint", side_effect=_fake_hello):
            with mock.patch(
                "client.connect.ensure_device_admission_key",
                return_value=Path(tempfile.gettempdir()),
            ):
                with mock.patch(
                    "client.connect.load_client_private_key",
                    return_value=object(),
                ):
                    result = client.connect(timeout=2.0)

        self.assertTrue(result.ok)
        self.assertNotEqual(client.last_selection_reason, "hello_failover")
        self.assertFalse(
            any("Primary residual failed" in s for s in statuses),
            statuses,
        )

    def test_connect_primary_fail_then_failover_status(self) -> None:
        cfg = multihop_config_for_entry_country("US", multihop_enabled=False)
        client = RptClient(multihop=cfg)
        statuses: list[str] = []
        client.status_cb = statuses.append
        calls: list[str] = []

        def _fake_hello(ep, **_kw):
            calls.append(ep.host)
            raise TimeoutError("simulated primary HELLO timeout")

        with mock.patch.object(client, "_hello_to_endpoint", side_effect=_fake_hello):
            with mock.patch(
                "client.connect.ensure_device_admission_key",
                return_value=Path(tempfile.gettempdir()),
            ):
                with mock.patch(
                    "client.connect.load_client_private_key",
                    return_value=object(),
                ):
                    result = client.connect(timeout=2.0)

        # DE primary fail → Singapore failover; never Iceland.
        self.assertFalse(result.ok)
        self.assertEqual(calls, [PRODUCT_DE_HOST, PRODUCT_SG_HOST])
        self.assertNotIn(PRODUCT_NODE_HOST, calls)


class TestCatalogPubHeal(unittest.TestCase):
    def test_sync_catalog_installs_sg_pub_from_product(self) -> None:
        product_sg = ROOT / "product" / "sg_node_elgamal.pub"
        if not product_sg.is_file():
            self.skipTest("product/sg_node_elgamal.pub missing")
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td)
            # Seed only Iceland pub (historical install layout)
            (dest / "node_elgamal.pub").write_bytes(
                (ROOT / "product" / "node_elgamal.pub").read_bytes()
            )
            installed = sync_catalog_public_pubs_into(dest)
            self.assertIn("sg_node_elgamal.pub", installed)
            self.assertTrue((dest / "sg_node_elgamal.pub").is_file())
            pub = load_node_elgamal_public_for_endpoint(
                Endpoint(host=PRODUCT_SG_HOST, port=44044),
                dest,
            )
            self.assertEqual(pub.export(), product_sg.read_bytes())

    def test_ensure_admission_heals_catalog_pubs_when_node_pub_present(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td)
            (dest / "node_elgamal.pub").write_bytes(
                (ROOT / "product" / "node_elgamal.pub").read_bytes()
            )
            out = ensure_device_admission_key(dest)
            self.assertEqual(out, dest)
            for name in CATALOG_NODE_PUB_NAMES:
                if name == "exit_node_elgamal.pub" and not (
                    ROOT / "product" / name
                ).is_file():
                    continue
                self.assertTrue(
                    (dest / name).is_file(),
                    f"missing healed catalog pin {name}",
                )


class TestLeanPrivacyOff(unittest.TestCase):
    def setUp(self) -> None:
        self._env_backup = {
            k: os.environ.get(k)
            for k in ("RPT_TRAFFIC_SHAPE", "RPT_OBFS", "RPT_MULTIHOP_ENABLED", "RPT_FREE_TIER")
        }
        for k in self._env_backup:
            os.environ.pop(k, None)

    def tearDown(self) -> None:
        for k, v in self._env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_all_privacy_scale_off_resolves_lean(self) -> None:
        prefs = PrivacyScalePrefs(
            traffic_shape=False,
            outer_obfuscation=False,
            multihop=False,
        )
        pol = resolve_privacy_policy(prefs=prefs)
        self.assertFalse(pol.traffic_shape_enabled)
        self.assertFalse(pol.outer_obfuscation_enabled)
        self.assertFalse(pol.multihop_enabled)
        shape = product_dataplane_traffic_shape(prefs=prefs)
        self.assertEqual(shape, DEFAULT_TRAFFIC_SHAPE)
        self.assertFalse(shape.padding)
        self.assertFalse(shape.cover_traffic)
        self.assertEqual(shape.jitter_ms_max, 0)

    def test_windows_tunnel_uses_product_dataplane_shape(self) -> None:
        src = (ROOT / "client" / "windows" / "tunnel_win.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("product_dataplane_traffic_shape", src)
        self.assertIn("RptDataPlane", src)


class TestWindowsPackageShipsUsPub(unittest.TestCase):
    def test_inject_product_secrets_includes_us_pub(self) -> None:
        import importlib.util

        path = ROOT / "scripts" / "build_release_0.0.8.py"
        if not (ROOT / "product" / US_NODE_PUB_NAME).is_file():
            self.skipTest("product/us_node_elgamal.pub missing")
        if not (ROOT / "product" / "node_elgamal.pub").is_file():
            self.skipTest("product/node_elgamal.pub missing")
        spec = importlib.util.spec_from_file_location("br08_us", path)
        assert spec and spec.loader
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as td:
            tree = Path(td)
            m.inject_product_secrets(tree)
            self.assertTrue((tree / "secrets" / US_NODE_PUB_NAME).is_file())
            self.assertTrue((tree / "product" / US_NODE_PUB_NAME).is_file())
            self.assertTrue((tree / "secrets" / "node_elgamal.pub").is_file())


if __name__ == "__main__":
    unittest.main()

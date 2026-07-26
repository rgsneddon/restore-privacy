"""Windows Connect critical-path speed: skip avoidable serial status-host waits."""

from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestConnectStatusHostRefreshNeeded(unittest.TestCase):
    def test_warm_active_keygen_skips_remote(self):
        from client.payment_entitlement import (
            connect_status_host_refresh_needed,
            record_payment_success,
        )

        with tempfile.TemporaryDirectory() as td:
            pay = Path(td) / "payment_entitlement.json"
            record_payment_success(
                "cs_warm",
                path=pay,
                keygen="RPT-KEY-WARM-TEST-KEY1",
            )
            with mock.patch(
                "client.payment_entitlement.default_entitlement_path",
                return_value=pay,
            ):
                with mock.patch(
                    "client.payment_entitlement.payment_entitlement_required",
                    return_value=True,
                ):
                    self.assertFalse(connect_status_host_refresh_needed(path=pay))

    def test_missing_entitlement_needs_remote(self):
        from client.payment_entitlement import connect_status_host_refresh_needed

        with tempfile.TemporaryDirectory() as td:
            pay = Path(td) / "payment_entitlement.json"
            with mock.patch(
                "client.payment_entitlement.default_entitlement_path",
                return_value=pay,
            ):
                with mock.patch(
                    "client.payment_entitlement.payment_entitlement_required",
                    return_value=True,
                ):
                    self.assertTrue(connect_status_host_refresh_needed(path=pay))

    def test_near_expiry_forces_refresh(self):
        from client.payment_entitlement import (
            PaymentEntitlement,
            STATUS_ACTIVE,
            connect_status_host_refresh_needed,
            save_payment_entitlement,
        )

        with tempfile.TemporaryDirectory() as td:
            pay = Path(td) / "payment_entitlement.json"
            save_payment_entitlement(
                PaymentEntitlement(
                    session_id="cs_near",
                    status=STATUS_ACTIVE,
                    keygen="RPT-KEY-NEAR-EXPY-KEY1",
                    valid_until=time.time() + 600.0,  # 10 minutes
                    updated_at=time.time(),
                ),
                path=pay,
            )
            with mock.patch(
                "client.payment_entitlement.default_entitlement_path",
                return_value=pay,
            ):
                self.assertTrue(connect_status_host_refresh_needed(path=pay))


class TestAssertMayConnectWarmPath(unittest.TestCase):
    def test_warm_assert_does_not_call_ensure(self):
        from client.licence_gate import accept_licence, assert_may_connect
        from client.payment_entitlement import record_payment_success

        with tempfile.TemporaryDirectory() as td:
            lic = Path(td) / "licence_acceptance.json"
            pay = Path(td) / "payment_entitlement.json"
            accept_licence(path=lic)
            record_payment_success(
                "cs_ok", path=pay, keygen="RPT-KEY-OKAY-TEST-KEY1"
            )
            with mock.patch(
                "client.payment_entitlement.default_entitlement_path",
                return_value=pay,
            ):
                with mock.patch(
                    "client.payment_entitlement.payment_entitlement_required",
                    return_value=True,
                ):
                    with mock.patch(
                        "client.payment_entitlement.ensure_entitlement_for_connect",
                    ) as ensure:
                        ok, msg = assert_may_connect(path=lic, refresh=False)
                        self.assertTrue(ok, msg)
                        ensure.assert_not_called()

    def test_cold_assert_refreshes_when_refresh_true(self):
        from client.licence_gate import accept_licence, assert_may_connect

        with tempfile.TemporaryDirectory() as td:
            lic = Path(td) / "licence_acceptance.json"
            pay = Path(td) / "payment_entitlement.json"
            accept_licence(path=lic)
            with mock.patch(
                "client.payment_entitlement.default_entitlement_path",
                return_value=pay,
            ):
                with mock.patch(
                    "client.payment_entitlement.payment_entitlement_required",
                    return_value=True,
                ):
                    with mock.patch(
                        "client.payment_entitlement.ensure_entitlement_for_connect",
                    ) as ensure:
                        ok, _msg = assert_may_connect(path=lic, refresh=True)
                        self.assertFalse(ok)
                        ensure.assert_called()

    def test_licence_still_blocks_without_accept(self):
        from client.licence_gate import assert_may_connect, clear_licence_acceptance

        with tempfile.TemporaryDirectory() as td:
            lic = Path(td) / "licence_acceptance.json"
            clear_licence_acceptance(path=lic)
            ok, msg = assert_may_connect(path=lic, refresh=False)
            self.assertFalse(ok)
            self.assertIn("licence", msg.lower())


class TestCriticalPathPlan(unittest.TestCase):
    def test_warm_plan_status_host_not_blocking(self):
        from client.payment_entitlement import windows_connect_critical_path_plan

        plan = windows_connect_critical_path_plan(local_payment_ready=True)
        by = {s["stage"]: s for s in plan}
        self.assertFalse(by["status_host_bootstrap_bind"]["blocks_hello"])
        self.assertFalse(by["assert_may_connect"]["remote_refresh"])
        self.assertTrue(by["residual_hello"]["blocks_hello"])
        self.assertFalse(by["capacity_probes"]["blocks_hello"])

    def test_cold_plan_status_host_blocks(self):
        from client.payment_entitlement import windows_connect_critical_path_plan

        plan = windows_connect_critical_path_plan(local_payment_ready=False)
        by = {s["stage"]: s for s in plan}
        self.assertTrue(by["status_host_bootstrap_bind"]["blocks_hello"])
        self.assertTrue(by["assert_may_connect"]["remote_refresh"])


class TestCapacityProbeParallelAndNonForce(unittest.TestCase):
    def test_connect_uses_force_false_capacity_refresh(self):
        src = (ROOT / "client" / "connect.py").read_text(encoding="utf-8")
        # Shipped connect path must not force re-probe every dial
        self.assertIn("_refresh_capacity_from_probes(force=False)", src)
        self.assertNotIn(
            "# Live private capacity probes (fail-soft) when token configured\n"
            "                self._refresh_capacity_from_probes(force=True)",
            src,
        )

    def test_probe_map_parallel_wall_shorter_than_serial(self):
        """Shipped probe_peer_capacity_map overlaps peer waits (parallel)."""
        from client.capacity_probe import probe_peer_capacity_map

        calls: list[float] = []

        def slow_transport(url, headers, timeout_s):
            time.sleep(0.12)
            calls.append(time.time())
            # Echo host from URL path segment
            if "peer-a" in url:
                return '{"utilization": 0.5, "host": "10.0.0.1"}'
            return '{"utilization": 0.4, "host": "10.0.0.2"}'

        urls = {
            "10.0.0.1": "http://example.test/peer-a",
            "10.0.0.2": "http://example.test/peer-b",
        }
        t0 = time.perf_counter()
        with mock.patch.dict(
            "os.environ",
            {"RPT_CAPACITY_TOKEN": "tok", "RPT_CAPACITY_PROBE_TIMEOUT": "2"},
            clear=False,
        ):
            m = probe_peer_capacity_map(
                transport=slow_transport,
                url_map=urls,
                timeout_s=2.0,
            )
        elapsed = time.perf_counter() - t0
        self.assertEqual(set(m.keys()), {"10.0.0.1", "10.0.0.2"})
        # Serial would be ~0.24s+; parallel ~0.12s+overhead — allow headroom
        self.assertLess(elapsed, 0.22, f"probes not overlapped: {elapsed:.3f}s")
        self.assertGreaterEqual(len(calls), 2)

    def test_windows_app_skips_bootstrap_when_warm(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("connect_status_host_refresh_needed", src)
        self.assertIn("assert_may_connect(refresh=need_status_host)", src)
        self.assertIn("rpt-connect-entitlement-bg", src)


if __name__ == "__main__":
    unittest.main()

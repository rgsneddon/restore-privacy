"""Suite-oriented residual push-update → client receive (shipped helpers)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestSuitePushUpdate(unittest.TestCase):
    def test_validate_and_push_suite_package_directive(self) -> None:
        from node.update_push import (
            UpdatePushQueue,
            apply_client_update_directive,
            client_receive_update_directives,
            validate_update_directive,
        )

        ok, err, d = validate_update_directive(
            version="1.0.1",
            url="https://restoreprivacy.online/suite/download?platform=macos",
            message="Suite package — unpack and relaunch in the app",
            target_client_id="",
        )
        self.assertTrue(ok, err)
        assert d is not None
        self.assertEqual(d.version, "1.0.1")
        self.assertIn("suite/download", d.url)

        q = UpdatePushQueue()
        q.push(d)
        pending = client_receive_update_directives("any-client", queue=q)
        self.assertEqual(len(pending), 1)
        applied = apply_client_update_directive(pending[0])
        self.assertTrue(applied["ok"])
        store = applied["store"]
        self.assertIsNotNone(store)
        self.assertEqual(store["pending_update_version"], "1.0.1")
        self.assertIn("suite/download", store["pending_update_url"])
        self.assertEqual(store["kind"], "rpt_client_update")

    def test_operator_push_update_suite_version(self) -> None:
        from node.operator_admin import NodeOperatorController

        # Pure validate path used by admin "Push update to clients"
        ctrl = NodeOperatorController.__new__(NodeOperatorController)
        # catalog default should be suite monopin-shaped
        from node.operator_admin import NodeOperatorController as NOC

        c = NOC.__new__(NOC)
        # Use real validate via module
        from node.update_push import validate_update_directive

        ok, _, d = validate_update_directive(
            version="1.0.0",
            url="https://135.181.152.10.sslip.io/paid_assets/1.0.1/suite.pkg",
            message="Push update to clients — Suite",
        )
        self.assertTrue(ok)
        self.assertIsNotNone(d)


if __name__ == "__main__":
    unittest.main()

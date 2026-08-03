"""Suite-oriented residual push-update → client receive (shipped helpers)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestSuitePushUpdate(unittest.TestCase):
    def test_validate_and_push_suite_package_directive(self) -> None:
        from node.update_push import operator_push_update, UpdatePushQueue

        q = UpdatePushQueue()
        r = operator_push_update(
            version="1.1.3",
            url="https://restoreprivacy.online/",
            message="Suite package",
            queue=q,
            connected_client_ids=["c1"],
        )
        self.assertFalse(r.get("ok"), r)
        self.assertTrue(r.get("disabled") or "disabled" in str(r.get("error", "")).lower())
        self.assertEqual(r.get("count") or 0, 0)


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

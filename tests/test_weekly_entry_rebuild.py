"""Weekly entry-only wipe/rebuild plan + CLI dry-run."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from node.ephemeral_node import (  # noqa: E402
    HONESTY_EXCLUSIVE,
    HONESTY_FAILOVER,
    assert_weekly_entry_role_only,
    build_weekly_entry_rebuild_plan,
    systemd_service_unit,
)


class TestWeeklyEntryPlan(unittest.TestCase):
    def test_role_guard_refuses_exit_both(self):
        ok, msg = assert_weekly_entry_role_only("exit")
        self.assertFalse(ok)
        self.assertIn("entry-only", msg.lower())
        ok_b, _ = assert_weekly_entry_role_only("both")
        self.assertFalse(ok_b)
        ok_e, _ = assert_weekly_entry_role_only("entry")
        self.assertTrue(ok_e)
        with self.assertRaises(ValueError):
            build_weekly_entry_rebuild_plan(role="exit")

    def test_weekly_plan_steps_and_lock(self):
        plan = build_weekly_entry_rebuild_plan(
            period="7d", dry_run=True, exit_healthy=True, entry_healthy=True
        )
        self.assertEqual(plan.mode, "weekly_entry_rebuild")
        self.assertEqual(plan.period_seconds, 7 * 86400)
        ids = [s.id for s in plan.steps]
        self.assertIn("role_guard", ids)
        self.assertIn("exclusive_lock_acquire", ids)
        self.assertIn("exit_failover_preflight", ids)
        self.assertIn("entry_node_preflight", ids)
        self.assertIn("mark_entry_draining", ids)
        self.assertIn("rebuild_host", ids)
        self.assertIn("selfhost_reapply", ids)
        self.assertIn("exclusive_lock_release", ids)
        self.assertIn("schedule_next", ids)
        # Lock before rebuild; release after health
        self.assertLess(
            ids.index("exclusive_lock_acquire"), ids.index("rebuild_host")
        )
        self.assertLess(
            ids.index("exit_failover_preflight"), ids.index("rebuild_host")
        )
        self.assertLess(
            ids.index("entry_node_preflight"), ids.index("rebuild_host")
        )
        self.assertGreater(
            ids.index("selfhost_reapply"), ids.index("rebuild_host")
        )
        self.assertGreater(
            ids.index("exclusive_lock_release"), ids.index("health_check")
        )
        self.assertIn(HONESTY_EXCLUSIVE, plan.honesty)
        self.assertIn(HONESTY_FAILOVER, plan.honesty)
        text = plan.format_text().lower()
        self.assertIn("exclusive", text)
        self.assertIn("entry", text)
        self.assertIn("failover", text)
        self.assertIn("package", text)

    def test_abort_when_exit_unhealthy(self):
        plan = build_weekly_entry_rebuild_plan(
            period="7d", dry_run=True, exit_healthy=False
        )
        self.assertEqual(plan.mode, "weekly_entry_rebuild_aborted")
        ids = [s.id for s in plan.steps]
        self.assertIn("abort_exit_unhealthy", ids)
        self.assertNotIn("rebuild_host", ids)

    def test_service_unit_weekly_entry(self):
        unit = systemd_service_unit(dry_run=True, weekly_entry=True)
        self.assertIn("weekly_entry_rebuild.py", unit)
        self.assertIn("--dry-run", unit)
        self.assertNotIn("RPT_EPHEMERAL_CONFIRM=yes", unit)
        live = systemd_service_unit(dry_run=False, weekly_entry=True)
        self.assertIn("RPT_EPHEMERAL_CONFIRM=yes", live)


class TestWeeklyCliDryRun(unittest.TestCase):
    def test_cli_dry_run_and_lock_probe(self):
        script = ROOT / "scripts" / "weekly_entry_rebuild.py"
        self.assertTrue(script.is_file())
        with tempfile.TemporaryDirectory() as td:
            env = {
                **os.environ,
                "PYTHONPATH": str(ROOT),
                "INSTALL_ROOT": td,
            }
            r = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--dry-run",
                    "--period",
                    "7d",
                    "--install-root",
                    td,
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        out = r.stdout.lower()
        self.assertIn("exclusive", out)
        self.assertIn("entry", out)
        self.assertIn("dry-run", out)
        self.assertIn("acquire2", out)
        self.assertIn("must fail closed", out)
        self.assertIn("exit failover", out)
        self.assertIn("re-entry", out)

    def test_cli_refuses_exit_role(self):
        script = ROOT / "scripts" / "weekly_entry_rebuild.py"
        env = {**os.environ, "PYTHONPATH": str(ROOT)}
        r = subprocess.run(
            [sys.executable, str(script), "--dry-run", "--role", "exit"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("entry", (r.stderr + r.stdout).lower())


if __name__ == "__main__":
    unittest.main()

"""Weekly sequential fleet wipe plan + CLI dry-run (IS → RO → new)."""

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
    SELFHOST_FULL_CMD,
    assert_role_reinstall_lists_differ,
    assert_weekly_entry_role_only,
    build_exit_manual_reinstall_plan,
    build_weekly_entry_rebuild_plan,
    entry_reinstall_requirements,
    exit_reinstall_requirements,
    plan_embeds_mandatory_reinstall,
    role_reinstall_requirement_ids,
    systemd_service_unit,
)
from node.fleet_wipe import resolve_weekly_target  # noqa: E402
from node.wipe_preflight import (  # noqa: E402
    package_reinstall_required_for_live_wipe,
    plan_has_required_live_steps,
)


class TestWeeklyEntryPlan(unittest.TestCase):
    def test_role_guard_refuses_exit_both(self):
        ok, msg = assert_weekly_entry_role_only("exit")
        self.assertFalse(ok)
        self.assertTrue(
            "entry-only" in msg.lower() or "sequential" in msg.lower() or "never" in msg.lower(),
            msg,
        )
        ok_b, _ = assert_weekly_entry_role_only("both")
        self.assertFalse(ok_b)
        ok_e, _ = assert_weekly_entry_role_only("entry")
        self.assertTrue(ok_e)
        ok_a, _ = assert_weekly_entry_role_only("auto")
        self.assertTrue(ok_a)
        with self.assertRaises(ValueError):
            build_weekly_entry_rebuild_plan(role="exit")
        # exit must not map to RO and produce a plan
        d = resolve_weekly_target(completed=["IS"], role_hint="exit")
        self.assertFalse(d.allow)
        self.assertIsNone(d.target_code)

    def test_auto_cycle_rolls_after_is_ro_complete(self):
        d = resolve_weekly_target(completed=["IS", "RO"], role_hint="auto")
        self.assertTrue(d.allow, d.reason)
        self.assertEqual(d.target_code, "IS")
        self.assertEqual(d.completed, ())
        self.assertIn("rolled", d.reason.lower())

    def test_weekly_plan_steps_and_lock(self):
        plan = build_weekly_entry_rebuild_plan(
            period="7d",
            dry_run=True,
            exit_healthy=True,
            entry_healthy=True,
            role="auto",
            completed=[],
        )
        self.assertEqual(plan.mode, "weekly_fleet_rebuild")
        self.assertEqual(plan.period_seconds, 7 * 86400)
        ids = [s.id for s in plan.steps]
        self.assertIn("role_guard", ids)
        self.assertIn("fleet_target_resolve", ids)
        self.assertIn("exclusive_lock_acquire", ids)
        self.assertIn("peer_failover_preflight", ids)
        self.assertIn("entry_node_preflight", ids)
        self.assertIn("mark_entry_draining", ids)
        self.assertIn("rebuild_host", ids)
        self.assertIn("selfhost_reapply", ids)
        self.assertIn("mark_fleet_peer_complete", ids)
        self.assertIn("exclusive_lock_release", ids)
        self.assertIn("schedule_next", ids)
        # Lock before rebuild; release after health
        self.assertLess(
            ids.index("exclusive_lock_acquire"), ids.index("rebuild_host")
        )
        self.assertLess(
            ids.index("peer_failover_preflight"), ids.index("rebuild_host")
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
        self.assertIn("failover", text)
        self.assertIn("package", text)
        self.assertIn("sequential", text)
        self.assertTrue(plan_embeds_mandatory_reinstall(ids))
        ok_steps, missing = plan_has_required_live_steps(ids)
        self.assertTrue(ok_steps, missing)
        self.assertTrue(package_reinstall_required_for_live_wipe())
        # Full selfhost command forces DNS + host privacy
        sh = next(s for s in plan.steps if s.id == "selfhost_reapply")
        self.assertIn("SKIP_DNS=0", sh.command)
        self.assertIn("SKIP_HOST_PRIVACY=0", sh.command)
        self.assertIn("selfhost_node.sh", sh.command)
        # Host-identity gate prefixes selfhost on local target
        self.assertIn("assert_local_host_is_target", sh.command)
        self.assertTrue(
            sh.command.endswith(SELFHOST_FULL_CMD)
            or SELFHOST_FULL_CMD in sh.command,
            sh.command,
        )
        self.assertIn("host_identity_gate", ids)
        self.assertIn("reinstall_core_dns_privacy_verify", ids)
        self.assertIn("entry_product_pin_check", ids)
        self.assertLess(
            ids.index("selfhost_reapply"), ids.index("health_check")
        )
        # First target is IS
        self.assertIn("acquire_rebuild_lock('is'", plan.format_text())

    def test_role_reinstall_entry_differs_from_exit(self):
        ok, msg = assert_role_reinstall_lists_differ()
        self.assertTrue(ok, msg)
        entry_ids = set(role_reinstall_requirement_ids("entry"))
        exit_ids = set(role_reinstall_requirement_ids("exit"))
        self.assertNotEqual(entry_ids, exit_ids)
        for need in (
            "core_node_install",
            "tunnel_dns",
            "host_privacy",
            "selfhost_full",
        ):
            self.assertIn(need, entry_ids)
            self.assertIn(need, exit_ids)
        self.assertIn("entry_weekly_failover_gates", entry_ids)
        self.assertIn("entry_exclusive_rebuild_lock", entry_ids)
        self.assertNotIn("entry_weekly_failover_gates", exit_ids)
        self.assertIn("exit_only_elgamal_keys", exit_ids)
        self.assertIn("exit_no_weekly_timer", exit_ids)
        self.assertNotIn("exit_only_elgamal_keys", entry_ids)
        e_desc = " ".join(r.description for r in entry_reinstall_requirements())
        x_desc = " ".join(r.description for r in exit_reinstall_requirements())
        self.assertIn("failover", e_desc.lower())
        self.assertIn("exit", x_desc.lower())

    def test_exit_manual_plan_not_weekly_and_has_reinstall(self):
        plan = build_exit_manual_reinstall_plan(dry_run=True)
        self.assertEqual(plan.mode, "exit_manual_reinstall")
        ids = [s.id for s in plan.steps]
        self.assertIn("selfhost_reapply", ids)
        self.assertIn("exit_key_and_firewall", ids)
        self.assertIn("no_weekly_timer", ids)
        self.assertIn("health_check", ids)
        self.assertNotIn("peer_failover_preflight", ids)
        self.assertNotIn("exit_failover_preflight", ids)
        self.assertNotIn("exclusive_lock_acquire", ids)
        text = plan.format_text().lower()
        self.assertIn("exit", text)
        self.assertIn("selfhost", text)
        sh = next(s for s in plan.steps if s.id == "selfhost_reapply")
        self.assertEqual(sh.command, SELFHOST_FULL_CMD)

    def test_abort_when_peer_unhealthy(self):
        plan = build_weekly_entry_rebuild_plan(
            period="7d", dry_run=True, exit_healthy=False, entry_healthy=True
        )
        self.assertEqual(plan.mode, "weekly_fleet_rebuild_aborted")
        ids = [s.id for s in plan.steps]
        self.assertTrue(
            "abort_peer_unhealthy" in ids or "abort_exit_unhealthy" in ids,
            ids,
        )
        self.assertNotIn("rebuild_host", ids)

    def test_service_unit_weekly_entry(self):
        unit = systemd_service_unit(dry_run=True, weekly_entry=True)
        self.assertIn("weekly_entry_rebuild.py", unit)
        self.assertIn("--dry-run", unit)
        self.assertNotIn("RPT_EPHEMERAL_CONFIRM=yes", unit)
        # Honest fleet wording — not "entry-only never wipe RO"
        self.assertIn("sequential fleet", unit.lower())
        self.assertNotIn("entry-only", unit.lower())
        live = systemd_service_unit(dry_run=False, weekly_entry=True)
        self.assertIn("RPT_EPHEMERAL_CONFIRM=yes", live)

    def test_host_identity_gate_ro_remote_on_orchestrator(self):
        """When orchestrator is IS, RO destructive steps must not wipe local host."""
        plan = build_weekly_entry_rebuild_plan(
            period="7d",
            dry_run=True,
            exit_healthy=True,
            entry_healthy=True,
            role="auto",
            completed=["IS"],
            local_country="IS",
        )
        self.assertEqual(plan.mode, "weekly_fleet_rebuild")
        ids = [s.id for s in plan.steps]
        self.assertIn("host_identity_gate", ids)
        self.assertIn("acquire_rebuild_lock('ro'", plan.format_text())
        stop = next(s for s in plan.steps if s.id == "stop_runtime")
        self.assertIn("REMOTE", stop.action)
        self.assertNotIn("systemctl stop rpt-node", stop.command)
        self.assertIn("exit 1", stop.command)
        sh = next(s for s in plan.steps if s.id == "selfhost_reapply")
        self.assertIn("REMOTE", sh.action)
        self.assertNotIn(SELFHOST_FULL_CMD, sh.command)
        # RO pin (not entry product pin)
        self.assertIn("exit_product_pin_check", ids)
        self.assertNotIn("entry_product_pin_check", ids)
        pin = next(s for s in plan.steps if s.id == "exit_product_pin_check")
        self.assertIn("exit_node_elgamal.pub", pin.detail + pin.command)
        mark = next(s for s in plan.steps if s.id == "mark_fleet_peer_complete")
        self.assertIn("RPT_REMOTE_WIPE_OK", mark.command)
        self.assertIn("mark_wipe_complete('RO'", mark.command)

    def test_host_identity_gate_ro_local_on_ro_host(self):
        """When running on RO host, local destructive + exit pin OK."""
        plan = build_weekly_entry_rebuild_plan(
            period="7d",
            dry_run=True,
            exit_healthy=True,
            entry_healthy=True,
            role="auto",
            completed=["IS"],
            local_country="RO",
        )
        ids = [s.id for s in plan.steps]
        stop = next(s for s in plan.steps if s.id == "stop_runtime")
        self.assertIn("local", stop.action.lower())
        self.assertIn("assert_local_host_is_target", stop.command)
        self.assertIn("systemctl stop", stop.command)
        sh = next(s for s in plan.steps if s.id == "selfhost_reapply")
        self.assertIn(SELFHOST_FULL_CMD.split()[-1], sh.command)  # selfhost_node.sh
        self.assertIn("assert_local_host_is_target", sh.command)
        self.assertIn("exit_product_pin_check", ids)
        pin = next(s for s in plan.steps if s.id == "exit_product_pin_check")
        self.assertIn("exit_node_elgamal.pub", pin.command)
        mark = next(s for s in plan.steps if s.id == "mark_fleet_peer_complete")
        self.assertIn("assert_local_host_is_target", mark.command)
        self.assertNotIn("RPT_REMOTE_WIPE_OK", mark.command)

    def test_exit_no_weekly_timer_honesty_allows_sequential_ro(self):
        """exit_no_weekly_timer must not claim RO is never fleet-wiped."""
        x_desc = " ".join(r.description for r in exit_reinstall_requirements())
        self.assertIn("sequential", x_desc.lower())
        # Must not say exit is never weekly-wiped forever
        self.assertNotIn("never weekly", x_desc.lower())
        self.assertNotIn("not on the weekly", x_desc.lower())


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
        self.assertIn("dry-run", out)
        self.assertIn("acquire2", out)
        self.assertIn("must fail closed", out)
        self.assertIn("selfhost", out)
        self.assertIn("package reinstall", out)
        self.assertIn("structural_live_steps: ok=true", out)
        self.assertIn("plan_embeds_mandatory_reinstall=true", out)
        self.assertIn("skip_dns=0", out)
        self.assertIn("target=is", out)
        self.assertIn("sequential fleet", out)
        # Peer failover wording (not legacy "entry-only" bulk deny of RO forever)
        self.assertTrue(
            "failover" in out or "peer" in out,
            out[:500],
        )

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
        blob = (r.stderr + r.stdout).lower()
        self.assertTrue(
            "entry" in blob or "refuse" in blob or "never" in blob or "sequential" in blob,
            blob,
        )
        self.assertNotIn("target=ro", blob)


if __name__ == "__main__":
    unittest.main()

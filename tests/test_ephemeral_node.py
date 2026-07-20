"""Ephemeral short-lived node: plan, schedule, dry-run, confirm gates."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from node.ephemeral_node import (  # noqa: E402
    DEFAULT_PERIOD,
    HONESTY_KEYS,
    HONESTY_NOLOG,
    HONESTY_PROVIDER,
    assert_live_confirm,
    build_ephemeral_plan,
    cron_line,
    format_period,
    is_live_confirmed,
    parse_period_seconds,
    systemd_service_unit,
    systemd_timer_unit,
)
from node.nolog import NO_LOG_POLICY  # noqa: E402


class TestPeriodParse(unittest.TestCase):
    def test_parse_common_periods(self):
        self.assertEqual(parse_period_seconds("7d"), 7 * 86400)
        self.assertEqual(parse_period_seconds("24h"), 24 * 3600)
        self.assertEqual(parse_period_seconds("30m"), 30 * 60)
        self.assertEqual(parse_period_seconds("1w"), 7 * 86400)
        # Prefer largest unit when evenly divisible
        self.assertIn(format_period(7 * 86400), ("7d", "1w"))
        self.assertIn(format_period(24 * 3600), ("24h", "1d"))
        self.assertEqual(format_period(30 * 60), "30m")

    def test_parse_rejects_bad(self):
        with self.assertRaises(ValueError):
            parse_period_seconds("nope")
        with self.assertRaises(ValueError):
            parse_period_seconds("0d")


class TestEphemeralPlan(unittest.TestCase):
    def test_dry_run_snapshot_then_rebuild_steps(self):
        plan = build_ephemeral_plan(
            mode="snapshot_then_rebuild",
            period="7d",
            dry_run=True,
        )
        self.assertTrue(plan.dry_run)
        ids = [s.id for s in plan.steps]
        self.assertIn("snapshot", ids)
        self.assertIn("rebuild_host", ids)
        self.assertIn("selfhost_reapply", ids)
        self.assertIn("health_check", ids)
        self.assertIn("schedule_next", ids)
        # Order: snapshot before rebuild
        self.assertLess(ids.index("snapshot"), ids.index("rebuild_host"))
        self.assertLess(ids.index("rebuild_host"), ids.index("selfhost_reapply"))
        text = plan.format_text()
        self.assertIn("snapshot", text.lower())
        self.assertIn("rebuild", text.lower())
        self.assertIn("periodic", text.lower())
        self.assertIn("selfhost", text.lower())
        d = plan.to_dict()
        self.assertEqual(d["period_seconds"], 7 * 86400)
        self.assertIn("snapshot", d["step_ids"])

    def test_snapshot_only_and_rebuild_only(self):
        snap = build_ephemeral_plan(mode="snapshot", period="24h")
        self.assertIn("snapshot", [s.id for s in snap.steps])
        self.assertNotIn("rebuild_host", [s.id for s in snap.steps])
        reb = build_ephemeral_plan(mode="rebuild", period="7d")
        self.assertIn("rebuild_host", [s.id for s in reb.steps])
        self.assertNotIn("snapshot", [s.id for s in reb.steps])

    def test_selfhost_and_nolog_in_plan(self):
        plan = build_ephemeral_plan(mode="rebuild")
        blob = plan.format_text().lower()
        self.assertIn("selfhost", blob)
        self.assertTrue(
            "no-log" in blob or "nolog" in blob or "no log" in blob,
            "plan text should mention no-log posture",
        )
        self.assertTrue(
            any("nolog" in h.lower() or "no-log" in h.lower() for h in plan.honesty)
        )
        self.assertIn(HONESTY_NOLOG, plan.honesty)
        self.assertIn(HONESTY_PROVIDER, plan.honesty)
        self.assertIn(HONESTY_KEYS, plan.honesty)

    def test_destructive_rebuild_marked(self):
        plan = build_ephemeral_plan(mode="rebuild")
        reb = next(s for s in plan.steps if s.id == "rebuild_host")
        self.assertTrue(reb.destructive)

    def test_rotate_keys_optional_step(self):
        plan = build_ephemeral_plan(mode="rebuild", rotate_keys=True)
        self.assertIn("rotate_keys", [s.id for s in plan.steps])


class TestConfirmGate(unittest.TestCase):
    def test_live_confirm_default_false(self):
        self.assertFalse(is_live_confirmed({}))
        ok, msg = assert_live_confirm({})
        self.assertFalse(ok)
        self.assertIn("RPT_EPHEMERAL_CONFIRM", msg)

    def test_live_confirm_yes(self):
        self.assertTrue(is_live_confirmed({"RPT_EPHEMERAL_CONFIRM": "yes"}))
        ok, msg = assert_live_confirm({"RPT_EPHEMERAL_CONFIRM": "1"})
        self.assertTrue(ok)
        self.assertEqual(msg, "")


class TestScheduleUnits(unittest.TestCase):
    def test_timer_has_periodic_interval(self):
        unit = systemd_timer_unit(period="7d")
        self.assertIn("OnUnitActiveSec=", unit)
        self.assertIn(str(7 * 86400), unit)
        self.assertIn("Timer", unit)
        self.assertIn("periodic", unit.lower() or "Periodic" in unit)

    def test_service_default_dry_run(self):
        unit = systemd_service_unit(dry_run=True)
        self.assertIn("--dry-run", unit)
        self.assertNotIn("RPT_EPHEMERAL_CONFIRM=yes", unit)

    def test_cron_line_periodic(self):
        line = cron_line(period="7d", dry_run=True)
        self.assertIn("periodic", line.lower())
        self.assertIn("ephemeral_node.py", line)
        self.assertIn("--dry-run", line)


class TestCliDryRun(unittest.TestCase):
    def test_cli_dry_run_exit_0(self):
        script = ROOT / "scripts" / "ephemeral_node.py"
        self.assertTrue(script.is_file())
        r = subprocess.run(
            [sys.executable, str(script), "--dry-run", "--mode", "snapshot_then_rebuild", "--period", "7d"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
            env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONPATH": str(ROOT)},
        )
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        out = r.stdout.lower()
        self.assertIn("snapshot", out)
        self.assertIn("rebuild", out)
        self.assertIn("dry-run", out)
        self.assertIn("periodic", out)
        self.assertIn("selfhost", out)

    def test_cli_live_without_confirm_fails(self):
        script = ROOT / "scripts" / "ephemeral_node.py"
        env = {
            k: v
            for k, v in __import__("os").environ.items()
            if k != "RPT_EPHEMERAL_CONFIRM"
        }
        env["PYTHONPATH"] = str(ROOT)
        r = subprocess.run(
            [sys.executable, str(script), "--live", "--mode", "rebuild"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("RPT_EPHEMERAL_CONFIRM", r.stderr + r.stdout)


class TestScriptsAndDocs(unittest.TestCase):
    def test_install_timer_script(self):
        p = ROOT / "scripts" / "install_ephemeral_timer.sh"
        self.assertTrue(p.is_file())
        text = p.read_text(encoding="utf-8")
        self.assertIn("periodic", text.lower())
        self.assertIn("timer", text.lower())
        self.assertIn("ephemeral_node.py", text)
        self.assertIn("selfhost", text.lower() or "no-log")

    def test_nolog_still_off(self):
        self.assertFalse(NO_LOG_POLICY["connection_log"])
        self.assertFalse(NO_LOG_POLICY["session_log"])

    def test_sundries_or_readme_mentions_ephemeral(self):
        sundries = (ROOT / "sundries.txt").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        blob = sundries + readme
        self.assertTrue(
            "ephemeral" in blob.lower() or "short-lived" in blob.lower(),
            "operator docs should mention ephemeral/short-lived nodes",
        )
        self.assertIn("snapshot", blob.lower())
        self.assertIn("rebuild", blob.lower())


if __name__ == "__main__":
    unittest.main()

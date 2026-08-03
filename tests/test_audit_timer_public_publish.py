"""Timer-expiry audit must write + publish so public last-run advances."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "status_page"))


class TestTimerWritePathStructural(unittest.TestCase):
    def test_oneshot_invokes_write_not_dry_run(self) -> None:
        text = (ROOT / "scripts" / "install_security_audit_timer.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("run_security_audit.py", text)
        self.assertIn("--write", text)
        self.assertIn("--node-only", text)
        # Must not be dry-run only
        self.assertNotIn("--dry-run", text)
        # Timer period product default
        self.assertIn('PERIOD="${PERIOD:-1d}"', text)
        # After write: stamp + optional constrained publish for public last-run
        self.assertIn("last_audit_write", text)
        self.assertIn("RPT_AUDIT_STATUS_SSH", text)
        self.assertIn("publish_audit_artifacts", text)

    def test_pull_agent_timer_wires_sync_publish(self) -> None:
        path = ROOT / "scripts" / "install_audit_public_refresh_timer.sh"
        self.assertTrue(path.is_file(), "pull-agent timer installer required")
        text = path.read_text(encoding="utf-8")
        self.assertIn("sync_audit_artifacts_from_node.py", text)
        self.assertIn("--publish", text)
        self.assertIn("rpt-audit-public-refresh.timer", text)

    def test_sync_script_default_host_and_publish_flag(self) -> None:
        text = (ROOT / "scripts" / "sync_audit_artifacts_from_node.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("--publish", text)
        self.assertIn("publish_pulled_artifacts", text)
        self.assertIn("DEFAULT_HOST", text)
        # Default residual timer home (IS monopin with active timer)
        self.assertIn("82.221.101.241", text)


class TestPublishTimerHelpers(unittest.TestCase):
    def test_timer_write_then_publish_steps_order(self) -> None:
        from publish_timer_audit_to_status import timer_write_then_publish_expected_steps

        steps = timer_write_then_publish_expected_steps()
        self.assertEqual(steps[0], "run_security_audit_write")
        self.assertIn("publish_or_pull_to_status", steps)
        self.assertIn("status_serves_new_generated_at", steps)
        self.assertLess(
            steps.index("run_security_audit_write"),
            steps.index("publish_or_pull_to_status"),
        )

    def test_generated_at_and_artifacts_ready(self) -> None:
        from publish_timer_audit_to_status import (
            artifacts_ready_for_publish,
            generated_at_from_json_file,
        )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            static = root / "status_page" / "static"
            static.mkdir(parents=True)
            json_path = static / "security_audit_latest.json"
            self.assertIsNone(generated_at_from_json_file(json_path))
            missing = artifacts_ready_for_publish(root)
            self.assertFalse(missing["ok"])
            stamp = "2026-08-04T12:00:00Z"
            json_path.write_text(
                json.dumps({"generated_at": stamp, "overall": "ok"}) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(generated_at_from_json_file(json_path), stamp)
            # Still missing AUDIT mirrors
            mid = artifacts_ready_for_publish(root)
            self.assertFalse(mid["ok"])
            for rel in (
                "AUDIT.md",
                "status_page/AUDIT.md",
                "status_page/public/AUDIT.md",
            ):
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("# audit\n", encoding="utf-8")
            ready = artifacts_ready_for_publish(root)
            self.assertTrue(ready["ok"], ready)
            self.assertEqual(ready["generated_at"], stamp)

    def test_live_repo_json_has_generated_at_parser_roundtrip(self) -> None:
        from audit_countdown import load_last_audit_generated_at, parse_audit_generated_at
        from publish_timer_audit_to_status import generated_at_from_json_file

        path = ROOT / "status_page" / "static" / "security_audit_latest.json"
        if not path.is_file():
            self.skipTest("security_audit_latest.json not staged")
        raw = generated_at_from_json_file(path)
        self.assertTrue(raw)
        dt = parse_audit_generated_at(raw)
        self.assertIsNotNone(dt)
        last = load_last_audit_generated_at(path)
        self.assertIsNotNone(last)
        self.assertEqual(
            last.strftime("%Y-%m-%dT%H:%M:%SZ"),
            dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )


class TestClientRefreshOnRoll(unittest.TestCase):
    def test_countdown_js_polls_faster_after_roll_and_realigns(self) -> None:
        js = (ROOT / "status_page" / "static" / "audit_countdown.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("awaitingNewRun", js)
        self.assertIn("pollEveryTicksWhenRolled", js)
        self.assertIn("refreshLastRun", js)
        self.assertIn("generatedAtFromPayload", js)
        # Realign deadline when last-run advances (timer publish landed)
        self.assertIn("deadlineMs = parsed + period", js)
        self.assertIn("lastSeenIso", js)


class TestHomepageIntroReword(unittest.TestCase):
    def test_new_intro_present_old_absent(self) -> None:
        from public_chrome import SUITE_HOME_INTRO_BODY

        self.assertIn(
            "virtual private network for your device and personal use",
            SUITE_HOME_INTRO_BODY,
        )
        self.assertIn("no obligation to pay", SUITE_HOME_INTRO_BODY)
        self.assertIn("Restore Privacy VPN subscription", SUITE_HOME_INTRO_BODY)
        self.assertNotIn(
            "Download free below, try three days with no card, then keep going with a KEYGEN",
            SUITE_HOME_INTRO_BODY,
        )
        static = (ROOT / "public_site" / "index.html").read_text(encoding="utf-8")
        self.assertIn(SUITE_HOME_INTRO_BODY, static)
        self.assertNotIn(
            "Download free below, try three days with no card, then keep going with a KEYGEN",
            static,
        )


if __name__ == "__main__":
    unittest.main()

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
        # Fresh stamp gate (do not treat prior generated_at as success)
        self.assertIn("GEN_BEFORE", text)
        self.assertIn("GEN_AFTER", text)
        self.assertIn("uk_ping_estimates.py", text)
        self.assertIn("last_audit_write", text)
        self.assertIn("RPT_AUDIT_STATUS_SSH", text)
        self.assertIn("publish_audit_artifacts", text)
        # Never hard-code historical residual 0.3.6 as catalog fallback
        # (empty paid_assets/0.3.6 → permanent false Red package RAG).
        self.assertNotIn('RPT_CATALOG_VERSION:-0.3.6', text)
        self.assertIn("missing catalog monopin", text)

    def test_build_markdown_soft_fails_missing_uk_ping(self) -> None:
        src = (ROOT / "scripts" / "run_security_audit.py").read_text(encoding="utf-8")
        self.assertIn("UK ping section unavailable this pass", src)
        self.assertIn("never abort write_outputs", src)
        # ImportError must not escape the soft-fail block
        idx = src.index("from client.uk_ping_estimates import")
        block = src[idx - 200 : idx + 500]
        self.assertIn("except Exception", block)

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
        # Default residual timer home (Germany default entry)
        self.assertIn("178.105.187.178", text)
        self.assertNotIn("82.221.101.241", text)


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
        from audit_countdown import (
            audit_json_matches_product_monopin,
            load_last_audit_generated_at,
            load_security_audit_json_prefer_upstream,
            parse_audit_generated_at,
            product_monopin_for_audit,
        )
        from publish_timer_audit_to_status import generated_at_from_json_file

        path = ROOT / "status_page" / "static" / "security_audit_latest.json"
        if not path.is_file():
            self.skipTest("security_audit_latest.json not staged")
        raw = generated_at_from_json_file(path)
        self.assertTrue(raw)
        dt = parse_audit_generated_at(raw)
        self.assertIsNotNone(dt)
        # Prefer-upstream monopin-matches product; wrong-pin residual (e.g. 0.3.6
        # on Helsinki) and wrong-pin local are discarded — last-run may be None
        # until a monopin-matching --write is staged.
        last = load_last_audit_generated_at(path)
        preferred = load_security_audit_json_prefer_upstream(path)
        local_raw = json.loads(path.read_text(encoding="utf-8"))
        pin = product_monopin_for_audit()
        if pin and not audit_json_matches_product_monopin(local_raw, monopin=pin):
            # Honest: no monopin-matching inventory → no public last-run stamp.
            self.assertIsNone(preferred)
            return
        self.assertIsNotNone(last)
        self.assertIsNotNone(preferred)
        pref_at = parse_audit_generated_at(str(preferred.get("generated_at") or ""))
        self.assertIsNotNone(pref_at)
        self.assertEqual(
            last.strftime("%Y-%m-%dT%H:%M:%SZ"),
            pref_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
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


class TestUpstreamPreferForPublicLastRun(unittest.TestCase):
    def test_prefer_newer_and_default_helsinki_upstream(self) -> None:
        from audit_countdown import (
            DEFAULT_AUDIT_UPSTREAM_JSON_URL,
            load_security_audit_json_prefer_upstream,
            parse_audit_generated_at,
            prefer_newer_generated_at,
        )
        from datetime import datetime, timezone

        older = datetime(2026, 8, 2, 15, 42, 27, tzinfo=timezone.utc)
        newer = datetime(2026, 8, 3, 23, 27, 13, tzinfo=timezone.utc)
        self.assertEqual(prefer_newer_generated_at(older, newer), newer)
        self.assertEqual(prefer_newer_generated_at(newer, older), newer)
        self.assertIn("135.181.152.10.sslip.io/public-audit/", DEFAULT_AUDIT_UPSTREAM_JSON_URL)
        # Local-only load still works when upstream disabled via empty override
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "security_audit_latest.json"
            p.write_text(
                json.dumps({"generated_at": "2026-08-01T00:00:00Z", "ok": True}) + "\n",
                encoding="utf-8",
            )
            data = load_security_audit_json_prefer_upstream(
                p, upstream_url=""  # empty string = no fetch
            )
            self.assertIsNotNone(data)
            self.assertEqual(
                parse_audit_generated_at(str(data.get("generated_at"))),
                datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc),
            )

    def test_oneshot_always_attempts_scp_when_key_present(self) -> None:
        text = (ROOT / "scripts" / "install_security_audit_timer.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("rpt_audit_status_key", text)
        self.assertIn("publish_audit_artifacts", text)
        self.assertIn("publish_scp", text)
        self.assertIn("135.181.152.10", text)
        self.assertIn("public-audit", (ROOT / "scripts" / "run_security_audit.py").read_text(encoding="utf-8"))

    def test_app_read_static_prefers_upstream_audit_json(self) -> None:
        app = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("load_security_audit_json_prefer_upstream", app)
        self.assertIn("security_audit_latest.json", app)
        self.assertIn("audit_upstream_audit_url", app)


if __name__ == "__main__":
    unittest.main()

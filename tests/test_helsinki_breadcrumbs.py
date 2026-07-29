"""Unit tests for Helsinki breadcrumb vault hash/diff (GitHub is not the queue)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import helsinki_breadcrumbs as hb  # noqa: E402


MANIFEST_OK = {
    "schema": "rpt.breadcrumbs.v1",
    "monopin": "0.5.1",
    "source_of_truth": "helsinki_breadcrumbs_vault",
    "github_breadcrumb_flow": "deprecated",
    "helsinki_host": "135.181.152.10",
    "needs_any_apple_work": False,
    "platforms": {
        "macos": {"needs_work": False, "bundle_version": "0.5.1"},
    },
    "macbook_actions": [],
}

MANIFEST_WORK = {
    **MANIFEST_OK,
    "needs_any_apple_work": True,
    "platforms": {
        "macos": {
            "needs_work": True,
            "bundle_version": "0.2.3",
            "status": "carry_forward_or_lag",
        },
        "ios": {"needs_work": True, "bundle_version": "0.1.7"},
    },
    "macbook_actions": ["rebuild_macos_native_seal", "rebuild_ios_team_sign"],
}


class TestVaultHashDiff(unittest.TestCase):
    def test_aggregate_hash_stable(self):
        files = {
            "manifest.json": json.dumps(MANIFEST_OK, sort_keys=True),
            "checklist.md": "# hi\n",
        }
        h1 = hb.vault_aggregate_hash(files)
        h2 = hb.vault_aggregate_hash(dict(reversed(list(files.items()))))
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    def test_unchanged_when_same_hash(self):
        files = {"manifest.json": json.dumps(MANIFEST_OK)}
        h = hb.vault_aggregate_hash(files)
        diff = hb.compare_vault(h, files, manifest=MANIFEST_OK)
        self.assertFalse(diff["changed"])
        self.assertEqual(diff["status"], "unchanged")
        self.assertFalse(diff["should_act"])

    def test_changed_and_should_act_when_needs_work(self):
        a = {"manifest.json": json.dumps(MANIFEST_OK)}
        b = {"manifest.json": json.dumps(MANIFEST_WORK)}
        h = hb.vault_aggregate_hash(a)
        diff = hb.compare_vault(h, b, manifest=MANIFEST_WORK)
        self.assertTrue(diff["changed"])
        self.assertTrue(diff["needs_work"])
        self.assertTrue(diff["should_act"])

    def test_baseline_first_poll(self):
        files = {"manifest.json": json.dumps(MANIFEST_WORK)}
        diff = hb.compare_vault(None, files, manifest=MANIFEST_WORK)
        self.assertEqual(diff["status"], "baseline")
        self.assertTrue(diff["changed"])
        self.assertTrue(diff["should_act"])

    def test_is_helsinki_sourced(self):
        self.assertTrue(hb.is_helsinki_sourced(MANIFEST_OK))
        bad = {**MANIFEST_OK, "source_of_truth": "github", "github_breadcrumb_flow": "active"}
        bad.pop("helsinki_host", None)
        self.assertFalse(hb.is_helsinki_sourced(bad))

    def test_needs_work_platform_flag(self):
        self.assertFalse(hb.needs_work(MANIFEST_OK))
        self.assertTrue(hb.needs_work(MANIFEST_WORK))
        only_plat = {
            "platforms": {"macos": {"needs_work": True}},
            "needs_any_apple_work": False,
        }
        self.assertTrue(hb.needs_work(only_plat))

    def test_script_forbids_github_primary_queue_docs(self):
        src = (ROOT / "scripts" / "helsinki_breadcrumbs.py").read_text(encoding="utf-8")
        self.assertIn("GitHub is NOT the queue", src)
        self.assertIn("135.181.152.10", src)
        self.assertIn("id_ed25519_restore_privacy_eu", src)
        self.assertIn("/opt/restore-privacy/breadcrumbs/current", src)


if __name__ == "__main__":
    unittest.main()

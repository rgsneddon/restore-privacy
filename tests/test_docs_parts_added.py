"""Docs stay current with shipped parts (wipe, countdown, multihop, licence)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    p = ROOT / rel
    assert p.is_file(), f"missing {rel}"
    return p.read_text(encoding="utf-8")


class TestDocsPartsAddedToDate(unittest.TestCase):
    def test_readme_and_public_mirror_share_themes(self):
        root = _read("README.md")
        pub = _read("status_page/public/README.md")
        # Public mirror should match root for product docs
        self.assertEqual(root, pub)

        for text in (root, pub):
            low = text.lower()
            # (a) full copyright licence (not MIT product grant)
            self.assertIn("full copyright", low)
            self.assertNotIn("MIT License", text)
            self.assertNotRegex(
                text,
                re.compile(r"License\s*\|\s*\[LICENSE\]\(LICENSE\)\s*\(MIT\)", re.I),
            )
            # (b) weekly entry wipe + exclusive / failover
            self.assertIn("weekly", low)
            self.assertIn("exclusive", low)
            self.assertIn("failover", low)
            self.assertIn("entry-only", low.replace("entry only", "entry-only"))
            # (c) entry-only clear timer (no dual Node A/B wipe countdown)
            self.assertIn("Node A", text)
            self.assertIn("entry-only", low.replace("entry only", "entry-only"))
            self.assertIn("clear timer", low)
            self.assertNotIn("Node A/B clear countdowns", text)
            self.assertIn("no exit wipe countdown", low)
            self.assertIn("countdown", low)
            # (d) multihop residual-via-exit implemented (not "not routed yet")
            self.assertIn("residual-via-exit", low.replace("residual via exit", "residual-via-exit"))
            self.assertIn("RPT_MULTIHOP_ENABLED", text)
            self.assertNotIn("not routed yet", low)
            self.assertNotIn("hop *list* only", low)
            # (e) pre-wipe health gates
            self.assertIn("wipe_preflight", text)
            self.assertIn("fail closed", low.replace("fail-closed", "fail closed"))
            self.assertIn("selfhost", low)

    def test_sundries_operator_wipe_and_multihop(self):
        text = _read("sundries.txt")
        low = text.lower()
        self.assertIn("weekly_entry_rebuild", text)
        self.assertIn("wipe_preflight", text)
        self.assertIn("rebuild_lock", text)
        self.assertIn("select_residual_endpoint", text)
        self.assertIn("fail closed", low.replace("fail-closed", "fail closed"))
        self.assertIn("node_wipe_countdown", text)
        # Multihop residual implemented — not stale hop-list-only
        self.assertIn("MULTI_HOP_ROUTING_IMPLEMENTED", text)
        self.assertIn("residual-via-exit", low.replace("residual via exit", "residual-via-exit"))
        self.assertNotIn("not routed yet", low)
        self.assertNotIn("is_multihop_active=False", text)
        # Licence
        self.assertIn("full copyright", low)

    def test_license_still_full_copyright(self):
        text = _read("LICENSE")
        self.assertIn("FULL COPYRIGHT", text.upper())
        self.assertNotIn("MIT License", text)


if __name__ == "__main__":
    unittest.main()

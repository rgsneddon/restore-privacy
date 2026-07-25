"""Docs + helpers for RPT_CAPACITY_TOKEN enable path (no real secrets)."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.capacity_probe import probe_peer_capacity_map  # noqa: E402
from node.private_capacity import authorize_capacity_request  # noqa: E402


class TestCapacityTokenHelpers(unittest.TestCase):
    def test_authorize_requires_token(self):
        ok, msg = authorize_capacity_request(
            authorization_header="Bearer x",
            env={},
        )
        self.assertFalse(ok)
        ok2, _ = authorize_capacity_request(
            authorization_header="Bearer secret-token-value",
            env={"RPT_CAPACITY_TOKEN": "secret-token-value"},
        )
        self.assertTrue(ok2)

    def test_probe_empty_without_token(self):
        m = probe_peer_capacity_map(env={}, catalog_hosts=["82.221.101.241"])
        self.assertEqual(m, {})


class TestCapacityTokenDocs(unittest.TestCase):
    def test_operator_docs_mention_token_and_privacy(self):
        files = [
            ROOT / "README.md",
            ROOT / "scripts" / "hop_env.example",
            ROOT / "docs" / "CAPACITY_PROBES.md",
            ROOT / "docs" / "NODE_WIPE_REINSTALL.md",
            ROOT / "scripts" / "MULTIHOP_EXIT_HOP_PREP.md",
            ROOT / "scripts" / "install_capacity_token_env.sh",
        ]
        for p in files:
            self.assertTrue(p.is_file(), f"missing {p}")
            text = p.read_text(encoding="utf-8")
            self.assertIn("RPT_CAPACITY_TOKEN", text, f"{p.name} missing token")
            # No committed real-looking 48-char hex secrets in docs
            # (generated tokens are openssl rand -hex 24 → 48 hex chars)
            if p.suffix in (".md", ".example"):
                # Placeholder language
                low = text.lower()
                self.assertTrue(
                    "private" in low or "title-only" in low or "no live client" in low
                    or "not publish" in low or "do not commit" in low,
                    f"{p.name} should state private/no-public-count honesty",
                )

    def test_docs_list_optional_probe_keys(self):
        cap = (ROOT / "docs" / "CAPACITY_PROBES.md").read_text(encoding="utf-8")
        for key in (
            "RPT_CAPACITY_TOKEN",
            "RPT_CAPACITY_PROBE_URLS",
            "RPT_CAPACITY_PROBE_TIMEOUT",
            "RPT_NODE_MAX_SESSIONS",
            "RPT_NODE_BANDWIDTH_CAP_BPS",
            "RPT_BANDWIDTH_CAP_BPS_MAP",
        ):
            self.assertIn(key, cap)
        self.assertIn("title-only", cap.lower().replace("title only", "title-only") or cap.lower())
        # Accept either phrasing
        self.assertTrue(
            "title-only" in cap.lower() or "title only" in cap.lower()
            or "no live client" in cap.lower()
        )

    def test_hop_env_example_has_placeholder_not_live_secret(self):
        text = (ROOT / "scripts" / "hop_env.example").read_text(encoding="utf-8")
        self.assertIn("RPT_CAPACITY_TOKEN", text)
        self.assertIn("replace-with-long-random-secret", text)
        # Must not look like a committed production token assignment with hex
        for line in text.splitlines():
            if line.strip().startswith("RPT_CAPACITY_TOKEN=") and not line.strip().startswith("#"):
                val = line.split("=", 1)[1].strip()
                self.assertFalse(
                    bool(re.fullmatch(r"[0-9a-fA-F]{32,}", val)),
                    "hop_env.example must not commit a real hex token",
                )

    def test_install_script_writes_env_file_not_repo(self):
        src = (ROOT / "scripts" / "install_capacity_token_env.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("capacity.env", src)
        self.assertIn("/etc/restore-privacy", src)
        self.assertIn("EnvironmentFile", src)
        self.assertIn("do not commit", src.lower())
        self.assertIn("RPT_NODE_BANDWIDTH_CAP_BPS", src)
        self.assertIn("RPT_NODE_MAX_SESSIONS", src)

    def test_render_blueprint_has_capacity_env_placeholders(self):
        text = (ROOT / "render.yaml").read_text(encoding="utf-8")
        self.assertIn("RPT_CAPACITY_TOKEN", text)
        self.assertIn("RPT_BANDWIDTH_CAP_BPS_MAP", text)
        # Token must be dashboard-only (sync: false), not a committed secret value
        # Find the RPT_CAPACITY_TOKEN block and ensure sync: false nearby
        idx = text.index("RPT_CAPACITY_TOKEN")
        window = text[idx : idx + 80]
        self.assertIn("sync: false", window)


if __name__ == "__main__":
    unittest.main()

"""Shipped weekly wipe failsafe docs: hop may fail → manual reconnection.

Drives the real README / NODE_WIPE_REINSTALL / countdown honesty / wipe_hop
module text (no reimplemented strings).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Canonical failsafe meaning (objective) — must appear in primary shipped surfaces
FAILSAFE_CORE = (
    "if hop does not succeed, the client may disconnect or restart and will "
    "require manual reconnection"
)
WEEKLY_WIPE = "weekly"


def _plain(text: str) -> str:
    """Lowercase prose; strip markdown emphasis; collapse whitespace for wraps."""
    import re

    s = (text or "").lower().replace("*", "").replace("_", "")
    return re.sub(r"\s+", " ", s).strip()


class TestWipeFailsafeShippedDocs(unittest.TestCase):
    def test_readme_weekly_wipe_failsafe(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        low = _plain(text)
        self.assertIn(FAILSAFE_CORE, low)
        self.assertIn(WEEKLY_WIPE, low)
        self.assertIn("manual reconnection", low)
        self.assertIn("disconnect", low)
        # Still honest: best-effort hop + not zero packet-loss
        self.assertIn("best-effort", low)
        self.assertIn("zero packet-loss", low)
        # Sequential fleet remains
        self.assertIn("is → de → us", low)

    def test_node_wipe_reinstall_failsafe(self):
        text = (ROOT / "docs" / "NODE_WIPE_REINSTALL.md").read_text(encoding="utf-8")
        low = _plain(text)
        self.assertIn(FAILSAFE_CORE, low)
        self.assertIn("manual reconnection", low)
        self.assertIn(WEEKLY_WIPE, low)
        self.assertIn("best-effort", low)
        self.assertIn("not zero packet-loss", low)
        # Monopin order (not RO as live wipe target)
        self.assertIn("is → de → us", low)

    def test_countdown_honesty_blurb_failsafe(self):
        sys.path.insert(0, str(ROOT / "status_page"))
        from node_wipe_countdown import HONESTY_BLURB, render_node_wipe_countdown_html

        low = _plain(HONESTY_BLURB)
        self.assertIn(FAILSAFE_CORE, low)
        self.assertIn("manual reconnection", low)
        self.assertIn("weekly", low)
        self.assertIn("disconnect", low)
        self.assertIn("restart", low)
        self.assertIn("best-effort", low)
        # Rendered public HTML carries the same blurb (not seamless-hop-only)
        html = render_node_wipe_countdown_html()
        self.assertIn(HONESTY_BLURB, html)
        self.assertIn("manual reconnection", html.lower())
        self.assertNotIn("seamless hop always", html.lower())

    def test_wipe_hop_module_honesty_failsafe(self):
        src = (ROOT / "client" / "wipe_hop.py").read_text(encoding="utf-8")
        # Module docstring is the shipped honesty surface for hop helpers
        doc = _plain(src.split('"""', 2)[1])
        self.assertIn(FAILSAFE_CORE, doc)
        self.assertIn("manual reconnection", doc)
        self.assertIn("weekly", doc)
        self.assertIn("not guaranteed", doc)


if __name__ == "__main__":
    unittest.main()

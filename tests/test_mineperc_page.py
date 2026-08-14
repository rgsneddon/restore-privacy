"""Shipped mineperc page: longest-string boxes + per-part copy."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "perc_chain" / "mineperc" / "public" / "index.html"


class TestMinepercPage(unittest.TestCase):
    def test_facts_copy_and_no_clip(self) -> None:
        html = PAGE.read_text(encoding="utf-8")
        self.assertIn("mineperc.restoreprivacy.online", html)
        self.assertIn("1466", html)
        self.assertIn("PERC", html)
        self.assertIn("PERC_USERNAME.WORKER", html)
        self.assertIn(
            "perc-mine --pool mineperc.restoreprivacy.online:1466",
            html,
        )
        self.assertNotRegex(html, r"(?i)beam")
        for part in ("stratum", "worker", "high", "perc-mine"):
            self.assertIn(f'data-copy-part="{part}"', html)
            self.assertIn(f'data-copy-target="{part}"', html)
        self.assertEqual(html.count('class="copy-icon"'), 4)
        self.assertIn("minWidthChFromParts", html)
        self.assertIn("copyPayloadForPart", html)
        self.assertIn("Live miners", html)
        self.assertIn("72 seconds", html)
        self.assertIn("miner-body", html)
        self.assertIn("/api/stats", html)
        self.assertIn("<th>Wallet</th>", html)
        self.assertIn("m.wallet", html)
        self.assertNotIn("<th>Remote</th>", html)
        self.assertNotIn("m.remote", html)
        css = html[html.index(".info-value") : html.index(".copy-icon")]
        self.assertNotIn("ellipsis", css)
        self.assertNotIn("overflow: hidden", css)
        self.assertNotIn("overflow:hidden", css)


if __name__ == "__main__":
    unittest.main()

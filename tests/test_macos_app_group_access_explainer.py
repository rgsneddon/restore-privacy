"""Drive shipped Mac App Group product explainer (copy + show-once + wire).

Reads production Swift (`RptAppGroupAccessExplainer.swift`, `RptVpnChannel.swift`)
— does not re-implement product strings in the test as the sole source of truth.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPLAINER = (
    ROOT / "client_app" / "macos" / "NativePrep" / "RptAppGroupAccessExplainer.swift"
)
VPN_CHANNEL = ROOT / "client_app" / "macos" / "NativePrep" / "RptVpnChannel.swift"
PBX = ROOT / "client_app" / "macos" / "Runner.xcodeproj" / "project.pbxproj"
DOC = ROOT / "client_app" / "APPLE_APP_GROUP_ACCESS.md"


def _swift_static_string(src: str, name: str) -> str:
    """Extract `static let name = \"...\"` (single-line or continued one-line literal)."""
    # Single line: static let name = "..."
    m = re.search(
        rf'static let {re.escape(name)}\s*=\s*"((?:\\.|[^"\\])*)"',
        src,
    )
    if m:
        return bytes(m.group(1), "utf-8").decode("unicode_escape")
    # Multi-line assignment: static let name =\n    "..."
    m = re.search(
        rf'static let {re.escape(name)}\s*=\s*\n\s*"((?:\\.|[^"\\])*)"',
        src,
    )
    if not m:
        raise AssertionError(f"could not extract static let {name} from explainer")
    return bytes(m.group(1), "utf-8").decode("unicode_escape")


def _register_body(src: str) -> str:
    m = re.search(
        r"static func register\(with messenger: FlutterBinaryMessenger\)\s*\{(?P<body>.*?)case \"connect\"",
        src,
        re.S,
    )
    if not m:
        raise AssertionError("register(with:) body not found")
    return m.group("body")


class TestMacosAppGroupAccessExplainer(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.explainer = EXPLAINER.read_text(encoding="utf-8")
        cls.channel = VPN_CHANNEL.read_text(encoding="utf-8")

    def test_shipped_one_line_mentions_allow_tunnel_nodes(self) -> None:
        one = _swift_static_string(self.explainer, "oneLine")
        low = one.lower()
        self.assertIn("allow", low)
        self.assertIn("tunnel", low)
        self.assertIn("node", low)
        # Concise: primary line is one sentence-scale string
        self.assertLessEqual(len(one), 160)
        self.assertNotIn("scan", low)
        self.assertNotIn("all apps", low)

    def test_shipped_secondary_not_third_party_inventory(self) -> None:
        sec = _swift_static_string(self.explainer, "secondaryLine")
        low = sec.lower()
        self.assertTrue(
            "not" in low and ("chrome" in low or "mail" in low or "other apps" in low),
            f"secondary should clarify non-third-party scope: {sec!r}",
        )
        self.assertTrue(
            "tunnel" in low or "extension" in low,
            f"secondary should name tunnel/extension: {sec!r}",
        )

    def test_copy_is_valid_helper_in_shipped_source(self) -> None:
        self.assertIn("static func copyIsValid", self.explainer)
        # Drive the same predicates copyIsValid encodes against extracted strings
        one = _swift_static_string(self.explainer, "oneLine")
        sec = _swift_static_string(self.explainer, "secondaryLine")
        for m in ("allow", "tunnel", "node"):
            self.assertIn(m, one.lower())
        self.assertNotIn("scan", one.lower())
        sec_l = sec.lower()
        self.assertTrue(
            "tunnel" in sec_l or "extension" in sec_l or "not" in sec_l
        )

    def test_show_once_gate_uses_seen_key(self) -> None:
        key = _swift_static_string(self.explainer, "seenKey")
        self.assertEqual(key, "rpt_app_group_access_explainer_seen")
        self.assertIn("shouldShow", self.explainer)
        self.assertIn("markShown", self.explainer)
        self.assertIn("bool(forKey: seenKey)", self.explainer)
        self.assertIn("set(true, forKey: seenKey)", self.explainer)

    def test_register_presents_explainer_before_app_group_seed(self) -> None:
        body = _register_body(self.channel)
        present_i = body.find("RptAppGroupAccessExplainer.presentIfNeeded")
        seed_i = body.find("seedAppGroupFromKnownSourcesIfNeeded")
        self.assertGreaterEqual(present_i, 0, "presentIfNeeded must be in register()")
        self.assertGreaterEqual(seed_i, 0, "seedAppGroup must remain in register()")
        self.assertLess(
            present_i,
            seed_i,
            "product explainer must run before App Group seed",
        )

    def test_pbxproj_compiles_explainer_on_runner(self) -> None:
        pbx = PBX.read_text(encoding="utf-8")
        self.assertIn("RptAppGroupAccessExplainer.swift", pbx)
        self.assertIn("RptAppGroupAccessExplainer.swift in Sources", pbx)

    def test_analysis_doc_notes_product_cannot_rewrite_os_dialog(self) -> None:
        text = DOC.read_text(encoding="utf-8").lower()
        self.assertIn("cannot change", text)
        self.assertIn("rptappgroupaccessexplainer", text.replace(" ", "").replace("_", "").replace("`", ""))
        # softer: product explainer name present
        self.assertIn("explainer", text)


if __name__ == "__main__":
    unittest.main()

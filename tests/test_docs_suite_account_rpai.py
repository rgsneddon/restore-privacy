"""Docs must describe optional Suite sign-up/sign-in and rpAI (Ned) as shipped.

Drives real documentation files and shipped string constants from
``client_app/lib/suite_account.dart`` and ``suite_ned_guide.dart``.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PRIMARY_DOCS = [
    "docs/SUITE_ACCOUNT_AND_RPAI.md",
    "client_app/SUITE.md",
    "client_app/README.md",
    "README.md",
    "docs/SUITE_FREE_DOWNLOAD.md",
]

ACCOUNT_SRC = "client_app/lib/suite_account.dart"
NED_SRC = "client_app/lib/suite_ned_guide.dart"


def _read(rel: str) -> str:
    p = ROOT / rel
    assert p.is_file(), f"missing {rel}"
    return p.read_text(encoding="utf-8")


def _dart_string_const(src: str, name: str) -> str:
    """Extract Dart ``const String name = '…';`` (possibly adjacent string parts)."""
    m = re.search(
        rf"const String {re.escape(name)}\s*=\s*((?:'[^']*'\s*)+);",
        src,
        re.S,
    )
    if not m:
        raise AssertionError(f"const String {name} not found")
    parts = re.findall(r"'((?:\\'|[^'])*)'", m.group(1))
    return "".join(p.replace("\\'", "'") for p in parts)


class TestDocsSuiteAccountAndRpai(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.account_src = _read(ACCOUNT_SRC)
        cls.ned_src = _read(NED_SRC)
        cls.docs = {rel: _read(rel) for rel in PRIMARY_DOCS}
        cls.blob = "\n".join(cls.docs.values())
        cls.blob_low = cls.blob.lower()

    def test_primary_docs_exist(self) -> None:
        for rel in PRIMARY_DOCS:
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_optional_suite_account_and_defer(self) -> None:
        self.assertIn("optional", self.blob_low)
        self.assertIn("keygen", self.blob_low)
        self.assertIn("evolve", self.blob_low)
        self.assertTrue(
            "suite account" in self.blob_low or "register for % wallet" in self.blob_low
        )
        self.assertTrue("not now" in self.blob_low or "defer" in self.blob_low)
        self.assertTrue("vpn only" in self.blob_low or "use vpn" in self.blob_low)

    def test_connect_independent_of_suite_account(self) -> None:
        independent = (
            "never gated" in self.blob_low
            or "not gated" in self.blob_low
            or "never consult" in self.blob_low
            or "independent" in self.blob_low
            or "never gates connect" in self.blob_low
            or "not required for residual" in self.blob_low
        )
        self.assertTrue(
            independent,
            "docs must state Connect is independent of Suite account",
        )
        forbidden = [
            r"must register.*(connect|vpn)",
            r"required.*suite account.*connect",
            r"connect requires.*(wallet|evolve|suite account) (register|sign)",
        ]
        for pat in forbidden:
            self.assertIsNone(
                re.search(pat, self.blob_low),
                f"forbidden primary-doc pattern: {pat}",
            )

    def test_rpai_ned_resume_howto_vpn_tour(self) -> None:
        self.assertTrue("rpai" in self.blob_low or "ned" in self.blob_low)
        self.assertTrue(
            "continue wallet" in self.blob_low or "resume" in self.blob_low
        )
        self.assertTrue(
            "how-to" in self.blob_low
            or "howto" in self.blob_low
            or "offer how-to" in self.blob_low
        )
        self.assertTrue(
            "Continue…" in self.blob or "continue…" in self.blob_low
        )
        self.assertTrue(
            "vpn tour" in self.blob_low or "tour of the vpn" in self.blob_low
        )

    def test_docs_match_shipped_suite_account_prompt_copy(self) -> None:
        title = _dart_string_const(self.account_src, "kSuiteAccountPromptTitle")
        defer = _dart_string_const(self.account_src, "kSuiteAccountDeferLabel")
        body = _dart_string_const(self.account_src, "kSuiteAccountPromptBody")
        self.assertIn(title, self.blob)
        self.assertIn(defer, self.blob)
        self.assertIn("Optionally create one account", body)
        self.assertIn("not required for residual", body.lower())
        self.assertTrue(
            "Optionally create one account" in self.blob
            or "optional" in self.blob_low
        )

    def test_docs_match_shipped_ned_questions(self) -> None:
        ask_setup = _dart_string_const(self.ned_src, "kNedAskContinueSetup")
        ask_vpn = _dart_string_const(self.ned_src, "kNedAskVpnTour")
        resume = _dart_string_const(self.ned_src, "kNedResumeSetupLabel")
        offer = _dart_string_const(self.ned_src, "kNedOfferHowToLabel")
        cont = _dart_string_const(self.ned_src, "kNedContinueLabel")

        self.assertIn(resume, self.blob)
        self.assertIn(offer, self.blob)
        self.assertIn(cont, self.blob)

        guide = self.docs["docs/SUITE_ACCOUNT_AND_RPAI.md"]
        self.assertIn(ask_setup, guide)
        self.assertIn(ask_vpn, guide)

    def test_no_dual_register_wall_invention(self) -> None:
        self.assertNotIn("dual register wall", self.blob_low)
        unified = (
            "one identity" in self.blob_low
            or "one suite account" in self.blob_low
            or "one account" in self.blob_low
            or "unified" in self.blob_low
        )
        self.assertTrue(unified, "docs should describe one unified Suite identity")
        # Explicit no-second-wall language in dedicated guide
        guide = self.docs["docs/SUITE_ACCOUNT_AND_RPAI.md"].lower()
        self.assertTrue(
            "no" in guide and "second" in guide and "register" in guide
            or "not a parallel" in guide
            or "same" in guide and "unified" in guide
        )

    def test_suite_account_source_vpn_independence(self) -> None:
        self.assertIn("mayConnect", self.account_src)
        self.assertIn("suiteAccountBlocksVpnConnect", self.account_src)
        self.assertTrue(
            "Independent of VPN" in self.account_src
            or "never" in self.account_src.lower()
        )

    def test_public_readme_mirrors_root(self) -> None:
        # Existing project invariant (see test_docs_parts_added).
        root = _read("README.md")
        pub = _read("status_page/public/README.md")
        self.assertEqual(root, pub)


if __name__ == "__main__":
    unittest.main()

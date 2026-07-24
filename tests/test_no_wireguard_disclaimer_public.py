"""Public site copy must not disclaim “not WireGuard / OpenVPN”."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

# Marketing-style competitor disclaimers (case-insensitive).
_DISCLAIMER = re.compile(
    r"(?is)"
    r"(not\s+(?:wireguard|openvpn)\b)"
    r"|(not\s+the\s+wireguard\s+protocol)"
    r"|(wireguard\s*/\s*openvpn)"
    r"|(wireguard\s+or\s+openvpn)"
    r"|(not\s+wireguard,\s*openvpn)"
    r"|(pre-existing\s+vpn\s+product)"
)


class TestNoWireGuardOpenVpnDisclaimerPublic(unittest.TestCase):
    def test_public_markdown_mirrors_have_no_disclaimer(self) -> None:
        pub = ROOT / "status_page" / "public"
        # LICENSE intentionally excluded (architecture legal language may remain).
        for name in (
            "README.md",
            "PRIVACY_POLICY.md",
            "CREDITS.md",
            "AUDIT.md",
        ):
            path = pub / name
            self.assertTrue(path.is_file(), f"missing {path}")
            text = path.read_text(encoding="utf-8")
            m = _DISCLAIMER.search(text)
            self.assertIsNone(
                m,
                msg=f"{name} still has disclaimer near: {m.group(0)!r}" if m else "",
            )

    def test_root_public_doc_mirrors_match_and_clean(self) -> None:
        for name in ("PRIVACY_POLICY.md", "CREDITS.md", "README.md"):
            root = ROOT / name
            pub = ROOT / "status_page" / "public" / name
            if not root.is_file() or not pub.is_file():
                continue
            rt = root.read_text(encoding="utf-8")
            pt = pub.read_text(encoding="utf-8")
            self.assertEqual(rt, pt, f"{name} root/public mirror drift")
            self.assertIsNone(_DISCLAIMER.search(rt), f"root {name} still has disclaimer")

    def test_rendered_privacy_and_credits_html_clean(self) -> None:
        import public_docs

        for path in ("/PRIVACY_POLICY.md", "/CREDITS.md", "/README.md"):
            got = public_docs.document_bytes_for_path(path)
            self.assertIsNotNone(got, path)
            assert got is not None
            html = got[0].decode("utf-8", errors="replace")
            m = _DISCLAIMER.search(html)
            self.assertIsNone(
                m,
                msg=f"rendered {path} disclaimer: {m.group(0)!r}" if m else "",
            )


if __name__ == "__main__":
    unittest.main()

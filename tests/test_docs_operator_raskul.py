"""Doc surfaces credit Raskul; no operator person-name leftovers (shipped markdown)."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Person/operator name forms that must not appear in product documentation.
_BANNED = re.compile(
    r"Russell\s+G\.?\s+Sneddon|Russell\s+Gray\s+Sneddon|Russell\s+Sneddon|"
    r"\bRussell\b|\bSneddon\b",
    re.IGNORECASE,
)

# Markdown doc roots in scope (not generated dist/build trees).
_DOC_GLOBS = (
    "README.md",
    "PRIVACY_POLICY.md",
    "CREDITS.md",
    "LICENSE",
    "AUDIT.md",
    "docs/**/*.md",
    "status_page/public/**/*.md",
    "client/**/*.md",
    "client_app/**/*.md",
    "browser_extension/**/*.md",
)

# Certificate Common Name literals (Apple signing) — not operator display prose.
_CERT_CN_ALLOW = "Developer ID Application: Russell Sneddon (SFCBP95595)"
_CERT_CN_ALLOW_2 = "Apple Development: Russell Sneddon"
_CERT_CN_ALLOW_3 = "Apple Distribution: Russell Sneddon"


def _iter_doc_files() -> list[Path]:
    out: list[Path] = []
    for pattern in _DOC_GLOBS:
        out.extend(ROOT.glob(pattern))
    # de-dupe, skip vendor-ish paths
    seen: set[Path] = set()
    files: list[Path] = []
    for p in out:
        if not p.is_file():
            continue
        s = str(p).replace("\\", "/")
        if any(x in s for x in ("/dist/", "/build/", "/.venv/", "/node_modules/")):
            continue
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            files.append(p)
    return files


class TestDocsOperatorRaskul(unittest.TestCase):
    def test_public_and_root_credit_raskul(self):
        for rel in (
            "README.md",
            "CREDITS.md",
            "PRIVACY_POLICY.md",
            "LICENSE",
            "status_page/public/README.md",
            "status_page/public/CREDITS.md",
            "status_page/public/PRIVACY_POLICY.md",
        ):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("Raskul", text, rel)
            # Full banned operator strings must not appear
            self.assertNotIn("Russell G Sneddon", text, rel)
            self.assertNotIn("Russell Gray Sneddon", text, rel)

    def test_doc_surfaces_no_operator_person_names(self):
        """Grep-like: markdown docs have no bare Russell/Sneddon person attribution.

        Apple certificate CN lines may still contain the legal name — allow only
        known codesign identity prefixes (not free-form prose).
        """
        offenders: list[str] = []
        for path in _iter_doc_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(text.splitlines(), 1):
                if not _BANNED.search(line):
                    continue
                # Allow certificate identity documentation only
                if (
                    _CERT_CN_ALLOW in line
                    or _CERT_CN_ALLOW_2 in line
                    or _CERT_CN_ALLOW_3 in line
                    or "certificate Common Name" in line
                    or "codesign literal" in line
                ):
                    # Still require Raskul nearby if this is BUILD_ON_MAC style
                    continue
                # assertNotIn in tests themselves is fine
                if "assertNotIn" in line or "assertIn" in line:
                    continue
                rel = path.relative_to(ROOT).as_posix()
                offenders.append(f"{rel}:{i}:{line.strip()[:120]}")
        self.assertEqual(
            offenders,
            [],
            "Banned operator person names remain in docs:\n" + "\n".join(offenders),
        )

    def test_readme_multi_peer_currency(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("167.233.224.5", text)
        self.assertIn("Germany", text)
        self.assertIn("Raskul", text)
        pub = (ROOT / "status_page" / "public" / "README.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("167.233.224.5", pub)
        self.assertIn("Raskul", pub)


if __name__ == "__main__":
    unittest.main()

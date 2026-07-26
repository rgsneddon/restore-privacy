"""Package AUDIT STATE (Green/Amber/Red) from the security audit writer."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def _load_audit_mod():
    spec = importlib.util.spec_from_file_location(
        "run_security_audit", ROOT / "scripts" / "run_security_audit.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class TestPackageRagEvaluation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_audit_mod()

    def test_missing_package_is_red(self):
        out = self.mod.evaluate_package_audit_state(
            "windows", None, pin="abc"
        )
        self.assertEqual(out["state"], "Red")
        why = " ".join(out["reasons"]).lower()
        # Architecture: missing monopin asset under releases/assets (honest Red)
        self.assertTrue(
            "not staged" in why
            or "not found" in why
            or "missing" in why
            or "looked for" in why,
            f"expected missing-asset reason, got: {why}",
        )
        self.assertTrue(
            "releases/" in why or "status_page/assets" in why or "assets/" in why,
            f"reason should cite package search paths: {why}",
        )
        self.assertIn("relative_path", why)

    def test_catalog_filenames_match_downloads_monopin(self):
        """Package RAG must use same basenames as downloads catalog list."""
        ver = self.mod.load_catalog_version()
        pin = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(ver, pin)
        self.assertEqual(ver, "0.4.7")
        rows = self.mod.catalog_platform_filenames(ver)
        self.assertEqual(len(rows), 5)
        # Prefer status_page.downloads when importable
        import sys

        sp = str(ROOT / "status_page")
        if sp not in sys.path:
            sys.path.insert(0, sp)
        from downloads import list_catalog_platform_packages  # type: ignore

        cat = {p["platform"]: p for p in list_catalog_platform_packages(version=ver)}
        for plat, _lab, fname, rel in rows:
            self.assertIn(plat, cat)
            self.assertEqual(fname, cat[plat]["filename"])
            self.assertEqual(rel, cat[plat]["relative_path"])
            self.assertTrue(rel.startswith(f"{ver}/"))
            self.assertTrue(fname.startswith(f"restore-privacy-client-{ver}-"))

    def test_search_dirs_align_with_fulfilment_roots(self):
        """Search roots include status assets, releases, and VPS paid_assets monopin."""
        ver = self.mod.load_catalog_version()
        dirs = self.mod.catalog_asset_search_dirs(ver)
        as_posix = [str(d).replace("\\", "/") for d in dirs]
        joined = " | ".join(as_posix)
        self.assertTrue(
            any(f"status_page/assets/{ver}" in p or f"assets\\{ver}" in p or p.endswith(f"assets/{ver}") for p in as_posix)
            or any(p.endswith(f"assets/{ver}") or p.endswith(f"assets\\{ver}") for p in as_posix),
            f"missing status assets root: {joined}",
        )
        self.assertTrue(
            any(f"releases/{ver}" in p or p.endswith(f"releases/{ver}") or p.endswith(f"releases\\{ver}") for p in as_posix),
            f"missing releases root: {joined}",
        )
        self.assertTrue(
            any("paid_assets" in p for p in as_posix),
            f"missing VPS paid_assets root: {joined}",
        )
        # Display reasons use monopin path text
        disp = self.mod.catalog_search_roots_display(ver)
        self.assertTrue(any(ver in d for d in disp))

    def test_resolve_finds_staged_windows_via_catalog_relative_path(self):
        """Present status_page/assets or releases package is not false-missing."""
        ver = self.mod.load_catalog_version()
        fname = f"restore-privacy-client-{ver}-windows-x64-setup.exe"
        rel = f"{ver}/{fname}"
        path = self.mod.resolve_catalog_package_path(ver, fname, relative_path=rel)
        if path is None:
            self.skipTest(f"Windows {ver} setup not staged under releases/assets")
        self.assertIsNotNone(
            path,
            f"Windows {ver} setup must resolve from catalog fulfilment paths",
        )
        assert path is not None
        self.assertTrue(path.is_file())
        self.assertEqual(path.name, fname)
        # Honest state: not Red-for-missing
        pin = self.mod.product_node_pub_pin()
        st = self.mod.evaluate_package_audit_state(
            "windows", path, pin=pin, expected_filename=fname
        )
        self.assertIn(st["state"], ("Green", "Amber"))
        self.assertNotIn("not staged", " ".join(st["reasons"]).lower())

    def test_entry_pub_matcher_excludes_exit_pub_name(self):
        """exit_node_elgamal.pub must not be treated as entry pin."""
        self.assertTrue(self.mod._is_entry_node_pub_member("secrets/node_elgamal.pub"))
        self.assertFalse(
            self.mod._is_entry_node_pub_member("secrets/exit_node_elgamal.pub")
        )
        self.assertFalse(
            self.mod._is_entry_node_pub_member("product/exit_node_elgamal.pub")
        )

    def test_catalog_036_all_platforms_green_when_staged(self):
        """When monopin assets are fully staged, none may be Red-for-missing.

        Apple/Linux/Android must be Green. Windows may be Amber when the PE is a
        carry-forward rename without multihop residual markers (honest RAG).
        """
        ver = self.mod.load_catalog_version()
        pin = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(ver, pin)
        rag = self.mod.evaluate_catalog_packages(ver)
        if int(rag.get("staged_count") or 0) < 5:
            self.skipTest(
                f"catalog {ver} packages not fully staged "
                f"(staged_count={rag.get('staged_count')})"
            )
        self.assertEqual(
            rag.get("staged_count"),
            5,
            f"expected five staged packages, got {rag.get('staged_count')}: {rag['packages']}",
        )
        by_plat = {p["platform"]: p for p in rag["packages"]}
        for plat in ("macos", "ios", "linux", "android"):
            p = by_plat[plat]
            self.assertTrue(p.get("path"), f"{plat} missing path")
            self.assertEqual(
                p.get("state"),
                "Green",
                f"{plat} not Green: {p.get('reasons')}",
            )
        win = by_plat["windows"]
        self.assertTrue(win.get("path"), "windows missing path")
        self.assertIn(
            win.get("state"),
            ("Green", "Amber"),
            f"windows unexpected state: {win.get('state')} {win.get('reasons')}",
        )
        self.assertNotEqual(rag["overall"], "Red")

    def test_valid_states_only(self):
        for s in ("Green", "Amber", "Red"):
            self.assertIn(s, self.mod.VALID_PACKAGE_STATES)

    def test_evaluate_catalog_has_five_platforms(self):
        """Drive real catalog monopin packages when present under releases/."""
        ver = self.mod.load_catalog_version()
        rag = self.mod.evaluate_catalog_packages(ver)
        self.assertEqual(rag.get("catalog_version"), ver)
        plats = {p["platform"] for p in rag["packages"]}
        self.assertEqual(
            plats, {"windows", "linux", "macos", "ios", "android"}
        )
        for p in rag["packages"]:
            self.assertIn(p["state"], self.mod.VALID_PACKAGE_STATES)
            self.assertIn("relative_path", p)
            self.assertTrue(str(p["relative_path"]).startswith(f"{ver}/"))
            # Missing rows must cite monopin search roots (not a wrong version path)
            if p.get("path") is None:
                why = " ".join(p.get("reasons") or []).lower()
                self.assertIn(ver, why)
                self.assertIn("relative_path", why)
        self.assertIn(rag["overall"], self.mod.VALID_PACKAGE_STATES)
        # packages may be absent on clones (gitignored assets/releases)
        present = sum(1 for p in rag["packages"] if p.get("path"))
        if present < 1:
            self.skipTest(f"no staged packages for catalog {ver}")
        self.assertGreaterEqual(present, 1)
        # Windows when staged must not be Red-for-missing
        win = next(p for p in rag["packages"] if p["platform"] == "windows")
        if win.get("path"):
            self.assertIn(win["state"], ("Green", "Amber"))

    def test_render_section_lists_all_platforms(self):
        rag = {
            "catalog_version": "0.4.0",
            "overall": "Green",
            "packages": [
                {
                    "platform": "windows",
                    "label": "Windows",
                    "filename": "w.exe",
                    "state": "Green",
                    "reasons": ["ok"],
                },
                {
                    "platform": "linux",
                    "label": "Linux",
                    "filename": "l.tgz",
                    "state": "Green",
                    "reasons": ["ok"],
                },
                {
                    "platform": "macos",
                    "label": "macOS",
                    "filename": "m.zip",
                    "state": "Amber",
                    "reasons": ["soft"],
                },
                {
                    "platform": "ios",
                    "label": "iOS",
                    "filename": "i.zip",
                    "state": "Green",
                    "reasons": ["ok"],
                },
                {
                    "platform": "android",
                    "label": "Android",
                    "filename": "a.apk",
                    "state": "Red",
                    "reasons": ["fail"],
                },
            ],
            "legend": {
                "Green": "g",
                "Amber": "a",
                "Red": "r",
            },
        }
        md = self.mod.render_package_rag_section(rag)
        self.assertIn("Installer package AUDIT STATE", md)
        # Table column heading is STATE (not AUDIT STATE)
        self.assertIn("| Platform | Package | STATE | Notes |", md)
        self.assertNotIn("| Platform | Package | AUDIT STATE | Notes |", md)
        for label in ("Windows", "Linux", "macOS", "iOS", "Android"):
            self.assertIn(label, md)
        # Platform column: distinct OS-relative icons with labels
        labels = {
            "windows": "Windows",
            "linux": "Linux",
            "macos": "macOS",
            "ios": "iOS",
            "android": "Android",
        }
        for plat, icon in self.mod.PLATFORM_ICONS.items():
            self.assertIn(icon, md, msg=plat)
            cell = self.mod.package_platform_cell_markup(plat, labels[plat])
            self.assertIn(icon, cell)
            self.assertIn(labels[plat], cell)
        self.assertIn("🪟", md)
        self.assertIn("🐧", md)
        self.assertIn("🍎", md)
        self.assertIn("📱", md)
        self.assertIn("🤖", md)
        # State column uses solid colour swatches, not bare **Green**/**Amber**/**Red** cells
        green = self.mod.package_state_cell_markup("Green")
        amber = self.mod.package_state_cell_markup("Amber")
        red = self.mod.package_state_cell_markup("Red")
        self.assertEqual(green, "🟩")
        self.assertEqual(amber, "🟧")
        self.assertEqual(red, "🟥")
        self.assertIn(green, md)
        self.assertIn(amber, md)
        self.assertIn(red, md)
        # Package data rows must not use bold state words as the AUDIT STATE cell
        self.assertNotRegex(md, r"\| \*\*Green\*\* \|")
        self.assertNotRegex(md, r"\| \*\*Amber\*\* \|")
        self.assertNotRegex(md, r"\| \*\*Red\*\* \|")
        self.assertIn("Catalog overall", md)
        self.assertIn("solid colour", md.lower())
        self.assertIn("inside the cell", md.lower())

    def test_priv_hit_is_red(self):
        # Synthetic: mock contains_priv
        with mock.patch.object(self.mod, "_package_contains_priv", return_value=True):
            with mock.patch.object(
                self.mod, "_package_node_pub_sha256", return_value="deadbeef" * 8
            ):
                p = ROOT / "releases" / self.mod.load_catalog_version()
                # any existing file path if present
                hits = list(p.glob("restore-privacy-client-*")) if p.is_dir() else []
                if not hits:
                    self.skipTest("no catalog packages on disk")
                out = self.mod.evaluate_package_audit_state(
                    "linux", hits[0], pin="aa" * 32
                )
        self.assertEqual(out["state"], "Red")
        self.assertTrue(any("priv" in r.lower() for r in out["reasons"]))


class TestAuditMdHasPackageRag(unittest.TestCase):
    def test_written_audit_has_top_package_states(self):
        audit = ROOT / "AUDIT.md"
        if not audit.is_file():
            self.skipTest("AUDIT.md missing")
        text = audit.read_text(encoding="utf-8")
        # After a --write pass this is required; if stale, still require structure
        # once goal has run write — test_runner will regenerate.
        if "Installer package AUDIT STATE" not in text:
            self.skipTest("AUDIT.md not yet regenerated with package RAG (run --write)")
        self.assertLess(
            text.index("Installer package AUDIT STATE"),
            text.index("## 1. Executive summary"),
        )
        for plat in ("Windows", "Linux", "macOS", "iOS", "Android"):
            self.assertIn(plat, text)
        # Solid colour indicators present; legend may still name colours in words
        self.assertTrue(
            "🟩" in text or "🟧" in text or "🟥" in text,
            "AUDIT package table should use solid colour swatches",
        )
        # Legend still explains meaning
        self.assertIn("Green", text)
        self.assertIn("Meaning", text)


class TestPkgRagCellScrollHtml(unittest.TestCase):
    """Status-host HTML: lengthy Package/Notes scroll in-cell, not page-widen."""

    def test_css_and_html_cell_scroll(self):
        import sys

        sys.path.insert(0, str(ROOT / "status_page"))
        from public_docs import DOC_SHELL_CSS, markdownish_to_html  # noqa: E402

        css = DOC_SHELL_CSS
        self.assertIn("cell-scroll", css)
        self.assertIn("overflow-x: auto", css)
        self.assertIn("table-layout: fixed", css)
        self.assertNotIn("width: max-content", css)
        long_name = "restore-privacy-client-0.4.0-windows-x64-setup.exe"
        md = self.mod.render_package_rag_section(
            {
                "catalog_version": "0.4.0",
                "overall": "Green",
                "packages": [
                    {
                        "platform": "windows",
                        "label": "Windows",
                        "filename": long_name,
                        "state": "Green",
                        "reasons": ["pin ok; lengthy note for scroll"],
                    }
                ],
                "legend": {"Green": "g", "Amber": "a", "Red": "r"},
            }
        )
        html = markdownish_to_html(md)
        self.assertIn("pkg-rag", html)
        self.assertIn("pkg-cell-scroll", html)
        self.assertIn("cell-scroll", html)
        self.assertIn(long_name, html)

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_audit_mod()


if __name__ == "__main__":
    unittest.main()

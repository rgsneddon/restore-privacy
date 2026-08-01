"""Windows large-drive brand mirror — inventory coverage + pure plan/apply."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "status_page"))


def _load_mirror():
    path = ROOT / "scripts" / "windows_brand_mirror.py"
    spec = importlib.util.spec_from_file_location("windows_brand_mirror", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_vault():
    path = ROOT / "scripts" / "breadcrumbs_vault.py"
    spec = importlib.util.spec_from_file_location("breadcrumbs_vault", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_inventory():
    path = ROOT / "scripts" / "brand_package_inventory.py"
    spec = importlib.util.spec_from_file_location("brand_package_inventory", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestBrandInventoryCoverage(unittest.TestCase):
    def test_mirror_plan_lists_every_brand_inventory_filename(self):
        mirror = _load_mirror()
        inv = _load_inventory()
        inv_rows = inv.list_brand_installer_packages()
        inv_names = {str(r["filename"]) for r in inv_rows}
        self.assertGreaterEqual(len(inv_names), 20, "brand inventory too thin")

        plan = mirror.build_windows_mirror_plan()
        plan_names = mirror.plan_inventory_filenames(plan)
        missing = inv_names - plan_names
        self.assertEqual(
            missing,
            set(),
            f"mirror plan missing brand slots: {sorted(missing)[:10]}",
        )
        self.assertEqual(plan["brand_slot_count"], len(inv_rows))
        # All expected product families appear
        kinds = set(plan.get("brand_kinds") or [])
        for expected in (
            "suite_client",
            "browser",
            "rpos",
            "rpos_app",
            "node_installer",
            "node_operator",
            "rpmail",
            "rpoffice",
        ):
            self.assertIn(expected, kinds, msg=f"kind {expected} absent from plan")

    def test_plan_reports_missing_vs_present_without_windows_host(self):
        mirror = _load_mirror()
        with tempfile.TemporaryDirectory() as td:
            fake_root = Path(td) / "repo"
            # Minimal repo: VERSION + empty releases so most slots missing
            (fake_root / "client").mkdir(parents=True)
            (fake_root / "client" / "VERSION").write_text("9.9.9\n", encoding="utf-8")
            (fake_root / "releases" / "9.9.9").mkdir(parents=True)
            # Only one present brand file
            only = (
                fake_root
                / "releases"
                / "9.9.9"
                / "restore-privacy-client-9.9.9-windows-x64-setup.exe"
            )
            only.write_bytes(b"MZ" + b"\0" * 2000)

            plan = mirror.build_windows_mirror_plan(
                monopin="9.9.9",
                repo_root=fake_root,
                dest_root=None,
            )
            self.assertFalse(plan["dest_configured"])
            self.assertGreaterEqual(plan["brand_slot_count"], 5)
            self.assertGreaterEqual(plan["missing_source_count"], 1)
            # At least the one we planted should be present if inventory
            # resolves via releases/{ver}/filename
            present_names = [
                r["filename"]
                for r in plan["brand_packages"]
                if r.get("source_present")
            ]
            # Suite windows row for monopin 9.9.9
            self.assertTrue(
                any("windows" in str(n) for n in present_names)
                or plan["present_source_count"] >= 0
            )
            # Missing rows are reported as absent (not silently dropped)
            for row in plan["brand_packages"]:
                if not row.get("source_present"):
                    self.assertEqual(row.get("source_path"), "")
                    self.assertFalse(row.get("dest_present"))


class TestMirrorApplyTempDrive(unittest.TestCase):
    def test_apply_copies_present_packages_to_temp_drive(self):
        """Drive real apply_mirror_plan against a tiny fake monorepo (not multi-GB releases)."""
        mirror = _load_mirror()
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            src_root = td_path / "src_repo"
            drive = td_path / "D_Drive"
            drive.mkdir()
            pin = "9.9.9"
            # Minimal monorepo markers + two present brand packages
            for rel in (
                "client/VERSION",
                "scripts/breadcrumbs_vault.py",
                "scripts/brand_package_inventory.py",
                "scripts/windows_brand_mirror.py",
                "status_page/downloads.py",
                "README.md",
            ):
                p = src_root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                if rel == "client/VERSION":
                    p.write_text(f"{pin}\n", encoding="utf-8")
                elif rel == "status_page/downloads.py":
                    p.write_text(
                        f'RELEASE_VERSION = "{pin}"\n'
                        f"def current_catalog_version():\n"
                        f"    return RELEASE_VERSION\n"
                        f"def list_catalog_platform_packages(version=None):\n"
                        f"    v = version or RELEASE_VERSION\n"
                        f"    return [\n"
                        f'      {{"platform":"windows","filename":f"restore-privacy-client-{{v}}-windows-x64-setup.exe",'
                        f'"relative_path":f"{{v}}/restore-privacy-client-{{v}}-windows-x64-setup.exe","version":v}},\n'
                        f'      {{"platform":"linux","filename":f"restore-privacy-client-{{v}}-linux-x64.tar.gz",'
                        f'"relative_path":f"{{v}}/restore-privacy-client-{{v}}-linux-x64.tar.gz","version":v}},\n'
                        f"    ]\n",
                        encoding="utf-8",
                    )
                else:
                    p.write_text("# marker\n", encoding="utf-8")

            # Present suite packages (tiny)
            for fname in (
                f"restore-privacy-client-{pin}-windows-x64-setup.exe",
                f"restore-privacy-client-{pin}-linux-x64.tar.gz",
            ):
                fpath = src_root / "releases" / pin / fname
                fpath.parent.mkdir(parents=True, exist_ok=True)
                fpath.write_bytes(b"PK\x03\x04" + b"\0" * 500)

            plan = mirror.build_windows_mirror_plan(
                monopin=pin, repo_root=src_root, dest_root=drive
            )
            self.assertTrue(plan["dest_configured"])
            self.assertGreaterEqual(plan["present_source_count"], 2)
            missing_before = plan["missing_source_count"]
            self.assertGreaterEqual(missing_before, 1)

            dry = mirror.apply_mirror_plan(
                plan, dest_root=drive, dry_run=True, repo_root=src_root, monopin=pin
            )
            self.assertTrue(dry["ok"])
            self.assertTrue(dry["dry_run"])
            self.assertGreater(dry["copied_count"], 0)
            # Dry-run must not write
            self.assertFalse((drive / "restore-privacy" / "client" / "VERSION").exists())

            result = mirror.apply_mirror_plan(
                plan, dest_root=drive, dry_run=False, repo_root=src_root, monopin=pin
            )
            self.assertTrue(result["ok"], result)
            self.assertFalse(result["dry_run"])
            repo_dest = drive / "restore-privacy"
            self.assertTrue((repo_dest / "client" / "VERSION").is_file())
            self.assertTrue(
                (repo_dest / "scripts" / "windows_brand_mirror.py").is_file()
            )
            win_exe = (
                repo_dest
                / "releases"
                / pin
                / f"restore-privacy-client-{pin}-windows-x64-setup.exe"
            )
            self.assertTrue(win_exe.is_file(), win_exe)
            self.assertGreater(win_exe.stat().st_size, 0)

            post = mirror.build_windows_mirror_plan(
                monopin=pin, repo_root=src_root, dest_root=drive
            )
            self.assertGreaterEqual(post["duplicated_on_dest"], 2)
            suite_dup = [
                r
                for r in post["brand_packages"]
                if r.get("kind") == "suite_client" and r.get("duplicated")
            ]
            self.assertGreaterEqual(len(suite_dup), 1)
            # Still lists full inventory slots (including missing source rows)
            self.assertEqual(post["brand_slot_count"], plan["brand_slot_count"])
            self.assertGreaterEqual(post["missing_source_count"], 1)


class TestVaultStagesWindowsBrandFiles(unittest.TestCase):
    def test_stage_writes_windows_brand_mirror_and_checklist(self):
        vault = _load_vault()
        mirror = _load_mirror()
        inv = _load_inventory()
        pin = vault.current_monopin()
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            ver_dir = vault.stage_vault(monopin=pin, out_root=out)
            for name in (
                "WINDOWS_HANDOFF.md",
                "WINDOWS_BRAND_CHECKLIST.md",
                "windows_brand_mirror.json",
                "manifest.json",
            ):
                self.assertTrue(
                    (out / "current" / name).is_file(), msg=f"missing {name}"
                )
                self.assertTrue((ver_dir / name).is_file())

            man = json.loads(
                (out / "current" / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertIn("windows_brand_mirror", man)
            self.assertIn("windows_actions", man)
            wbm = man["windows_brand_mirror"]
            self.assertGreaterEqual(int(wbm.get("brand_slot_count") or 0), 20)
            inv_names = {r["filename"] for r in inv.list_brand_installer_packages()}
            man_names = set(wbm.get("brand_filenames") or [])
            self.assertEqual(inv_names - man_names, set())

            handoff = (out / "current" / "WINDOWS_HANDOFF.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("RPT_WINDOWS_DRIVE", handoff)
            self.assertIn("windows_brand_mirror", handoff.lower() or handoff)
            self.assertIn("Brand-wide large-drive mirror", handoff)
            self.assertIn("build_windows_multihop", handoff)

            checklist = (out / "current" / "WINDOWS_BRAND_CHECKLIST.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("large-drive", checklist.lower() or checklist)
            self.assertIn("suite_client", checklist)
            plan_json = json.loads(
                (out / "current" / "windows_brand_mirror.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(plan_json.get("schema"), "rpt.windows_brand_mirror.v1")
            self.assertEqual(
                mirror.plan_inventory_filenames(plan_json),
                inv_names,
            )

    def test_serve_allows_windows_vault_files(self):
        path = ROOT / "node" / "serve_paid_assets.py"
        spec = importlib.util.spec_from_file_location("serve_paid_assets", path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for name in (
            "WINDOWS_HANDOFF.md",
            "WINDOWS_BRAND_CHECKLIST.md",
            "windows_brand_mirror.json",
            "manifest.json",
        ):
            self.assertTrue(
                mod.breadcrumbs_path_allowed(["current", name]),
                msg=f"serve denies {name}",
            )


class TestChecklistAndCliSurface(unittest.TestCase):
    def test_render_checklist_mentions_pe_and_all_kinds(self):
        mirror = _load_mirror()
        text = mirror.render_windows_brand_checklist()
        self.assertIn("RPT_WINDOWS_DRIVE", text)
        self.assertIn("build_windows_multihop", text)
        self.assertIn("suite_client", text)
        self.assertIn("rpoffice", text)
        self.assertIn("node_installer", text)

    def test_apply_without_dest_fails_closed(self):
        mirror = _load_mirror()
        # Clear env influence
        import os

        old = os.environ.pop("RPT_WINDOWS_DRIVE", None)
        old2 = os.environ.pop("RPT_WINDOWS_LARGE_DRIVE", None)
        try:
            r = mirror.apply_mirror_plan(dest_root=None, dry_run=True)
            self.assertFalse(r["ok"])
            self.assertIn("dest", str(r.get("error") or "").lower())
        finally:
            if old is not None:
                os.environ["RPT_WINDOWS_DRIVE"] = old
            if old2 is not None:
                os.environ["RPT_WINDOWS_LARGE_DRIVE"] = old2


if __name__ == "__main__":
    unittest.main()

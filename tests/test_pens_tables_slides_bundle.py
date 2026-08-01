"""Pens · Tables · Slides brand, desktop placement, Ned locked tour."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "rpos" / "apps"))
sys.path.insert(0, str(ROOT / "scripts"))


class TestBrandIdentity(unittest.TestCase):
    def test_rpoffice_brands_and_entries(self) -> None:
        from rpoffice.apps import pens, slides, tables
        from rpoffice.brand import PENS, SLIDES, TABLES, primary_app_names
        from rpoffice.parity_scope import OFFICE_PILLARS
        from rpoffice.shell import suite_status

        self.assertEqual(primary_app_names(), ["Pens", "Tables", "Slides"])
        self.assertEqual(OFFICE_PILLARS, ("Pens", "Tables", "Slides"))
        st = suite_status()
        self.assertEqual(st["brands"], ["Pens", "Tables", "Slides"])
        for bad in ("Word", "Excel", "PowerPoint"):
            self.assertNotIn(bad, st["brands"])
        p = pens.smoke()
        self.assertEqual(p["product"], PENS)
        self.assertGreaterEqual(p["paragraphs"], 1)
        t = tables.smoke()
        self.assertEqual(t["product"], TABLES)
        self.assertEqual(t["formula_A1_plus_B1"], 15.0)
        s = slides.smoke()
        self.assertEqual(s["product"], SLIDES)
        self.assertGreaterEqual(s["slide_count"], 2)
        self.assertEqual(pens.main(["--version"]), 0)
        self.assertEqual(tables.main(["--smoke"]), 0)
        self.assertEqual(slides.main(["--smoke"]), 0)


class TestDesktopPlacement(unittest.TestCase):
    def test_place_launchers_on_prefix_desktop(self) -> None:
        from rpos.installer.desktop import (
            assert_desktop_has_all_three,
            place_app_launchers,
            prefix_desktop_dir,
        )
        from rpos.installer.pipeline import RestorePipeline
        from rpos.installer.wipe_adapter import DryRunWipeAdapter

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            prefix = tdp / "install"
            user_desk = tdp / "UserDesktop"
            user_desk.mkdir()
            src = ROOT / "rpos"
            # Install with injected "user" desktop (simulates real Desktop)
            pipe = RestorePipeline(
                prefix=prefix, source_rpos=src, wipe=DryRunWipeAdapter()
            )
            # Run foundation then place with desktop_root override for test isolation
            r = pipe.run("RESTORE")
            self.assertTrue(r["proceeded"])
            # Always have prefix Desktop from install
            pdesk = prefix_desktop_dir(prefix)
            self.assertTrue(assert_desktop_has_all_three(pdesk))
            # Product path also stages to user desktop when provided
            place_app_launchers(
                prefix,
                desktop_root=user_desk,
                apps_root=prefix / "apps",
                also_user_desktop=False,
            )
            self.assertTrue(assert_desktop_has_all_three(user_desk))
            for brand in ("Pens", "Tables", "Slides"):
                launcher = user_desk / brand
                self.assertTrue(launcher.is_file(), brand)
                body = launcher.read_text(encoding="utf-8")
                self.assertIn("rpoffice.apps.", body)
            man = json.loads((prefix / "DESKTOP_APPS.json").read_text())
            self.assertEqual(man["brands"], ["Pens", "Tables", "Slides"])
            self.assertTrue(man.get("user_desktop") or man.get("prefix_desktop"))


class TestNedLockedTour(unittest.TestCase):
    def test_tour_order_and_unlock(self) -> None:
        from rpos.installer.ned_apps_tour import NedAppsTour, persist_tour
        from rpos.installer.pipeline import RestorePipeline
        from rpos.installer.wipe_adapter import DryRunWipeAdapter

        tour = NedAppsTour()
        self.assertTrue(tour.state.locked)
        self.assertFalse(tour.state.os_fully_unlocked)
        self.assertEqual(tour.state.current_app, "Pens")
        # Cannot unlock early
        tour.acknowledge_current()  # Pens done
        self.assertEqual(tour.state.completed, ["Pens"])
        self.assertTrue(tour.state.locked)
        self.assertEqual(tour.state.current_app, "Tables")
        tour.acknowledge_current()  # Tables
        self.assertEqual(tour.state.current_app, "Slides")
        self.assertFalse(tour.state.os_fully_unlocked)
        tour.acknowledge_current()  # Slides
        self.assertFalse(tour.state.locked)
        self.assertTrue(tour.state.os_fully_unlocked)
        self.assertEqual(tour.state.completed, ["Pens", "Tables", "Slides"])
        # Full auto tour
        with tempfile.TemporaryDirectory() as td:
            prefix = Path(td) / "p"
            RestorePipeline(
                prefix=prefix, source_rpos=ROOT / "rpos", wipe=DryRunWipeAdapter()
            ).run("RESTORE")
            t2 = NedAppsTour()
            res = t2.run_full_tour(auto=True, print_fn=lambda *_a, **_k: None)
            self.assertTrue(res["os_fully_unlocked"])
            self.assertEqual(res["completed"], ["Pens", "Tables", "Slides"])
            self.assertEqual(len(res["steps"]), 3)
            self.assertTrue(all("ned" in s and s["ned"] for s in res["steps"]))
            persist_tour(prefix, res)
            m = json.loads((prefix / "RPOS_INSTALLED.json").read_text())
            self.assertTrue(m["os_fully_unlocked"])
            self.assertEqual(m["apps_tour"], ["Pens", "Tables", "Slides"])


class TestPerAppPackages(unittest.TestCase):
    def test_package_pts_installers(self) -> None:
        import package_pts_apps as pts

        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            r = pts.package_all(out_dir=out)
            self.assertTrue(r["ok"], r)
            self.assertEqual(len(r["packages"]), 3)
            brands = {p["brand"] for p in r["packages"]}
            self.assertEqual(brands, {"Pens", "Tables", "Slides"})
            for p in r["packages"]:
                self.assertGreater(p["bytes"], 0)
                with zipfile.ZipFile(p["archive"]) as zf:
                    names = "\n".join(zf.namelist())
                    self.assertIn("install.sh", names)
                    self.assertIn("apps/rpoffice/", names)
                    install_name = next(n for n in zf.namelist() if n.endswith("install.sh"))
                    install_sh = zf.read(install_name).decode("utf-8")
                    # Real user Desktop default (not only prefix Desktop)
                    self.assertTrue(
                        "HOME/Desktop" in install_sh or "XDG_DESKTOP" in install_sh,
                        msg=f"{p['brand']} install.sh must default to user Desktop",
                    )
                    # Must not be PREFIX/Desktop-only default
                    self.assertNotIn(
                        'DESKTOP="${RPOS_DESKTOP:-$PREFIX/Desktop}"',
                        install_sh,
                    )
                    self.assertIn("PREFIX_DESKTOP", install_sh)

    def test_shipped_releases_rpos_apps_install_sh_user_desktop(self) -> None:
        """Shipped artifacts under releases/rpos-apps must match generator Desktop path."""
        rel = ROOT / "releases" / "rpos-apps" / "0.1.0"
        if not rel.is_dir():
            self.skipTest("releases/rpos-apps/0.1.0 not present")
        zips = sorted(rel.glob("*-0.1.0-installer.zip"))
        self.assertEqual(len(zips), 3, f"expected 3 installers in {rel}")
        for zpath in zips:
            with zipfile.ZipFile(zpath) as zf:
                install_name = next(n for n in zf.namelist() if n.endswith("install.sh"))
                text = zf.read(install_name).decode("utf-8")
                self.assertTrue(
                    "HOME/Desktop" in text or "XDG_DESKTOP" in text,
                    msg=f"{zpath.name} install.sh missing user Desktop default",
                )
                self.assertNotIn(
                    'DESKTOP="${RPOS_DESKTOP:-$PREFIX/Desktop}"',
                    text,
                )


class TestInstallerSmoke(unittest.TestCase):
    def test_full_smoke_includes_apps(self) -> None:
        from rpos.installer import __main__ as m

        self.assertEqual(m.main(["smoke"]), 0)
        self.assertEqual(m.main(["smoke"]), 0)


if __name__ == "__main__":
    unittest.main()

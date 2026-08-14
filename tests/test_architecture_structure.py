"""Planned multi-product architecture: inventory, trees, identity, honesty."""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "status_page"))


class TestArchitectureInventory(unittest.TestCase):
    def test_validate_architecture_ok_and_kinds(self) -> None:
        from architecture_inventory import (
            BRAND_PACKAGE_KINDS,
            SUITE_REQUIRED_PLATFORMS,
            architecture_summary_text,
            planned_programs,
            validate_architecture,
        )
        from brand_package_inventory import list_brand_installer_packages

        report = validate_architecture(repo_root=ROOT)
        self.assertTrue(report["ok"], msg=report.get("gaps"))
        self.assertEqual(report["gaps"], [])
        self.assertGreaterEqual(report["programs"], 8)
        self.assertGreaterEqual(report["brand_rows"], 5)

        # Every brand kind present with non-empty product/platform/path
        rows = list_brand_installer_packages(repo_root=ROOT)
        kinds = {r["kind"] for r in rows}
        for kind in BRAND_PACKAGE_KINDS:
            self.assertIn(kind, kinds, msg=kind)
        for r in rows:
            self.assertTrue(str(r["product"]).strip(), r)
            self.assertTrue(str(r["platform"]).strip(), r)
            rel = str(r["relative_path"])
            self.assertTrue(rel)
            self.assertNotIn("..", rel)
            self.assertFalse(rel.startswith("/"))

        suite = [r for r in rows if r["kind"] == "suite_client" and r["required"]]
        plats = {r["platform"] for r in suite}
        self.assertEqual(plats, set(SUITE_REQUIRED_PLATFORMS))

        # Structural homes exist
        for prog in planned_programs(repo_root=ROOT):
            for rel in prog["trees"]:
                self.assertTrue((ROOT / rel).exists(), msg=f"{prog['id']}:{rel}")
            entry = str(prog.get("package_entry") or "")
            if entry:
                self.assertTrue((ROOT / entry).is_file(), msg=entry)

        text = architecture_summary_text(repo_root=ROOT)
        self.assertIn("PLANNED ARCHITECTURE INVENTORY", text)
        self.assertIn("suite_client", text)
        self.assertIn("rpos", text)
        self.assertIn("ok=True", text)

    def test_desktop_only_not_mobile_rpos(self) -> None:
        from architecture_inventory import planned_programs

        by_id = {p["id"]: p for p in planned_programs()}
        self.assertTrue(by_id["rpos"]["desktop_only"])
        self.assertFalse(by_id["rpos"]["mobile_installable"])
        self.assertTrue(by_id["rpos_apps"]["desktop_only"])
        self.assertFalse(by_id["rpos"]["public_residual_dial"])


class TestSuiteStorefrontAndProductFamily(unittest.TestCase):
    def test_suite_free_download_five_platforms(self) -> None:
        from downloads import (
            RELEASE_VERSION,
            render_suite_storefront_html,
            suite_free_download_href,
        )

        suite = render_suite_storefront_html()
        for plat in ("windows", "android", "macos", "ios", "linux"):
            self.assertIn(suite_free_download_href(plat), suite)
            self.assertIn(f'data-platform="{plat}"', suite)
        self.assertIn(RELEASE_VERSION, suite)
        self.assertIn("KEYGEN", suite)

    def test_product_family_omits_vpn_shop_structure(self) -> None:
        from product_family import render_browser_page_html, render_vault_page_html

        for name, raw in (
            ("browser", render_browser_page_html()),
            ("vault", render_vault_page_html()),
        ):
            html = raw.decode("utf-8")
            self.assertIn("product-coming", html, msg=name)
            self.assertNotIn("suite-storefront", html, msg=name)
            self.assertNotIn("node-wipe", html, msg=name)
            self.assertNotIn("dl-buy-now", html, msg=name)
            self.assertNotIn("home-shop-row", html, msg=name)


class TestRposPipelineAndAdminArchitecture(unittest.TestCase):
    def test_rpos_pipeline_stages_and_hidden_enable(self) -> None:
        from rpos.installer.pipeline import RestorePipeline
        from rpos.installer.wipe_adapter import DryRunWipeAdapter
        from client.flyclient_hidden_node import stop_all_live_agents

        try:
            with tempfile.TemporaryDirectory() as td:
                pipe = RestorePipeline(
                    prefix=Path(td) / "root",
                    source_rpos=ROOT / "rpos",
                    wipe=DryRunWipeAdapter(),
                )
                r = pipe.run("RESTORE", skip_wipe=True)
                self.assertTrue(r["proceeded"])
                stages = r["stages"]
                self.assertIn("install_foundation", stages)
                self.assertIn("hidden_node_enable", stages)
                self.assertIn("complete", stages)
                self.assertTrue(r.get("hidden_node", {}).get("enabled"))
                self.assertFalse(r["hidden_node"].get("public_catalog"))
        finally:
            stop_all_live_agents()

    def test_admin_architecture_honesty_copy(self) -> None:
        from admin_panel import ADMIN_ARCHITECTURE_BLURB, ADMIN_ARCHITECTURE_FULL

        full = ADMIN_ARCHITECTURE_FULL.lower()
        blurb = ADMIN_ARCHITECTURE_BLURB.lower()
        blob = full + "\n" + blurb
        self.assertIn("free suite installer", full)
        self.assertIn("keygen", full)
        self.assertIn("germany", full)
        self.assertIn("iceland", full)
        self.assertIn("one at a time", full)  # IS → DE sequential wipe language
        self.assertRegex(full, r"iceland.*germany|is.*de|one at a time")
        # Honesty
        self.assertIn("not full onion", full)
        self.assertIn("foss", full)  # proprietary / not full FOSS
        self.assertIn("desktop-only", full)
        self.assertIn("no mobile", full)
        self.assertIn("flyclient", full)
        self.assertIn("never listed as public residual", full)
        self.assertIn("united states", full)
        self.assertIn("romania", full)
        self.assertIn("retired", full)
        # Brand structure present
        self.assertIn("rpos", full)
        self.assertIn("pens", full)
        self.assertIn("brand-wide", full)
        # Blurb still has free Suite + KEYGEN + peers
        self.assertIn("free", blurb)
        self.assertIn("keygen", blurb)


class TestPublicCatalogNotHidden(unittest.TestCase):
    def test_catalog_is_de_only_not_flyclient(self) -> None:
        from client.multihop import (
            PRODUCT_COUNTRY_CATALOG,
            product_country_catalog,
            public_catalog_hosts,
            public_dialable_peers,
        )
        from client.flyclient_hidden_node import synthetic_hidden_host

        codes = {n.code for n in product_country_catalog()}
        self.assertEqual(codes, {"DE"})
        self.assertNotIn("IS", codes)
        hosts = public_catalog_hosts()
        for n in PRODUCT_COUNTRY_CATALOG:
            self.assertIn(n.host, hosts)
        hid = synthetic_hidden_host(seed="arch")
        self.assertNotIn(hid, hosts)
        peers = public_dialable_peers(hidden_hosts=[hid])
        self.assertTrue(all(p.host != hid for p in peers))
        # Retired hosts not in live catalog
        retired = {"5.161.242.85", "185.146.232.107"}
        for h in retired:
            self.assertNotIn(h, hosts)


if __name__ == "__main__":
    unittest.main()

"""Multihop node-structure probes for the security audit timer path."""

from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from audit_multihop_structure import (  # noqa: E402
    EXPECTED_ENTRY_HOST,
    EXPECTED_EXIT_HOST,
    probe_multihop_module_flags,
    probe_multihop_product_pubs,
    probe_multihop_residual_via_exit,
    probe_multihop_node_host_layout,
    render_multihop_structure_markdown,
    run_all_multihop_structure_probes,
)


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "run_security_audit", ROOT / "scripts" / "run_security_audit.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class TestMultihopStructureProbes(unittest.TestCase):
    def test_module_flags_match_product_monopin(self):
        r = probe_multihop_module_flags(repo_root=ROOT, install_root=ROOT)
        self.assertFalse(r.get("skipped"), msg=r)
        self.assertTrue(r.get("ok"), msg=r)
        self.assertEqual(r.get("entry_host"), EXPECTED_ENTRY_HOST)
        self.assertEqual(r.get("exit_host"), EXPECTED_EXIT_HOST)
        self.assertTrue(r.get("routing_implemented"))

    def test_product_pubs_present_and_distinct(self):
        r = probe_multihop_product_pubs(repo_root=ROOT, install_root=ROOT)
        self.assertTrue(r.get("ok"), msg=r)
        self.assertIsNotNone(r.get("entry_pub"))
        self.assertIsNotNone(r.get("exit_pub"))
        entry = Path(r["entry_pub"]).read_bytes()
        exit_b = Path(r["exit_pub"]).read_bytes()
        self.assertNotEqual(entry, exit_b)

    def test_residual_via_exit_when_multihop_enabled(self):
        r = probe_multihop_residual_via_exit(repo_root=ROOT, install_root=ROOT)
        self.assertTrue(r.get("ok"), msg=r)
        joined = " ".join(r.get("reasons") or []).lower()
        self.assertIn("residual-via-exit", joined.replace(" ", "-") or joined)
        self.assertIn(EXPECTED_EXIT_HOST, " ".join(r.get("reasons") or []))

    def test_missing_exit_pub_fails(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            prod = tdp / "product"
            prod.mkdir()
            # only entry pub
            shutil.copy2(ROOT / "product" / "node_elgamal.pub", prod / "node_elgamal.pub")
            r = probe_multihop_product_pubs(repo_root=tdp, install_root=tdp)
            self.assertFalse(r.get("ok"), msg=r)
            self.assertTrue(
                any("exit" in str(x).lower() for x in r.get("reasons") or [])
            )

    def test_identical_entry_exit_pubs_fail(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            prod = tdp / "product"
            prod.mkdir()
            entry = (ROOT / "product" / "node_elgamal.pub").read_bytes()
            (prod / "node_elgamal.pub").write_bytes(entry)
            (prod / "exit_node_elgamal.pub").write_bytes(entry)
            r = probe_multihop_product_pubs(repo_root=tdp, install_root=tdp)
            self.assertFalse(r.get("ok"), msg=r)
            self.assertTrue(
                any("distinct" in str(x).lower() for x in r.get("reasons") or [])
            )

    def test_routing_flag_false_fails_module_probe(self):
        r = probe_multihop_module_flags(repo_root=ROOT, install_root=ROOT)
        self.assertTrue(r.get("ok"))
        with mock.patch(
            "client.multihop.MULTI_HOP_ROUTING_IMPLEMENTED",
            False,
            create=True,
        ):
            # Re-import path uses live module; drive residual probe with patched flag
            import client.multihop as mh

            old = mh.MULTI_HOP_ROUTING_IMPLEMENTED
            try:
                mh.MULTI_HOP_ROUTING_IMPLEMENTED = False
                r2 = probe_multihop_module_flags(repo_root=ROOT, install_root=ROOT)
                self.assertFalse(r2.get("ok"), msg=r2)
            finally:
                mh.MULTI_HOP_ROUTING_IMPLEMENTED = old

    def test_aggregate_and_markdown(self):
        agg = run_all_multihop_structure_probes(repo_root=ROOT, install_root=ROOT)
        self.assertTrue(agg.get("ok"), msg=agg)
        self.assertIn("multihop_module_flags", agg.get("probes") or {})
        self.assertIn("multihop_product_pubs", agg.get("probes") or {})
        self.assertIn("multihop_residual_via_exit", agg.get("probes") or {})
        md = render_multihop_structure_markdown(agg)
        self.assertIn("Multihop node structure", md)
        self.assertIn("Multihop structure overall", md)
        self.assertIn(EXPECTED_ENTRY_HOST, md)
        self.assertIn(EXPECTED_EXIT_HOST, md)
        self.assertIn("residual-via-exit", md.lower().replace(" ", "-") or md.lower())
        self.assertIn("**PASS**", md)

    def test_node_host_layout_finds_zram_recipe(self):
        r = probe_multihop_node_host_layout(repo_root=ROOT, install_root=ROOT)
        # Monorepo has install_zram_luks.sh
        self.assertFalse(r.get("skipped"), msg=r)
        self.assertTrue(r.get("ok"), msg=r)

    def test_runner_wires_multihop_section(self):
        mod = _load_runner()
        text = (ROOT / "scripts" / "run_security_audit.py").read_text(encoding="utf-8")
        self.assertIn("run_multihop_structure_probes", text)
        self.assertIn("multihop_structure", text)
        self.assertIn("audit_multihop_structure", text)
        # collect includes key
        results = {
            "generated_at": "2026-07-22T00:00:00Z",
            "node_host": "127.0.0.1",
            "catalog_version": "0.3.7",
            "unit_suite": {"ran": False, "ok": True, "reason": "skipped"},
            "tcp_status": {"ok": True},
            "http_status": {
                "ok": True,
                "status_code": 200,
                "body": {"title": "RESTORE PRIVACY"},
            },
            "udp": {"sent": True},
            "no_priv": {"ok": True, "hits": []},
            "package_rag": {
                "catalog_version": "0.3.7",
                "overall": "Green",
                "packages": [],
                "legend": {"Green": "OK", "Amber": "A", "Red": "R"},
            },
            "section_b": {"ok": True, "probes": {}},
            "multihop_structure": run_all_multihop_structure_probes(
                repo_root=ROOT, install_root=ROOT
            ),
        }
        md = mod.build_markdown(results)
        self.assertIn("Multihop node structure", md)
        self.assertIn("multihop_module_flags", md)
        self.assertIn(EXPECTED_EXIT_HOST, md)

    def test_timer_install_seeds_multihop_module(self):
        text = (
            ROOT / "scripts" / "install_security_audit_timer.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("audit_multihop_structure.py", text)
        self.assertIn("client/multihop.py", text)
        self.assertIn("client/endpoint.py", text)
        self.assertIn("run_security_audit.py", text)
        self.assertIn("4h", text)


if __name__ == "__main__":
    unittest.main()

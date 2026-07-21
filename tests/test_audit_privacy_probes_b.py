"""Section B privacy probes for the security audit timer (no firewall scan)."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from audit_privacy_probes import (  # noqa: E402
    probe_disk_wipe_readiness,
    probe_ephemeral_dry_run,
    probe_host_privacy_drift,
    probe_kill_switch_default_off,
    probe_nolog_journald,
    probe_no_priv_public_trees,
    probe_title_only_status,
    render_section_b_markdown,
    run_all_section_b_probes,
)


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "run_security_audit", ROOT / "scripts" / "run_security_audit.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class TestSectionBProbes(unittest.TestCase):
    def test_nolog_policy_and_fixture_unit(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            unit = tdp / "rpt-node.service"
            unit.write_text(
                "[Service]\nStandardOutput=null\nStandardError=null\n",
                encoding="utf-8",
            )
            cfg = tdp / "rpt-node.json"
            cfg.write_text(
                '{"logging": {"logging_enabled": false, "connection_log": false, '
                '"session_log": false, "access_log": false, "traffic_log": false, '
                '"accounting_log": false, "peer_activity_log": false, '
                '"user_info_log": false, "verbose": false, "log_file": null, '
                '"log_path": null, "journal": false}, "collect_user_data": false}\n',
                encoding="utf-8",
            )
            r = probe_nolog_journald(
                install_root=tdp,
                unit_path=unit,
                config_json=cfg,
                repo_root=ROOT,
            )
            self.assertTrue(r["ok"], msg=r)
            self.assertFalse(r["warn"])

            bad_unit = tdp / "bad.service"
            bad_unit.write_text(
                "[Service]\nStandardOutput=journal\n", encoding="utf-8"
            )
            r2 = probe_nolog_journald(
                install_root=tdp,
                unit_path=bad_unit,
                config_json=cfg,
                repo_root=ROOT,
            )
            self.assertTrue(r2["warn"] or not r2["ok"])

    def test_no_priv_detects_fixture_hit(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            pub = tdp / "status_page" / "static"
            pub.mkdir(parents=True)
            evil = pub / "leak.priv"
            evil.write_bytes(b"\x00" * 32)
            r = probe_no_priv_public_trees(
                repo_root=tdp,
                install_root=tdp / "missing-install",
                extra_roots=[pub],
            )
            self.assertFalse(r["ok"])
            self.assertTrue(any("leak.priv" in h for h in r.get("hits") or []))

    def test_kill_switch_default_off(self):
        r = probe_kill_switch_default_off(env={}, repo_root=ROOT)
        self.assertTrue(r["ok"])
        self.assertFalse(r.get("operator_opt_in"))
        r2 = probe_kill_switch_default_off(
            env={"RPT_KILL_SWITCH": "1"}, repo_root=ROOT
        )
        self.assertTrue(r2["ok"])
        self.assertTrue(r2.get("warn"))
        self.assertTrue(r2.get("operator_opt_in"))

    def test_title_only_status(self):
        ok = probe_title_only_status(
            {"ok": True, "body": {"title": "RESTORE PRIVACY"}}
        )
        self.assertTrue(ok["ok"])
        self.assertTrue(ok["title_only"])
        bad = probe_title_only_status(
            {"ok": True, "body": {"title": "X", "clients_connected": 3}}
        )
        self.assertFalse(bad["ok"])

    def test_host_privacy_unit_without_dropin_warns(self):
        """Node unit present + missing 99-rpt-privacy.conf ⇒ WARN (not false PASS)."""
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            unit = tdp / "rpt-node.service"
            unit.write_text(
                "[Service]\nStandardOutput=null\nStandardError=null\n",
                encoding="utf-8",
            )
            missing_dropin = tdp / "no-such-dropin.conf"
            # Recipe may exist under ROOT — must not force PASS without drop-in
            r = probe_host_privacy_drift(
                install_root=tdp,
                unit_path=unit,
                journald_dropin=missing_dropin,
                log_dirs=[tdp / "no-logs"],
                recipe_paths=[ROOT / "node" / "install_host_privacy.sh"],
            )
            self.assertFalse(r.get("skipped"), msg=r)
            self.assertTrue(r.get("warn"), msg=r)
            self.assertFalse(r.get("ok"), msg=r)
            self.assertFalse(r.get("dropin_present"))
            self.assertTrue(r.get("unit_present"))
            joined = " ".join(r.get("reasons") or [])
            self.assertIn("drop-in", joined.lower())

    def test_host_privacy_no_host_artifacts_skips(self):
        """No unit/drop-in/log dirs ⇒ honest SKIP even if recipe exists in monorepo."""
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            r = probe_host_privacy_drift(
                install_root=tdp,
                unit_path=tdp / "missing.service",
                journald_dropin=tdp / "missing.conf",
                log_dirs=[tdp / "no-log-a", tdp / "no-log-b"],
                recipe_paths=[ROOT / "node" / "install_host_privacy.sh"],
            )
            self.assertTrue(r.get("skipped"), msg=r)
            self.assertTrue(r.get("ok"), msg=r)
            self.assertFalse(r.get("warn"), msg=r)
            self.assertIn("non-node host", " ".join(r.get("reasons") or []))

    def test_host_privacy_dropin_and_unit_pass(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            unit = tdp / "rpt-node.service"
            unit.write_text(
                "[Service]\nStandardOutput=null\nStandardError=null\n",
                encoding="utf-8",
            )
            dropin = tdp / "99-rpt-privacy.conf"
            dropin.write_text(
                "[Journal]\nStorage=volatile\nRuntimeMaxUse=32M\n",
                encoding="utf-8",
            )
            r = probe_host_privacy_drift(
                install_root=tdp,
                unit_path=unit,
                journald_dropin=dropin,
                log_dirs=[tdp / "absent-log"],
                recipe_paths=[ROOT / "node" / "install_host_privacy.sh"],
            )
            self.assertFalse(r.get("skipped"), msg=r)
            self.assertTrue(r.get("ok"), msg=r)
            self.assertFalse(r.get("warn"), msg=r)
            self.assertTrue(r.get("dropin_present"))
            self.assertTrue(r.get("unit_present"))

    def test_disk_and_ephemeral(self):
        disk = probe_disk_wipe_readiness(repo_root=ROOT, install_root=ROOT)
        self.assertTrue(
            any("no LUKS format" in str(x) for x in disk["reasons"])
        )
        eph = probe_ephemeral_dry_run(repo_root=ROOT, run_subprocess=True)
        self.assertTrue(eph.get("ok") or eph.get("warn"))
        self.assertTrue(
            any("dry-run" in str(x).lower() for x in eph.get("reasons") or [])
        )

    def test_run_all_excludes_firewall_scan(self):
        agg = run_all_section_b_probes(
            http_status={"ok": True, "body": {"title": "RESTORE PRIVACY"}},
            repo_root=ROOT,
            install_root=ROOT,
            run_ephemeral_subprocess=False,
        )
        self.assertTrue(agg["firewall_excluded"])
        probes = agg["probes"]
        for key in (
            "nolog_journald",
            "no_priv_public_trees",
            "kill_switch_default_off",
            "title_only_status",
            "host_privacy_drift",
            "disk_wipe_readiness",
            "ephemeral_dry_run",
        ):
            self.assertIn(key, probes)
        fw = probes["firewall_expose_surface"]
        self.assertTrue(fw["skipped"])
        self.assertIn("excluded", " ".join(fw["reasons"]).lower())
        md = render_section_b_markdown(agg)
        self.assertIn("section B", md)
        self.assertIn("firewall", md.lower())
        self.assertIn("kill_switch_default_off", md)

    def test_runner_collect_includes_section_b(self):
        mod = _load_runner()
        # Avoid network dependency: inject host loopback not required
        results = {
            "generated_at": "2026-07-21T00:00:00Z",
            "node_host": "127.0.0.1",
            "catalog_version": "0.3.4",
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
                "catalog_version": "0.3.4",
                "overall": "Green",
                "packages": [],
                "legend": {"Green": "OK", "Amber": "A", "Red": "R"},
            },
            "section_b": run_all_section_b_probes(
                http_status={
                    "ok": True,
                    "body": {"title": "RESTORE PRIVACY"},
                },
                repo_root=ROOT,
                run_ephemeral_subprocess=False,
            ),
        }
        md = mod.build_markdown(results)
        self.assertIn("Privacy probes (section B", md)
        self.assertIn("kill_switch_default_off", md)
        self.assertIn("firewall", md.lower())
        self.assertIn("no firewall", md.lower() or "excluded" in md.lower())


if __name__ == "__main__":
    unittest.main()

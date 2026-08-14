"""Android DE residual pin honesty — source map + packaged APK assets.

Proves shipped Android residual HELLO for Germany monopin uses
``de_node_elgamal.pub`` (not Iceland ``node_elgamal.pub``), and that
``copyRptSecretsToAssets`` packages that basename into the APK.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VPN = (
    ROOT
    / "client_app"
    / "android"
    / "app"
    / "src"
    / "main"
    / "kotlin"
    / "com"
    / "restoreprivacy"
    / "restore_privacy_client"
    / "RptVpnService.kt"
)
GRADLE = ROOT / "client_app" / "android" / "app" / "build.gradle.kts"
PRODUCT_DE = ROOT / "product" / "de_node_elgamal.pub"
APK = ROOT / "releases" / "0.5.7" / "restore-privacy-client-0.5.7-android.apk"
DE_HOST = "178.105.187.178"


def _parse_constants(src: str) -> dict[str, str]:
    consts: dict[str, str] = {}
    for m in re.finditer(r'const val (PRODUCT_[A-Z_]+) = "([^"]+)"', src):
        consts[m.group(1)] = m.group(2)
    return consts


def residual_node_pub_name_for_host_from_source(src: str, host: str) -> str:
    """Execute the shipped residualNodePubNameForHost policy from RptVpnService.kt.

    Reads PRODUCT_* constants and applies the same branch order as the Kotlin
    function body (DE/exit → de_node; retired US → de_node; IS → node; RO legacy → exit).
    """
    c = _parse_constants(src)
    de = c["PRODUCT_DE_HOST"]
    exit_h = c["PRODUCT_EXIT_HOST"]
    us = c["PRODUCT_US_HOST"]
    iceland = c["PRODUCT_ICELAND_HOST"]
    sg = c.get("PRODUCT_SG_HOST", "")
    ro_legacy = c.get("PRODUCT_RO_LEGACY_HOST", "")

    # Function must exist and return de_node for DE
    assert "fun residualNodePubNameForHost" in src
    body_m = re.search(
        r"fun residualNodePubNameForHost\(host: String\): String \{(.*?)(?=\n        /\*\*|\n        @JvmStatic|\n        fun )",
        src,
        re.S,
    )
    assert body_m, "could not isolate residualNodePubNameForHost body"
    body = body_m.group(1)
    assert 'return "de_node_elgamal.pub"' in body
    assert "PRODUCT_DE_HOST" in body or "PRODUCT_EXIT_HOST" in body
    assert "PRODUCT_SG_HOST" in body
    assert 'return "sg_node_elgamal.pub"' in body

    h = host.strip()
    if h == de or h.endswith(de) or h == exit_h or h.endswith(exit_h):
        return "de_node_elgamal.pub"
    if sg and (h == sg or h.endswith(sg)):
        return "sg_node_elgamal.pub"
    if h == us or h.endswith(us):
        return "de_node_elgamal.pub"  # retired US monopin heals to DE
    if h == iceland or h.endswith(iceland):
        return "de_node_elgamal.pub"
    if ro_legacy and (h == ro_legacy or h.endswith(ro_legacy)):
        return "exit_node_elgamal.pub"
    return "de_node_elgamal.pub"


def test_android_residual_node_pub_name_maps_de_host():
    src = VPN.read_text(encoding="utf-8")
    consts = _parse_constants(src)
    assert consts["PRODUCT_DE_HOST"] == DE_HOST
    assert consts["PRODUCT_ENTRY_HOST"] == DE_HOST
    assert consts["PRODUCT_EXIT_HOST"] == DE_HOST
    assert consts["PRODUCT_US_HOST"] == "5.161.242.85"
    # Must not still hardcode Romania as product exit
    assert "185.146.232.107" not in (
        consts["PRODUCT_EXIT_HOST"],
        consts["PRODUCT_ENTRY_HOST"],
        consts["PRODUCT_DE_HOST"],
    )

    assert residual_node_pub_name_for_host_from_source(src, DE_HOST) == "de_node_elgamal.pub"
    assert residual_node_pub_name_for_host_from_source(src, "5.161.242.85") == "de_node_elgamal.pub"
    assert residual_node_pub_name_for_host_from_source(src, "82.221.101.241") == "de_node_elgamal.pub"
    assert residual_node_pub_name_for_host_from_source(src, "5.223.48.8") == "sg_node_elgamal.pub"
    assert residual_node_pub_name_for_host_from_source(src, DE_HOST) != "node_elgamal.pub"


def test_copy_rpt_secrets_packages_de_node_pin():
    g = GRADLE.read_text(encoding="utf-8")
    # Must package de_node (not delete it)
    assert re.search(
        r'de_node_elgamal\.pub"\s*\)\.let\s*\{\s*if\s*\(it\.exists\(\)\)\s*it\.delete\(\)',
        g,
    ) is None
    m = re.search(r"val names = listOf\((.*?)\)", g, re.S)
    assert m, "names list missing in copyRptSecretsToAssets"
    names_block = m.group(1)
    assert "de_node_elgamal.pub" in names_block
    assert "node_elgamal.pub" in names_block
    assert "sg_node_elgamal.pub" in names_block
    assert "exit_node_elgamal.pub" in names_block


def test_product_de_pub_exists():
    assert PRODUCT_DE.is_file(), f"missing {PRODUCT_DE}"
    assert PRODUCT_DE.stat().st_size >= 32


def test_apk_contains_de_node_elgamal_pub():
    """Gating: rebuilt 0.5.7 APK must ship assets/secrets/de_node_elgamal.pub."""
    assert APK.is_file(), f"missing APK {APK} — rebuild after Android pin fix"
    with zipfile.ZipFile(APK, "r") as zf:
        names = zf.namelist()
        candidates = [
            n
            for n in names
            if n.endswith("assets/secrets/de_node_elgamal.pub")
            or n.endswith("secrets/de_node_elgamal.pub")
        ]
        assert candidates, (
            "APK missing de_node_elgamal.pub under assets/secrets — "
            f"sample assets: {[n for n in names if 'secrets' in n][:20]}"
        )
        data = zf.read(candidates[0])
        assert len(data) >= 32
        product = PRODUCT_DE.read_bytes()
        assert data == product, "APK de_node pin must match product/de_node_elgamal.pub"


if __name__ == "__main__":
    test_android_residual_node_pub_name_maps_de_host()
    test_copy_rpt_secrets_packages_de_node_pin()
    test_product_de_pub_exists()
    print("source gates OK")

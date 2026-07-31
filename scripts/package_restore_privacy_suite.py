#!/usr/bin/env python3
"""Redeploy-anywhere package path for Restore Privacy Suite v1.0.0.

Produces (or documents) suite client artifacts for catalog platforms:
  windows, android, macos, ios, linux

and packages the Helsinki perc_chain stack. Dry-run works without SSH or
signed store credentials.

Usage::

  python3 scripts/package_restore_privacy_suite.py --list
  python3 scripts/package_restore_privacy_suite.py --stage --dry-run
  python3 scripts/package_restore_privacy_suite.py --stage
  python3 scripts/package_restore_privacy_suite.py --build-commands
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITE_VERSION = "1.0.0"
SUITE_NAME = "Restore Privacy Suite"
PRODUCT_SLUG = "restore-privacy-suite"

# Catalog platforms (same set as host_paid_assets_vps / downloads.py).
PLATFORMS = ("windows", "android", "macos", "ios", "linux")


def suite_filenames(version: str = SUITE_VERSION) -> dict[str, str]:
    """Canonical installable names for suite monopin."""
    return {
        "windows": f"{PRODUCT_SLUG}-{version}-windows-x64-setup.exe",
        "android": f"{PRODUCT_SLUG}-{version}-android.apk",
        "macos": f"{PRODUCT_SLUG}-{version}-macos.zip",
        "ios": f"{PRODUCT_SLUG}-{version}-ios.zip",
        "linux": f"{PRODUCT_SLUG}-{version}-linux-x64.tar.gz",
    }


def list_catalog(version: str = SUITE_VERSION) -> list[dict[str, str]]:
    names = suite_filenames(version)
    return [
        {
            "platform": plat,
            "filename": names[plat],
            "version": version,
            "product": SUITE_NAME,
            "relative_path": f"releases/{version}/{names[plat]}",
            "build_cwd": "client_app",
        }
        for plat in PLATFORMS
    ]


def build_commands(version: str = SUITE_VERSION) -> dict[str, str]:
    """One discoverable command per platform (from suite Flutter tree)."""
    # Commands are the redeploy method; full signing is optional when keys exist.
    return {
        "windows": (
            f"cd client_app && flutter build windows --release "
            f"--build-name={version} && "
            f"# package → releases/{version}/{suite_filenames(version)['windows']}"
        ),
        "android": (
            f"cd client_app && flutter build apk --release "
            f"--build-name={version} --build-number=1 && "
            f"cp build/app/outputs/flutter-apk/app-release.apk "
            f"../releases/{version}/{suite_filenames(version)['android']}"
        ),
        "macos": (
            f"cd client_app && flutter build macos --release "
            f"--build-name={version} && "
            f"# zip app → releases/{version}/{suite_filenames(version)['macos']}"
        ),
        "ios": (
            f"cd client_app && flutter build ipa --release "
            f"--build-name={version} && "
            f"# archive → releases/{version}/{suite_filenames(version)['ios']}"
        ),
        "linux": (
            f"cd client_app && flutter build linux --release "
            f"--build-name={version} && "
            f"tar -czf ../releases/{version}/{suite_filenames(version)['linux']} "
            f"-C build/linux/x64/release bundle"
        ),
        "perc_chain": (
            "python3 scripts/deploy_perc_chain_helsinki.py --package --dry-run"
        ),
        "perc_chain_local_health": (
            "python3 scripts/deploy_perc_chain_helsinki.py --local-run --port 9478"
        ),
        "perc_chain_helsinki_upload": (
            "python3 scripts/deploy_perc_chain_helsinki.py "
            "--package --upload --install-service"
        ),
    }


def stage_manifest(version: str = SUITE_VERSION, dry_run: bool = False) -> Path:
    """Write suite stage manifest under dist/suite/{version}/."""
    dist = ROOT / "dist" / "suite" / version
    releases = ROOT / "releases" / version
    if not dry_run:
        dist.mkdir(parents=True, exist_ok=True)
        releases.mkdir(parents=True, exist_ok=True)

    catalog = list_catalog(version)
    cmds = build_commands(version)
    manifest = {
        "product": SUITE_NAME,
        "version": version,
        "display": f"{SUITE_NAME} v {version}",
        "platforms": catalog,
        "build_commands": cmds,
        "perc_chain": {
            "deploy_script": "scripts/deploy_perc_chain_helsinki.py",
            "host_default": "135.181.152.10",
            "port": 9478,
            "paused_render": "evolve-perc-internet.onrender.com",
            "paused_note": "evolve-perc-internet is paused to save money",
        },
        "client_app": "client_app",
        "monopin_sources": [
            "client/VERSION",
            "client_app/pubspec.yaml",
            "client_app/lib/suite_version.dart",
            "client_app/lib/rpt_config.dart",
        ],
    }

    out = dist / "suite_package_manifest.json"
    text = json.dumps(manifest, indent=2) + "\n"
    if dry_run:
        print(f"dry_run_manifest_path={out}")
        print(text)
        return out

    out.write_text(text, encoding="utf-8")
    # Placeholder staging files so --stage is visible without full flutter builds.
    for entry in catalog:
        marker = releases / f"{entry['filename']}.stage.json"
        marker.write_text(
            json.dumps(
                {
                    "platform": entry["platform"],
                    "filename": entry["filename"],
                    "version": version,
                    "product": SUITE_NAME,
                    "status": "staged_awaiting_binary",
                    "build_command": cmds[entry["platform"]],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    # Also package perc_chain when not dry-run
    deploy = ROOT / "scripts" / "deploy_perc_chain_helsinki.py"
    if deploy.is_file():
        import subprocess

        subprocess.check_call(
            [sys.executable, str(deploy), "--package"],
            cwd=str(ROOT),
        )
    print(f"manifest={out}")
    print(f"releases_dir={releases}")
    for entry in catalog:
        print(f"  platform={entry['platform']:<8} file={entry['filename']}")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--list", action="store_true", help="List suite catalog packages")
    p.add_argument("--stage", action="store_true", help="Write manifest + stage markers")
    p.add_argument("--dry-run", action="store_true", help="No filesystem writes for stage")
    p.add_argument(
        "--build-commands",
        action="store_true",
        help="Print one redeploy command per platform",
    )
    p.add_argument("--version", default=SUITE_VERSION)
    args = p.parse_args(argv)

    if args.list:
        print(f"product={SUITE_NAME}")
        print(f"catalog_version={args.version}")
        for e in list_catalog(args.version):
            print(
                f"  platform={e['platform']:<8} file={e['filename']} "
                f"rel={e['relative_path']}"
            )
        return 0

    if args.build_commands:
        for plat, cmd in build_commands(args.version).items():
            print(f"## {plat}\n{cmd}\n")
        return 0

    if args.stage:
        stage_manifest(args.version, dry_run=args.dry_run)
        return 0

    if args.dry_run:
        stage_manifest(args.version, dry_run=True)
        return 0

    p.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

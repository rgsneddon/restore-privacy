"""CLI: single-click RESTORE + Ned OOBE entry for rpOS packages."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from . import NED_NAME, PRODUCT, __version__
from .advisories import advisory_text_blob, has_required_warning_keywords
from .gate import evaluate_confirmation, gate_preview
from .ned_oobe import run_oobe_scripted
from .pipeline import RestorePipeline


def _default_prefix() -> Path:
    return Path.home() / ".rpos" / "install"


def _package_rpos_src() -> Path | None:
    # When running from an extracted package: ../rpos relative to installer
    here = Path(__file__).resolve().parent
    cand = here.parent  # rpos/
    if (cand / "README.md").is_file() and (cand / "sdk").is_dir():
        return cand
    # Monorepo checkout
    mono = here.parents[1] / "rpos"
    if mono.is_dir():
        return mono
    return None


def cmd_advisories() -> int:
    text = advisory_text_blob()
    print(text)
    print(
        json.dumps(
            {
                "ok": has_required_warning_keywords(text),
                "product": PRODUCT,
                "ned": NED_NAME,
            }
        )
    )
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    print(advisory_text_blob())
    if not args.yes_advisories:
        print("Pass --yes-advisories after reading advisories.", file=sys.stderr)
        return 2
    confirm = args.confirm
    if confirm is None and args.smoke:
        confirm = "RESTORE"
    pipe = RestorePipeline(
        prefix=Path(args.prefix) if args.prefix else _default_prefix(),
        source_rpos=_package_rpos_src(),
    )
    result = pipe.run(
        confirm,
        advisories_acknowledged=True,
        skip_wipe=bool(args.skip_wipe),
    )
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


def cmd_oobe(args: argparse.Namespace) -> int:
    path = Path(args.persist) if args.persist else None
    if args.smoke and not (args.timezone and args.language and args.email):
        args.timezone = args.timezone or "Europe/London"
        args.language = args.language or "en-GB"
        args.email = args.email or "user@example.com"
    if not path and args.smoke:
        path = Path(tempfile.mkdtemp(prefix="rpos-oobe-")) / "oobe_state.json"
    out = run_oobe_scripted(
        args.timezone or "",
        args.language or "",
        args.email or "",
        persist_path=path,
    )
    print(json.dumps(out, indent=2))
    return 0 if out.get("ok") else 1


def cmd_smoke() -> int:
    """Full dry-run: gate reject, gate accept, wipe dry-run, OOBE."""
    adv = advisory_text_blob()
    assert has_required_warning_keywords(adv)
    bad = evaluate_confirmation("nope", advisories_acknowledged=True)
    good = evaluate_confirmation("RESTORE", advisories_acknowledged=True)
    assert not bad.allowed and good.allowed
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        pipe = RestorePipeline(prefix=tdp / "root", source_rpos=_package_rpos_src())
        denied = pipe.run("WRONG")
        assert denied["proceeded"] is False
        ok = pipe.run("RESTORE")
        assert ok["proceeded"] is True
        assert ok["wipe"] and ok["wipe"]["host_disk_touched"] is False
        oobe = run_oobe_scripted(
            "UTC",
            "en",
            "ned.user@restoreprivacy.example",
            persist_path=tdp / "oobe.json",
        )
        assert oobe["timezone"] == "UTC"
        assert oobe["email"]
        assert oobe["rpmail"]["bound"] is True
    payload = {
        "ok": True,
        "product": PRODUCT,
        "version": __version__,
        "ned": NED_NAME,
        "single_click_entry": "python -m rpos.installer restore",
        "gate_preview": gate_preview()["confirm_phrase"],
        "wipe_default": "dry_run",
        "oobe_steps": ["timezone", "language", "email_rpmail"],
    }
    print(json.dumps(payload, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="rpos.installer",
        description="rpOS single-click RESTORE + Ned OOBE",
    )
    ap.add_argument("--version", action="store_true")
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("advisories", help="Print multi-layer RESTORE advisories")
    p_rest = sub.add_parser("restore", help="Single-click RESTORE pipeline")
    p_rest.add_argument(
        "--confirm",
        default=None,
        help='Exact confirmation phrase (must be RESTORE)',
    )
    p_rest.add_argument(
        "--yes-advisories",
        action="store_true",
        help="Assert you read the advisories",
    )
    p_rest.add_argument("--prefix", default=None)
    p_rest.add_argument("--skip-wipe", action="store_true")
    p_rest.add_argument("--smoke", action="store_true", help="Use RESTORE confirm")

    p_oobe = sub.add_parser("oobe", help="Ned-guided first setup")
    p_oobe.add_argument("--timezone", default="")
    p_oobe.add_argument("--language", default="")
    p_oobe.add_argument("--email", default="")
    p_oobe.add_argument("--persist", default=None)
    p_oobe.add_argument("--smoke", action="store_true")

    sub.add_parser("smoke", help="Dry-run full path (no host wipe)")

    args = ap.parse_args(argv)
    if args.version:
        print(f"{PRODUCT} installer {__version__}")
        return 0
    if args.cmd == "advisories":
        return cmd_advisories()
    if args.cmd == "restore":
        return cmd_restore(args)
    if args.cmd == "oobe":
        return cmd_oobe(args)
    if args.cmd == "smoke" or args.cmd is None:
        if args.cmd is None:
            return cmd_smoke()
        return cmd_smoke()
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

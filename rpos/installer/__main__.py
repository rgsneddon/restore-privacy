"""CLI: single-click RESTORE + Ned OOBE + Pens/Tables/Slides locked tour."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from . import NED_NAME, PRODUCT, __version__
from .advisories import advisory_text_blob, has_required_warning_keywords
from .desktop import assert_desktop_has_all_three, place_app_launchers
from .gate import evaluate_confirmation, gate_preview
from .ned_apps_tour import NedAppsTour, persist_tour
from .ned_oobe import (
    install_marker_path,
    oobe_state_path,
    run_oobe_interactive,
    run_oobe_scripted,
)
from .pipeline import RestorePipeline


def _default_prefix() -> Path:
    return Path.home() / ".rpos" / "install"


def _package_rpos_src() -> Path | None:
    here = Path(__file__).resolve().parent
    cand = here.parent
    if (cand / "README.md").is_file() and (cand / "sdk").is_dir():
        return cand
    mono = here.parents[1] / "rpos"
    if mono.is_dir():
        return mono
    return None


def _resolve_prefix(args: argparse.Namespace) -> Path:
    if getattr(args, "prefix", None):
        return Path(args.prefix)
    return _default_prefix()


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
    if confirm is None:
        try:
            confirm = input("Type RESTORE to confirm absolute wipe intent: ")
        except EOFError:
            confirm = ""
    prefix = _resolve_prefix(args)
    pipe = RestorePipeline(
        prefix=prefix,
        source_rpos=_package_rpos_src(),
    )
    result = pipe.run(
        confirm,
        advisories_acknowledged=True,
        skip_wipe=bool(args.skip_wipe),
    )
    print(json.dumps(result, indent=2))
    if not result.get("ok"):
        return 1
    if args.run_oobe:
        oobe_args = argparse.Namespace(
            timezone="",
            language="",
            email="",
            persist=None,
            prefix=str(prefix),
            smoke=bool(args.smoke),
            run_apps_tour=True,
        )
        return cmd_oobe(oobe_args)
    return 0


def cmd_oobe(args: argparse.Namespace) -> int:
    prefix = Path(args.prefix) if args.prefix else None
    path = Path(args.persist) if args.persist else None
    if prefix is not None and path is None:
        path = oobe_state_path(prefix)

    has_all = bool(args.timezone and args.language and args.email)
    if args.smoke:
        tz = args.timezone or "Europe/London"
        lang = args.language or "en-GB"
        email = args.email or "user@example.com"
        if path is None and prefix is None:
            path = Path(tempfile.mkdtemp(prefix="rpos-oobe-")) / "oobe_state.json"
        out = run_oobe_scripted(
            tz, lang, email, persist_path=path if prefix is None else None, prefix=prefix
        )
    elif has_all:
        out = run_oobe_scripted(
            args.timezone,
            args.language,
            args.email,
            persist_path=path if prefix is None else None,
            prefix=prefix,
        )
    else:
        out = run_oobe_interactive(
            persist_path=path if prefix is None else None,
            prefix=prefix,
        )
    print(json.dumps(out, indent=2))
    if not out.get("ok"):
        return 1
    if getattr(args, "run_apps_tour", False):
        return cmd_apps_tour(
            argparse.Namespace(
                prefix=str(prefix) if prefix else None,
                smoke=bool(getattr(args, "smoke", False)),
                auto=bool(getattr(args, "smoke", False)),
            )
        )
    return 0


def cmd_apps_tour(args: argparse.Namespace) -> int:
    prefix = Path(args.prefix) if args.prefix else _default_prefix()
    # Ensure desktop launchers exist (re-entrant safe)
    place_app_launchers(
        prefix,
        apps_root=(prefix / "apps") if (prefix / "apps").is_dir() else None,
    )
    tour = NedAppsTour()
    auto = bool(getattr(args, "auto", False) or getattr(args, "smoke", False))
    result = tour.run_full_tour(auto=auto)
    path = persist_tour(prefix, result)
    result["persisted"] = str(path)
    result["prefix"] = str(prefix)
    desk = prefix / "Desktop"
    result["desktop_ready"] = assert_desktop_has_all_three(desk)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") and result.get("os_fully_unlocked") else 1


def cmd_smoke() -> int:
    adv = advisory_text_blob()
    assert has_required_warning_keywords(adv)
    bad = evaluate_confirmation("nope", advisories_acknowledged=True)
    good = evaluate_confirmation("RESTORE", advisories_acknowledged=True)
    assert not bad.allowed and good.allowed
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        prefix = tdp / "root"
        pipe = RestorePipeline(prefix=prefix, source_rpos=_package_rpos_src())
        denied = pipe.run("WRONG")
        assert denied["proceeded"] is False
        ok = pipe.run("RESTORE")
        assert ok["proceeded"] is True
        assert ok.get("desktop")
        desk = Path(ok["desktop"]["desktop"])
        assert assert_desktop_has_all_three(desk)
        marker = install_marker_path(prefix)
        assert json.loads(marker.read_text())["oobe_pending"] is True
        answers = iter(["UTC", "en", "ned.user@restoreprivacy.example"])
        oobe = run_oobe_interactive(
            prefix=prefix,
            input_fn=lambda _p: next(answers),
            print_fn=lambda *_a, **_k: None,
        )
        assert oobe["oobe_pending"] is False
        tour = NedAppsTour()
        tres = tour.run_full_tour(auto=True, print_fn=lambda *_a, **_k: None)
        persist_tour(prefix, tres)
        assert tres["os_fully_unlocked"] is True
        assert tres["completed"] == ["Pens", "Tables", "Slides"]
        m = json.loads(marker.read_text())
        assert m["os_fully_unlocked"] is True
    payload = {
        "ok": True,
        "product": PRODUCT,
        "version": __version__,
        "ned": NED_NAME,
        "apps": ["Pens", "Tables", "Slides"],
        "single_click_entry": "RESTORE_rpOS",
        "gate_preview": gate_preview()["confirm_phrase"],
        "wipe_default": "dry_run",
        "oobe_default": "interactive",
        "apps_tour": ["Pens", "Tables", "Slides"],
    }
    print(json.dumps(payload, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="rpos.installer",
        description="rpOS RESTORE + Ned OOBE + Pens/Tables/Slides tour",
    )
    ap.add_argument("--version", action="store_true")
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("advisories", help="Print multi-layer RESTORE advisories")
    p_rest = sub.add_parser("restore", help="Single-click RESTORE pipeline")
    p_rest.add_argument("--confirm", default=None)
    p_rest.add_argument("--yes-advisories", action="store_true")
    p_rest.add_argument("--prefix", default=None)
    p_rest.add_argument("--skip-wipe", action="store_true")
    p_rest.add_argument("--smoke", action="store_true")
    p_rest.add_argument("--run-oobe", action="store_true")

    p_oobe = sub.add_parser("oobe", help="Ned timezone/language/email (interactive)")
    p_oobe.add_argument("--timezone", default="")
    p_oobe.add_argument("--language", default="")
    p_oobe.add_argument("--email", default="")
    p_oobe.add_argument("--persist", default=None)
    p_oobe.add_argument("--prefix", default=None)
    p_oobe.add_argument("--smoke", action="store_true")
    p_oobe.add_argument(
        "--run-apps-tour",
        action="store_true",
        help="After personal OOBE, run Ned locked Pens→Tables→Slides tour",
    )

    p_tour = sub.add_parser("apps-tour", help="Ned locked guide: Pens → Tables → Slides")
    p_tour.add_argument("--prefix", default=None)
    p_tour.add_argument("--smoke", action="store_true")
    p_tour.add_argument("--auto", action="store_true", help="Acknowledge steps without Enter")

    sub.add_parser("smoke", help="Dry-run full path including apps tour")

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
    if args.cmd == "apps-tour":
        return cmd_apps_tour(args)
    if args.cmd == "smoke" or args.cmd is None:
        return cmd_smoke()
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

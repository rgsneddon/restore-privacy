"""RxShell interactive REPL + non-interactive CLI entry."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, TextIO

from . import __version__
from .runner import (
    SUPPORTED_LANGUAGES,
    list_languages,
    resolve_language,
    run_snippet,
)

PRODUCT = "RxShell"
PROMPT = "RxShell> "
HELP_TEXT = """\
RxShell — PowerShell-type multi-language CLI for rpOS (not full MS PowerShell).

Built-ins:
  help, ?          this help
  version          product version
  languages, langs list supported languages + host runtime availability
  exit, quit       leave the shell

Run a snippet:
  :python print(1+1)
  :js console.log(1+1)
  :shell echo hi
  :powershell Write-Host 'hi'
  :auto <snippet>     auto-detect language (default)

Or paste code after a language tag on the same line. Multi-line: end with a
lone '.' on a line after entering :python / :js / etc. then code lines.

Honesty: only languages with a host interpreter run; others fail closed.
Supported tags: shell, python, javascript, powershell (+ aliases py, js, bash, ps1).
"""


def _print_result(result: Any, out: TextIO, err: TextIO) -> int:
    if result.stdout:
        out.write(result.stdout)
        if not result.stdout.endswith("\n"):
            out.write("\n")
    if result.stderr:
        err.write(result.stderr)
        if not result.stderr.endswith("\n"):
            err.write("\n")
    if not result.ok and result.error:
        err.write(f"RxShell: {result.error}\n")
    return int(result.exit_code)


def run_line(
    line: str,
    *,
    default_language: str | None = None,
    out: TextIO | None = None,
    err: TextIO | None = None,
) -> int:
    """Execute one REPL line (built-in or multi-language snippet). Returns exit code."""
    out = out or sys.stdout
    err = err or sys.stderr
    text = (line or "").rstrip("\n")
    stripped = text.strip()
    if not stripped:
        return 0

    low = stripped.lower()
    if low in ("exit", "quit", "q"):
        return -1  # signal exit
    if low in ("help", "?"):
        out.write(HELP_TEXT)
        return 0
    if low in ("version", "ver"):
        out.write(f"{PRODUCT} {__version__} (rpOS multi-language CLI)\n")
        return 0
    if low in ("languages", "langs", "lang"):
        for row in list_languages():
            flag = "ok" if row["available"] else "missing"
            out.write(
                f"  {row['language']:12} runtime={row['runtime'] or '-':10} "
                f"[{flag}] aliases={','.join(row['aliases'])}\n"
            )
        return 0

    language: str | None = default_language
    code = text
    if stripped.startswith(":"):
        # :lang rest...
        parts = stripped[1:].split(None, 1)
        tag = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""
        if tag in ("auto", "detect"):
            language = None
            code = rest
        else:
            resolved = resolve_language(tag)
            if resolved is None:
                err.write(
                    f"RxShell: unknown language tag {tag!r}; "
                    f"try {', '.join(SUPPORTED_LANGUAGES)}\n"
                )
                return 127
            language = resolved
            code = rest
        if not code.strip():
            err.write("RxShell: empty snippet after language tag\n")
            return 2

    result = run_snippet(code, language=language)
    return _print_result(result, out, err)


def interactive_loop(
    *,
    stdin: TextIO | None = None,
    out: TextIO | None = None,
    err: TextIO | None = None,
) -> int:
    """PowerShell-type prompt loop until exit."""
    stdin = stdin or sys.stdin
    out = out or sys.stdout
    err = err or sys.stderr
    out.write(f"{PRODUCT} {__version__} — multi-language CLI for rpOS\n")
    out.write("Type 'help' for commands. Not full Microsoft PowerShell.\n")
    last = 0
    while True:
        try:
            out.write(PROMPT)
            out.flush()
            line = stdin.readline()
        except KeyboardInterrupt:
            out.write("\n")
            continue
        except EOFError:
            out.write("\n")
            break
        if line == "":
            break
        # multi-line block: :lang then lines until lone '.'
        st = line.strip()
        if st.startswith(":") and len(st.split(None, 1)) == 1:
            tag = st[1:].strip().lower()
            if resolve_language(tag) or tag in ("auto", "detect"):
                out.write(f"(enter {tag} code; lone '.' to run)\n")
                buf: list[str] = []
                while True:
                    out.write("… ")
                    out.flush()
                    more = stdin.readline()
                    if more == "" or more.strip() == ".":
                        break
                    buf.append(more.rstrip("\n"))
                line = st + " " + "\n".join(buf)
        rc = run_line(line, out=out, err=err)
        if rc == -1:
            return last
        last = rc
    return last


def main(argv: list[str] | None = None) -> int:
    """CLI entry: ``python -m rpos.rxshell`` / package ``RxShell`` launcher."""
    ap = argparse.ArgumentParser(
        prog="rxshell",
        description="RxShell — multi-language PowerShell-type CLI for rpOS",
    )
    ap.add_argument("--version", action="store_true")
    ap.add_argument(
        "-c",
        "--command",
        action="append",
        default=[],
        help="Run command/snippet (repeatable). Prefix with :lang for language.",
    )
    ap.add_argument(
        "-l",
        "--language",
        default="",
        help="Default language for -c snippets (python, shell, javascript, powershell)",
    )
    ap.add_argument(
        "-f",
        "--file",
        default="",
        help="Run snippet from file (use --language or detect)",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="Print RunResult JSON for -c/-f (non-interactive)",
    )
    ap.add_argument(
        "--list-languages",
        action="store_true",
        help="Print language table and exit",
    )
    args = ap.parse_args(argv)

    if args.version:
        print(f"{PRODUCT} {__version__}")
        return 0
    if args.list_languages:
        print(json.dumps(list_languages(), indent=2))
        return 0

    default_lang = resolve_language(args.language) if args.language else None
    if args.language and default_lang is None:
        print(
            f"RxShell: unknown language {args.language!r}",
            file=sys.stderr,
        )
        return 127

    if args.file:
        path = Path(args.file)
        code = path.read_text(encoding="utf-8")
        result = run_snippet(code, language=default_lang)
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            _print_result(result, sys.stdout, sys.stderr)
        return int(result.exit_code)

    if args.command:
        last = 0
        for cmd in args.command:
            if args.json:
                # Parse optional :lang prefix
                language = default_lang
                code = cmd
                s = cmd.strip()
                if s.startswith(":"):
                    parts = s[1:].split(None, 1)
                    tag = parts[0]
                    rest = parts[1] if len(parts) > 1 else ""
                    if tag.lower() in ("auto", "detect"):
                        language = None
                        code = rest
                    else:
                        language = resolve_language(tag) or language
                        code = rest
                result = run_snippet(code, language=language)
                print(json.dumps(result.to_dict(), indent=2))
                last = int(result.exit_code)
            else:
                last = run_line(cmd, default_language=default_lang)
                if last == -1:
                    return 0
        return last

    if not sys.stdin.isatty():
        # Scripted stdin: each line is a command
        last = 0
        for line in sys.stdin:
            last = run_line(line, default_language=default_lang)
            if last == -1:
                return 0
        return last

    return interactive_loop()


if __name__ == "__main__":
    raise SystemExit(main())

"""Multi-language command dispatch for RxShell (real subprocess runners).

Declared set: shell, python, javascript, powershell (+ aliases).
Unknown language or missing host runtime → fail closed (ok=False), never fake success.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

# Canonical language ids shipped in this version.
SUPPORTED_LANGUAGES: tuple[str, ...] = (
    "shell",
    "python",
    "javascript",
    "powershell",
)

LANG_ALIASES: dict[str, str] = {
    "shell": "shell",
    "sh": "shell",
    "bash": "shell",
    "zsh": "shell",
    "cmd": "shell",
    "python": "python",
    "py": "python",
    "python3": "python",
    "javascript": "javascript",
    "js": "javascript",
    "node": "javascript",
    "nodejs": "javascript",
    "powershell": "powershell",
    "ps": "powershell",
    "ps1": "powershell",
    "pwsh": "powershell",
}

# Heuristic auto-detect markers (first match wins; fallback shell).
_DETECT_ORDER: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("powershell", re.compile(r"^\s*(Write-Host|Get-ChildItem|\$\w+\s*=|param\s*\()", re.I | re.M)),
    ("python", re.compile(r"^\s*(def |import |from |print\(|class )", re.M)),
    ("javascript", re.compile(r"^\s*(const |let |var |console\.|function |=>)", re.M)),
    ("shell", re.compile(r"^\s*(echo |export |cd |ls |#!/bin/)", re.M)),
)

DEFAULT_TIMEOUT_SEC = 30.0


@dataclass
class RunResult:
    """Outcome of one multi-language run (always from real runner path)."""

    ok: bool
    language: str
    exit_code: int
    stdout: str
    stderr: str
    argv: list[str] = field(default_factory=list)
    runtime: str = ""
    error: str = ""
    missing_runtime: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "language": self.language,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "argv": list(self.argv),
            "runtime": self.runtime,
            "error": self.error,
            "missing_runtime": self.missing_runtime,
        }


def resolve_language(name: str | None) -> str | None:
    """Map user language tag to canonical id, or None if unknown."""
    key = (name or "").strip().lower()
    if not key:
        return None
    return LANG_ALIASES.get(key)


def detect_language(code: str) -> str:
    """Best-effort auto-detect; defaults to shell."""
    text = code or ""
    for lang, pat in _DETECT_ORDER:
        if pat.search(text):
            return lang
    return "shell"


def list_languages() -> list[dict[str, Any]]:
    """Describe supported languages and whether a host runtime is available."""
    out: list[dict[str, Any]] = []
    for lang in SUPPORTED_LANGUAGES:
        runtime, path = _find_runtime(lang)
        out.append(
            {
                "language": lang,
                "runtime": runtime or "",
                "available": bool(path),
                "path": path or "",
                "aliases": sorted(k for k, v in LANG_ALIASES.items() if v == lang),
            }
        )
    return out


def _find_runtime(lang: str) -> tuple[str, str | None]:
    """Return (runtime_label, executable_path or None)."""
    if lang == "shell":
        if sys.platform == "win32":
            for name in ("bash.exe", "sh.exe", "powershell.exe", "cmd.exe"):
                p = shutil.which(name)
                if p:
                    return name, p
            return "cmd", None
        for name in ("bash", "sh", "zsh"):
            p = shutil.which(name)
            if p:
                return name, p
        return "sh", None
    if lang == "python":
        # Prefer current interpreter (always present when RxShell runs under Python).
        return "python", sys.executable or shutil.which("python3") or shutil.which("python")
    if lang == "javascript":
        for name in ("node", "nodejs"):
            p = shutil.which(name)
            if p:
                return name, p
        return "node", None
    if lang == "powershell":
        for name in ("pwsh", "pwsh.exe", "powershell", "powershell.exe"):
            p = shutil.which(name)
            if p:
                return name, p
        return "pwsh", None
    return "", None


def _argv_for(
    lang: str,
    runtime_path: str,
    script_path: Path,
) -> list[str]:
    if lang == "shell":
        base = Path(runtime_path).name.lower()
        if base in ("cmd", "cmd.exe"):
            return [runtime_path, "/c", str(script_path)]
        if "powershell" in base:
            return [runtime_path, "-NoProfile", "-NonInteractive", "-File", str(script_path)]
        return [runtime_path, str(script_path)]
    if lang == "python":
        return [runtime_path, str(script_path)]
    if lang == "javascript":
        return [runtime_path, str(script_path)]
    if lang == "powershell":
        return [
            runtime_path,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
        ]
    return [runtime_path, str(script_path)]


def _script_suffix(lang: str) -> str:
    return {
        "shell": ".sh" if sys.platform != "win32" else ".cmd",
        "python": ".py",
        "javascript": ".js",
        "powershell": ".ps1",
    }.get(lang, ".txt")


def run_snippet(
    code: str,
    *,
    language: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SEC,
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
) -> RunResult:
    """Execute *code* via the multi-language runner (shipped entry for CLI + tests).

    Language resolution:
      1. explicit *language* tag (aliases ok)
      2. auto-detect from snippet
    Unknown language → ok=False, exit_code=127, clear error.
    Missing host runtime → ok=False, missing_runtime=True (never fake success).
    """
    raw = code if code is not None else ""
    if language:
        lang = resolve_language(language)
        if lang is None:
            return RunResult(
                ok=False,
                language=(language or "").strip().lower() or "unknown",
                exit_code=127,
                stdout="",
                stderr="",
                error=(
                    f"unsupported language {language!r}; "
                    f"supported: {', '.join(SUPPORTED_LANGUAGES)} "
                    f"(aliases: py, js, bash, sh, ps1, pwsh, …). "
                    "RxShell does not embed every language runtime."
                ),
            )
    else:
        lang = detect_language(raw)

    runtime_label, runtime_path = _find_runtime(lang)
    if not runtime_path:
        return RunResult(
            ok=False,
            language=lang,
            exit_code=127,
            stdout="",
            stderr="",
            runtime=runtime_label,
            missing_runtime=True,
            error=(
                f"no host runtime for language {lang!r} "
                f"(expected {runtime_label or 'interpreter'} on PATH). "
                "Install the interpreter or pick an available language "
                f"({', '.join(SUPPORTED_LANGUAGES)})."
            ),
        )

    suffix = _script_suffix(lang)
    work = Path(cwd) if cwd else Path.cwd()
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=suffix,
            delete=False,
            encoding="utf-8",
            dir=str(work) if work.is_dir() else None,
        ) as tf:
            # Shell scripts need a shebang-friendly body on Unix.
            body = raw
            if lang == "shell" and sys.platform != "win32" and not body.lstrip().startswith("#!"):
                body = "#!/usr/bin/env bash\nset -e\n" + body
            if lang == "shell" and sys.platform == "win32" and suffix == ".cmd":
                if not body.lstrip().lower().startswith("@echo"):
                    body = "@echo off\n" + body
            tf.write(body)
            if not body.endswith("\n"):
                tf.write("\n")
            script = Path(tf.name)
    except OSError as exc:
        return RunResult(
            ok=False,
            language=lang,
            exit_code=1,
            stdout="",
            stderr="",
            runtime=runtime_label,
            error=f"could not write temp script: {exc}",
        )

    if lang == "shell" and sys.platform != "win32":
        try:
            script.chmod(script.stat().st_mode | 0o700)
        except OSError:
            pass

    argv = _argv_for(lang, runtime_path, script)
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=float(timeout),
            cwd=str(work) if work.is_dir() else None,
            env=run_env,
            check=False,
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        code_i = int(proc.returncode)
        return RunResult(
            ok=code_i == 0,
            language=lang,
            exit_code=code_i,
            stdout=stdout,
            stderr=stderr,
            argv=list(argv),
            runtime=runtime_label,
            error="" if code_i == 0 else (stderr.strip() or f"exit {code_i}"),
        )
    except subprocess.TimeoutExpired:
        return RunResult(
            ok=False,
            language=lang,
            exit_code=124,
            stdout="",
            stderr="",
            argv=list(argv),
            runtime=runtime_label,
            error=f"timeout after {timeout}s",
        )
    except OSError as exc:
        return RunResult(
            ok=False,
            language=lang,
            exit_code=126,
            stdout="",
            stderr="",
            argv=list(argv),
            runtime=runtime_label,
            error=f"failed to execute runtime: {exc}",
            missing_runtime=True,
        )
    finally:
        try:
            script.unlink(missing_ok=True)
        except OSError:
            pass

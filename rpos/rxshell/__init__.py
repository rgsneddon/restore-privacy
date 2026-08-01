"""RxShell — PowerShell-type multi-language CLI for rpOS.

Honesty: not full Microsoft PowerShell parity. Accepts multi-language snippets
via host interpreters (shell, Python, JavaScript, PowerShell/pwsh when present)
with explicit fail-closed errors for unsupported or missing runtimes.
"""

from .__version__ import __version__
from .runner import (
    LANG_ALIASES,
    SUPPORTED_LANGUAGES,
    RunResult,
    detect_language,
    list_languages,
    resolve_language,
    run_snippet,
)
from .repl import main as rxshell_main

PRODUCT = "RxShell"
PRODUCT_FAMILY = "rpOS"

__all__ = [
    "PRODUCT",
    "PRODUCT_FAMILY",
    "LANG_ALIASES",
    "SUPPORTED_LANGUAGES",
    "RunResult",
    "detect_language",
    "list_languages",
    "resolve_language",
    "run_snippet",
    "rxshell_main",
    "__version__",
]

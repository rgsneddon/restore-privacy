#!/usr/bin/env python3
"""Upload a local Evolve Flutter web build to evolve.restoreprivacy.online/app/."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEB = Path.home() / "evolve" / "build" / "web"
REMOTE_APP = "/var/www/evolve.restoreprivacy.online/app"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--web-dir", type=Path, default=DEFAULT_WEB)
    p.add_argument("--host", default="helsinki")
    args = p.parse_args(argv)

    web = args.web_dir.resolve()
    index = (web / "index.html").read_text(encoding="utf-8")
    if '<base href="/app/">' not in index:
        print(f"ERROR: {web}/index.html must contain <base href=\"/app/\">", file=sys.stderr)
        return 2
    if not (web / "main.dart.js").is_file():
        print(f"ERROR: missing {web}/main.dart.js", file=sys.stderr)
        return 2

    with tempfile.NamedTemporaryFile(suffix=".tgz", delete=False) as tmp:
        tgz = Path(tmp.name)
    try:
        with tarfile.open(tgz, "w:gz") as tar:
            for path in web.rglob("*"):
                if path.suffix == ".symbols" or not path.is_file():
                    continue
                tar.add(path, arcname=path.relative_to(web))
        subprocess.check_call(
            ["scp", "-o", "BatchMode=yes", str(tgz), f"{args.host}:/tmp/evolve-web-app.tgz"]
        )
        subprocess.check_call(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                args.host,
                (
                    f"mkdir -p {REMOTE_APP} && "
                    f"tar -xzf /tmp/evolve-web-app.tgz -C {REMOTE_APP} && "
                    "rm -f /tmp/evolve-web-app.tgz && "
                    f"test -f {REMOTE_APP}/main.dart.js && echo APP_OK"
                ),
            ]
        )
    finally:
        tgz.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Stage Arch/CachyOS packaging sources for the current monopin Linux client.

Does **not** require ``makepkg`` on this host (macOS cannot produce a real
``.pkg.tar.zst`` without Arch/Docker). Writes:

  releases/<version>/arch/
    PKGBUILD
    install_linux_arch.sh
    install_linux_cachyos.sh
    README_ARCH.md
    (optional copy of linux-x64.tar.gz when present)

Also embeds monopin version from ``client/VERSION``.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def package_version() -> str:
    pin = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
    return (os.environ.get("RPT_PRODUCT_VERSION") or pin).strip() or pin


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def linux_tarball_name(version: str) -> str:
    return f"restore-privacy-client-{version}-linux-x64.tar.gz"


def arch_pkg_basename(version: str) -> str:
    """Intended makepkg output name (built only on Arch/CachyOS)."""
    return f"restore-privacy-client-{version}-1-x86_64.pkg.tar.zst"


def stage_arch_packaging(
    *,
    version: str | None = None,
    out_dir: Path | None = None,
    copy_tarball: bool = True,
) -> dict:
    """Write Arch packaging tree; return paths and metadata."""
    ver = (version or package_version()).strip()
    out = out_dir or (ROOT / "releases" / ver / "arch")
    out.mkdir(parents=True, exist_ok=True)

    tgz_name = linux_tarball_name(ver)
    tgz_src = ROOT / "releases" / ver / tgz_name
    digest = "SKIP"
    if tgz_src.is_file():
        digest = sha256_file(tgz_src)
        if copy_tarball:
            shutil.copy2(tgz_src, out / tgz_name)

    # PKGBUILD from template
    tmpl = (ROOT / "client" / "linux" / "packaging" / "arch" / "PKGBUILD.in").read_text(
        encoding="utf-8"
    )
    pkgbuild = (
        tmpl.replace("@VERSION@", ver)
        .replace("@SHA256@", digest if digest != "SKIP" else "SKIP")
    )
    (out / "PKGBUILD").write_text(pkgbuild, encoding="utf-8")

    # Install scripts
    for name in ("install_linux_arch.sh", "install_linux_cachyos.sh"):
        src = ROOT / "scripts" / name
        if src.is_file():
            dest = out / name
            shutil.copy2(src, dest)
            dest.chmod(dest.stat().st_mode | 0o111)

    readme = f"""# Arch / CachyOS install — Restore Privacy monopin **{ver}**

## Paid catalog package (all Linux)

Download **`{tgz_name}`** (same residual client as Ubuntu).

```bash
tar xzf {tgz_name}
cd restore-privacy-{ver}-linux
bash install.sh          # detects pacman on Arch/CachyOS
# or explicitly:
bash install_linux_arch.sh
# CachyOS alias:
bash install_linux_cachyos.sh
```

## Optional pacman package (build on Arch/CachyOS only)

On an Arch or CachyOS machine with ``makepkg``:

```bash
# copy {tgz_name} next to PKGBUILD (already staged under releases/{ver}/arch/ when built)
makepkg -si
```

Expected package name: `{arch_pkg_basename(ver)}`

**Do not** run ``makepkg`` on macOS — stage only. Native ``.pkg.tar.zst`` seal
requires Arch/CachyOS or an Arch container.

## System packages (pacman)

```
sudo pacman -S --needed python tk iproute2
```

App cryptography is installed offline from bundled manylinux wheels in the tarball.

## Residual client

Same ``python -m client.linux`` / ``bin/privacy-restored`` entry as other Linux.
"""
    (out / "README_ARCH.md").write_text(readme, encoding="utf-8")

    # Copy packaging template tree for repo consumers
    arch_src = ROOT / "client" / "linux" / "packaging" / "arch"
    if arch_src.is_dir():
        dest_tree = out / "src"
        if dest_tree.exists():
            shutil.rmtree(dest_tree)
        shutil.copytree(
            arch_src,
            dest_tree,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        # Materialize PKGBUILD in src/ too
        (dest_tree / "PKGBUILD").write_text(pkgbuild, encoding="utf-8")

    return {
        "version": ver,
        "out_dir": str(out),
        "pkgbuild": str(out / "PKGBUILD"),
        "readme": str(out / "README_ARCH.md"),
        "tarball": str(tgz_src) if tgz_src.is_file() else "",
        "tarball_sha256": digest if digest != "SKIP" else "",
        "arch_pkg_basename": arch_pkg_basename(ver),
        "makepkg_available": bool(shutil.which("makepkg")),
        "deployed": False,
    }


def main() -> int:
    info = stage_arch_packaging()
    print("Arch packaging staged (no deploy):")
    for k, v in info.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

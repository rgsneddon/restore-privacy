"""Linux distro-family compatibility helpers (Ubuntu/Debian + Arch/CachyOS).

Supported floors:
  - Ubuntu 20.04 LTS+ and derivatives (Mint, Pop!_OS, elementary, …)
  - Arch Linux family including **CachyOS**, EndeavourOS, Manjaro, Garuda, Artix
    (pacman; ``ID_LIKE=arch``)

Older Ubuntu EOL (16.04/18.04) is not guaranteed. Residual client is the same
tree; install package managers differ (apt vs pacman).
"""

from __future__ import annotations

import os
import sys
from typing import Literal, Optional, Sequence, Tuple

# Practical support floor (document + enforce at install/run time)
MIN_PYTHON = (3, 8)
SUPPORTED_UBUNTU_FLOOR = "20.04"
SUPPORTED_NOTE = (
    "Ubuntu 20.04 LTS and newer (and derivatives such as Linux Mint, Pop!_OS), "
    "or Arch Linux family (Arch, CachyOS, EndeavourOS, Manjaro, …). "
    "Requires Python 3.8+, iproute2, TUN (/dev/net/tun), and root for full tunnel."
)
SUPPORTED_ARCH_NOTE = (
    "Arch Linux and derivatives (CachyOS, EndeavourOS, Manjaro, Garuda, Artix). "
    "Install via pacman: python, tk, iproute2; residual package uses bundled wheels."
)

LinuxFamily = Literal["ubuntu", "arch", "unknown"]

# Arch-family IDs commonly seen on desktop (CachyOS is first-class for this product)
ARCH_FAMILY_IDS = frozenset(
    {
        "arch",
        "archarm",
        "cachyos",
        "endeavouros",
        "manjaro",
        "garuda",
        "artix",
        "arco",
        "arcolinux",
        "rebornos",
        "bluestar",
        "athena",
    }
)

# System packages for residual GUI + TUN routes (names differ by family)
UBUNTU_SYSTEM_PACKAGES: tuple[str, ...] = (
    "python3",
    "python3-venv",
    "python3-tk",
    "python3-pip",
    "iproute2",
)
ARCH_SYSTEM_PACKAGES: tuple[str, ...] = (
    "python",
    "tk",
    "iproute2",
)


def python_version_tuple() -> Tuple[int, int]:
    return (sys.version_info.major, sys.version_info.minor)


def python_meets_minimum(version: Optional[Tuple[int, int]] = None) -> bool:
    """True when the running interpreter is new enough for the Linux client."""
    v = version if version is not None else python_version_tuple()
    return v >= MIN_PYTHON


def python_version_error_message(version: Optional[Tuple[int, int]] = None) -> str:
    v = version if version is not None else python_version_tuple()
    return (
        f"Python {v[0]}.{v[1]} is too old. "
        f"Need Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ "
        f"({SUPPORTED_NOTE})"
    )


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def read_os_release(path: str = "/etc/os-release") -> dict:
    """Parse /etc/os-release into a dict (empty if missing — e.g. non-Linux host)."""
    out: dict = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                v = v.strip().strip('"').strip("'")
                out[k] = v
    except OSError:
        pass
    return out


def is_ubuntu_family(os_release: Optional[dict] = None) -> bool:
    """True for Ubuntu and common derivatives (Mint, Pop, elementary, …)."""
    data = os_release if os_release is not None else read_os_release()
    if not data:
        return False
    # Prefer Arch when both tags appear (should not happen on real hosts)
    if is_arch_family(data):
        return False
    id_ = (data.get("ID") or "").lower()
    like = (data.get("ID_LIKE") or "").lower()
    name = (data.get("NAME") or "").lower()
    if id_ in (
        "ubuntu",
        "linuxmint",
        "pop",
        "elementary",
        "zorin",
        "neon",
        "kubuntu",
        "xubuntu",
        "lubuntu",
        "ubuntustudio",
    ):
        return True
    if "ubuntu" in like or "debian" in like:
        # Debian-family desktops are the install-script target (apt)
        return True
    if "ubuntu" in name or "mint" in name:
        return True
    return False


def is_arch_family(os_release: Optional[dict] = None) -> bool:
    """True for Arch Linux and derivatives including **CachyOS**.

    Matches ``ID`` in known Arch-family set or ``ID_LIKE`` containing ``arch``.
    """
    data = os_release if os_release is not None else read_os_release()
    if not data:
        return False
    id_ = (data.get("ID") or "").lower().strip()
    like = (data.get("ID_LIKE") or "").lower()
    name = (data.get("NAME") or "").lower()
    if id_ in ARCH_FAMILY_IDS:
        return True
    # ID_LIKE tokens are space-separated (e.g. "arch" or "archlinux arch")
    like_tokens = set(like.replace(",", " ").split())
    if "arch" in like_tokens or "archlinux" in like_tokens:
        return True
    if "cachyos" in name or name.startswith("arch "):
        return True
    return False


def is_cachyos(os_release: Optional[dict] = None) -> bool:
    """True when the host identifies as CachyOS (Arch-based gaming/desktop)."""
    data = os_release if os_release is not None else read_os_release()
    if not data:
        return False
    id_ = (data.get("ID") or "").lower()
    name = (data.get("NAME") or "").lower()
    return id_ == "cachyos" or "cachyos" in name


def linux_family(os_release: Optional[dict] = None) -> LinuxFamily:
    """Return ``arch``, ``ubuntu``, or ``unknown`` for residual install routing."""
    data = os_release if os_release is not None else read_os_release()
    if is_arch_family(data):
        return "arch"
    if is_ubuntu_family(data):
        return "ubuntu"
    return "unknown"


def system_packages_for_family(family: str) -> tuple[str, ...]:
    """Package manager package names for residual GUI + TUN floor deps."""
    f = (family or "").strip().lower()
    if f == "arch":
        return ARCH_SYSTEM_PACKAGES
    if f == "ubuntu":
        return UBUNTU_SYSTEM_PACKAGES
    return ()


def package_manager_for_family(family: str) -> str:
    """Primary package manager binary name (``pacman`` / ``apt-get`` / empty)."""
    f = (family or "").strip().lower()
    if f == "arch":
        return "pacman"
    if f == "ubuntu":
        return "apt-get"
    return ""


def install_command_for_family(family: str, packages: Sequence[str] | None = None) -> str:
    """Shell one-liner (documentation / scripts) to install *packages*."""
    f = (family or "").strip().lower()
    pkgs = list(packages) if packages is not None else list(system_packages_for_family(f))
    joined = " ".join(pkgs)
    if f == "arch":
        return f"sudo pacman -S --needed --noconfirm {joined}".rstrip()
    if f == "ubuntu":
        return (
            "sudo apt-get update -y && "
            f"sudo DEBIAN_FRONTEND=noninteractive apt-get install -y {joined}"
        ).rstrip()
    return ""


def support_summary() -> str:
    return SUPPORTED_NOTE


def arch_support_summary() -> str:
    return SUPPORTED_ARCH_NOTE


def ensure_repo_on_sys_path(repo_root: Optional[str] = None) -> str:
    """Ensure repo root is on sys.path so ``python3 -m client.linux`` works from any cwd."""
    if repo_root:
        root = os.path.abspath(repo_root)
    else:
        # client/linux/ubuntu_compat.py -> parents[2] = repo root
        root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
        )
    if root not in sys.path:
        sys.path.insert(0, root)
    return root

"""Ubuntu-family compatibility helpers (portable across LTS releases).

Supported floor: Ubuntu 20.04 LTS (Python 3.8+) and derivatives (Mint, Pop!_OS,
elementary, etc.). Older EOL series (16.04/18.04) are not guaranteed.
"""

from __future__ import annotations

import os
import sys
from typing import Optional, Tuple

# Practical support floor (document + enforce at install/run time)
MIN_PYTHON = (3, 8)
SUPPORTED_UBUNTU_FLOOR = "20.04"
SUPPORTED_NOTE = (
    "Ubuntu 20.04 LTS and newer (and derivatives such as Linux Mint, Pop!_OS). "
    "Requires Python 3.8+, iproute2, TUN (/dev/net/tun), and root for full tunnel."
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


def support_summary() -> str:
    return SUPPORTED_NOTE


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

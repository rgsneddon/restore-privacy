"""Default OS install roots for the Restore Privacy client bundle.

Pure helpers (env-injectable) so installers and tests share one source of truth.

Windows default: ``%ProgramFiles%\\Restore Privacy`` (architecture-correct
Program Files). Per-user fallback remains available for non-elevated installs.

Linux default program root: ``/opt/restore-privacy`` (system); portable package
root is the extracted tarball (``install.sh`` lives there).

macOS default: ``/Applications/Restore Privacy.app`` product surface.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


# Product folder under Program Files / Applications (branded display name)
PRODUCT_FOLDER_DISPLAY = "Restore Privacy"
# Legacy internal id used for LocalAppData Programs and some shortcuts
PRODUCT_FOLDER_LEGACY_ID = "RestorePrivacy"

CLIENT_EXE_NAMES_WINDOWS: tuple[str, ...] = (
    "RestorePrivacy.exe",
    "PrivacyRestored.exe",
)
RESTORE_INTERNET_NAMES_WINDOWS: tuple[str, ...] = (
    "Restore Internet.bat",
    "RestoreInternet.bat",
)
RESTORE_INTERNET_NAMES_UNIX: tuple[str, ...] = (
    "Restore Internet",
    "restore-internet",
    "bin/restore-internet",
)


def _env_map(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return env if env is not None else os.environ


def windows_program_files_root(
    env: Mapping[str, str] | None = None,
    *,
    prefer_x86: bool | None = None,
) -> Path:
    """Architecture-correct Program Files directory (no product folder)."""
    e = _env_map(env)
    if prefer_x86 is True:
        x86 = (e.get("ProgramFiles(x86)") or e.get("PROGRAMFILES(X86)") or "").strip()
        if x86:
            return Path(x86)
    # Native Program Files for this process bitness
    pf = (e.get("ProgramFiles") or e.get("PROGRAMFILES") or "").strip()
    if pf:
        return Path(pf)
    # Fail-soft default when env stripped (tests / exotic shells)
    if prefer_x86:
        return Path(r"C:\Program Files (x86)")
    return Path(r"C:\Program Files")


def default_windows_install_dir(
    env: Mapping[str, str] | None = None,
    *,
    product_folder: str = PRODUCT_FOLDER_DISPLAY,
) -> Path:
    """``Program Files\\Restore Privacy`` (or RPT_INSTALL_DIR override)."""
    e = _env_map(env)
    override = (e.get("RPT_INSTALL_DIR") or "").strip()
    if override:
        return Path(override)
    # Explicit per-user opt-in
    per_user = (e.get("RPT_INSTALL_PER_USER") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if per_user:
        return per_user_windows_install_dir(e, product_folder=PRODUCT_FOLDER_LEGACY_ID)
    return windows_program_files_root(e) / product_folder


def per_user_windows_install_dir(
    env: Mapping[str, str] | None = None,
    *,
    product_folder: str = PRODUCT_FOLDER_LEGACY_ID,
) -> Path:
    """Historical non-elevated path: ``%LOCALAPPDATA%\\Programs\\RestorePrivacy``."""
    e = _env_map(env)
    local = (e.get("LOCALAPPDATA") or "").strip()
    if not local:
        local = str(Path.home() / "AppData" / "Local")
    return Path(local) / "Programs" / product_folder


def default_linux_install_dir(
    env: Mapping[str, str] | None = None,
) -> Path:
    """System install root ``/opt/restore-privacy`` (or RPT_INSTALL_DIR / PREFIX)."""
    e = _env_map(env)
    override = (e.get("RPT_INSTALL_DIR") or "").strip()
    if override:
        return Path(override)
    prefix = (e.get("PREFIX") or "").strip()
    if prefix:
        return Path(prefix) / "restore-privacy"
    return Path("/opt/restore-privacy")


def default_macos_install_dir(
    env: Mapping[str, str] | None = None,
    *,
    app_name: str = "Restore Privacy.app",
) -> Path:
    """``/Applications/Restore Privacy.app`` (or RPT_INSTALL_DIR)."""
    e = _env_map(env)
    override = (e.get("RPT_INSTALL_DIR") or "").strip()
    if override:
        return Path(override)
    return Path("/Applications") / app_name


def default_install_dir_for_platform(
    platform: str | None = None,
    env: Mapping[str, str] | None = None,
) -> Path:
    """Dispatch default install root for win32 / linux / darwin."""
    plat = (platform or sys.platform).lower()
    if plat.startswith("win"):
        return default_windows_install_dir(env)
    if plat == "darwin":
        return default_macos_install_dir(env)
    return default_linux_install_dir(env)


def is_under_program_files(
    path: Path | str,
    env: Mapping[str, str] | None = None,
) -> bool:
    """True when *path* is under Program Files or Program Files (x86)."""
    p = Path(path).resolve()
    roots = [
        windows_program_files_root(env),
        windows_program_files_root(env, prefer_x86=True),
    ]
    for root in roots:
        try:
            p.relative_to(root.resolve())
            return True
        except ValueError:
            continue
        except OSError:
            # Unresolved path — string prefix compare
            s = str(p).lower().replace("/", "\\")
            r = str(root).lower().replace("/", "\\")
            if s == r or s.startswith(r.rstrip("\\") + "\\"):
                return True
    return False


@dataclass(frozen=True)
class BundleInventory:
    """Client + Restore Internet entries under an install or stage tree."""

    install_dir: Path
    client_entry: str | None
    restore_internet_entry: str | None

    @property
    def complete(self) -> bool:
        return bool(self.client_entry and self.restore_internet_entry)

    def to_dict(self) -> dict[str, str | bool | None]:
        return {
            "install_dir": str(self.install_dir),
            "client_entry": self.client_entry,
            "restore_internet_entry": self.restore_internet_entry,
            "complete": self.complete,
        }


def inventory_install_bundle(
    install_dir: Path | str,
    *,
    platform: str | None = None,
    required_client_names: Sequence[str] | None = None,
    required_restore_names: Sequence[str] | None = None,
) -> BundleInventory:
    """List client + Restore Internet entries present under *install_dir*.

    Does not invent missing files — reports None when absent.
    """
    root = Path(install_dir)
    plat = (platform or sys.platform).lower()
    if plat.startswith("win"):
        clients = list(required_client_names or CLIENT_EXE_NAMES_WINDOWS)
        restores = list(required_restore_names or RESTORE_INTERNET_NAMES_WINDOWS)
    else:
        clients = list(
            required_client_names
            or (
                "bin/privacy-restored",
                "privacy-restored",
                "Restore Privacy.app",
            )
        )
        restores = list(required_restore_names or RESTORE_INTERNET_NAMES_UNIX)

    def _find(names: Sequence[str], *, soft_client_exe: bool = False) -> str | None:
        for name in names:
            p = root / name
            if p.is_file() or p.is_dir():
                return name
        # Soft search for versioned client exe only when finding the client entry
        if soft_client_exe and plat.startswith("win"):
            for p in root.glob("RestorePrivacy*.exe"):
                if p.is_file() and "uninstall" not in p.name.lower():
                    return p.name
        return None

    return BundleInventory(
        install_dir=root,
        client_entry=_find(clients, soft_client_exe=True),
        restore_internet_entry=_find(restores, soft_client_exe=False),
    )


def planned_windows_bundle_entries() -> tuple[str, ...]:
    """Names the Windows installer must place next to the client."""
    return (
        *CLIENT_EXE_NAMES_WINDOWS,
        *RESTORE_INTERNET_NAMES_WINDOWS,
        "Uninstall.bat",
        "LaunchPrivacyRestored.bat",
    )

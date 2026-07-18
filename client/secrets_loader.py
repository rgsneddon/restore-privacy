"""Load authorized product client keys (never commit privkeys to git).

Windows installers provision ``client_ed25519.priv`` + ``node_elgamal.pub`` into
install- and user-profile secrets dirs at setup time. Search order covers
frozen PyInstaller, install tree, and developer repo paths.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from node.elgamal import ElGamalPublicKey

CLIENT_PRIV_NAME = "client_ed25519.priv"
NODE_PUB_NAME = "node_elgamal.pub"
# Never load or expect node private key on the client
NODE_PRIV_NAME = "node_elgamal.priv"


class SecretsError(FileNotFoundError):
    pass


def _install_dir_candidates() -> list[Path]:
    """Windows install / frozen layout locations."""
    out: list[Path] = []
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if local:
        out.append(Path(local) / "Programs" / "RestorePrivacy" / "secrets")
    # Next to the running executable (onedir install layout)
    try:
        exe = Path(sys.executable).resolve()
        out.append(exe.parent / "secrets")
        # setup sometimes leaves secrets one level up from _internal
        out.append(exe.parent.parent / "secrets")
    except Exception:
        pass
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        out.append(meipass / "secrets")
        out.append(meipass / "payload" / "secrets")
    # Module-adjacent (dev: client/../secrets; frozen: _MEIPASS/secrets if packed)
    try:
        here = Path(__file__).resolve()
        out.append(here.parents[1] / "secrets")  # repo root when unfrozen
        out.append(here.parent / "secrets")
    except Exception:
        pass
    return out


def candidate_secrets_dirs(explicit: str | Path | None = None) -> list[Path]:
    """Ordered list of directories that may hold admission keys."""
    dirs: list[Path] = []
    env = os.environ.get("RPT_SECRETS_DIR", "").strip()
    if env:
        dirs.append(Path(env))
    if explicit:
        dirs.append(Path(explicit))
    dirs.extend(_install_dir_candidates())
    dirs.append(Path.home() / ".restore-privacy" / "secrets")
    # Linux node-style (rare on Windows client)
    dirs.append(Path("/opt/restore-privacy/secrets"))
    # De-dupe while preserving order
    seen: set[str] = set()
    unique: list[Path] = []
    for d in dirs:
        key = str(d)
        if key not in seen:
            seen.add(key)
            unique.append(d)
    return unique


def dir_has_client_secrets(d: Path) -> bool:
    return (
        d.is_dir()
        and (d / CLIENT_PRIV_NAME).is_file()
        and (d / NODE_PUB_NAME).is_file()
    )


def resolve_secrets_dir(explicit: str | Path | None = None) -> Path:
    if explicit:
        p = Path(explicit)
        if dir_has_client_secrets(p):
            return p
        if p.is_dir():
            raise SecretsError(
                f"secrets dir incomplete: {p} (need {CLIENT_PRIV_NAME} and {NODE_PUB_NAME})"
            )
        raise SecretsError(f"secrets dir not found: {p}")

    for d in candidate_secrets_dirs():
        if dir_has_client_secrets(d):
            return d

    searched = ", ".join(str(d) for d in candidate_secrets_dirs()[:6])
    raise SecretsError(
        "No client secrets found. Need "
        f"{CLIENT_PRIV_NAME} and {NODE_PUB_NAME} under one of: "
        f"%LOCALAPPDATA%\\Programs\\RestorePrivacy\\secrets, "
        f"%USERPROFILE%\\.restore-privacy\\secrets, or next to the app. "
        f"(Also checked: {searched}…)"
    )


def load_client_private_key(secrets_dir: Path | None = None) -> Ed25519PrivateKey:
    d = resolve_secrets_dir(secrets_dir)
    raw = (d / CLIENT_PRIV_NAME).read_bytes()
    if len(raw) != 32:
        raise SecretsError(f"{CLIENT_PRIV_NAME} must be 32 raw bytes")
    return Ed25519PrivateKey.from_private_bytes(raw)


def load_node_elgamal_public(secrets_dir: Path | None = None) -> ElGamalPublicKey:
    d = resolve_secrets_dir(secrets_dir)
    raw = (d / NODE_PUB_NAME).read_bytes()
    return ElGamalPublicKey.import_bytes(raw)


def secrets_present(secrets_dir: Path | None = None) -> bool:
    try:
        if secrets_dir is not None:
            return dir_has_client_secrets(Path(secrets_dir))
        resolve_secrets_dir()
        return True
    except SecretsError:
        return False


def provision_secrets_files(
    dest_dir: Path,
    source_dir: Path | None = None,
) -> list[str]:
    """Copy product admission files into dest_dir. Never copies node_elgamal.priv.

    Returns list of basenames written. Used by the Windows installer.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    sources: list[Path] = []
    if source_dir is not None:
        sources.append(Path(source_dir))
    sources.extend(candidate_secrets_dirs())
    # Prefer first source that has both files
    src: Path | None = None
    for s in sources:
        if dir_has_client_secrets(s):
            src = s
            break
    if src is None:
        return written
    for name in (CLIENT_PRIV_NAME, NODE_PUB_NAME):
        sp = src / name
        if sp.is_file():
            target = dest_dir / name
            target.write_bytes(sp.read_bytes())
            try:
                os.chmod(target, 0o600)
            except OSError:
                pass
            written.append(name)
    return written

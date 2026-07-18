"""Load / generate product client admission keys (never commit privkeys to git).

Per-device model (0.1.3+):
- Each install generates a unique Ed25519 private key on first run and stores it
  only in local device-private secrets dirs.
- Packages may ship ``node_elgamal.pub`` (public) so HELLO can encrypt to the node.
- Packages must **not** ship a shared ``client_ed25519.priv`` for all users.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from node.elgamal import ElGamalPublicKey
from node.handshake import (
    ed25519_priv_raw,
    ed25519_pub_raw,
    generate_client_admission_keypair,
)

CLIENT_PRIV_NAME = "client_ed25519.priv"
CLIENT_PUB_NAME = "client_ed25519.pub"
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
    try:
        exe = Path(sys.executable).resolve()
        out.append(exe.parent / "secrets")
        out.append(exe.parent.parent / "secrets")
    except Exception:
        pass
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        out.append(meipass / "secrets")
        out.append(meipass / "payload" / "secrets")
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
    dirs.append(Path("/opt/restore-privacy/secrets"))
    seen: set[str] = set()
    unique: list[Path] = []
    for d in dirs:
        key = str(d)
        if key not in seen:
            seen.add(key)
            unique.append(d)
    return unique


def preferred_writable_secrets_dir(explicit: str | Path | None = None) -> Path:
    """Directory where a new per-device key should be created (user-private)."""
    if explicit:
        return Path(explicit)
    env = os.environ.get("RPT_SECRETS_DIR", "").strip()
    if env:
        return Path(env)
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if local:
        return Path(local) / "Programs" / "RestorePrivacy" / "secrets"
    return Path.home() / ".restore-privacy" / "secrets"


def dir_has_node_pub(d: Path) -> bool:
    return d.is_dir() and (d / NODE_PUB_NAME).is_file()


def dir_has_client_secrets(d: Path) -> bool:
    return (
        d.is_dir()
        and (d / CLIENT_PRIV_NAME).is_file()
        and (d / NODE_PUB_NAME).is_file()
    )


def is_package_readonly_secrets_dir(d: Path) -> bool:
    """True for frozen/package payload paths — never trust client_ed25519.priv there.

    Shared product priv left in ``_internal/secrets`` or PyInstaller extract dirs
    must not be adopted as the device identity.
    """
    try:
        s = str(d.resolve()).replace("\\", "/").lower()
    except Exception:
        s = str(d).replace("\\", "/").lower()
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        try:
            mei = str(Path(sys._MEIPASS).resolve()).replace("\\", "/").lower()  # type: ignore[attr-defined]
            if s == mei or s.startswith(mei.rstrip("/") + "/"):
                return True
        except Exception:
            pass
    # Package layout markers (Windows onedir / older installer trees)
    markers = (
        "/_internal/",
        "/_internal",
        "/payload/secrets",
        "/payload/",
        "/_mei",
        "\\_mei",
    )
    # Normalize already lowercased with /
    for m in markers:
        if m in s:
            return True
    # Bare meipass-style extract folders
    if "/_mei" in s or s.endswith("_internal/secrets"):
        return True
    return False


def is_trusted_device_key_dir(d: Path) -> bool:
    """Writable locations where per-device keys are stored (not package bundles)."""
    if is_package_readonly_secrets_dir(d):
        return False
    try:
        resolved = d.resolve()
    except Exception:
        resolved = d
    trusted: list[Path] = [
        Path.home() / ".restore-privacy" / "secrets",
        preferred_writable_secrets_dir(),
    ]
    env = os.environ.get("RPT_SECRETS_DIR", "").strip()
    if env:
        trusted.append(Path(env))
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if local:
        trusted.append(Path(local) / "Programs" / "RestorePrivacy" / "secrets")
    for t in trusted:
        try:
            if resolved == t.resolve():
                return True
        except Exception:
            if str(resolved) == str(t):
                return True
    # Install tree secrets/ (not _internal)
    s = str(resolved).replace("\\", "/").lower()
    if s.endswith("/secrets") and "restoreprivacy" in s and "/_internal/" not in s:
        return True
    return False


def _find_node_pub(candidates: list[Path]) -> bytes | None:
    for d in candidates:
        p = d / NODE_PUB_NAME
        if p.is_file():
            return p.read_bytes()
    return None


def generate_and_persist_device_key(dest_dir: Path) -> Ed25519PrivateKey:
    """Create a new Ed25519 admission keypair and write it under dest_dir.

    Writes ``client_ed25519.priv`` (32 raw bytes) and ``client_ed25519.pub``.
    Does not touch ``node_elgamal.pub``.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    cpriv, cpub = generate_client_admission_keypair()
    priv_path = dest_dir / CLIENT_PRIV_NAME
    pub_path = dest_dir / CLIENT_PUB_NAME
    priv_path.write_bytes(ed25519_priv_raw(cpriv))
    pub_path.write_bytes(ed25519_pub_raw(cpub))
    for p in (priv_path, pub_path):
        try:
            os.chmod(p, 0o600 if p == priv_path else 0o644)
        except OSError:
            pass
    return cpriv


def priv_matches_any_package_resident_key(
    raw: bytes, candidates: list[Path] | None = None
) -> bool:
    """True if ``raw`` equals a client_ed25519.priv under a package/read-only tree.

    Used to rotate leftover shared product keys after upgrades from old installers
    that embedded the same priv for every user.
    """
    if len(raw) != 32:
        return False
    for d in candidates if candidates is not None else candidate_secrets_dirs():
        if not is_package_readonly_secrets_dir(d):
            continue
        p = d / CLIENT_PRIV_NAME
        try:
            if p.is_file() and p.read_bytes() == raw:
                return True
        except OSError:
            continue
    return False


def _rotate_device_key_if_shared(dest: Path, candidates: list[Path] | None = None) -> None:
    """If dest holds a priv that matches package-resident shared material, regenerate."""
    priv_path = dest / CLIENT_PRIV_NAME
    if not priv_path.is_file():
        return
    try:
        raw = priv_path.read_bytes()
    except OSError:
        return
    if priv_matches_any_package_resident_key(raw, candidates):
        try:
            priv_path.unlink()
        except OSError:
            pass
        pub = dest / CLIENT_PUB_NAME
        try:
            if pub.is_file():
                pub.unlink()
        except OSError:
            pass
        generate_and_persist_device_key(dest)


def ensure_device_admission_key(
    secrets_dir: str | Path | None = None,
) -> Path:
    """Ensure local device Ed25519 priv + node pub are available; generate priv if missing.

    Returns the secrets directory that holds both files.
    Idempotent: second call reuses the same private key bytes (unless that key
    is detected as a leftover shared package priv — then rotate once).

    When ``secrets_dir`` is set explicitly, bootstrap is confined to that directory
    (node pub must already be present there) so tests and custom installs do not
    leak keys from other candidate paths.
    """
    if secrets_dir is not None:
        dest = Path(secrets_dir)
        dest.mkdir(parents=True, exist_ok=True)
        if dir_has_client_secrets(dest):
            return dest
        if not (dest / NODE_PUB_NAME).is_file():
            raise SecretsError(
                f"secrets dir incomplete: {dest} "
                f"(need {NODE_PUB_NAME}; device {CLIENT_PRIV_NAME} is auto-generated)"
            )
        if not (dest / CLIENT_PRIV_NAME).is_file():
            generate_and_persist_device_key(dest)
        else:
            raw = (dest / CLIENT_PRIV_NAME).read_bytes()
            if len(raw) != 32:
                raise SecretsError(f"{CLIENT_PRIV_NAME} must be 32 raw bytes")
        return dest

    candidates = candidate_secrets_dirs()
    # Only reuse a client priv from trusted writable storage — never package/_internal
    for d in candidates:
        if dir_has_client_secrets(d) and is_trusted_device_key_dir(d):
            _rotate_device_key_if_shared(d, candidates)
            if dir_has_client_secrets(d):
                return d

    dest = preferred_writable_secrets_dir()
    dest.mkdir(parents=True, exist_ok=True)

    if not (dest / NODE_PUB_NAME).is_file():
        raw = _find_node_pub(candidates)
        if raw is None:
            searched = ", ".join(str(d) for d in candidates[:6])
            raise SecretsError(
                f"No {NODE_PUB_NAME} found. Packages should ship the node public key. "
                f"Checked: {searched}…"
            )
        (dest / NODE_PUB_NAME).write_bytes(raw)
        try:
            os.chmod(dest / NODE_PUB_NAME, 0o644)
        except OSError:
            pass

    # Always generate into writable dest when missing — ignore package-resident shared priv
    if not (dest / CLIENT_PRIV_NAME).is_file():
        generate_and_persist_device_key(dest)
    else:
        raw = (dest / CLIENT_PRIV_NAME).read_bytes()
        if len(raw) != 32:
            raise SecretsError(f"{CLIENT_PRIV_NAME} must be 32 raw bytes")
        _rotate_device_key_if_shared(dest, candidates)

    if not dir_has_client_secrets(dest):
        raise SecretsError(
            f"Failed to prepare device secrets in {dest} "
            f"(need {CLIENT_PRIV_NAME} and {NODE_PUB_NAME})"
        )
    return dest


def resolve_secrets_dir(explicit: str | Path | None = None) -> Path:
    """Resolve secrets dir, generating a per-device key on first run when needed."""
    return ensure_device_admission_key(explicit)


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
            p = Path(secrets_dir)
            if dir_has_client_secrets(p):
                return True
            # Can bootstrap if node pub is findable
            if dir_has_node_pub(p) or _find_node_pub(candidate_secrets_dirs(p)):
                return True
            return False
        for d in candidate_secrets_dirs():
            if dir_has_client_secrets(d) or dir_has_node_pub(d):
                return True
        return False
    except SecretsError:
        return False


def provision_secrets_files(
    dest_dir: Path,
    source_dir: Path | None = None,
    *,
    include_shared_client_priv: bool = False,
) -> list[str]:
    """Copy public node material into dest_dir. Never copies node_elgamal.priv.

    By default only ``node_elgamal.pub`` is provisioned — device Ed25519 keys are
    generated on first client run. Set ``include_shared_client_priv=True`` only
    for operator/dev tooling (not public installer packages).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    sources: list[Path] = []
    if source_dir is not None:
        sources.append(Path(source_dir))
    sources.extend(candidate_secrets_dirs())

    names = [NODE_PUB_NAME]
    if include_shared_client_priv:
        names.insert(0, CLIENT_PRIV_NAME)

    for name in names:
        if (dest_dir / name).is_file():
            written.append(name)
            continue
        for s in sources:
            sp = s / name
            if sp.is_file():
                target = dest_dir / name
                target.write_bytes(sp.read_bytes())
                try:
                    os.chmod(target, 0o600 if name.endswith(".priv") else 0o644)
                except OSError:
                    pass
                written.append(name)
                break
    return written


def packaging_must_not_ship_shared_client_priv() -> bool:
    """Policy flag used by tests / docs: public packages must not embed shared priv."""
    return True

"""Ensure residual ElGamal public pin is present for HELLO (portable algorithm).

Mirrors Android ``always open secrets/$pubName from package`` and the Apple
``ensureResidualPubInWritableDir`` path: when the residual dial host needs
the DE pin (RO/US monopin retired), copy that basename from package/candidate dirs into the writable
secrets directory before load. Never fall back to Iceland ``node_elgamal.pub``
for a non-IS monopin.

Used by unit/fixture tests on Windows; production Apple code ports this
contract into ``RptSecrets.ensureResidualPubInWritableDir``.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Sequence


class ResidualPubError(Exception):
    """Missing residual public pin (fail closed)."""


# Catalog monopin → public pin basename (same as Flutter residualNodePubNameForHost)
def residual_node_pub_name_for_host(host: str) -> str:
    h = (host or "").strip()
    if h == "178.105.187.178" or h.endswith("178.105.187.178"):
        return "de_node_elgamal.pub"
    if h == "5.223.48.8" or h.endswith("5.223.48.8"):
        return "sg_node_elgamal.pub"
    # Retired US monopin — heal to DE pin (entry prefs normalize US → DE)
    if h == "5.161.242.85" or h.endswith("5.161.242.85"):
        return "de_node_elgamal.pub"
    # Stale RO host: exit pin file now holds DE public material
    if h == "185.146.232.107" or h.endswith("185.146.232.107"):
        return "exit_node_elgamal.pub"
    if h == "82.221.101.241" or h.endswith("82.221.101.241"):
        return "node_elgamal.pub"
    return "de_node_elgamal.pub"


NODE_PUB = "node_elgamal.pub"


def ensure_residual_pub_in_writable_dir(
    writable_dir: Path | str,
    residual_host: str,
    candidate_dirs: Sequence[Path | str],
    *,
    min_size: int = 32,
) -> Path:
    """Copy residual-required public pin into *writable_dir* from candidates.

    Always refreshes from the first candidate that has the basename when found
    (heals stale keys). If no package candidate has the pin:
    - IS (node_elgamal.pub): keep existing writable file if valid
    - Non-IS without package pin: raise :class:`ResidualPubError` (never substitute Iceland pin for DE)

    Returns path to the pin under *writable_dir*.
    """
    wdir = Path(writable_dir)
    wdir.mkdir(parents=True, exist_ok=True)
    pub_name = residual_node_pub_name_for_host(residual_host)
    dest = wdir / pub_name

    source: Path | None = None
    for raw in candidate_dirs:
        cand = Path(raw) / pub_name
        if cand.is_file() and cand.stat().st_size >= min_size:
            source = cand
            break

    if source is not None:
        # Overwrite refresh (Android-style package → filesDir)
        if source.resolve() != dest.resolve():
            shutil.copy2(source, dest)
        if not dest.is_file() or dest.stat().st_size < min_size:
            raise ResidualPubError(
                f"failed to install {pub_name} into {wdir}"
            )
        return dest

    # No package source
    if dest.is_file() and dest.stat().st_size >= min_size:
        return dest

    if pub_name != NODE_PUB:
        raise ResidualPubError(
            f"Missing {pub_name} for residual host {residual_host or '(unknown)'} "
            f"— refuse Iceland entry pub fallback (RO/US HELLO would use wrong key)"
        )
    raise ResidualPubError(f"Missing {pub_name} in {wdir}")


def load_residual_node_pub(
    writable_dir: Path | str,
    residual_host: str,
    candidate_dirs: Sequence[Path | str],
    *,
    min_size: int = 32,
) -> bytes:
    """Ensure then load residual node public pin bytes (fail closed)."""
    path = ensure_residual_pub_in_writable_dir(
        writable_dir,
        residual_host,
        candidate_dirs,
        min_size=min_size,
    )
    data = path.read_bytes()
    if len(data) < min_size:
        raise ResidualPubError(f"{path.name} too short ({len(data)} bytes)")
    # Defense: loaded basename must match residual host requirement
    want = residual_node_pub_name_for_host(residual_host)
    if path.name != want:
        raise ResidualPubError(
            f"loaded {path.name} but residual host requires {want}"
        )
    return data


# Catalog public pin basenames (DE / SG + exit alias) — never private keys.
# exit_node_elgamal.pub mirrors DE pin for multi-hop residual-via-exit.
CATALOG_PUBLIC_PUBS: tuple[str, ...] = (
    "node_elgamal.pub",
    "de_node_elgamal.pub",
    "sg_node_elgamal.pub",
    "exit_node_elgamal.pub",
)


def seed_catalog_public_keys(
    dest_dir: Path | str,
    candidate_dirs: Sequence[Path | str],
    *,
    min_size: int = 32,
    overwrite: bool = True,
) -> list[str]:
    """Copy all catalog public pins found in *candidate_dirs* into *dest_dir*.

    Used by host pre-seed into App Group / ``~/.restore-privacy/secrets`` so the
    Packet Tunnel extension (IS-only seed historically) can HELLO to RO/DE.
    Returns list of basenames installed.
    """
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    installed: list[str] = []
    for name in CATALOG_PUBLIC_PUBS:
        source: Path | None = None
        for raw in candidate_dirs:
            cand = Path(raw) / name
            if cand.is_file() and cand.stat().st_size >= min_size:
                source = cand
                break
        if source is None:
            continue
        out = dest / name
        if overwrite or not out.is_file():
            if source.resolve() != out.resolve():
                shutil.copy2(source, out)
        if out.is_file() and out.stat().st_size >= min_size:
            installed.append(name)
    return installed


def preseed_shared_writable_for_residual_host(
    residual_host: str,
    *,
    host_package_secrets: Path | str,
    shared_writable_dirs: Sequence[Path | str],
    tunnel_bundle_secrets: Path | str | None = None,
    min_size: int = 32,
) -> bytes:
    """Host-side pre-seed before Packet Tunnel start (integrated layout).

    Layout modeled after production:
    - *host_package_secrets*: main app Resources/secrets (inject_apple_secrets)
    - *tunnel_bundle_secrets*: PacketTunnel.appex secrets (often missing RO/DE)
    - *shared_writable_dirs*: App Group and/or ``~/.restore-privacy/secrets``
      that the tunnel will load from (may start as IS-only)

    Seeds all catalog pubs from host package into each shared writable dir,
    then ensure+load residual pin for *residual_host*. Tunnel bundle alone is
    **not** required to contain DE when shared dirs were pre-seeded by host.
    """
    host_pkg = Path(host_package_secrets)
    candidates: list[Path] = [host_pkg]
    if tunnel_bundle_secrets is not None:
        candidates.append(Path(tunnel_bundle_secrets))

    for raw in shared_writable_dirs:
        w = Path(raw)
        seed_catalog_public_keys(w, candidates, min_size=min_size, overwrite=True)
        # Also ensure residual-specific pin (idempotent refresh)
        ensure_residual_pub_in_writable_dir(
            w, residual_host, candidates, min_size=min_size
        )

    # Tunnel load path: first shared writable only (App Group first)
    if not shared_writable_dirs:
        raise ResidualPubError("no shared writable dirs for tunnel residual HELLO")
    primary = Path(shared_writable_dirs[0])
    # Tunnel candidates: package may be invisible; shared writable must suffice
    return load_residual_node_pub(
        primary,
        residual_host,
        [primary, host_pkg],
        min_size=min_size,
    )

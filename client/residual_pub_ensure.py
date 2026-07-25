"""Ensure residual ElGamal public pin is present for HELLO (portable algorithm).

Mirrors Android ``always open secrets/$pubName from package`` and the Apple
``ensureResidualPubInWritableDir`` path: when the residual dial host needs
RO/DE pin, copy that basename from package/candidate dirs into the writable
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
    if h == "185.146.232.107" or h.endswith("185.146.232.107"):
        return "exit_node_elgamal.pub"
    if h == "167.233.224.5" or h.endswith("167.233.224.5"):
        return "de_node_elgamal.pub"
    return "node_elgamal.pub"


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
    - RO/DE: raise :class:`ResidualPubError` (never substitute Iceland pin)

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
            f"— refuse Iceland entry pub fallback (DE/RO HELLO would use wrong key)"
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

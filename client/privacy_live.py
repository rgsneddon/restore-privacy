"""Hot-apply privacy-scale prefs to a live residual session (no Tk).

Settings UI calls :func:`hot_apply_privacy_scale` after persisting prefs so
traffic shaping and outer obfuscation update the running residual path without
a mandatory Disconnect → Connect. Multi-hop path changes require residual
re-establish (HELLO/tunnel target); this module reports that need — the UI
invokes reconnect while keeping the control interactive.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from client.product_policy import (
    PrivacyScalePrefs,
    ResolvedPrivacyPolicy,
    load_privacy_scale_prefs,
    resolve_privacy_policy,
)
from node.traffic_shape import TrafficShapePolicy


@dataclass(frozen=True)
class HotApplyResult:
    """Outcome of applying privacy-scale prefs to a live (or idle) session."""

    policy: ResolvedPrivacyPolicy
    shaping_hot_applied: bool
    obfuscation_live: bool
    multihop_reconnect_needed: bool
    message: str
    was_connected: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "traffic_shape_enabled": self.policy.traffic_shape_enabled,
            "outer_obfuscation_enabled": self.policy.outer_obfuscation_enabled,
            "multihop_enabled": self.policy.multihop_enabled,
            "residual_vpn_core": self.policy.residual_vpn_core,
            "shaping_hot_applied": self.shaping_hot_applied,
            "obfuscation_live": self.obfuscation_live,
            "multihop_reconnect_needed": self.multihop_reconnect_needed,
            "was_connected": self.was_connected,
            "message": self.message,
        }


def prefs_from_product_settings(settings: Any) -> PrivacyScalePrefs:
    """Map ProductSettings (or any object with privacy_* attrs) to prefs."""
    return PrivacyScalePrefs(
        traffic_shape=bool(getattr(settings, "privacy_traffic_shape", True)),
        outer_obfuscation=bool(getattr(settings, "privacy_outer_obfuscation", True)),
        multihop=bool(getattr(settings, "privacy_multihop", False)),
    )


def hot_apply_privacy_scale(
    *,
    dataplane: Any = None,
    client: Any = None,
    prefs: Optional[PrivacyScalePrefs] = None,
    previous_multihop: Optional[bool] = None,
    connected: bool = False,
) -> HotApplyResult:
    """Apply resolved privacy-scale policy to the live residual session.

    - **Traffic shaping**: updates ``dataplane.apply_traffic_shape`` when a
      plane is present; else session crypto if connected client is provided.
    - **Outer obfuscation**: product wrap path reads resolved policy per
      packet after prefs are saved — marked live when prefs are applied
      (no disconnect required).
    - **Multi-hop**: if ``previous_multihop`` differs from the new resolved
      multi-hop enable flag while ``connected``, sets
      ``multihop_reconnect_needed`` so the UI can re-establish residual.

    Residual VPN core / admission / crypto are never disabled.
    """
    p = prefs if prefs is not None else load_privacy_scale_prefs()
    pol = resolve_privacy_policy(prefs=p)
    shape: TrafficShapePolicy = pol.traffic_shape_policy()

    shaping_hot = False
    if dataplane is not None and hasattr(dataplane, "apply_traffic_shape"):
        dataplane.apply_traffic_shape(shape)
        shaping_hot = True
    elif client is not None:
        sess = getattr(client, "session", None)
        crypto = getattr(sess, "crypto", None) if sess is not None else None
        if crypto is not None:
            crypto.traffic_shape = shape
            shaping_hot = True

    # Outer wrap: seal_packet / dataplane cover already call product policy each use
    obfuscation_live = True

    prev_mh = previous_multihop
    if prev_mh is None:
        prev_mh = pol.multihop_enabled
    mh_reconnect = bool(connected) and (bool(prev_mh) != bool(pol.multihop_enabled))

    parts = [
        f"shape={'on' if pol.traffic_shape_enabled else 'off'}",
        f"obfs={'on' if pol.outer_obfuscation_enabled else 'off'}",
        f"multihop={'on' if pol.multihop_enabled else 'off'}",
    ]
    if connected and shaping_hot:
        msg = (
            "Privacy scale hot-applied to live residual — "
            + ", ".join(parts)
            + ". Residual VPN core stays on."
        )
    elif connected and not shaping_hot:
        msg = (
            "Privacy scale saved while connected — outer obfuscation applies "
            "immediately; shaping applies when residual dataplane is active — "
            + ", ".join(parts)
            + "."
        )
    else:
        msg = (
            "Privacy scale saved — will apply on next Connect — "
            + ", ".join(parts)
            + ". Residual VPN core stays on."
        )
    if mh_reconnect:
        msg += " Multi-hop path changed — re-establishing residual connection…"

    return HotApplyResult(
        policy=pol,
        shaping_hot_applied=shaping_hot,
        obfuscation_live=obfuscation_live,
        multihop_reconnect_needed=mh_reconnect,
        message=msg,
        was_connected=bool(connected),
    )

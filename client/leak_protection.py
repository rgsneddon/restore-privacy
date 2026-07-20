"""DNS / WebRTC / common leak policy helpers for product clients.

- Product full-tunnel DNS is tunnel gateway only (see ``full_tunnel``).
- No public DNS fallback constants (1.1.1.1 / 8.8.8.8 / 9.9.9.9) on residual path.
- WebRTC mitigations: block STUN/mDNS ports under kill-switch; Android builder
  flags; document browser WebRTC as OS/browser-limited.
"""

from __future__ import annotations

from typing import Iterable

from client.full_tunnel import (
    DEFAULT_TUNNEL_DNS_SERVERS,
    DEFAULT_TUNNEL_GATEWAY,
    default_tunnel_dns_servers,
)

# Known public resolvers that must never appear as product residual DNS defaults
PUBLIC_DNS_BLOCKLIST: tuple[str, ...] = (
    "1.1.1.1",
    "1.0.0.1",
    "8.8.8.8",
    "8.8.4.4",
    "9.9.9.9",
    "149.112.112.112",
    "208.67.222.222",
    "208.67.220.220",
    "8.26.56.26",
)


def product_dns_servers() -> list[str]:
    """Shipped residual DNS plan — tunnel gateway only."""
    return default_tunnel_dns_servers()


def assert_no_public_dns_fallback(servers: Iterable[str]) -> list[str]:
    """Return violations if any public resolver is used as product DNS."""
    violations: list[str] = []
    for s in servers:
        ip = str(s).strip().split("%", 1)[0]
        if ip in PUBLIC_DNS_BLOCKLIST:
            violations.append(f"public DNS fallback not allowed: {ip}")
    if list(servers) != list(DEFAULT_TUNNEL_DNS_SERVERS) and not servers:
        violations.append("empty DNS list is not a tunnel gateway plan")
    return violations


def dns_leak_check_plan() -> dict:
    """Structural DNS leak check object driven by shipped defaults."""
    servers = product_dns_servers()
    return {
        "dns_servers": servers,
        "tunnel_gateway_only": servers == [DEFAULT_TUNNEL_GATEWAY],
        "public_fallback_violations": assert_no_public_dns_fallback(servers),
        "ok": servers == [DEFAULT_TUNNEL_GATEWAY]
        and not assert_no_public_dns_fallback(servers),
    }


def webrtc_leak_mitigations() -> dict:
    """Documented + enforceable WebRTC-related mitigations on product path."""
    return {
        "block_stun_udp_3478": True,
        "block_turn_udp_5349": True,
        "block_mdns_udp_5353": True,
        "android_vpn_blocking": True,
        "android_allow_bypass": False,
        "browser_webrtc_note": (
            "Browser WebRTC may still use local interfaces unless the OS VPN "
            "captures all apps (Android VpnService / Windows dual /1 + kill-switch). "
            "Disable WebRTC in the browser for maximum assurance."
        ),
        "kill_switch_required": True,
    }


def android_leak_builder_extras() -> dict:
    """Merge into Android VpnService builder config for leak posture."""
    from client.kill_switch import android_kill_switch_builder_flags

    flags = android_kill_switch_builder_flags()
    flags["dns"] = product_dns_servers()
    flags["disallowPublicDnsFallback"] = True
    return flags

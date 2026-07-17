"""Node configuration generation (pure; no secrets embedded)."""

from __future__ import annotations

import json
from typing import Any

from .nolog import apply_no_log_policy, assert_no_log_config, config_text_forbids_log_sinks
from .routing import assert_routing_enabled, routing_config_block

DEFAULT_LISTEN_PORT = 44044
DEFAULT_UI_PORT = 8080


def build_node_config(
    listen_host: str = "0.0.0.0",
    listen_port: int = DEFAULT_LISTEN_PORT,
    ui_port: int = DEFAULT_UI_PORT,
    secrets_dir: str = "/opt/restore-privacy/secrets",
) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "protocol": "RPT",
        "protocol_version": 2,
        "product": "restore-privacy-node",
        "description": (
            "Custom VPN node: ElGamal+Pedersen admission for RP client tunnel only; "
            "encrypted relay; no user-info logs. Not WireGuard/OpenVPN."
        ),
        "listen_host": listen_host,
        "listen_port": listen_port,
        "ListenPort": listen_port,
        "ui_host": "0.0.0.0",
        "ui_port": ui_port,
        "encrypted_tunnel": True,
        "tunnel_termination": True,
        "collect_user_data": False,
        "admission": {
            "method": "elgamal_pedersen_ed25519_allowlist",
            "require_authorized_client_key": True,
            "require_username_password": False,
            "open_to_public": False,
            "only_restore_privacy_client": True,
        },
        "secrets_dir": secrets_dir,
        "pool_start": "10.88.0.2",
        "pool_end": "10.88.0.254",
        "routing": routing_config_block(),
        "ui": {
            "title": "RESTORE PRIVACY",
            "show_client_count": True,
            "show_client_identities": False,
            "show_client_ips": False,
        },
    }
    return apply_no_log_policy(raw)


def render_node_config_text(config: dict[str, Any] | None = None) -> str:
    cfg = config if config is not None else build_node_config()
    lines = [
        "# restore-privacy RPT node configuration",
        "# Custom encrypted tunnel (not WireGuard / not OpenVPN)",
        f"Protocol = {cfg['protocol']}",
        f"ProtocolVersion = {cfg['protocol_version']}",
        f"ListenHost = {cfg['listen_host']}",
        f"ListenPort = {cfg['listen_port']}",
        f"UIPort = {cfg['ui_port']}",
        "EncryptedTunnel = true",
        "TunnelTermination = true",
        "CollectUserData = false",
        "AdmissionMethod = elgamal_pedersen_ed25519_allowlist",
        "RequireAuthorizedClientKey = true",
        "RequireUsernamePassword = false",
        "OpenToPublic = false",
        "OnlyRestorePrivacyClient = true",
        f"TunnelIface = {cfg['routing']['tunnel_iface']}",
        f"EnableIPForward = true",
        f"NATMasquerade = true",
        "UITitle = RESTORE PRIVACY",
        "UIShowClientCount = true",
        "UIShowClientIdentities = false",
        "LoggingEnabled = false",
        "ConnectionLog = false",
        "SessionLog = false",
        "AccessLog = false",
        "TrafficLog = false",
        "UserInfoLog = false",
        "LogFile = none",
        "LogPath = none",
        "ConnectionLogPath = none",
    ]
    text = "\n".join(lines) + "\n"
    if not config_text_forbids_log_sinks(text):
        raise RuntimeError("config failed no-log check")
    return text


def render_node_config_json(config: dict[str, Any] | None = None) -> str:
    cfg = config if config is not None else build_node_config()
    return json.dumps(cfg, indent=2, sort_keys=True) + "\n"


def validate_node_config(config: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    if config.get("protocol") != "RPT":
        violations.append("protocol must be RPT")
    if not config.get("encrypted_tunnel"):
        violations.append("encrypted_tunnel required")
    adm = config.get("admission") or {}
    if not adm.get("require_authorized_client_key"):
        violations.append("require_authorized_client_key must be True")
    if adm.get("open_to_public"):
        violations.append("open_to_public must be False")
    if adm.get("require_username_password"):
        violations.append("must not require username/password user accounts")
    if not adm.get("only_restore_privacy_client"):
        violations.append("only_restore_privacy_client must be True")
    if config.get("collect_user_data"):
        violations.append("collect_user_data must be False")
    ui = config.get("ui") or {}
    if ui.get("title") != "RESTORE PRIVACY":
        violations.append("ui.title must be RESTORE PRIVACY")
    if ui.get("show_client_identities") or ui.get("show_client_ips"):
        violations.append("ui must not show identities/ips")
    violations.extend(assert_no_log_config(config))
    violations.extend(assert_routing_enabled(config))
    return violations

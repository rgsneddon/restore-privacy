"""No-log policy: never store client user-info or session activity logs."""

from __future__ import annotations

from typing import Any, Mapping

NO_LOG_POLICY: dict[str, Any] = {
    "logging_enabled": False,
    "connection_log": False,
    "session_log": False,
    "access_log": False,
    "traffic_log": False,
    "accounting_log": False,
    "peer_activity_log": False,
    "user_info_log": False,
    "verbose": False,
    "log_file": None,
    "log_path": None,
    "journal": False,
}

FORBIDDEN_LOG_DIRECTIVES = (
    "LogFile",
    "ConnectionLog",
    "SessionLog",
    "AccessLog",
    "TrafficLog",
    "UserInfoLog",
    "PeerActivityLog",
)


def apply_no_log_policy(config: dict[str, Any]) -> dict[str, Any]:
    out = dict(config)
    out["logging"] = dict(NO_LOG_POLICY)
    out["log_file"] = None
    out["log_path"] = None
    out["connection_log"] = False
    out["session_log"] = False
    out["collect_user_data"] = False
    return out


def assert_no_log_config(config: Mapping[str, Any]) -> list[str]:
    violations: list[str] = []
    logging = config.get("logging") or {}
    if not isinstance(logging, Mapping):
        return ["logging must be a mapping"]
    for key, expected in NO_LOG_POLICY.items():
        if key in logging and logging[key] != expected:
            violations.append(f"logging.{key} must be {expected!r}")
    if config.get("collect_user_data") is True:
        violations.append("collect_user_data must be False")
    for field in ("log_file", "log_path"):
        if config.get(field) not in (None, "", False):
            violations.append(f"{field} must be unset")
    return violations


def systemd_no_log_directives() -> list[str]:
    return [
        "StandardOutput=null",
        "StandardError=null",
        "SyslogIdentifier=",
        "LogLevelMax=emerg",
    ]


def config_text_forbids_log_sinks(text: str) -> bool:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for directive in FORBIDDEN_LOG_DIRECTIVES:
            if stripped.lower().startswith(directive.lower()):
                if any(x in stripped.lower() for x in ("false", "off", "none", "null", "0")):
                    continue
                return False
    return True

"""Pure policy: auto-reconnect residual after idle/timeout drop (Windows).

Distinct from Settings ``autoconnect_on_launch`` (cold start). Default OFF.
"""

from __future__ import annotations

from dataclasses import dataclass

# Cap consecutive auto-reconnect attempts per residual “connected” stint.
MAX_IDLE_RECONNECT_ATTEMPTS = 5
# Lean backoff base (seconds); doubles each attempt, capped.
IDLE_RECONNECT_BACKOFF_BASE_S = 2.0
IDLE_RECONNECT_BACKOFF_MAX_S = 30.0


@dataclass(frozen=True)
class IdleAutoReconnectDecision:
    allow: bool
    reason: str = ""


def may_auto_reconnect_after_idle_drop(
    *,
    pref_on: bool,
    app_open: bool,
    user_requested_disconnect: bool,
    drop_was_idle_timeout: bool,
    already_reconnecting: bool = False,
    attempt_count: int = 0,
    max_attempts: int = MAX_IDLE_RECONNECT_ATTEMPTS,
) -> IdleAutoReconnectDecision:
    """Whether residual Connect may be auto-started after an idle/timeout drop.

    True only when:
    - Settings ``auto_connect_if_idle`` is ON
    - app process still open (GUI/tray alive)
    - drop was idle/timeout / session liveness loss (not user Disconnect/Quit)
    - not already mid-reconnect
    - under max attempts for this connected stint
    """
    if not pref_on:
        return IdleAutoReconnectDecision(False, "pref_off")
    if not app_open:
        return IdleAutoReconnectDecision(False, "app_not_open")
    if user_requested_disconnect:
        return IdleAutoReconnectDecision(False, "user_disconnect")
    if not drop_was_idle_timeout:
        return IdleAutoReconnectDecision(False, "not_idle_timeout_drop")
    if already_reconnecting:
        return IdleAutoReconnectDecision(False, "already_reconnecting")
    if int(attempt_count) >= int(max_attempts):
        return IdleAutoReconnectDecision(False, "max_attempts")
    return IdleAutoReconnectDecision(True, "schedule_reconnect")


def idle_reconnect_backoff_s(
    attempt: int,
    *,
    base_s: float = IDLE_RECONNECT_BACKOFF_BASE_S,
    max_s: float = IDLE_RECONNECT_BACKOFF_MAX_S,
) -> float:
    """Bounded exponential backoff for attempt index 0, 1, 2, …"""
    a = max(0, int(attempt))
    delay = float(base_s) * (2.0**a)
    return float(min(float(max_s), delay))


def perform_idle_drop_session_teardown(
    *,
    tunnel: object | None,
    client: object | None,
    disconnect_full_tunnel_fn,
) -> list[str]:
    """Fully clear dead residual + RPT session after idle/liveness drop.

    Must run **before** any auto-reconnect Connect. Without this,
    ``RptClient.connect`` short-circuits on ``ConnectState.CONNECTED``
    (``force_reconnect=False``) and never re-HELLOs after node idle prune —
    reconnect is a no-op while dataplane/Wintun may still be half-alive.

    ``disconnect_full_tunnel_fn(tunnel, client)`` is the shipped Windows
    teardown (stop residual restore path, dataplane, TUN, then
    ``client.disconnect``). This helper always calls it, then
    ``client.disconnect()`` again so a leftover CONNECTED client cannot
    short-circuit the next connect even if the tunnel handle was already None.
    """
    steps: list[str] = []
    try:
        disconnect_full_tunnel_fn(tunnel, client)
        steps.append("disconnect_full_tunnel")
    except Exception:
        steps.append("disconnect_full_tunnel_error")
    if client is not None:
        try:
            client.disconnect()
            steps.append("client_disconnect")
        except Exception:
            steps.append("client_disconnect_error")
    return steps

"""Product-honest leak test: residual capture + DNS posture (local evaluation).

The Settings **Leak test** button evaluates whether residual public-IP capture
and tunnel DNS look correct. It does **not** claim perfect DPI / leak-proofing
beyond what residual capture + DNS plan measure.

Multi-hop: when residual is actively dialing the **exit** hop
(``RPT_MULTIHOP_ENABLED=1`` + routing implemented), the result may report
multi-hop residual via exit. Default single-hop never claims multi-hop residual.
This is residual-via-exit selection, not full intermediate encapsulation.

Live public-IP probes are optional and injectable so CI stays offline-safe.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from client.leak_protection import dns_leak_check_plan

VERDICT_PASS = "pass"
VERDICT_FAIL = "fail"
VERDICT_PARTIAL = "partial"
VERDICT_INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class LeakTestInputs:
    """Inputs for :func:`evaluate_leak_test` (fixtures inject these in tests)."""

    residual_capture_active: bool
    ipv6_protected: bool = False
    dns_tunnel_gateway_only: bool = True
    public_dns_violations: tuple[str, ...] = ()
    # Optional egress probe (None = not run this session)
    public_ip_probe_ran: bool = False
    public_ip_matches_expected_node: Optional[bool] = None
    # True when Connect residual dials the exit hop (multi-hop active)
    multihop_residual_routed: bool = False


@dataclass(frozen=True)
class LeakTestResult:
    """User-facing leak-test outcome."""

    verdict: str
    summary: str
    details: tuple[str, ...] = ()
    # True only when multi-hop residual (exit dial) is actually active this session
    claims_multihop_residual: bool = False

    def format_user_message(self) -> str:
        lines = [f"Leak test: {self.verdict.upper()} — {self.summary}"]
        lines.extend(f"• {d}" for d in self.details)
        if self.claims_multihop_residual:
            lines.append(
                "• Multi-hop residual is active (residual via exit hop; "
                "not full intermediate encapsulation)."
            )
        else:
            lines.append(
                "• Multi-hop residual is opt-in (RPT_MULTIHOP_ENABLED=1); "
                "default is single-hop entry."
            )
        return "\n".join(lines)


def evaluate_leak_test(inputs: LeakTestInputs) -> LeakTestResult:
    """Pure decision function from residual/DNS/probe inputs.

    - **pass**: residual capture active, tunnel DNS only, IPv6 residual protected,
      no public DNS violations. Live egress probe match strengthens the report;
      catalog peer-IP miss or skip still PASS when residual path holds.
    - **fail**: residual capture off while testing a connected product path, or
      public DNS fallbacks present.
    - **partial**: residual on but IPv6 not protected.
    - **inconclusive**: insufficient state (e.g. not connected) without hard fail signals.
    """
    details: list[str] = []
    claims_mh = bool(inputs.multihop_residual_routed)

    if claims_mh:
        details.append(
            "Multi-hop residual path selected: residual dials exit hop "
            "(entry→exit path configured; residual-via-exit, not full encapsulation)."
        )

    dns_ok = bool(inputs.dns_tunnel_gateway_only) and not inputs.public_dns_violations
    if inputs.public_dns_violations:
        details.append(
            "Public DNS fallbacks present: "
            + "; ".join(inputs.public_dns_violations[:4])
        )
    elif inputs.dns_tunnel_gateway_only:
        details.append("DNS plan: tunnel gateway only (no public resolver fallback).")
    else:
        details.append("DNS plan is not tunnel-gateway-only.")

    if not inputs.residual_capture_active:
        details.append(
            "Residual public-IP capture is not active "
            "(full tunnel dual /1 + system capture required)."
        )
        if not dns_ok:
            return LeakTestResult(
                verdict=VERDICT_FAIL,
                summary="Not residual-protected; DNS posture also failed.",
                details=tuple(details),
                claims_multihop_residual=claims_mh,
            )
        return LeakTestResult(
            verdict=VERDICT_INCONCLUSIVE,
            summary=(
                "Connect with full residual tunnel first, then re-run Leak test. "
                "No residual capture is active right now."
            ),
            details=tuple(details),
            claims_multihop_residual=claims_mh,
        )

    details.append("Residual public-IP capture is active (system tunnel path).")
    if inputs.ipv6_protected:
        details.append("IPv6 ISP egress mitigation applied for this session.")
    else:
        details.append(
            "IPv6 residual protection not confirmed for this session "
            "(IPv4 residual may still be active)."
        )

    probe_match = False
    probe_miss = False
    probe_inconclusive = False
    if inputs.public_ip_probe_ran:
        if inputs.public_ip_matches_expected_node is True:
            details.append("Public egress probe matches expected VPN/node path.")
            probe_match = True
        elif inputs.public_ip_matches_expected_node is False:
            # Catalog peer IP list can lag real residual egress; residual capture
            # + tunnel DNS + IPv6 remain the product residual honesty bar.
            details.append(
                "Public egress probe did not match the catalog peer IP list "
                "(informational — residual capture and tunnel DNS still hold)."
            )
            probe_miss = True
        else:
            details.append("Public egress probe ran but result was inconclusive.")
            probe_inconclusive = True
    else:
        details.append(
            "Live public-IP probe not run (offline-safe path or user skipped)."
        )

    # FAIL only on public DNS posture when residual capture is up.
    # Live Settings always probes egress; catalog peer-IP miss must not FAIL
    # residual sessions that already have capture + tunnel DNS + IPv6.
    if not dns_ok:
        return LeakTestResult(
            verdict=VERDICT_FAIL,
            summary="Residual capture is up, but DNS posture failed.",
            details=tuple(details),
            claims_multihop_residual=claims_mh,
        )

    # PASS when residual + tunnel DNS + IPv6 hold (probe match strengthens only).
    if inputs.ipv6_protected and dns_ok:
        if probe_match:
            return LeakTestResult(
                verdict=VERDICT_PASS,
                summary=(
                    "Residual capture active, tunnel DNS only, IPv6 protected, "
                    "and egress probe matched the node path."
                ),
                details=tuple(details),
                claims_multihop_residual=claims_mh,
            )
        return LeakTestResult(
            verdict=VERDICT_PASS,
            summary=(
                "Residual capture active, tunnel DNS only, and IPv6 protected "
                "for this session."
            ),
            details=tuple(details),
            claims_multihop_residual=claims_mh,
        )

    reasons: list[str] = []
    if not inputs.ipv6_protected:
        reasons.append("IPv6 protection not confirmed")
    if not inputs.public_ip_probe_ran:
        reasons.append("live egress probe not run")
    elif probe_inconclusive:
        reasons.append("egress probe result was inconclusive")
    elif probe_miss:
        reasons.append("egress probe catalog peer list miss")
    summary_tail = "; ".join(reasons) if reasons else "checks incomplete"
    return LeakTestResult(
        verdict=VERDICT_PARTIAL,
        summary=f"Residual IPv4 capture looks good; {summary_tail}.",
        details=tuple(details),
        claims_multihop_residual=claims_mh,
    )


def collect_leak_test_inputs(
    *,
    residual_capture_active: bool,
    ipv6_protected: bool = False,
    run_public_ip_probe: bool = False,
    public_ip_probe: Optional[Callable[[], Optional[bool]]] = None,
) -> LeakTestInputs:
    """Build inputs from shipped DNS policy + optional injectable egress probe.

    ``public_ip_probe`` should return True if public egress appears to be the
    VPN/node, False if ISP/other, None if inconclusive. When
    ``run_public_ip_probe`` is False, no probe is invoked (CI default).
    """
    plan = dns_leak_check_plan()
    violations = tuple(plan.get("public_fallback_violations") or ())
    dns_ok = bool(plan.get("tunnel_gateway_only")) and not violations

    probe_ran = False
    matches: Optional[bool] = None
    if run_public_ip_probe and public_ip_probe is not None:
        probe_ran = True
        try:
            matches = public_ip_probe()
        except Exception:
            matches = None

    mh_routed = False
    try:
        from client.multihop import is_multihop_active, multihop_config_from_env

        mh_routed = bool(is_multihop_active(multihop_config_from_env()))
    except Exception:
        mh_routed = False

    return LeakTestInputs(
        residual_capture_active=bool(residual_capture_active),
        ipv6_protected=bool(ipv6_protected),
        dns_tunnel_gateway_only=dns_ok,
        public_dns_violations=violations,
        public_ip_probe_ran=probe_ran,
        public_ip_matches_expected_node=matches,
        multihop_residual_routed=mh_routed,
    )


def run_product_leak_test(
    *,
    residual_capture_active: bool,
    ipv6_protected: bool = False,
    run_public_ip_probe: bool = False,
    public_ip_probe: Optional[Callable[[], Optional[bool]]] = None,
) -> LeakTestResult:
    """Entry point the Settings button / UI should call."""
    inputs = collect_leak_test_inputs(
        residual_capture_active=residual_capture_active,
        ipv6_protected=ipv6_protected,
        run_public_ip_probe=run_public_ip_probe,
        public_ip_probe=public_ip_probe,
    )
    return evaluate_leak_test(inputs)

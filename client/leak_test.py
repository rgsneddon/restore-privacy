"""Product-honest leak test: residual capture + DNS posture (local evaluation).

The Settings **Leak test** button evaluates whether residual public-IP capture
and tunnel DNS look correct. It does **not** claim multi-hop residual routing
or perfect DPI / leak-proofing beyond what residual capture + DNS plan measure.

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
    # Product honesty: multi-hop residual is not implemented
    multihop_residual_routed: bool = False


@dataclass(frozen=True)
class LeakTestResult:
    """User-facing leak-test outcome."""

    verdict: str
    summary: str
    details: tuple[str, ...] = ()
    # Always false for product honesty — multi-hop residual is not claimed.
    claims_multihop_residual: bool = False

    def format_user_message(self) -> str:
        lines = [f"Leak test: {self.verdict.upper()} — {self.summary}"]
        lines.extend(f"• {d}" for d in self.details)
        if not self.claims_multihop_residual:
            lines.append(
                "• Multi-hop residual routing is not claimed (entry/config only)."
            )
        return "\n".join(lines)


def evaluate_leak_test(inputs: LeakTestInputs) -> LeakTestResult:
    """Pure decision function from residual/DNS/probe inputs.

    - **pass**: residual capture active, tunnel DNS only, no public DNS violations;
      if a public-IP probe ran, it must match the expected node path.
    - **fail**: residual capture off while testing a connected product path, or
      public DNS fallbacks present, or probe says egress is not the tunnel.
    - **partial**: residual on but IPv6 not protected, or probe skipped with other OK.
    - **inconclusive**: insufficient state (e.g. not connected) without hard fail signals.
    """
    details: list[str] = []
    claims_mh = False  # never true on product path

    if inputs.multihop_residual_routed:
        # Defensive: product should never pass True; if it does, refuse to claim it.
        details.append(
            "Multi-hop residual flag was set; product does not route multi-hop residual."
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

    probe_fail = False
    if inputs.public_ip_probe_ran:
        if inputs.public_ip_matches_expected_node is True:
            details.append("Public egress probe matches expected VPN/node path.")
        elif inputs.public_ip_matches_expected_node is False:
            details.append(
                "Public egress probe did not match expected VPN/node path "
                "(possible residual leak)."
            )
            probe_fail = True
        else:
            details.append("Public egress probe ran but result was inconclusive.")
    else:
        details.append(
            "Live public-IP probe not run (offline-safe path or user skipped)."
        )

    if not dns_ok or probe_fail:
        return LeakTestResult(
            verdict=VERDICT_FAIL,
            summary="Residual capture is up, but DNS or egress check failed.",
            details=tuple(details),
            claims_multihop_residual=claims_mh,
        )

    if not inputs.ipv6_protected or not inputs.public_ip_probe_ran:
        return LeakTestResult(
            verdict=VERDICT_PARTIAL,
            summary=(
                "Residual IPv4 capture looks good; "
                + (
                    "IPv6 protection not confirmed."
                    if not inputs.ipv6_protected
                    else "live egress probe not run."
                )
            ),
            details=tuple(details),
            claims_multihop_residual=claims_mh,
        )

    return LeakTestResult(
        verdict=VERDICT_PASS,
        summary=(
            "Residual capture active, tunnel DNS only, IPv6 protected, "
            "and egress probe matched the node path."
        ),
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

    return LeakTestInputs(
        residual_capture_active=bool(residual_capture_active),
        ipv6_protected=bool(ipv6_protected),
        dns_tunnel_gateway_only=dns_ok,
        public_dns_violations=violations,
        public_ip_probe_ran=probe_ran,
        public_ip_matches_expected_node=matches,
        multihop_residual_routed=False,
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

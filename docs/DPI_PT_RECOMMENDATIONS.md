# DPI-undetectability & pluggable-transport parity — recommendations only

## Current product honesty (baseline)

Restore Privacy residual traffic already ships **mitigations**, not
**DPI-undetectability** and not **full Tor pluggable-transport (PT) parity**:

| Shipped surface | Role | Honest limit |
|-----------------|------|--------------|
| `node/obfuscation.py` | Outer **QUIC-mimic-class** wrap; hides clear `RPT2` magic on UDP | Not probe-resistant PT; fixed outer key is **not** authentication |
| `node/traffic_shape.py` | Padding / send jitter / cover frames on DATA path | Softens size/timing fingerprints; not “looks like ordinary web” |
| Transparency copy (`DPI_MITIGATION_*`) | UI disclaimer | Explicitly not DPI-undetectability / PT parity |

Full **PT parity** is a **system**: client + intermediate (bridge/proxy/CDN) +
probe resistance + active-attacker model — not a single env toggle on residual
UDP to FlokiNET.

**Moving target:** Any “undetectability” claim is jurisdiction- and year-
dependent. Recommendations below are **design options**, not guarantees.

---

## Can RPT apply stronger methods?

**Yes, as layered architecture options** — typically by placing a **pluggable
transport or CDN/decoy channel under or in front of** residual RPT (or replacing
bare residual UDP with a PT pipe that carries RPT frames).

They should be added as **optional residual underlays**, not marketed as the
default product guarantee, unless you invest in continuous censor testing.

---

## Recommended approaches (≥5 named classes)

### 1. obfs4-class (look-like-nothing, randomized high-entropy)

**What:** Tor **obfs4** / similar “looks like random noise” transports over TCP
(with handshake that resists active probing of the bridge).

**Improves:** Hides RPT/QUIC-mimic fingerprints behind a mature PT; good against
classifiers looking for known VPN/QUIC shapes; bridges can be distributed out
of band.

**Does not claim:** Automatic domain-fronting; immunity to IP blocklists of
known bridges; free lunch on mobile battery/CPU.

**RPT fit:** Run residual RPT frames inside an obfs4 client↔bridge pipe, then
bridge→entry (or bridge terminates and re-Hellos). Requires **bridge fleet**
ops, not only Iceland/Romania residual IPs.

### 2. meek-class / domain fronting (HTTPS to big CDN front)

**What:** Client speaks TLS to a high-volume front domain; origin routing
delivers to a meek-style reflector that forwards to the VPN/bridge.

**Improves:** Traffic looks like ordinary HTTPS to a popular host; hard to
block without collateral damage (when fronting still works).

**Does not claim:** Permanent availability — **cloud policy often kills** true
domain fronting; cost and ToS risk; not “private” from the CDN operator.

**RPT fit:** meek-like front → RPT HELLO/DATA. Honest limit: third-party CDN
can change rules without notice. Prefer only as **opt-in hard-mode** residual
path.

### 3. Snowflake-class (WebRTC / browser proxy swarm)

**What:** Tor **Snowflake**: short-lived browser proxies + broker; WebRTC data
channels look like video-call-ish traffic.

**Improves:** Massive, ephemeral proxy diversity; hard to enumerate all
endpoints; good for censored last-mile.

**Does not claim:** Low latency equal to direct residual UDP; stable throughput;
zero broker dependency.

**RPT fit:** Snowflake (or similar) as **access link** into an RPT entry or
bridge. Heavy client stack; not a drop-in for current Windows PE residual alone.

### 4. WebTunnel / Conjure-class (HTTPS camouflage / refraction)

**What:** **WebTunnel** (HTTPS camouflage through ordinary web hosts) and
**Conjure**-class refraction networking (tap/decoy on ISP-scale infrastructure
research deployments).

**Improves:** Stronger “looks like normal HTTPS/web” story than bare UDP;
WebTunnel is closer to deployable product PT than full Conjure research stack.

**Does not claim:** Conjure-class is not something a single VPS vendor ships
off-the-shelf; research deployments and ISP cooperation differ from self-host
FlokiNET.

**RPT fit:** Prefer **WebTunnel-class** underlay for product roadmap realism;
treat Conjure as long-horizon research partnership, not next release.

### 5. Full TLS-mimic / VPN-over-CDN / “masquerade as mainstream app”

**What:** Residual tunnel fully inside **TLS 1.3** (or HTTP/2/3) to a
CDN/worker that unwraps to RPT; or commercial “stealth VPN” patterns that
impersonate common apps.

**Improves:** Deep packet inspection that only allows popular TLS SNI/ALPN
patterns; works with existing HTTPS allow-lists.

**Does not claim:** Immunity to active TLS fingerprint (JA3/JA4) or endpoint
blocking; may reintroduce **third-party** (CDN) metadata exposure vs pure
FlokiNET residual honesty.

**RPT fit:** Natural extension of product QUIC-mimic **outer** layer toward
real TLS termination + ALPN. Larger rewrite than more XOR/padding on UDP.

### 6. Multi-hop residual + PT only on the first hop (complement)

**What:** Keep product **entry→exit residual-via-exit** for egress diversity;
put **PT only on client→entry** (or client→bridge).

**Improves:** Separates “looks like VPN to ISP” problem from “egress IP
jurisdiction” problem.

**Does not claim:** Hides that a VPN is in use from the PT bridge operator or
destination sites; not full mesh onion PT.

---

## What full PT parity would require (checklist, not a toggle)

1. **Client** PT library + UI for bridge lines / front domains / snowflake.  
2. **Bridge/proxy fleet** (or CDN workers) with **probe resistance**.  
3. **Bridge distribution** channel (not only public status downloads).  
4. **Active testing** against real classifiers (not unit tests alone).  
5. **Honest UX:** “hard-mode residual” vs default Iceland residual.  
6. **Ops privacy:** bridges must not undo node **no-log / no-outbound**
   defaults without an explicit gated design.

---

## Practical recommendation order for Restore Privacy

| Priority | Recommendation | Why |
|----------|----------------|-----|
| 1 | Keep current mitigations; **never market as undetectable** | Already honest product stance |
| 2 | Optional **WebTunnel- or TLS-underlay** residual path (opt-in) | Best product-shaped PT without full Tor stack |
| 3 | Optional **obfs4-class bridge** mode for high-censor regions | Mature PT; clear ops model |
| 4 | Research **meek/Snowflake** only as hard-mode experiments | High value, high dependency/cost |
| 5 | Do **not** rely on more cover frames alone for “undetectability” | Insufficient vs active DPI |

**Not recommended as “security”:** further obfuscation of **public** node pins,
or shipping private keys. Crypto authenticity remains HELLO + AEAD; PT is a
**channel** problem.

---

## Non-goals of this note

- Implementing any PT in product code  
- Claiming current QUIC-mimic wrap or traffic shaping equals Tor Browser PT  
- Guaranteeing any method works in every jurisdiction forever

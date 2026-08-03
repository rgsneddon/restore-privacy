# VPN-only dedicated residual product — evidence

Date: 2026-08-03  
Commits: `3f8ae8c` (product), follow-up EULA + PASS captures

## Goal
Strip multi-product Suite chrome (Evolve / % wallet / rpAI / Backup) and
username/password first-use. Ship residual VPN only:

1. First use: licence (scroll-to-bottom, justified full text) → KEYGEN paste
   or continue 72h device trial → main VPN.
2. Return: entitlement (trial remaining or KEYGEN) required; if trial expired
   KEYGEN is mandatory → main VPN.
3. No Suite account / seed first-use path.

## Verification plan captures (implementer SCRATCH)

Directory:
`/var/folders/qb/tz4y4zts04z4846pbq95l6kw0000gp/T/grok-goal-90d777e1b612/implementer/`

| Capture | Tests / audit | Observation |
|---------|----------------|-------------|
| `vpn_only_entry_flow.out` | first_run_gate, entry_access, portal, seed hang retirement | **All tests passed!** (+21) |
| `vpn_only_shell.out` | suite_parts_usage, suite_flat_nav, vpn_only_product | **All tests passed!** (+31) |
| `licence_vpn_only.out` | first_run_licence_scroll (justify, scroll-to-bottom, VPN EULA) | **All tests passed!** (+3) |
| `no_suite_family_entry.out` | structural grep + vpn_only_product + portal | **RESULT: PASS** + **All tests passed!** (+6) |

## Product locks
- `suiteNavDestinations` always `[vpn]`
- `SuitePartsState.fromJson` / `SuitePartsStore.load` → `vpnOnly`
- Settings product panel shows VPN tile only
- `FirstRunStep`: licence → keygenOrTrial → complete
- `isAppEntryUnlocked`: licence accepted + trial/KEYGEN entitlement
- Full EULA: residual VPN only (no `USE OF RESTORE PRIVACY SUITE` / `Suite installers`)

## Desktop
`client/first_run_flow.py` already sequences licence → keygen → settings → main
(no username/password identity gate).

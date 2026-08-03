# VPN-only dedicated residual product

Date: 2026-08-03

## Goal
Strip multi-product Suite chrome (Evolve / % wallet / rpAI / Backup) and
username/password first-use. Ship residual VPN only:

1. First use: licence (scroll-to-bottom, justified full text) → KEYGEN paste
   or continue 72h device trial → main VPN.
2. Return: entitlement (trial remaining or KEYGEN) required; if trial expired
   KEYGEN is mandatory → main VPN.
3. No Suite account / seed first-use path.

## Product locks
- `suiteNavDestinations` always `[vpn]` (install flags cannot expand bar).
- `SuitePartsState.fromJson` / `SuitePartsStore.load` → `vpnOnly`.
- Settings product panel shows VPN tile only.
- `FirstRunStep`: licence → keygenOrTrial → complete.
- `isAppEntryUnlocked`: licence accepted + trial/KEYGEN entitlement.
- Licence copy scoped to residual VPN (full EULA + short summary).

## Tests
- first_run_gate_test, entry_access_test, first_run_licence_scroll_test
- first_run_portal_seed_test (no account/seed surfaces)
- suite_parts_usage_test, suite_flat_nav_test (VPN-only chrome)
- vpn_only_product_test (source locks)

## Out of scope
- Full C++ UI rewrite
- monopin rebuild unless release ship needed
- trial duration change
- reintroducing UPDATE_PUSH

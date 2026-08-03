# VPN-only dedicated residual product — evidence

Date: 2026-08-03  
Commits: `3f8ae8c` (product), `177ff0c` (EULA), follow-up (no Suite account prompt)

## Goal
Dedicated residual VPN: no Evolve/%/rpAI/Backup chrome; no username/password
first-use or post-KEYGEN Suite account prompt.

## First-use / return
1. Licence (justified, scroll-to-bottom) → KEYGEN or continue 72h trial → VPN
2. Return: entitlement required (trial or KEYGEN); expired trial → KEYGEN must

## Skeptic fix (account prompt)
- `shouldOfferSuiteAccountPrompt` hard-returns `false`
- `main.dart` no longer calls `showSuiteAccountPrompt` after KEYGEN unlock
- Connect-blocked copy is licence + KEYGEN/trial only (no account/seed)

## Verification plan captures

Implementer: `/var/folders/qb/tz4y4zts04z4846pbq95l6kw0000gp/T/grok-goal-90d777e1b612/implementer/`
Repo: `SCRATCH/vpn_only_captures/`

| Capture | Observation |
|---------|-------------|
| vpn_only_entry_flow.out | All tests passed! (+25) |
| vpn_only_shell.out | All tests passed! (+31) |
| licence_vpn_only.out | All tests passed! (+3) |
| no_suite_family_entry.out | RESULT: PASS + All tests passed! (+17) |

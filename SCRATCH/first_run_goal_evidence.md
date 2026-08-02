# First-run goal evidence (implementer)

## Seed confirm hang
- `attachAndPublishSuiteSeedForUser` returns `SuiteSeedAttachResult`; overall timeout `kSuiteSeedConfirmTimeout` (45s); publish sub-timeout 20s.
- Local attach required; network publish soft-fails so portal advances.
- Portal `_confirmSeed` surfaces TimeoutException; re-enables button (no infinite busy).
- Tests: `test/first_run_seed_confirm_hang_test.dart` → `{SCRATCH}/first_run_seed_confirm.out`

## Evolve inherits Suite login
- Pure helpers: `suiteEvolveInheritsSuiteLogin` / `suiteEvolveShowsLoginWall` in `suite_account.dart`.
- `SuiteAccountBus.hasRegisteredSession`; family host reloads ledger after bus notify; pre-init wallet order.
- Banner on Evolve family body when Suite registered.
- Tests: `test/evolve_inherits_suite_login_test.dart` → `{SCRATCH}/evolve_inherits_suite_login.out`

## Licence scroll-to-bottom + public link
- First-run licence step: Expanded scroll pane of full text; accept disabled until bottom; link to `https://restoreprivacy.online/LICENSE`.
- Pane height bounded by app Expanded layout (not free-floating overflow).
- Tests: `test/first_run_licence_scroll_test.dart` → `{SCRATCH}/first_run_licence_scroll.out`

## macOS VPN permission sequence
- Pure order: prepare → await → open Settings if needed → connect.
- Native `openSettingsOnDenial` default false; Flutter `preparePacketTunnelSequenced`.
- Tests: `test/macos_vpn_permission_sequence_test.dart` → `{SCRATCH}/macos_vpn_permission_sequence.out`

## Flow order
- account → seed → licence still gated: `test/first_run_gate_test.dart` → `{SCRATCH}/first_run_flow_order.out`

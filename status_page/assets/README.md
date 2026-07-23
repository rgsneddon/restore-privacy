# Staged installers for paid fulfilment

Catalog packages under `{VERSION}/` are served by the status host after payment
(`open_release_asset` → local source). This keeps fulfilment working when the
GitHub repo is private without requiring a runtime `RPT_GITHUB_TOKEN`.

Current ship: **0.4.1** under `0.4.1/`. Keep prior version dirs only if needed for rollback.

**0.4.1 staging** (from `releases/0.4.1/` — match `scripts/RELEASE_NOTES_0.4.1.md`
Build provenance):

| Platform | Provenance |
|----------|------------|
| **macOS** | Fresh Flutter freeze + DevID sign + notary on Darwin (`CFBundleShortVersionString` **0.4.1**) |
| **iOS** | Fresh Flutter freeze + Team-signed on Darwin (marketing **0.4.1**) — handoff `client_app/APPLE_HANDOFF_0.4.1.md` |
| **Linux** | Rebuilt via `package_linux.py` (native 0.4.1 package) |
| **Android** | **Carry-forward** residual-wire APK from 0.4.0 under 0.4.1 filename — Flutter/Android SDK rebuild still required for a native freeze |
| **Windows** | **Carry-forward** from 0.4.0 PE (Darwin SFX/filename pin only; 7z extract failed) — **not** a Windows-host multihop PE rebuild. Full PE: Windows x64 `scripts/build_windows_multihop.py` |

Node-only **zram + LUKS2** is a host deploy feature and does not change residual client packages.

Do not put `*.priv` here. Re-stage from `releases/{VERSION}/` on each ship.

# Staged installers for paid fulfilment

Catalog packages under `{VERSION}/` are served by the status host after payment
(`open_release_asset` → local source). This keeps fulfilment working when the
GitHub repo is private without requiring a runtime `RPT_GITHUB_TOKEN`.

Current ship: **0.4.2** under `0.4.2/`. Keep prior version dirs only if needed for rollback.

**0.4.2 staging** (from `releases/0.4.2/` — match `scripts/RELEASE_NOTES_0.4.2.md`
Build provenance):

| Platform | Provenance |
|----------|------------|
| **macOS** | Fresh Flutter freeze + DevID sign + notary on Darwin (`CFBundleShortVersionString` **0.4.2**) |
| **iOS** | Fresh Flutter freeze + Team-signed on Darwin (marketing **0.4.2**) |
| **Linux** | Rebuilt via `package_linux.py` (native 0.4.2 package) |
| **Android** | **Carry-forward** residual-wire APK from 0.4.1 under 0.4.2 filename — Flutter/Android SDK rebuild still required for a native freeze |
| **Windows** | **Carry-forward** from 0.4.1 PE (Darwin SFX/filename pin only; 7z extract failed) — **not** a Windows-host multihop PE rebuild. Full PE: Windows x64 `scripts/build_windows_multihop.py` — see `client/windows/WINDOWS_HANDOFF_0.4.2.md` |

**Settings defaults (0.4.2):** run at startup off; autoconnect off; residual core always on; traffic shaping off; outer obfuscation off; multi-hop off.

Node-only **zram + LUKS2** is a host deploy feature and does not change residual client packages.

Do not put `*.priv` here. Re-stage from `releases/{VERSION}/` on each ship.

**Browser extension (0.4.2):** `restore-privacy-browser-extension-0.4.2.zip` — MV3 browser-scoped proxy; not OS residual. See `browser_extension/README.md`.

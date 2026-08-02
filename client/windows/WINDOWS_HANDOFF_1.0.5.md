# Windows brand breadcrumbs — monopin 1.0.5

**Action required on a Windows builder** for an honest PE seal.

## Why

Mac staged Suite **1.0.5** with:
- **macOS**: native Flutter build (CFBundle **1.0.5**)
- **Windows / Linux / Android / iOS**: catalog **filename** monopin 1.0.5 via carry-forward from 1.0.4 (not a native Windows Authenticode seal)

Helsinki paid_assets already has `restore-privacy-client-1.0.5-windows-x64-setup.exe` as a re-pinned carry-forward. Replace it with a native PE rebuild before calling the Windows seal final.

## Produce

```
releases/1.0.5/restore-privacy-client-1.0.5-windows-x64-setup.exe
```

Also rebuild/sign Windows companions if you seal brand packages there:

- `rpos-0.2.1-windows-x64.zip`
- `restore-privacy-rx-browser-1.0.5-windows.zip`
- `restore-privacy-node-installer-1.0.1-windows-x64.zip`
- `rpmail-0.1.1-windows.zip`
- `rpoffice-0.1.1-windows.zip`

## Steps

1. Mirror monorepo + brand installers onto the Windows large drive (`scripts/windows_brand_mirror.py`).
2. Follow vault `dist/breadcrumbs/current/WINDOWS_HANDOFF.md` and brand checklist.
3. Rebuild multihop Windows PE (`scripts/build_windows_multihop.py` / existing 1.0.x handoff flow).
4. Authenticode-sign the PE; stage to `status_page/assets/1.0.5/` and re-run Helsinki upload for that file only.
5. Refresh breadcrumbs: `python3 scripts/breadcrumbs_vault.py stage` then `publish`.

## Can you wait?

Yes for catalog continuity: download links already work under monopin 1.0.5.  
**Must action** before advertising a native Windows seal or Windows PE honesty gate.

Generated: 2026-08-02T07:56:51Z

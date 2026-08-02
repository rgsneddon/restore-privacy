# Windows brand breadcrumbs — monopin 1.0.7

## Context

Mac stages Suite **1.0.7** with native Flutter builds where the host allows:

- **macOS**: Developer ID signed + notarized when notarytool succeeds  
- **iOS**: Flutter release Runner.app zip (not Distribution IPA until ExportOptions export)  
- **Android**: APK from `client_app`  
- **Windows / Linux**: catalog **filename** monopin 1.0.7 may start as carry-forward from **1.0.6** until this Windows machine rebuilds and Authenticode-seals the PE  

Helsinki `paid_assets` expects:

```text
releases/1.0.7/restore-privacy-client-1.0.7-windows-x64-setup.exe
```

## On the Windows build machine

1. Sync monorepo to the **1.0.7** ship commit (`client/VERSION` must read `1.0.7`).
2. Build the Windows installer with the existing Windows freeze/package path (see prior handoffs for MSVC / Inno / brand assets).
3. Output must be named  
   `restore-privacy-client-1.0.7-windows-x64-setup.exe`.
4. Authenticode-sign the PE; copy to `status_page/assets/1.0.7/` and re-run Helsinki paid upload for that file only if the Mac carry-forward was temporary.
5. Refresh breadcrumbs:  
   `python3 scripts/breadcrumbs_vault.py stage --version 1.0.7`  
   then `publish` when the vault path is available.

## Companions (optional same monopin)

- `restore-privacy-rx-browser-1.0.7-windows.zip` if the Rx browser brand is shipping with this monopin.

## Honest status

Catalog links can serve monopin **1.0.7** with a re-pinned carry-forward PE for continuity. Replace with a native Authenticode-sealed build before calling the Windows seal final.

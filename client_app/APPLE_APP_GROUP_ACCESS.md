# macOS: “would like to access data from other apps”

**Product:** `restore_privacy_client` (Restore Privacy Suite host)  
**Dialog (OS-owned, Sequoia+ wording):**  
`“restore_privacy_client” would like to access data from other apps.`

**Product cannot change Apple’s system dialog text.** On first Mac channel
register, the Suite shows its own sheet (`RptAppGroupAccessExplainer`) **before**
App Group seed, with a one-line reason to Allow (Packet Tunnel ↔ residual nodes).
That sheet is show-once (`rpt_app_group_access_explainer_seen`).

This note answers three product questions from in-repo sources (entitlements + native Swift), not generic TCC lore alone.

---

## 1. Do we need this?

**Yes, for residual Connect as designed** — but it is **not** a scan of third-party apps.

The host and the **Packet Tunnel** Network Extension (`PacketTunnel.appex`) share one **App Group** container:

| Item | Value |
|------|--------|
| App Group id | `group.com.restoreprivacy.shared` |
| Host peer | `com.restoreprivacy.restorePrivacyClient` (main app) |
| Extension peer | `com.restoreprivacy.restorePrivacyClient.PacketTunnel` |

That container holds:

- Admission **secrets** (`client_ed25519.priv`, residual node public keys under `…/secrets/`) so the sandboxed tunnel can HELLO and open residual.
- **Shared prefs** residual stack / privacy-scale flags (`UserDefaults(suiteName:)` for IPv6 residual, traffic shape, outer obfs, multi-hop) so Packet Tunnel matches Settings.

Without a working App Group (or a fallback), residual tunnel start can fail to find the same keys the host prepared.

**Fallback already in code:** when App Group is unavailable, the host also seeds `~/.restore-privacy/secrets/`, and the appex may read that path via a home-relative temporary exception. App Group is still the preferred host↔appex path on Developer ID and Team-signed builds that declare the group.

---

## 2. Can the app open without granting the dialog?

**Yes — the UI shell can open if the user declines** (or dismisses without granting).

- The channel registration path **swallows** App Group seed failures:

```swift
// RptVpnChannel.register
_ = try? RptSecrets.seedAppGroupFromKnownSourcesIfNeeded()
```

- App launch does **not** hard-require a successful group container before showing Flutter.
- **What breaks if declined / group blocked:** Packet Tunnel may not see host-seeded secrets/prefs in the group; Connect can fail or fall back only to home/`Application Support` paths. Residual is the product path that depends on host↔appex shared state.

So: **decline does not brick the window**; it can impair **Connect / residual** honesty until access is allowed or fallbacks suffice.

---

## 3. Which “apps” is it checking?

**None of your other Mac apps (Chrome, Mail, etc.).**  
The system wording is generic. In this product the only designed peer is:

1. **This app’s own Packet Tunnel appex** — same product, separate process, same Team, App Group `group.com.restoreprivacy.shared`.

There is **no** inventory of third-party applications in the Mac client for this prompt. Startup calls:

- `FileManager.containerURL(forSecurityApplicationGroupIdentifier: "group.com.restoreprivacy.shared")`
- `UserDefaults(suiteName: "group.com.restoreprivacy.shared")`

…to share **our** container with **our** Network Extension — not to read Safari/Finder data.

### Where it is declared

| Target | Entitlements file | Key |
|--------|-------------------|-----|
| Host (DevID distribution) | `macos/Runner/DeveloperID.entitlements` | `com.apple.security.application-groups` → `group.com.restoreprivacy.shared` (sandbox **off**) |
| Host (Team / Release sandbox path) | `macos/Runner/Release.entitlements`, `DebugProfile.entitlements` | same App Group (sandbox **on**) |
| Packet Tunnel | `macos/PacketTunnel/PacketTunnel.entitlements` | same App Group + NE packet-tunnel |

### Where it is used at launch / prep

| Call | File | Role |
|------|------|------|
| `seedAppGroupFromKnownSourcesIfNeeded()` | `macos/NativePrep/RptVpnChannel.swift` → `register` | **Startup** (channel register): seed group secrets |
| `containerURL(forSecurityApplicationGroupIdentifier:)` | `macos/NativePrep/RptSecrets.swift` | Resolve group container / secrets dir |
| `UserDefaults(suiteName: appGroupId)` | `RptVpnChannel` (`setPrivacyScale`, `setResidualStack`, …) | Share Settings with tunnel |
| Same suite read | `PacketTunnelProvider` residual stack load | Appex reads host prefs |

---

## Practical advice

| User choice | Effect |
|-------------|--------|
| **Allow** | Host and Packet Tunnel share secrets + residual prefs; intended residual path. |
| **Don’t Allow** | UI still runs; residual Connect may fail or rely on `~/.restore-privacy` / App Support fallbacks. |

To re-prompt later: System Settings → Privacy & Security (and any App Group / “other apps” related entry for Restore Privacy), or reset TCC for the app.

**Non-goal of this note:** removing the dialog (would require redesigning residual secrets transport away from App Groups). The prompt is OS policy for cross-process container access, not a product bug.

---

*Evidence sources: in-repo entitlements, `RptSecrets` / `RptVpnChannel`, optional `codesign -d --entitlements` on a local Release build.*

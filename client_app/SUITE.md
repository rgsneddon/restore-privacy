# Restore Privacy Suite

One app: residual **VPN** Connect, Perccent wallet (**%**), Evolve (**EVOLVE**),
and **rpAI** (GOD helper).

Installers ship free from the Suite storefront on
[restoreprivacy.online](https://restoreprivacy.online/) (catalog monopin matches
`client/VERSION` / `status_page/downloads.py` `RELEASE_VERSION`). Residual
**Connect** needs a **KEYGEN** — monthly licence from **£3.00**. Enter it after
install (app entry screen, or Settings → Payment entitlement / keygen).

The public open site lives in [`public_site/`](../public_site/) for GitHub Pages.
Operator admin is not published there.

Full Suite account + GOD operator guide:
[docs/SUITE_ACCOUNT_AND_RPAI.md](../docs/SUITE_ACCOUNT_AND_RPAI.md).

---

## How residual Connect works

1. Install and accept the end-user licence.
2. Buy / start a KEYGEN plan on the site; paste **KEYGEN** (`RPT-KEY-…`) from
   the fulfilment email.
3. Press **Connect** while entitlement is **OK**.

Download alone does **not** unlock residual traffic. Connect is gated only by
licence + KEYGEN entitlement — **not** by Suite wallet/Evolve registration.

---

## Optional Suite sign-up / sign-in (% + EVOLVE)

After KEYGEN unlock, the Suite may show a **dismissible** prompt:

| Control | Meaning |
|---------|---------|
| **Register for % wallet & Evolve?** | Title — one optional account for both surfaces |
| **Create account** / **Sign in** | One username + password; applies to **%** and **EVOLVE** together |
| **Not now — use VPN only** | Defer registration; residual Connect keeps working |

### Rules (shipped)

- **One identity** covers Perccent wallet and Evolve analyser. There is no
  second forced register wall for the other tab on this Suite path.
- **Not now** stores a deferred flag. VPN Connect stays available with KEYGEN.
- Suite account state is **independent** of `LicenceGate.mayConnect`.
  Registration is never required for residual protection.

Prompt and store implementation: `lib/suite_account.dart`,
`lib/suite_account_prompt.dart`, `lib/suite_account_apply.dart`, post-KEYGEN
wiring in `lib/main.dart`.

---

## rpAI (GOD)

**GOD** is the Restore Privacy Helper on the **rpAI** tab (formerly named Ned).
Scripted guidance helps finish Suite setup and explains product sections. It is
not a second payment gate and does not block Connect.

| User state | What GOD offers |
|------------|-----------------|
| Deferred / not registered | **Continue wallet & analyser setup** → asks *Do you want to continue setting up the wallet and analyser?* → **Yes** reopens the **same** unified Suite form |
| Registered | **Offer how-to** → short typed explainers for **%** then **EVOLVE**, one part at a time with **Continue…** |
| After how-tos | *Do you want a tour of the VPN now?* → optional full residual VPN how-to (licence, KEYGEN, Connect, Settings tips) |

Implementation: pure guide machine in `lib/suite_ned_guide.dart`; tab surface in
`lib/suite_rpai_tab.dart`. Tests: `test/suite_ned_guide_test.dart`,
`test/suite_account_test.dart`.

---

## Tabs at a glance

| Tab | Purpose |
|-----|---------|
| **VPN** | Residual Connect / Disconnect, licence, KEYGEN unlock |
| **%** | Perccent wallet (optional Suite account) |
| **EVOLVE** | Evolve Chronoflux analyser (same optional Suite account) |
| **rpAI** | GOD helper — resume setup, how-tos, optional VPN tour |

---

## Build helpers

```bash
# Suite packaging (versioned scripts under scripts/)
python3 scripts/build_public_pages.py
```

Apple host builds: [APPLE_BUILD.md](APPLE_BUILD.md). Client module map:
[README.md](README.md).

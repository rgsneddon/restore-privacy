# Suite account (sign-up / sign-in) and rpAI (Ned)

Operator and implementer reference for the **optional unified Suite account**
and the **rpAI (Ned)** helper tab. Behaviour is defined by shipped Flutter
modules under `client_app/lib/` — this page describes outcomes, not a second
product contract.

| Concern | Source of truth |
|---------|-----------------|
| Suite account flags, prompt copy, VPN independence | `client_app/lib/suite_account.dart` |
| Unified register/login sheet | `client_app/lib/suite_account_prompt.dart` |
| Apply one identity to % + EVOLVE | `client_app/lib/suite_account_apply.dart` |
| Post-KEYGEN offer (deferrable) | `client_app/lib/main.dart` |
| Ned phases, how-to parts, VPN tour | `client_app/lib/suite_ned_guide.dart` |
| rpAI tab UI wiring | `client_app/lib/suite_rpai_tab.dart` |

---

## Optional Suite sign-up / sign-in (after KEYGEN)

Residual **VPN Connect** is gated only by licence + **KEYGEN** entitlement
(`LicenceGate.mayConnect`). Suite registration is **optional** and **never**
consulted for Connect.

### When the prompt appears

After KEYGEN unlock succeeds, the Suite may offer a single dismissible prompt
(title/body match shipped constants):

| UI string (shipped) | Role |
|---------------------|------|
| **Register for % wallet & Evolve?** | Prompt title |
| Optionally create one account for Perccent wallet and Evolve analyser. VPN Connect already works with your KEYGEN — this is not required for residual protection. | Prompt body |
| **Create account** | Register |
| **Sign in** | Login for an existing Suite identity |
| **Not now — use VPN only** | Defer — mark deferred; residual Connect stays available |

The prompt is **not** shown again when the user is already registered, or when
they already chose defer (until they resume from rpAI).

### One identity for % and EVOLVE

- **Create account** or **Sign in** records one Suite username and applies the
  same credentials to Perccent wallet (**%**) and Evolve (**EVOLVE**) via the
  shared Perc ledger path.
- There is **no** second independent register wall required for the other tab
  during this Suite setup path.
- Username/password fields are a **single** form (`suite_account_username` /
  `suite_account_password` keys), not dual package panels.

### Defer / Not now

Choosing **Not now — use VPN only**:

1. Sets the deferred flag (`suite_account_prompt_deferred`).
2. Leaves residual Connect fully available with KEYGEN.
3. Does **not** force registration on the VPN home screen.

---

## Connect is never gated on Suite account

| Gate | Affects Connect? |
|------|------------------|
| End-user licence acceptance | Yes |
| KEYGEN / payment entitlement (`mayConnect`) | Yes |
| Suite account registered | **No** |
| Suite account deferred | **No** |

`suiteAccountBlocksVpnConnect` ignores Suite flags and only reflects licence
`mayConnect`. Implementers must not wire Connect behind `SuiteAccountStore`.

---

## rpAI (Ned) — resume setup and how-tos

**Ned** is the Restore Privacy Helper on the **rpAI** tab (scripted lines +
buttons; not a freeform LLM chat wall). Growth narrative (ChronoFlux / nodes)
is separate from the Suite-account script.

### Deferred users — resume the same setup

If Suite account is **not** registered (including after defer):

1. rpAI shows **Continue wallet & analyser setup**.
2. Ned asks: **Do you want to continue setting up the wallet and analyser?**
3. **Yes** → opens the **same** unified Suite account sheet
   (`showSuiteAccountPrompt`) used after KEYGEN — not a parallel register-only
   UI.
4. **Not now** → script ends; residual VPN remains available; user can return
   to rpAI later.

### Registered users — offer how-to

If Suite account **is** registered:

1. rpAI shows **Offer how-to**.
2. Ned asks whether to offer how-to guides for **%** wallet and Evolve.
3. On accept, Ned types short explainers **one part at a time** with
   **Continue…** between parts (wallet sections, then Evolve sections).
4. After the last wallet/Evolve part, Ned asks:
   **Do you want a tour of the VPN now?**
5. **Yes** → full residual VPN how-to (licence, KEYGEN, Connect, connected use,
   Settings tips), again with **Continue…**.
6. **Not now** on any choice ends the script without blocking Connect.

### Ned control labels (shipped)

| Label | Key / constant |
|-------|----------------|
| Continue wallet & analyser setup | `kNedResumeSetupLabel` / `ned_resume_setup` |
| Offer how-to | `kNedOfferHowToLabel` / `ned_offer_howto` |
| Continue… | `kNedContinueLabel` / `ned_continue` |
| Yes / Not now | `kNedYesLabel` / `kNedNoLabel` |

---

## User path (summary)

```
Install Suite
    → accept licence
    → paste KEYGEN  →  residual Connect available
    → optional prompt: Register for % wallet & Evolve?
           ├─ Create account / Sign in  → one identity for % + EVOLVE
           │         └─ later: rpAI Offer how-to → Continue… → optional VPN tour
           └─ Not now — use VPN only   → Connect still works
                     └─ later: rpAI Continue wallet & analyser setup
                               → same unified form
```

---

## Related docs

- Product shell: [client_app/SUITE.md](../client_app/SUITE.md)
- Free download / KEYGEN storefront: [SUITE_FREE_DOWNLOAD.md](SUITE_FREE_DOWNLOAD.md)
- KEYGEN payment (operators): [SUBSCRIPTION_KEYGEN.md](SUBSCRIPTION_KEYGEN.md)
- Root install overview: [README.md](../README.md)

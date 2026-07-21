"""Payment-processor connection plugins for private admin settings.

Each plugin is a discrete connection unit that declares the correct environment
variables to enter for that processor option. Secrets are never returned in
readiness projections or HTML — only readiness flags and public labels.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProcessorVariable:
    """One env var the operator may enter for a processor connection."""

    key: str
    label: str
    purpose: str
    required: bool = False
    secret: bool = False
    input_type: str = "text"  # text | password | url
    placeholder: str = ""


@dataclass(frozen=True)
class ProcessorPlugin:
    """One payment-processor option (Stripe, BMC, …)."""

    id: str
    display_name: str
    role: str
    description: str
    variables: tuple[ProcessorVariable, ...]
    dashboard_links: tuple[tuple[str, str], ...] = ()  # (label, url)
    readiness_fn: Callable[[], dict[str, Any]] | None = field(
        default=None, repr=False, compare=False, hash=False
    )

    def variable_keys(self) -> list[str]:
        return [v.key for v in self.variables]

    def required_keys(self) -> list[str]:
        return [v.key for v in self.variables if v.required]


# ---------------------------------------------------------------------------
# Persist applied vars (gitignored data dir — not the public repo)
# ---------------------------------------------------------------------------


def _data_dir() -> Path:
    raw = os.environ.get("RPT_PAYMENT_DATA_DIR", "").strip()
    if raw:
        p = Path(raw)
    else:
        p = Path(__file__).resolve().parent / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p


def processor_env_store_path() -> Path:
    return _data_dir() / "processor_env.json"


def load_stored_processor_env() -> dict[str, str]:
    path = processor_env_store_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in data.items():
        if isinstance(k, str) and isinstance(v, str) and k and v.strip():
            out[k] = v.strip()
    return out


def save_stored_processor_env(values: dict[str, str]) -> None:
    """Merge and persist non-empty values; never write empty over existing secrets."""
    current = load_stored_processor_env()
    for k, v in values.items():
        if not k:
            continue
        s = (v or "").strip()
        if s:
            current[k] = s
    path = processor_env_store_path()
    path.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def apply_stored_env_to_process() -> dict[str, str]:
    """Load disk store into process env so payments/coffee helpers see values.

    Host/Render env already set wins; stored values only fill empty keys.
    """
    stored = load_stored_processor_env()
    for k, v in stored.items():
        if v and not os.environ.get(k, "").strip():
            os.environ[k] = v
    return dict(stored)


def inject_values_into_process(values: dict[str, str]) -> None:
    for k, v in values.items():
        s = (v or "").strip()
        if s:
            os.environ[k] = s


# ---------------------------------------------------------------------------
# Readiness probes (delegate to real shipped helpers)
# ---------------------------------------------------------------------------


def _stripe_readiness() -> dict[str, Any]:
    from payments import (
        PRICE_LABEL,
        public_base_url,
        stripe_payment_link_id,
        stripe_payment_page_url,
        stripe_price_id,
        stripe_remaining_required_keys,
        stripe_secret_key,
        stripe_webhook_endpoint_url,
        stripe_webhook_operator_guidance,
        stripe_webhook_secret,
        STRIPE_WEBHOOK_EVENTS,
        STRIPE_WEBHOOK_PATH,
    )

    secret = stripe_secret_key()
    webhook = stripe_webhook_secret()
    price = stripe_price_id()
    pay_page = stripe_payment_page_url()
    plink = stripe_payment_link_id()
    remaining = stripe_remaining_required_keys()
    mode = "unconfigured"
    if secret.startswith("sk_live_"):
        mode = "live"
    elif secret.startswith("sk_test_"):
        mode = "test"
    elif secret:
        mode = "configured"
    return {
        # Payment page alone is not "ready" for paid-download fulfilment
        "ready": bool(secret and webhook),
        "checkout_ready": bool(secret),
        "fulfilment_ready": bool(secret and webhook),
        "payment_page_ready": bool(
            pay_page.startswith("https://donate.stripe.com/")
            or pay_page.startswith("https://buy.stripe.com/")
            or "stripe.com" in pay_page
        ),
        "payment_page_url": pay_page,
        "payment_link_id": plink,
        "payment_link_ready": bool(plink.startswith("plink_")),
        "remaining_required": remaining,
        "whats_next": remaining,
        "fields": {
            "STRIPE_SECRET_KEY": bool(secret),
            "STRIPE_WEBHOOK_SECRET": bool(webhook),
            # Match form key STRIPE_CHECKOUT_PRICE_ID (not legacy STRIPE_PRICE_ID)
            "STRIPE_CHECKOUT_PRICE_ID": bool(price),
            "STRIPE_PRICE_ID": bool(price),  # back-compat alias for older views
            "RPT_PUBLIC_BASE_URL": bool(
                public_base_url()
                and public_base_url() != "http://127.0.0.1:10000"
            )
            or bool(os.environ.get("RPT_PUBLIC_BASE_URL", "").strip())
            or bool(
                (load_stored_processor_env().get("RPT_PUBLIC_BASE_URL") or "").strip()
            ),
            "STRIPE_PAYMENT_PAGE_URL": bool(pay_page),
            "STRIPE_PAYMENT_LINK_ID": bool(plink),
        },
        "stripe_mode": mode,
        "price_label": PRICE_LABEL,
        "public_base_url": public_base_url(),
        "webhook_path": STRIPE_WEBHOOK_PATH,
        "webhook_endpoint_url": stripe_webhook_endpoint_url(production=True),
        "webhook_events": list(STRIPE_WEBHOOK_EVENTS),
        "webhook_guidance": stripe_webhook_operator_guidance(),
    }


def _bmc_readiness() -> dict[str, Any]:
    from coffee_link import COFFEE_LINK_TEXT, coffee_tip_url

    url = coffee_tip_url()
    return {
        "ready": bool(url.startswith("https://") and "buymeacoffee.com" in url),
        "fields": {
            "RPT_BMC_TIP_URL": bool(url),
            "RPT_BMC_TIP_LABEL": bool(COFFEE_LINK_TEXT or os.environ.get("RPT_BMC_TIP_LABEL")),
        },
        "tip_url": url,
        "tip_label": os.environ.get("RPT_BMC_TIP_LABEL", "").strip() or COFFEE_LINK_TEXT,
        "role": "tip_support_only",
    }


# ---------------------------------------------------------------------------
# Plugin catalog
# ---------------------------------------------------------------------------

# Lazy import avoided: payments does not import this module.
from payments import DEFAULT_STRIPE_PAYMENT_PAGE_URL  # noqa: E402

STRIPE_PLUGIN = ProcessorPlugin(
    id="stripe",
    display_name="Stripe",
    role="paid_downloads",
    description=(
        "Paid package downloads (£2.45 GBP) via Stripe Checkout API. "
        "A public Payment Link / Donate page can be registered separately; "
        "Checkout fulfilment still needs secret key + webhook — never commit them."
    ),
    variables=(
        ProcessorVariable(
            key="STRIPE_SECRET_KEY",
            label="Secret key",
            purpose="Create Checkout sessions (Stripe secret API key)",
            required=True,
            secret=True,
            input_type="password",
            placeholder="paste Stripe secret key",
        ),
        ProcessorVariable(
            key="STRIPE_WEBHOOK_SECRET",
            label="Webhook signing secret",
            purpose="Verify checkout.session.completed events (webhook signing secret)",
            required=True,
            secret=True,
            input_type="password",
            placeholder="paste webhook signing secret",
        ),
        ProcessorVariable(
            key="STRIPE_CHECKOUT_PRICE_ID",
            label="One-time Checkout price id (optional)",
            purpose="One-time price_… only; leave empty for unit_amount=245. Never use a recurring Payment Link price.",
            required=False,
            secret=False,
            input_type="text",
            placeholder="price_… one-time only (optional)",
        ),
        ProcessorVariable(
            key="RPT_PUBLIC_BASE_URL",
            label="Public base URL",
            purpose="Origin for success/cancel/webhook display (no trailing slash)",
            required=True,
            secret=False,
            input_type="url",
            placeholder="https://restoreprivacy.online",
        ),
        ProcessorVariable(
            key="STRIPE_PAYMENT_PAGE_URL",
            label="Public payment page (Payment Link / Donate)",
            purpose="Operator Stripe donate/pay page — public URL, not a secret",
            required=False,
            secret=False,
            input_type="url",
            placeholder="https://donate.stripe.com/…",
        ),
        ProcessorVariable(
            key="STRIPE_PAYMENT_LINK_ID",
            label="Payment Link id",
            purpose="Stripe object id (plink_…) for the same payment page — not a secret",
            required=False,
            secret=False,
            input_type="text",
            placeholder="plink_…",
        ),
    ),
    dashboard_links=(
        ("Dashboard", "https://dashboard.stripe.com"),
        ("API keys", "https://dashboard.stripe.com/apikeys"),
        ("Webhooks", "https://dashboard.stripe.com/webhooks"),
        ("Payments", "https://dashboard.stripe.com/payments"),
        ("Payment page", DEFAULT_STRIPE_PAYMENT_PAGE_URL),
    ),
    readiness_fn=_stripe_readiness,
)

BMC_PLUGIN = ProcessorPlugin(
    id="bmc",
    display_name="Buy Me a Coffee",
    role="tip_support_only",
    description=(
        "Tip / support only — does not mint download tokens. "
        "Set the public tip URL shown on the VPN APP Shop footer."
    ),
    variables=(
        ProcessorVariable(
            key="RPT_BMC_TIP_URL",
            label="Public tip URL",
            purpose="Creator page buyers open for tips (https://buymeacoffee.com/…)",
            required=True,
            secret=False,
            input_type="url",
            placeholder="https://buymeacoffee.com/yourpage",
        ),
        ProcessorVariable(
            key="RPT_BMC_TIP_LABEL",
            label="Footer link label (optional)",
            purpose="Short text for the public coffee footer link",
            required=False,
            secret=False,
            input_type="text",
            placeholder="buy rus a coffee",
        ),
    ),
    dashboard_links=(
        ("Creator login", "https://www.buymeacoffee.com/login"),
    ),
    readiness_fn=_bmc_readiness,
)


def _vps_assets_readiness() -> dict[str, Any]:
    from payments import vps_asset_base_url, vps_asset_fetch_token

    tok = vps_asset_fetch_token()
    base = vps_asset_base_url()
    return {
        "ready": bool(tok and base.startswith("http")),
        "fields": {
            "RPT_ASSET_FETCH_TOKEN": bool(tok),
            "RPT_VPS_ASSET_BASE": bool(base),
        },
        "vps_base_url": base,
        "token_configured": bool(tok),
        "role": "paid_installer_fetch",
    }


VPS_ASSETS_PLUGIN = ProcessorPlugin(
    id="vps_assets",
    display_name="Iceland VPS paid installers",
    role="paid_installer_fetch",
    description=(
        "Shared secret for status host → Iceland VPS paid-asset HTTP fetch "
        "(X-RPT-Asset-Token). Must match rpt-paid-assets.service on the VPS. "
        "Never commit the token; set here or as Render env RPT_ASSET_FETCH_TOKEN."
    ),
    variables=(
        ProcessorVariable(
            key="RPT_ASSET_FETCH_TOKEN",
            label="Asset fetch token",
            purpose="Same secret as VPS unit Environment=RPT_ASSET_FETCH_TOKEN",
            required=True,
            secret=True,
            input_type="password",
            placeholder="paste shared VPS/Render token",
        ),
        ProcessorVariable(
            key="RPT_VPS_ASSET_BASE",
            label="VPS paid-asset base URL (optional)",
            purpose="Default http://82.221.101.241:8081/paid-assets",
            required=False,
            secret=False,
            input_type="text",
            placeholder="http://82.221.101.241:8081/paid-assets",
        ),
    ),
    dashboard_links=(),
    readiness_fn=_vps_assets_readiness,
)

_REGISTRY: tuple[ProcessorPlugin, ...] = (STRIPE_PLUGIN, BMC_PLUGIN, VPS_ASSETS_PLUGIN)


def list_processor_plugins() -> list[ProcessorPlugin]:
    """Ordered processor connection plugins (real catalog entry point)."""
    return list(_REGISTRY)


def get_processor_plugin(plugin_id: str) -> ProcessorPlugin | None:
    pid = (plugin_id or "").strip().lower()
    for p in _REGISTRY:
        if p.id == pid:
            return p
    return None


def plugin_variable_catalog() -> dict[str, list[dict[str, Any]]]:
    """id → list of variable dicts (for tests / JSON)."""
    out: dict[str, list[dict[str, Any]]] = {}
    for p in list_processor_plugins():
        out[p.id] = [
            {
                "key": v.key,
                "label": v.label,
                "required": v.required,
                "secret": v.secret,
                "purpose": v.purpose,
            }
            for v in p.variables
        ]
    return out


# ---------------------------------------------------------------------------
# Validate + apply (pure entry path used by admin POST)
# ---------------------------------------------------------------------------


def validate_processor_entry(
    plugin_id: str, submitted: dict[str, str]
) -> dict[str, Any]:
    """Validate form values for one processor plugin.

    Secret fields may be left blank to keep the existing value.
    Required non-secret fields must be non-empty if the connection is new
    (or if no existing env value).

    Returns {ok, errors: list[str], cleaned: dict[str,str], plugin_id}.
    """
    plugin = get_processor_plugin(plugin_id)
    if plugin is None:
        return {
            "ok": False,
            "errors": [f"unknown processor plugin: {plugin_id}"],
            "cleaned": {},
            "plugin_id": plugin_id,
        }
    errors: list[str] = []
    cleaned: dict[str, str] = {}
    for var in plugin.variables:
        raw = submitted.get(var.key)
        if raw is None:
            raw = submitted.get(var.key.lower(), "")
        value = (raw if isinstance(raw, str) else str(raw or "")).strip()
        existing = os.environ.get(var.key, "").strip()
        if not value:
            if var.required and not existing and not var.secret:
                errors.append(f"{var.key} is required")
            elif var.required and not existing and var.secret:
                errors.append(f"{var.key} is required (no existing value)")
            # blank secret with existing → keep existing (omit from cleaned)
            continue
        if var.secret and value:
            # Light format hints without requiring full Stripe validation
            if var.key == "STRIPE_SECRET_KEY" and not (
                value.startswith("sk_test_")
                or value.startswith("sk_live_")
                or value.startswith("rk_")
            ):
                errors.append(
                    f"{var.key} must be a Stripe secret key (test or live prefix)"
                )
                continue
            if var.key == "STRIPE_WEBHOOK_SECRET" and not value.startswith("whsec_"):
                errors.append(
                    f"{var.key} must be a Stripe webhook signing secret"
                )
                continue
        if var.input_type == "url" and value:
            # VPS paid-asset store is plain HTTP on the product host; allow http there.
            if var.key == "RPT_VPS_ASSET_BASE":
                if not (
                    value.startswith("https://") or value.startswith("http://")
                ):
                    errors.append(
                        f"{var.key} must be an http:// or https:// URL"
                    )
                    continue
            elif not value.startswith("https://"):
                errors.append(f"{var.key} must be an https:// URL")
                continue
        cleaned[var.key] = value
    return {
        "ok": not errors,
        "errors": errors,
        "cleaned": cleaned,
        "plugin_id": plugin.id,
    }


def apply_processor_entry(
    plugin_id: str, submitted: dict[str, str], *, persist: bool = True
) -> dict[str, Any]:
    """Validate, inject into process env, optionally persist to data store.

    Returns {ok, errors, applied_keys, readiness, plugin_id} — never secret values.
    Empty secret fields keep existing store/env values (never wipe on blank submit).
    """
    # Ensure existing disk secrets are visible to validate_processor_entry
    apply_stored_env_to_process()
    result = validate_processor_entry(plugin_id, submitted)
    if not result["ok"]:
        return {
            "ok": False,
            "errors": result["errors"],
            "applied_keys": [],
            "readiness": {},
            "plugin_id": plugin_id,
        }
    cleaned: dict[str, str] = result["cleaned"]
    inject_values_into_process(cleaned)
    if persist and cleaned:
        save_stored_processor_env(cleaned)
        # Re-apply full store so merge is active in this process
        apply_stored_env_to_process()
    plugin = get_processor_plugin(plugin_id)
    readiness: dict[str, Any] = {}
    if plugin and plugin.readiness_fn:
        readiness = plugin.readiness_fn()
    return {
        "ok": True,
        "errors": [],
        "applied_keys": sorted(cleaned.keys()),
        "kept_existing": [
            v.key
            for v in (plugin.variables if plugin else ())
            if v.key not in cleaned
            and (
                os.environ.get(v.key, "").strip()
                or (load_stored_processor_env().get(v.key) or "").strip()
            )
        ],
        "readiness": readiness,
        "plugin_id": plugin_id,
        # Confirm secrets not echoed
        "secrets_echoed": False,
    }


def _key_is_configured(key: str, field_ready: dict[str, Any]) -> bool:
    """True when readiness or env/store has a non-empty value for *key*."""
    if field_ready.get(key):
        return True
    if os.environ.get(key, "").strip():
        return True
    stored = load_stored_processor_env()
    if (stored.get(key) or "").strip():
        return True
    return False


def processor_plugin_views() -> list[dict[str, Any]]:
    """Safe projection of all plugins for admin UI (no secret values)."""
    # Disk → env so badges match last admin save without full process restart
    apply_stored_env_to_process()
    views: list[dict[str, Any]] = []
    for p in list_processor_plugins():
        readiness = p.readiness_fn() if p.readiness_fn else {}
        field_ready = readiness.get("fields") or {}
        vars_out = []
        for v in p.variables:
            configured = _key_is_configured(v.key, field_ready)
            # Optional Checkout price: empty means unit_amount path — not a failure
            status_kind = "set" if configured else "not_set"
            if (
                v.key == "STRIPE_CHECKOUT_PRICE_ID"
                and not configured
                and not v.required
            ):
                status_kind = "optional_ok"
            vars_out.append(
                {
                    "key": v.key,
                    "label": v.label,
                    "purpose": v.purpose,
                    "required": v.required,
                    "secret": v.secret,
                    "input_type": v.input_type,
                    "placeholder": v.placeholder,
                    "configured": configured
                    or status_kind == "optional_ok",
                    "status_kind": status_kind,
                }
            )
        views.append(
            {
                "id": p.id,
                "display_name": p.display_name,
                "role": p.role,
                "description": p.description,
                "variables": vars_out,
                "dashboard_links": [{"label": a, "url": b} for a, b in p.dashboard_links],
                "readiness": {
                    k: readiness[k]
                    for k in readiness
                    if k not in ("fields",) and not str(k).endswith("_secret")
                },
            }
        )
    return views

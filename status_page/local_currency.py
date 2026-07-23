"""Local-currency display for catalog prices (GBP anchors → visitor currency).

Anchors (single source of truth):
  - Monthly: **£2.45** GBP
  - Yearly:  **£29.40** GBP (12 × £2.45)

Conversion uses a fixed, testable FX table (units of currency per 1 GBP).
When the visitor currency is **not** in Stripe's presentment set for this
product, display and pay default to **USD**.

Currency resolution uses Accept-Language (and optional country headers) for
the **website only** — never gates residual VPN admission.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

# --- GBP anchors (pence for integer math where useful) ---
PRICE_MONTHLY_GBP = 2.45
PRICE_YEARLY_GBP = 29.40  # 12 × 2.45
PRICE_MONTHLY_PENCE = 245
PRICE_YEARLY_PENCE = 2940

FALLBACK_CURRENCY = "USD"
BASE_CURRENCY = "GBP"

# Approximate units of *currency* per 1 GBP for display (operator-fixed table).
# Not live market rates — deterministic for tests and catalog honesty.
# Override via inject ``rates`` argument on convert helpers if needed.
FX_UNITS_PER_GBP: dict[str, float] = {
    "GBP": 1.0,
    "USD": 1.27,
    "EUR": 1.17,
    "AUD": 1.92,
    "CAD": 1.73,
    "CHF": 1.12,
    "NZD": 2.08,
    "SEK": 13.2,
    "NOK": 13.5,
    "DKK": 8.75,
    "PLN": 5.05,
    "CZK": 29.0,
    "HUF": 460.0,
    "RON": 5.85,
    "BGN": 2.29,
    "TRY": 41.0,
    "MXN": 24.5,
    "BRL": 7.15,
    "ARS": 1200.0,
    "CLP": 1200.0,
    "COP": 5200.0,
    "PEN": 4.75,
    "JPY": 190.0,
    "CNY": 9.15,
    "HKD": 9.9,
    "SGD": 1.70,
    "KRW": 1700.0,
    "TWD": 40.5,
    "INR": 106.0,
    "IDR": 20000.0,
    "MYR": 5.65,
    "THB": 43.0,
    "PHP": 72.0,
    "VND": 32000.0,
    "ZAR": 23.0,
    "AED": 4.66,
    "SAR": 4.76,
    "ILS": 4.65,
    "EGP": 62.0,
    "NGN": 1950.0,
    "KES": 165.0,
    "GHS": 19.5,
    "PKR": 355.0,
    "BDT": 150.0,
}

# Stripe presentment currencies commonly available for Payment Links / Adaptive
# Pricing (subset Stripe can charge in — not every ISO code). Unsupported → USD.
STRIPE_PRESENTMENT_CURRENCIES: frozenset[str] = frozenset(
    {
        "USD",
        "EUR",
        "GBP",
        "AUD",
        "CAD",
        "CHF",
        "NZD",
        "SEK",
        "NOK",
        "DKK",
        "PLN",
        "CZK",
        "HUF",
        "RON",
        "BGN",
        "MXN",
        "BRL",
        "JPY",
        "HKD",
        "SGD",
        "MYR",
        "THB",
        "PHP",
        "INR",
        "AED",
        "SAR",
        "ILS",
        "ZAR",
        "TRY",
        # Additional Stripe-supported presentment codes (expand as Stripe allows)
        "QAR",
        "KWD",
        "BHD",
        "OMR",
        "JOD",
    }
)

# Zero-decimal presentment (no minor units in display)
ZERO_DECIMAL_CURRENCIES: frozenset[str] = frozenset(
    {
        "BIF",
        "CLP",
        "DJF",
        "GNF",
        "JPY",
        "KMF",
        "KRW",
        "MGA",
        "PYG",
        "RWF",
        "UGX",
        "VND",
        "VUV",
        "XAF",
        "XOF",
        "XPF",
    }
)

# Primary language → currency (fallback when no region tag)
_LANG_CURRENCY: dict[str, str] = {
    "en": "USD",  # generic English without region → USD (not GBP)
    "de": "EUR",
    "fr": "EUR",
    "es": "EUR",
    "it": "EUR",
    "nl": "EUR",
    "pt": "EUR",
    "pl": "PLN",
    "cs": "CZK",
    "hu": "HUF",
    "ro": "RON",
    "bg": "BGN",
    "sv": "SEK",
    "nb": "NOK",
    "nn": "NOK",
    "no": "NOK",
    "da": "DKK",
    "fi": "EUR",
    "el": "EUR",
    "tr": "TRY",
    "ru": "USD",  # Stripe may not present RUB widely; USD fallback policy
    "uk": "USD",
    "ja": "JPY",
    "zh": "CNY",
    "ko": "KRW",
    "hi": "INR",
    "th": "THB",
    "vi": "VND",
    "id": "IDR",
    "ms": "MYR",
    "ar": "AED",
    "he": "ILS",
    "he-il": "ILS",
}

# Region (ISO 3166-1 alpha-2) → currency
_REGION_CURRENCY: dict[str, str] = {
    "GB": "GBP",
    "UK": "GBP",
    "US": "USD",
    "CA": "CAD",
    "AU": "AUD",
    "NZ": "NZD",
    "IE": "EUR",
    "DE": "EUR",
    "FR": "EUR",
    "ES": "EUR",
    "IT": "EUR",
    "NL": "EUR",
    "BE": "EUR",
    "AT": "EUR",
    "PT": "EUR",
    "FI": "EUR",
    "GR": "EUR",
    "LU": "EUR",
    "MT": "EUR",
    "CY": "EUR",
    "EE": "EUR",
    "LV": "EUR",
    "LT": "EUR",
    "SK": "EUR",
    "SI": "EUR",
    "HR": "EUR",
    "CH": "CHF",
    "SE": "SEK",
    "NO": "NOK",
    "DK": "DKK",
    "PL": "PLN",
    "CZ": "CZK",
    "HU": "HUF",
    "RO": "RON",
    "BG": "BGN",
    "TR": "TRY",
    "JP": "JPY",
    "CN": "CNY",
    "HK": "HKD",
    "SG": "SGD",
    "KR": "KRW",
    "TW": "TWD",
    "IN": "INR",
    "ID": "IDR",
    "MY": "MYR",
    "TH": "THB",
    "PH": "PHP",
    "VN": "VND",
    "MX": "MXN",
    "BR": "BRL",
    "AR": "ARS",
    "CL": "CLP",
    "CO": "COP",
    "PE": "PEN",
    "ZA": "ZAR",
    "AE": "AED",
    "SA": "SAR",
    "IL": "ILS",
    "EG": "EGP",
    "NG": "NGN",
    "KE": "KES",
    "GH": "GHS",
    "PK": "PKR",
    "BD": "BDT",
}


@dataclass(frozen=True)
class LocalPriceDisplay:
    """Resolved display currency + monthly/yearly amounts for catalog UI."""

    currency: str
    monthly_amount: float
    yearly_amount: float
    monthly_label: str
    yearly_label: str
    accept_notice: str
    used_fallback_usd: bool
    stripe_presentment_currency: str
    monthly_gbp: float = PRICE_MONTHLY_GBP
    yearly_gbp: float = PRICE_YEARLY_GBP


def normalize_currency_code(code: str) -> str:
    return (code or "").strip().upper()


def is_stripe_presentment_currency(code: str) -> bool:
    c = normalize_currency_code(code)
    return c in STRIPE_PRESENTMENT_CURRENCIES


def stripe_presentment_or_usd(code: str) -> str:
    """Return *code* if Stripe can present it; else **USD**."""
    c = normalize_currency_code(code)
    if c and is_stripe_presentment_currency(c):
        return c
    return FALLBACK_CURRENCY


def currency_from_country(country: str) -> str:
    """Map ISO country code → currency (empty if unknown)."""
    cc = (country or "").strip().upper()
    if len(cc) == 2:
        return _REGION_CURRENCY.get(cc, "")
    return ""


def parse_accept_language(header: str) -> list[tuple[str, str, float]]:
    """Parse Accept-Language into (lang, region, q) tuples, best first."""
    raw = (header or "").strip()
    if not raw:
        return []
    out: list[tuple[str, str, float]] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        q = 1.0
        if ";q=" in part:
            tag, _, qpart = part.partition(";q=")
            try:
                q = float(qpart.strip())
            except ValueError:
                q = 0.0
        else:
            tag = part
        tag = tag.strip().replace("_", "-")
        if not tag:
            continue
        bits = tag.split("-")
        lang = bits[0].lower()
        region = bits[1].upper() if len(bits) > 1 and len(bits[1]) == 2 else ""
        out.append((lang, region, q))
    out.sort(key=lambda t: -t[2])
    return out


def resolve_preferred_currency(
    *,
    accept_language: str = "",
    country: str = "",
    explicit_currency: str = "",
) -> str:
    """Best-effort currency from explicit code, country, then Accept-Language."""
    if explicit_currency:
        c = normalize_currency_code(explicit_currency)
        if c:
            return c
    from_country = currency_from_country(country)
    if from_country:
        return from_country
    for lang, region, _q in parse_accept_language(accept_language):
        if region:
            rc = currency_from_country(region)
            if rc:
                return rc
        # language-region composite
        full = f"{lang}-{region.lower()}" if region else lang
        if full in _LANG_CURRENCY:
            return _LANG_CURRENCY[full]
        if lang in _LANG_CURRENCY:
            return _LANG_CURRENCY[lang]
    return FALLBACK_CURRENCY


def rate_units_per_gbp(
    currency: str, *, rates: dict[str, float] | None = None
) -> float | None:
    table = rates if rates is not None else FX_UNITS_PER_GBP
    c = normalize_currency_code(currency)
    if c in table:
        return float(table[c])
    return None


def convert_gbp_to_currency(
    amount_gbp: float,
    currency: str,
    *,
    rates: dict[str, float] | None = None,
) -> float:
    """Convert *amount_gbp* to *currency* units (relative sum)."""
    c = normalize_currency_code(currency)
    rate = rate_units_per_gbp(c, rates=rates)
    if rate is None:
        # Unknown FX → convert via USD if possible, else 1:1 USD of GBP*rate_usd
        usd_rate = rate_units_per_gbp(FALLBACK_CURRENCY, rates=rates) or 1.27
        return float(amount_gbp) * usd_rate
    return float(amount_gbp) * rate


def format_money(amount: float, currency: str) -> str:
    """Human display label, e.g. ``USD 3.11`` or ``JPY 466``."""
    c = normalize_currency_code(currency)
    if c in ZERO_DECIMAL_CURRENCIES:
        n = int(round(amount))
        return f"{c} {n:,}"
    # Two decimal places for most currencies
    return f"{c} {amount:,.2f}"


def accept_currency_notice(currency: str) -> str:
    """Customer-facing: we accept *user local currency*."""
    c = normalize_currency_code(currency) or FALLBACK_CURRENCY
    return f"we accept *{c}*"


def resolve_local_price_display(
    *,
    accept_language: str = "",
    country: str = "",
    explicit_currency: str = "",
    rates: dict[str, float] | None = None,
) -> LocalPriceDisplay:
    """Resolve visitor currency and monthly/yearly display from GBP anchors."""
    preferred = resolve_preferred_currency(
        accept_language=accept_language,
        country=country,
        explicit_currency=explicit_currency,
    )
    presentment = stripe_presentment_or_usd(preferred)
    used_fallback = presentment != normalize_currency_code(preferred)
    # If preferred has FX but is not Stripe-presentable → show USD (fallback)
    display_ccy = presentment
    # If preferred has no rate and isn't presentment, still USD
    if rate_units_per_gbp(display_ccy, rates=rates) is None:
        display_ccy = FALLBACK_CURRENCY
        used_fallback = True

    monthly = convert_gbp_to_currency(
        PRICE_MONTHLY_GBP, display_ccy, rates=rates
    )
    yearly = convert_gbp_to_currency(
        PRICE_YEARLY_GBP, display_ccy, rates=rates
    )
    return LocalPriceDisplay(
        currency=display_ccy,
        monthly_amount=monthly,
        yearly_amount=yearly,
        monthly_label=format_money(monthly, display_ccy),
        yearly_label=format_money(yearly, display_ccy),
        accept_notice=accept_currency_notice(display_ccy),
        used_fallback_usd=bool(
            used_fallback
            or (
                display_ccy == FALLBACK_CURRENCY
                and normalize_currency_code(preferred)
                not in ("", FALLBACK_CURRENCY)
            )
        ),
        stripe_presentment_currency=display_ccy,
    )


def currency_to_stripe_locale(currency: str) -> str:
    """Best-effort Stripe Checkout locale for presentment UX."""
    c = normalize_currency_code(currency)
    # Map common currencies to Stripe locale codes
    mapping = {
        "GBP": "en-GB",
        "USD": "en",
        "EUR": "en",  # generic; country would refine
        "JPY": "ja",
        "CNY": "zh",
        "KRW": "ko",
        "BRL": "pt-BR",
        "MXN": "es",
        "SEK": "sv",
        "NOK": "nb",
        "DKK": "da",
        "PLN": "pl",
        "CZK": "cs",
        "HUF": "hu",
        "RON": "ro",
        "TRY": "tr",
        "THB": "th",
        "VND": "vi",
        "IDR": "id",
        "MS": "ms",
        "MYR": "ms",
        "INR": "en",
        "AUD": "en-AU",
        "CAD": "en-CA",
        "NZD": "en",
        "CHF": "de",
        "AED": "ar",
        "SAR": "ar",
        "ILS": "he",
        "ZAR": "en",
    }
    return mapping.get(c, "en")


def country_headers_from_request(headers: dict | None) -> str:
    """Extract best country hint from HTTP headers (website only)."""
    if not headers:
        return ""
    # Normalize header keys case-insensitively
    lower = {str(k).lower(): str(v or "") for k, v in headers.items()}
    for key in (
        "cf-ipcountry",
        "cloudfront-viewer-country",
        "x-vercel-ip-country",
        "x-country-code",
        "x-appengine-country",
    ):
        v = (lower.get(key) or "").strip().upper()
        if v and len(v) == 2 and v not in ("XX", "T1", "ZZ"):
            return v
    return ""


def accept_language_from_request(headers: dict | None) -> str:
    if not headers:
        return ""
    lower = {str(k).lower(): str(v or "") for k, v in headers.items()}
    return (lower.get("accept-language") or "").strip()

"""UK public-IP security gate for Restore Privacy clients.

Only users whose core (public) IP is geolocated in the United Kingdom may
connect. Non-UK and total lookup failures fail closed with a clear notice.

Uses multiple free geo HTTPS providers with fallback so a single rate-limit
(HTTP 429) or outage does not block legitimate UK users.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

# Stable user-visible messages (Windows + Android surfaces)
UK_GATE_DENIED_MESSAGE = (
    "Access denied: Restore Privacy is only available when your public IP "
    "is located in the United Kingdom. Your current network location is not UK."
)
UK_GATE_LOOKUP_FAILED_MESSAGE = (
    "Access denied: could not verify that your public IP is in the United Kingdom. "
    "Check your network connection and try again."
)

# ISO country codes accepted as United Kingdom
UK_COUNTRY_CODES = frozenset({"GB", "UK", "GG", "JE", "IM"})  # GB + Crown Dependencies

# Primary + fallbacks (order matters). ipapi.co often rate-limits free clients.
DEFAULT_GEO_URLS: tuple[str, ...] = (
    "https://ipapi.co/json/",
    "https://ipinfo.io/json",
    "https://api.country.is/",
)
DEFAULT_GEO_URL = DEFAULT_GEO_URLS[0]
DEFAULT_TIMEOUT_SEC = 8.0

# Injected fetch: returns raw JSON dict from a geo provider (or raises).
GeoFetcher = Callable[[], dict]


@dataclass(frozen=True)
class UkGateResult:
    allowed: bool
    message: str
    country_code: str = ""
    public_ip: str = ""

    @property
    def ok(self) -> bool:
        return self.allowed


def normalize_country_code(raw: object) -> str:
    """Map provider fields to a 2-letter uppercase country code (or empty)."""
    if raw is None:
        return ""
    s = str(raw).strip().upper()
    if not s:
        return ""
    # Some providers return "United Kingdom"
    if s in {
        "UNITED KINGDOM",
        "GREAT BRITAIN",
        "ENGLAND",
        "SCOTLAND",
        "WALES",
        "NORTHERN IRELAND",
    }:
        return "GB"
    if len(s) >= 2 and s[:2].isalpha():
        return s[:2]
    return s


def is_uk_country(code: str) -> bool:
    return normalize_country_code(code) in UK_COUNTRY_CODES


def evaluate_geo_payload(data: dict | None) -> UkGateResult:
    """Pure decision from a geo JSON payload (no network). Fail closed on missing data."""
    if not isinstance(data, dict) or not data:
        return UkGateResult(False, UK_GATE_LOOKUP_FAILED_MESSAGE)

    # Prefer explicit country codes from common providers
    code = ""
    for key in (
        "country_code",
        "countryCode",
        "country",
        "country_code_iso3",
    ):
        if key in data and data[key] is not None:
            val = data[key]
            # ip-api style: country is full name, countryCode is ISO
            if key == "country" and isinstance(val, str) and len(val) > 2:
                code = normalize_country_code(val)
            else:
                code = normalize_country_code(val)
            if code:
                break

    # ipinfo / country.is use "country": "GB"
    if not code and "country" in data:
        code = normalize_country_code(data.get("country"))

    public_ip = ""
    for key in ("ip", "query", "origin"):
        if data.get(key):
            public_ip = str(data[key]).strip()
            break

    if not code:
        return UkGateResult(
            False,
            UK_GATE_LOOKUP_FAILED_MESSAGE,
            country_code="",
            public_ip=public_ip,
        )

    if is_uk_country(code):
        return UkGateResult(
            True,
            "UK location verified",
            country_code=normalize_country_code(code),
            public_ip=public_ip,
        )

    return UkGateResult(
        False,
        UK_GATE_DENIED_MESSAGE,
        country_code=normalize_country_code(code),
        public_ip=public_ip,
    )


def fetch_geo_url(url: str, timeout: float = DEFAULT_TIMEOUT_SEC) -> dict:
    """Fetch one geo JSON endpoint. Raises on HTTP/transport/parse errors."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "restore-privacy-client/0.1.5",
            "Accept": "application/json",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("geo response is not a JSON object")
    # ipapi.co uses error:true on failure / rate limit body
    if data.get("error") is True:
        raise ValueError(str(data.get("reason") or "geo API error"))
    return data


def default_geo_fetcher(
    url: str = DEFAULT_GEO_URL,
    timeout: float = DEFAULT_TIMEOUT_SEC,
    urls: tuple[str, ...] | None = None,
) -> dict:
    """Fetch public IP + country, trying fallback providers on failure.

    When ``urls`` is None, uses DEFAULT_GEO_URLS (primary + fallbacks).
    A single ``url`` override still allows one-shot fetch for tests that pass
    an explicit URL only via the first argument with urls=().
    """
    if urls is not None:
        chain = urls if urls else (url,)
    else:
        # Prefer full chain; put explicit url first if it is one of the defaults
        chain = DEFAULT_GEO_URLS
        if url and url not in chain:
            chain = (url,) + DEFAULT_GEO_URLS

    last_err: Exception | None = None
    for u in chain:
        try:
            return fetch_geo_url(u, timeout=timeout)
        except Exception as exc:
            last_err = exc
            continue
    if last_err is not None:
        raise last_err
    raise ValueError("no geo providers configured")


def check_uk_public_ip(
    fetcher: Optional[GeoFetcher] = None,
) -> UkGateResult:
    """Resolve core public IP country and gate on United Kingdom.

    ``fetcher`` is injectable for tests. Default uses live geo providers with
    fallback. Fail closed only when every provider fails or country is non-UK.
    """
    try:
        data = (fetcher or default_geo_fetcher)()
        return evaluate_geo_payload(data)
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        ValueError,
        TypeError,
        OSError,
        json.JSONDecodeError,
        KeyError,
    ):
        return UkGateResult(False, UK_GATE_LOOKUP_FAILED_MESSAGE)
    except Exception:
        return UkGateResult(False, UK_GATE_LOOKUP_FAILED_MESSAGE)


def assert_uk_or_raise(fetcher: Optional[GeoFetcher] = None) -> UkGateResult:
    """Convenience: return UK result or raise PermissionError with notice text."""
    result = check_uk_public_ip(fetcher=fetcher)
    if not result.allowed:
        raise PermissionError(result.message)
    return result

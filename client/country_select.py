"""Entry-country selector helpers (flags, default Iceland/IS, Connect gate).

Used by the main Connect shell dropdown (not Settings-only). Pure and
unit-testable without GUI.

Honesty: emoji flags may not render on every Windows font — option labels
always include country code + name; flag glyph is best-effort decoration.
Prefer Segoe UI Emoji on Windows so regional-indicator flags show in the menu.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .multihop import (
    COUNTRY_DE,
    COUNTRY_IS,
    COUNTRY_RO,
    COUNTRY_US,
    DEFAULT_ENTRY_COUNTRY,
    PRODUCT_COUNTRY_CATALOG,
    CountryNode,
    normalize_entry_country,
    product_country_catalog,
)

# Regional-indicator flag sequences (IS / DE live; US retired). Safe as unicode text.
_FLAG_BY_CODE: dict[str, str] = {
    COUNTRY_IS: "\U0001f1ee\U0001f1f8",  # 🇮🇸
    COUNTRY_DE: "\U0001f1e9\U0001f1ea",  # 🇩🇪
    COUNTRY_US: "\U0001f1fa\U0001f1f8",  # 🇺🇸
    # Retired RO flag kept for any legacy admin display only
    COUNTRY_RO: "\U0001f1f7\U0001f1f4",  # 🇷🇴
}


@dataclass(frozen=True)
class CountryOption:
    """One dropdown row for the main-shell entry-country control."""

    code: str
    name: str
    flag: str
    host: str = ""

    def label(self) -> str:
        """Display string: flag + name + code (flag may be empty on bare fonts)."""
        flag = (self.flag or "").strip()
        name = (self.name or self.code or "").strip()
        code = (self.code or "").strip().upper()
        if flag:
            return f"{flag}  {name} ({code})"
        return f"{name} ({code})"

    def to_dict(self, *, admin: bool = False) -> dict[str, str]:
        """UI/JSON dict. Non-admin omits residual monopin *host* (presentation hygiene)."""
        from client.residual_public import public_country_option_dict

        return public_country_option_dict(
            code=self.code,
            name=self.name,
            flag=self.flag,
            host=self.host,
            admin=admin,
        )


def country_flag_emoji(code: str | None) -> str:
    """Flag glyph for a catalog country code (empty if unknown)."""
    c = (code or "").strip().upper()
    if c in _FLAG_BY_CODE:
        return _FLAG_BY_CODE[c]
    # Best-effort regional indicators for 2-letter codes
    if len(c) == 2 and c.isalpha():
        try:
            return "".join(chr(0x1F1E6 + (ord(ch) - ord("A"))) for ch in c)
        except Exception:  # noqa: BLE001
            return ""
    return ""


def parse_catalog_country_code(
    raw: str | None,
    *,
    catalog: Sequence[CountryNode] | None = None,
) -> str | None:
    """Return catalog code if *raw* is a known entry country; else None.

    Unlike :func:`normalize_entry_country`, does **not** default unknown/empty
    to DE — used for Connect gate and strict validation.
    """
    raw_s = (raw or "").strip()
    if not raw_s:
        return None
    # Reuse alias table via normalize, then verify membership
    code = normalize_entry_country(raw_s)
    # If input was garbage, normalize returns DEFAULT — only accept if raw
    # maps intentionally (alias or exact catalog code).
    cat = list(catalog) if catalog is not None else list(product_country_catalog())
    codes = {str(getattr(n, "code", "") or "").strip().upper() for n in cat}
    upper = raw_s.upper()
    aliases = {
        "ICELAND": COUNTRY_IS,
        "IS": COUNTRY_IS,
        "GERMANY": COUNTRY_DE,
        "DE": COUNTRY_DE,
        "DEU": COUNTRY_DE,
        "DEUTSCHLAND": COUNTRY_DE,
        # Stale US/RO are not catalog members (normalize maps → DE)
        "UNITED STATES": COUNTRY_US,
        "UNITED STATES OF AMERICA": COUNTRY_US,
        "USA": COUNTRY_US,
        "US": COUNTRY_US,
        "AMERICA": COUNTRY_US,
        "ROMANIA": COUNTRY_RO,
        "RO": COUNTRY_RO,
        "ROU": COUNTRY_RO,
    }
    want = aliases.get(upper, upper)
    if want in codes:
        return want
    # normalize may have mapped — only accept if want was a known alias path
    if code in codes and upper in aliases:
        return code
    return None


def default_entry_country() -> str:
    """Product default entry: Germany (DE) on every client."""
    return DEFAULT_ENTRY_COUNTRY


def default_entry_reason() -> str:
    """Reason token when empty selection falls back to product default."""
    if DEFAULT_ENTRY_COUNTRY == COUNTRY_DE:
        return "default_germany"
    if DEFAULT_ENTRY_COUNTRY == COUNTRY_US:
        return "default_united_states"
    if DEFAULT_ENTRY_COUNTRY == COUNTRY_IS:
        return "default_iceland"
    return "default_entry"


def resolve_entry_country_selection(
    raw: str | None,
    *,
    catalog: Sequence[CountryNode] | None = None,
    allow_default: bool = True,
) -> tuple[bool, str, str]:
    """Resolve selection for Connect.

    Returns ``(ok, code, reason)``:
    - empty/None + allow_default → (True, IS, \"default_iceland\")
    - valid catalog → (True, code, \"ok\")
    - empty without default / unknown → (False, \"\", reason)
    """
    raw_s = (raw or "").strip()
    if not raw_s:
        if allow_default:
            return True, default_entry_country(), default_entry_reason()
        return False, "", "missing_entry_country"
    code = parse_catalog_country_code(raw_s, catalog=catalog)
    if code is None:
        return False, "", "invalid_entry_country"
    return True, code, "ok"


def entry_country_allows_connect(
    raw: str | None,
    *,
    catalog: Sequence[CountryNode] | None = None,
    allow_default: bool = True,
) -> bool:
    """True when Connect may dial for this selection (valid or product default)."""
    ok, _code, _reason = resolve_entry_country_selection(
        raw, catalog=catalog, allow_default=allow_default
    )
    return ok


def catalog_country_options(
    catalog: Sequence[CountryNode] | None = None,
) -> list[CountryOption]:
    """Dropdown options from product residual catalog (flags + labels)."""
    cat = list(catalog) if catalog is not None else list(product_country_catalog())
    out: list[CountryOption] = []
    seen: set[str] = set()
    for n in cat:
        code = str(getattr(n, "code", "") or "").strip().upper()
        if not code or code in seen:
            continue
        seen.add(code)
        name = str(getattr(n, "name", "") or code).strip() or code
        host = str(getattr(n, "host", "") or "").strip()
        flag = country_flag_emoji(code)
        # Always expose a non-empty flag field for catalog codes (emoji or fallback)
        if not flag:
            flag = f"[{code}]"
        out.append(
            CountryOption(
                code=code,
                name=name,
                flag=flag,
                host=host,
            )
        )
    if not out:
        # Fail soft: still offer product default IS
        code = default_entry_country()
        out.append(
            CountryOption(
                code=code,
                name="Iceland" if code == COUNTRY_IS else code,
                flag=country_flag_emoji(code) or f"[{code}]",
                host="",
            )
        )
    return out


def option_label_for_code(
    code: str | None,
    *,
    catalog: Sequence[CountryNode] | None = None,
) -> str:
    """Human label for a stored code (product default IS when empty)."""
    ok, resolved, _ = resolve_entry_country_selection(
        code, catalog=catalog, allow_default=True
    )
    use = resolved if ok else default_entry_country()
    for opt in catalog_country_options(catalog):
        if opt.code == use:
            return opt.label()
    return f"{country_flag_emoji(use)}  {use}".strip()


def label_to_country_code(
    label: str | None,
    *,
    catalog: Sequence[CountryNode] | None = None,
) -> str | None:
    """Map a dropdown label back to catalog code (or parse code from text)."""
    text = (label or "").strip()
    if not text:
        return None
    for opt in catalog_country_options(catalog):
        if text == opt.label() or text == opt.code or text.endswith(f"({opt.code})"):
            return opt.code
    # Last resort: strict parse
    return parse_catalog_country_code(text, catalog=catalog)

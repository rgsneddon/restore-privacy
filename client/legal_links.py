"""Public document links for client Settings (audit, privacy, end-user licence).

Installed clients open **status-origin** URLs on the public status host (restoreprivacy.online) so docs
remain available even when GitHub is private. Override the origin with
``RPT_PUBLIC_BASE_URL`` (same as the status page).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Default public status host (how-to-buy + legal docs are served here).
DEFAULT_STATUS_ORIGIN = "https://restoreprivacy.online"

# User-facing labels (Settings) and status-origin paths.
AUDIT_LABEL = "Most recent audit"
PRIVACY_POLICY_LABEL = "Privacy policy"
END_USER_LICENCE_LABEL = "End user licence"
HOW_TO_BUY_LABEL = "How to buy"

AUDIT_REPO_PATH = "AUDIT.md"
PRIVACY_POLICY_REPO_PATH = "PRIVACY_POLICY.md"
# On-disk spelling is LICENSE (US); UI label uses “licence”.
END_USER_LICENCE_REPO_PATH = "LICENSE"
HOW_TO_BUY_PATH = "how-to-buy"

# Status-origin URL paths (must match status_page/public_docs.py).
AUDIT_STATUS_PATH = "/AUDIT.md"
PRIVACY_STATUS_PATH = "/PRIVACY_POLICY.md"
LICENCE_STATUS_PATH = "/LICENSE"
HOW_TO_BUY_STATUS_PATH = "/how-to-buy"
README_STATUS_PATH = "/README.md"


def status_origin() -> str:
    """Public base for legal/how-to URLs (env RPT_PUBLIC_BASE_URL or production default)."""
    raw = os.environ.get("RPT_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if raw and not raw.startswith("http://127.0.0.1") and not raw.startswith(
        "http://localhost"
    ):
        return raw
    return DEFAULT_STATUS_ORIGIN


# Compatibility: older code expected a GitHub blob base constant.
# Docs are served on the status host (repo is private) — do not open this for users.
GITHUB_REPO_BLOB_BASE = (
    "https://github.com/rgsneddon/restore-privacy/blob/main"
)


def assert_status_origin_urls() -> list[str]:
    """Return legal URLs; used by tests to verify Render status-host targets."""
    return [link.url for link in LEGAL_DOC_LINKS]


@dataclass(frozen=True)
class LegalDocLink:
    """One Settings document entry."""

    label: str
    repo_path: str
    status_path: str

    @property
    def url(self) -> str:
        """Absolute URL on the public status host."""
        return status_origin().rstrip("/") + self.status_path


LEGAL_DOC_LINKS: tuple[LegalDocLink, ...] = (
    LegalDocLink(
        label=AUDIT_LABEL,
        repo_path=AUDIT_REPO_PATH,
        status_path=AUDIT_STATUS_PATH,
    ),
    LegalDocLink(
        label=PRIVACY_POLICY_LABEL,
        repo_path=PRIVACY_POLICY_REPO_PATH,
        status_path=PRIVACY_STATUS_PATH,
    ),
    LegalDocLink(
        label=END_USER_LICENCE_LABEL,
        repo_path=END_USER_LICENCE_REPO_PATH,
        status_path=LICENCE_STATUS_PATH,
    ),
    LegalDocLink(
        label=HOW_TO_BUY_LABEL,
        repo_path=HOW_TO_BUY_PATH,
        status_path=HOW_TO_BUY_STATUS_PATH,
    ),
)


def legal_doc_urls() -> dict[str, str]:
    """Map Settings label → public status-origin URL."""
    return {link.label: link.url for link in LEGAL_DOC_LINKS}


def audit_url() -> str:
    return LEGAL_DOC_LINKS[0].url


def privacy_policy_url() -> str:
    return LEGAL_DOC_LINKS[1].url


def end_user_licence_url() -> str:
    return LEGAL_DOC_LINKS[2].url


def how_to_buy_url() -> str:
    return LEGAL_DOC_LINKS[3].url


def readme_url() -> str:
    return status_origin().rstrip("/") + README_STATUS_PATH

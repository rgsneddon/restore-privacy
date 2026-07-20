"""Public document links for client Settings (audit, privacy, end-user licence).

Installed clients open stable GitHub blob URLs so they work without a local
source tree. Paths match repo root files: AUDIT.md, PRIVACY_POLICY.md, LICENSE.
"""

from __future__ import annotations

from dataclasses import dataclass

GITHUB_REPO_BLOB_BASE = (
    "https://github.com/rgsneddon/RUST-IN-PRIVACY/blob/main"
)

# User-facing labels (Settings) and relative repo paths.
AUDIT_LABEL = "Most recent audit"
PRIVACY_POLICY_LABEL = "Privacy policy"
END_USER_LICENCE_LABEL = "End user licence"

AUDIT_REPO_PATH = "AUDIT.md"
PRIVACY_POLICY_REPO_PATH = "PRIVACY_POLICY.md"
# On-disk spelling is LICENSE (US); UI label uses “licence”.
END_USER_LICENCE_REPO_PATH = "LICENSE"


@dataclass(frozen=True)
class LegalDocLink:
    """One Settings document entry."""

    label: str
    repo_path: str

    @property
    def url(self) -> str:
        return f"{GITHUB_REPO_BLOB_BASE}/{self.repo_path}"


LEGAL_DOC_LINKS: tuple[LegalDocLink, ...] = (
    LegalDocLink(label=AUDIT_LABEL, repo_path=AUDIT_REPO_PATH),
    LegalDocLink(label=PRIVACY_POLICY_LABEL, repo_path=PRIVACY_POLICY_REPO_PATH),
    LegalDocLink(
        label=END_USER_LICENCE_LABEL, repo_path=END_USER_LICENCE_REPO_PATH
    ),
)


def legal_doc_urls() -> dict[str, str]:
    """Map Settings label → public URL."""
    return {link.label: link.url for link in LEGAL_DOC_LINKS}


def audit_url() -> str:
    return LEGAL_DOC_LINKS[0].url


def privacy_policy_url() -> str:
    return LEGAL_DOC_LINKS[1].url


def end_user_licence_url() -> str:
    return LEGAL_DOC_LINKS[2].url

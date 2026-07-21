/// Public document links for Settings (audit, privacy, end-user licence, how-to-buy).
///
/// Always open **status-host** absolute URLs (readable HTML pages on
/// restoreprivacy.online). Paths match status_page/public_docs.py — never
/// GitHub blob/raw. Docs stay available when GitHub is private.
class LegalDocLink {
  const LegalDocLink({required this.label, required this.statusPath});

  final String label;
  final String statusPath;

  /// Public status host (restoreprivacy.online — paid downloads + docs).
  static const statusOrigin = 'https://restoreprivacy.online';

  /// Absolute URL opened by Settings (external browser).
  String get url => '$statusOrigin$statusPath';

  /// Basename for on-disk tests only (not a user-facing open target).
  String get repoPath =>
      statusPath.startsWith('/') ? statusPath.substring(1) : statusPath;
}

const String kAuditLabel = 'Most recent audit';
const String kPrivacyPolicyLabel = 'Privacy policy';
const String kEndUserLicenceLabel = 'End user licence';
const String kHowToBuyLabel = 'How to buy';

const List<LegalDocLink> kLegalDocLinks = [
  LegalDocLink(label: kAuditLabel, statusPath: '/AUDIT.md'),
  LegalDocLink(label: kPrivacyPolicyLabel, statusPath: '/PRIVACY_POLICY.md'),
  // On-disk spelling is LICENSE; UI label uses “licence”.
  LegalDocLink(label: kEndUserLicenceLabel, statusPath: '/LICENSE'),
  LegalDocLink(label: kHowToBuyLabel, statusPath: '/how-to-buy'),
];

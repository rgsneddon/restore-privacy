/// Public document links for Settings (audit, privacy, end-user licence, how-to-buy).
///
/// Status-origin URLs on the Render status host so docs stay available when
/// GitHub is private. Paths match status_page/public_docs.py.
class LegalDocLink {
  const LegalDocLink({required this.label, required this.statusPath});

  final String label;
  final String statusPath;

  /// Public status host (same as restore-privacy-status.onrender.com).
  static const statusOrigin = 'https://restore-privacy-status.onrender.com';

  String get url => '$statusOrigin$statusPath';

  /// Compatibility: former GitHub path basename.
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

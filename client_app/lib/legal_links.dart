/// Public document links for Settings (audit, privacy, end-user licence).
///
/// Stable GitHub blob URLs so installed clients work without a source tree.
/// Paths match repo root: AUDIT.md, PRIVACY_POLICY.md, LICENSE.
class LegalDocLink {
  const LegalDocLink({required this.label, required this.repoPath});

  final String label;
  final String repoPath;

  static const blobBase =
      'https://github.com/rgsneddon/restore-privacy/blob/main';

  String get url => '$blobBase/$repoPath';
}

const String kAuditLabel = 'Most recent audit';
const String kPrivacyPolicyLabel = 'Privacy policy';
const String kEndUserLicenceLabel = 'End user licence';

const List<LegalDocLink> kLegalDocLinks = [
  LegalDocLink(label: kAuditLabel, repoPath: 'AUDIT.md'),
  LegalDocLink(label: kPrivacyPolicyLabel, repoPath: 'PRIVACY_POLICY.md'),
  // On-disk spelling is LICENSE; UI label uses “licence”.
  LegalDocLink(label: kEndUserLicenceLabel, repoPath: 'LICENSE'),
];

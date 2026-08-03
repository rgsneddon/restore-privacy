/// Kill-switch Settings confirm gate (pure logic, no dialog I/O).
///
/// Enabling kill-switch requires an explicit typed confirmation so users do not
/// arm fail-closed egress by accident. Disabling never requires a phrase.
library;

/// Exact token the user must type to enable kill-switch (case-sensitive).
const String kKillSwitchConfirmToken = 'KILLSWITCH';

/// Dialog title / lead (all-caps warning).
const String kKillSwitchConfirmTitle = 'ARE YOU SURE?';

/// Risk explanation shown when enabling kill-switch.
const String kKillSwitchConfirmRiskBody =
    'Turning kill-switch ON can block all non-VPN traffic if residual drops. '
    'That may break captive portals, app/OS updates, local network access, '
    'and other connections until you turn it OFF or reconnect residual. '
    'Default is OFF for a reason. Type KILLSWITCH below to confirm enable.';

/// Confirm button label on the enable dialog.
const String kKillSwitchConfirmActionLabel = 'Enable kill switch';

/// Cancel button label.
const String kKillSwitchConfirmCancelLabel = 'Cancel';

/// Field hint for the typed confirm box.
const String kKillSwitchConfirmFieldHint = 'Type KILLSWITCH to confirm';

/// Marker key for the enable-confirm dialog shell (widget tests).
const String kKillSwitchConfirmDialogKey = 'kill_switch_confirm_dialog';

/// Marker key for the typed confirm TextField.
const String kKillSwitchConfirmFieldKey = 'kill_switch_confirm_field';

/// Result of evaluating whether a kill-switch opt-in change may persist.
class KillSwitchConfirmDecision {
  const KillSwitchConfirmDecision({
    required this.allowPersist,
    required this.nextOptIn,
    this.reason = '',
  });

  /// True when Settings may save [nextOptIn].
  final bool allowPersist;

  /// Value to persist when [allowPersist] is true.
  final bool nextOptIn;

  /// Why the gate rejected or allowed (tests / logs).
  final String reason;
}

/// Pure gate for kill-switch Settings changes.
///
/// - Turning **OFF** (`desiredOn == false`): always allowed, no token needed.
/// - Turning **ON** (`desiredOn == true`): allowed only when [confirmText]
///   equals [kKillSwitchConfirmToken] exactly (after optional trim of outer
///   whitespace only — internal case must match).
/// - Empty / wrong / cancelled ON attempts: [allowPersist] false, next stays off.
KillSwitchConfirmDecision evaluateKillSwitchConfirm({
  required bool desiredOn,
  String? confirmText,
  bool cancelled = false,
}) {
  if (!desiredOn) {
    return const KillSwitchConfirmDecision(
      allowPersist: true,
      nextOptIn: false,
      reason: 'disable_no_confirm',
    );
  }
  if (cancelled) {
    return const KillSwitchConfirmDecision(
      allowPersist: false,
      nextOptIn: false,
      reason: 'enable_cancelled',
    );
  }
  final typed = (confirmText ?? '').trim();
  if (typed == kKillSwitchConfirmToken) {
    return const KillSwitchConfirmDecision(
      allowPersist: true,
      nextOptIn: true,
      reason: 'enable_token_ok',
    );
  }
  return KillSwitchConfirmDecision(
    allowPersist: false,
    nextOptIn: false,
    reason: typed.isEmpty ? 'enable_empty_token' : 'enable_wrong_token',
  );
}

/// True when [text] is the exact enable token (trim outer whitespace).
bool killSwitchConfirmTokenMatches(String? text) {
  return (text ?? '').trim() == kKillSwitchConfirmToken;
}

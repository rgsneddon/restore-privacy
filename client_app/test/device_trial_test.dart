import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/entry_access.dart';
import 'package:restore_privacy_client/licence_gate.dart';

void main() {
  test('deviceTrialCacheAllowsConnect enforces 72h window', () {
    const start = 1e9;
    final ends = start + kDeviceTrialSeconds;
    expect(
      deviceTrialCacheAllowsConnect(
        status: kDeviceTrialStatusActive,
        endsAt: ends,
        nowSec: start + 60,
      ),
      isTrue,
    );
    expect(
      deviceTrialCacheAllowsConnect(
        status: kDeviceTrialStatusActive,
        endsAt: ends,
        nowSec: ends,
      ),
      isFalse,
    );
    expect(
      deviceTrialCacheAllowsConnect(
        status: kDeviceTrialStatusExpired,
        endsAt: ends,
        nowSec: start + 1,
      ),
      isFalse,
    );
    expect(kDeviceTrialSeconds, 72 * 3600);
  });

  test('connectAllowedTrialOrPaid isolates trial and keygen', () {
    expect(
      connectAllowedTrialOrPaid(keygenOk: false, trialOk: true),
      isTrue,
    );
    expect(
      connectAllowedTrialOrPaid(keygenOk: true, trialOk: false),
      isTrue,
    );
    expect(
      connectAllowedTrialOrPaid(keygenOk: false, trialOk: false),
      isFalse,
    );
  });

  test('entry access exposes start trial + get keygen keys and labels', () {
    expect(kStartFreeTrialButtonLabel.toLowerCase(), contains('trial'));
    expect(kEntryAccessStartTrialButtonKey, isNotNull);
    expect(kEntryAccessGetKeygenButtonKey, isNotNull);
    expect(shopPayUrl(), contains('/pay'));
    expect(kTrialExpiredUnlockMsg.toLowerCase(), contains('keygen'));
    expect(kTrialExpiredUnlockMsg.toLowerCase(), contains('pay'));
  });
}

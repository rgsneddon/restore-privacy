import 'dart:convert';

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
    expect(kTrialExpiredUnlockMsg.toLowerCase(), contains('3-day'));
    expect(kResidualTrialThenPayCopy.toLowerCase(), contains('72'));
    expect(kResidualTrialThenPayCopy.toLowerCase(), contains('no card'));
    expect(kEntryAccessTrialHint.toLowerCase(), contains('72'));
    expect(kEntryAccessTrialHint.toLowerCase(), isNot(contains('payment details')));
  });

  test('mayOfferDeviceTrialClaim blocks after local exhausted', () {
    expect(
      mayOfferDeviceTrialClaim(localExhausted: false, keygenOk: false),
      isTrue,
    );
    expect(
      mayOfferDeviceTrialClaim(localExhausted: true, keygenOk: false),
      isFalse,
    );
    expect(
      mayOfferDeviceTrialClaim(localExhausted: false, keygenOk: true),
      isFalse,
    );
  });

  test('claimDeviceTrial marks exhausted and install_id in body', () async {
    final gate = LicenceGate(MemoryLicenceBackend({}));
    final bodies = <String>[];
    final ends = DateTime.now().millisecondsSinceEpoch / 1000.0 - 10;
    final remote1 = await gate.claimDeviceTrial(
      devicePubHex: 'ab' * 32,
      installId: 'install-marker-001',
      post: (uri, body) async {
        bodies.add(utf8.decode(body));
        return {
          'ok': false,
          'connect_allowed': false,
          'error': 'trial_exhausted',
          'ends_at': ends,
          'status': 'expired',
        };
      },
    );
    expect(remote1['error'], 'trial_exhausted');
    expect(bodies.single, contains('install-marker-001'));
    expect(bodies.single, contains('device_pub'));
    expect(await gate.isLocalTrialExhausted(), isTrue);
    // Second claim short-circuits without network when local exhausted
    final remote2 = await gate.claimDeviceTrial(
      devicePubHex: 'ab' * 32,
      post: (uri, body) async {
        fail('must not hit network when local exhausted');
        return {};
      },
    );
    expect(remote2['error'], 'trial_exhausted');
    expect(
      connectAllowedTrialOrPaid(
        keygenOk: false,
        trialOk: await gate.deviceTrialAllowsConnect(),
      ),
      isFalse,
    );
  });
}

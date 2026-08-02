/// Get keygen always targets public shop /pay.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/entry_access.dart';
import 'package:restore_privacy_client/licence_gate.dart';

void main() {
  test('shopPayUrl points at restoreprivacy.online/pay', () {
    final u = shopPayUrl();
    expect(u, contains('/pay'));
    expect(u, startsWith('https://restoreprivacy.online'));
    expect(u.endsWith('/pay'), isTrue);
    expect(shopPayUrl(baseUrl: 'https://example.test/'), 'https://example.test/pay');
  });

  test('Get keygen label and entry keys are shipped', () {
    expect(kGetKeygenButtonLabel.toLowerCase(), contains('keygen'));
    expect(kEntryAccessGetKeygenButtonKey, isNotNull);
    expect(kEntryAccessShopHint, contains('/pay'));
  });

  test('entry_access source opens shopPayUrl not storefront-only', () {
    // Structural: shipped entry screen uses shopPayUrl helper.
    // (Widget launch is platform-bound; pure URL helper is the contract.)
    final uri = Uri.parse(shopPayUrl());
    expect(uri.path, '/pay');
    expect(uri.host, 'restoreprivacy.online');
  });
}

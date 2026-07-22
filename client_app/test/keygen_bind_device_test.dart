/// Drives real [LicenceGate.importKeygenAndVerify] bind path (POST body contract).
///
/// Injectable [postBind] proves `/api/bind-device-entitlement` is called with
/// session_id + device_pub after active keygen — parity with desktop bind.
library;

import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/licence_gate.dart';

void main() {
  test('importKeygenAndVerify POSTs bind-device-entitlement when active', () async {
    final backend = MemoryLicenceBackend();
    final gate = LicenceGate(backend);

    Uri? postedUri;
    List<int>? postedBody;
    var bindCalls = 0;

    final status = await gate.importKeygenAndVerify(
      'RPT-KEY-AAAA-BBBB-CCCC',
      fetch: (id) async => {
        'status': 'active',
        'connect_allowed': true,
        'session_id': 'cs_test_bind_flutter',
        'keygen': 'RPT-KEY-AAAA-BBBB-CCCC',
      },
      resolveDevicePub: () async =>
          '00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff',
      postBind: (uri, body) async {
        bindCalls += 1;
        postedUri = uri;
        postedBody = body;
        return {'ok': true, 'session_id': 'cs_test_bind_flutter'};
      },
    );

    expect(status, kPaymentStatusActive);
    expect(bindCalls, 1);
    expect(postedUri, isNotNull);
    expect(postedUri!.path, contains('bind-device-entitlement'));
    final decoded = jsonDecode(utf8.decode(postedBody!)) as Map<String, dynamic>;
    expect(decoded['session_id'], 'cs_test_bind_flutter');
    expect(
      decoded['device_pub'],
      '00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff',
    );
    expect(await gate.paymentAllowsConnect(), isTrue);
  });

  test('bindDeviceEntitlement fails closed without device pub', () async {
    final gate = LicenceGate(MemoryLicenceBackend());
    final r = await gate.bindDeviceEntitlement(
      'cs_x',
      devicePubHex: '',
      resolveDevicePub: () async => '',
      post: (uri, body) async {
        fail('post must not run without device pub');
      },
    );
    expect(r['ok'], isFalse);
    expect(r['error'], 'missing_session_or_device');
  });
}

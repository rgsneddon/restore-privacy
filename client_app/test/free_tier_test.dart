import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/free_tier.dart';
import 'package:restore_privacy_client/residual_privacy_policy.dart';
import 'package:restore_privacy_client/rpt_config.dart';

/// Free-tier helpers when [kFreeTierFromEnvironment] is false (default test build).
/// Compile-time free path is covered by [resolveFreeTierPrivacy] null when off
/// and locked defaults constants (always available).
void main() {
  test('kFreeTierVersion is permanent 3.3.3', () {
    expect(kFreeTierVersion, '3.3.3');
    expect(kFreeTierVersion.startsWith('0.'), isFalse);
  });

  test('freeAwareProductVersion uses 3.3.3 only when free enabled', () {
    // Default test binary is paid pin (dart-define off).
    expect(freeAwareProductVersion('0.4.0'), freeTierEnabled ? '3.3.3' : '0.4.0');
  });

  test('FreeTierLockedPrivacy defaults are lean Iceland', () {
    const p = FreeTierLockedPrivacy.defaults;
    expect(p.trafficShape, isFalse);
    expect(p.outerObfuscation, isFalse);
    expect(p.multihop, isFalse);
    expect(p.residualHost, kFreeTierEntryHost);
    expect(p.residualHost, RptConfig.entryHost);
  });

  test('paid residual defaults still privacy-max when free off', () {
    if (freeTierEnabled) {
      final f = resolveResidualPrivacy(trafficShape: true, outerObfuscation: true);
      expect(f.padding, isFalse);
      expect(f.outerObfuscation, isFalse);
    } else {
      final f = resolveResidualPrivacy();
      expect(f.padding, isTrue);
      expect(f.outerObfuscation, isTrue);
      expect(f.multihop, isFalse);
    }
  });

  test('RptConfig paid productVersion is 0.4.0 catalog pin', () {
    expect(RptConfig.productVersion, '0.4.0');
    expect(RptConfig.displayProductVersion, freeAwareProductVersion('0.4.0'));
    // Free: multi-hop forced off; paid default also off without settings.
    expect(RptConfig.multiHopEnabled, isFalse);
    expect(RptConfig.host, RptConfig.entryHost);
  });
}

import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/residual_privacy_policy.dart';

void main() {
  group('resolveResidualPrivacy', () {
    test('product defaults: shape/obfs/multihop OFF (lean residual)', () {
      final f = resolveResidualPrivacy();
      expect(f.padding, isFalse);
      expect(f.cover, isFalse);
      expect(f.sendJitter, isFalse);
      expect(f.outerObfuscation, isFalse);
      expect(f.multihop, isFalse);
      expect(f.padding, ResidualPrivacyFlags.productDefaults.padding);
      expect(f.outerObfuscation, ResidualPrivacyFlags.productDefaults.outerObfuscation);
    });

    test('shape ON enables padding, cover, and send jitter', () {
      final f = resolveResidualPrivacy(trafficShape: true);
      expect(f.padding, isTrue);
      expect(f.cover, isTrue);
      expect(f.sendJitter, isTrue);
      // Obfs independent of shape — still product default off
      expect(f.outerObfuscation, isFalse);
      expect(f.multihop, isFalse);
    });

    test('outer obfuscation ON enables wrap only', () {
      final f = resolveResidualPrivacy(outerObfuscation: true);
      expect(f.padding, isFalse);
      expect(f.cover, isFalse);
      expect(f.sendJitter, isFalse);
      expect(f.outerObfuscation, isTrue);
    });

    test('both shape and obfs OFF → lean residual DATA', () {
      final f = resolveResidualPrivacy(
        trafficShape: false,
        outerObfuscation: false,
      );
      expect(f.padding, isFalse);
      expect(f.cover, isFalse);
      expect(f.sendJitter, isFalse);
      expect(f.outerObfuscation, isFalse);
      expect(f.multihop, isFalse);
    });

    test('multihop ON is independent of shape/obfs', () {
      final f = resolveResidualPrivacy(
        trafficShape: false,
        outerObfuscation: false,
        multihop: true,
      );
      expect(f.multihop, isTrue);
      expect(f.padding, isFalse);
      expect(f.outerObfuscation, isFalse);
    });
  });

  group('residualPrivacyFromStoredPrefs', () {
    test('empty map uses product lean-off defaults', () {
      final f = residualPrivacyFromStoredPrefs({});
      expect(f.padding, isFalse);
      expect(f.outerObfuscation, isFalse);
      expect(f.multihop, isFalse);
    });

    test('explicit false for shape/obfs disables residual DATA flags', () {
      final f = residualPrivacyFromStoredPrefs({
        kResidualKeyTrafficShape: false,
        kResidualKeyOuterObfuscation: false,
        kResidualKeyMultihop: false,
      });
      expect(f.padding, isFalse);
      expect(f.cover, isFalse);
      expect(f.sendJitter, isFalse);
      expect(f.outerObfuscation, isFalse);
      expect(f.multihop, isFalse);
    });

    test('null keys treated as product defaults (shape/obfs off)', () {
      final f = residualPrivacyFromStoredPrefs({
        kResidualKeyTrafficShape: null,
        kResidualKeyOuterObfuscation: null,
        kResidualKeyMultihop: null,
      });
      expect(f.padding, isFalse);
      expect(f.outerObfuscation, isFalse);
      expect(f.multihop, isFalse);
    });

    test('multihop true only when explicitly stored true', () {
      final off = residualPrivacyFromStoredPrefs({
        kResidualKeyMultihop: false,
      });
      expect(off.multihop, isFalse);
      final on = residualPrivacyFromStoredPrefs({
        kResidualKeyMultihop: true,
      });
      expect(on.multihop, isTrue);
    });

    test('explicit true for shape/obfs enables residual DATA flags', () {
      final f = residualPrivacyFromStoredPrefs({
        kResidualKeyTrafficShape: true,
        kResidualKeyOuterObfuscation: true,
        kResidualKeyMultihop: false,
      });
      expect(f.padding, isTrue);
      expect(f.cover, isTrue);
      expect(f.sendJitter, isTrue);
      expect(f.outerObfuscation, isTrue);
      expect(f.multihop, isFalse);
    });
  });
}

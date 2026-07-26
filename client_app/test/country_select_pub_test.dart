import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/country_select.dart';
import 'package:restore_privacy_client/rpt_config.dart';

void main() {
  tearDown(() {
    RptConfig.setRuntimeMultiHop(null);
    RptConfig.setRuntimeEntryCountry(kDefaultEntryCountry);
  });

  test('pub name follows residual dial host (IS/RO/US)', () {
    expect(residualNodePubNameForHost('82.221.101.241'), 'node_elgamal.pub');
    expect(residualNodePubNameForHost('185.146.232.107'), 'exit_node_elgamal.pub');
    expect(residualNodePubNameForHost('5.161.242.85'), 'us_node_elgamal.pub');
  });

  test('catalog has IS RO US and no DE monopin', () {
    final codes = kProductCountryCatalog.map((o) => o.code).toSet();
    expect(codes, {'IS', 'RO', 'US'});
    expect(kProductCountryCatalog.any((o) => o.host == '167.233.224.5'), isFalse);
    expect(
      kProductCountryCatalog.any((o) => o.host == '5.161.242.85'),
      isTrue,
    );
  });

  test('stale DE prefs normalize to United States', () {
    expect(normalizeEntryCountry('DE'), 'US');
    expect(normalizeEntryCountry('Germany'), 'US');
    RptConfig.setRuntimeMultiHop(false);
    RptConfig.setRuntimeEntryCountry('DE');
    expect(RptConfig.host, '5.161.242.85');
    expect(RptConfig.residualNodePubName, 'us_node_elgamal.pub');
  });

  test('US aliases and single-hop uses us pub', () {
    expect(normalizeEntryCountry('US'), 'US');
    expect(normalizeEntryCountry('USA'), 'US');
    expect(normalizeEntryCountry('United States'), 'US');
    RptConfig.setRuntimeMultiHop(false);
    RptConfig.setRuntimeEntryCountry('US');
    expect(RptConfig.host, '5.161.242.85');
    expect(RptConfig.residualNodePubName, 'us_node_elgamal.pub');
  });

  test('RO single-hop uses exit pub', () {
    RptConfig.setRuntimeMultiHop(false);
    RptConfig.setRuntimeEntryCountry('RO');
    expect(RptConfig.host, '185.146.232.107');
    expect(RptConfig.residualNodePubName, 'exit_node_elgamal.pub');
  });

  test('default United States host and us_node pub', () {
    RptConfig.setRuntimeMultiHop(false);
    RptConfig.setRuntimeEntryCountry(null);
    expect(kDefaultEntryCountry, 'US');
    expect(RptConfig.host, '5.161.242.85');
    expect(RptConfig.residualNodePubName, 'us_node_elgamal.pub');
  });
}

import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/country_select.dart';
import 'package:restore_privacy_client/rpt_config.dart';

void main() {
  tearDown(() {
    RptConfig.setRuntimeMultiHop(null);
    RptConfig.setRuntimeEntryCountry(kDefaultEntryCountry);
  });

  test('pub name follows residual dial host (IS/DE/US)', () {
    expect(residualNodePubNameForHost('82.221.101.241'), 'node_elgamal.pub');
    expect(residualNodePubNameForHost('178.105.187.178'), 'de_node_elgamal.pub');
    expect(residualNodePubNameForHost('5.161.242.85'), 'us_node_elgamal.pub');
  });

  test('catalog has IS DE US and no RO monopin', () {
    final codes = kProductCountryCatalog.map((o) => o.code).toSet();
    expect(codes, {'IS', 'DE', 'US'});
    expect(kProductCountryCatalog.any((o) => o.host == '185.146.232.107'), isFalse);
    expect(
      kProductCountryCatalog.any((o) => o.host == '178.105.187.178'),
      isTrue,
    );
  });

  test('stale RO prefs normalize to Germany', () {
    expect(normalizeEntryCountry('RO'), 'DE');
    expect(normalizeEntryCountry('Romania'), 'DE');
    RptConfig.setRuntimeMultiHop(false);
    RptConfig.setRuntimeEntryCountry('RO');
    expect(RptConfig.host, '178.105.187.178');
    expect(RptConfig.residualNodePubName, 'de_node_elgamal.pub');
  });

  test('DE aliases and single-hop uses de pub', () {
    expect(normalizeEntryCountry('DE'), 'DE');
    expect(normalizeEntryCountry('Germany'), 'DE');
    RptConfig.setRuntimeMultiHop(false);
    RptConfig.setRuntimeEntryCountry('DE');
    expect(RptConfig.host, '178.105.187.178');
    expect(RptConfig.residualNodePubName, 'de_node_elgamal.pub');
  });

  test('US single-hop uses us pub', () {
    RptConfig.setRuntimeMultiHop(false);
    RptConfig.setRuntimeEntryCountry('US');
    expect(RptConfig.host, '5.161.242.85');
    expect(RptConfig.residualNodePubName, 'us_node_elgamal.pub');
  });

  test('default Germany host and de_node pub', () {
    RptConfig.setRuntimeMultiHop(false);
    RptConfig.setRuntimeEntryCountry(null);
    expect(kDefaultEntryCountry, 'DE');
    expect(RptConfig.host, '178.105.187.178');
    expect(RptConfig.residualNodePubName, 'de_node_elgamal.pub');
  });

  test('multi-hop from US dials DE exit with de pub', () {
    RptConfig.setRuntimeMultiHop(true);
    RptConfig.setRuntimeEntryCountry('US');
    expect(RptConfig.host, '178.105.187.178');
    expect(RptConfig.residualNodePubName, 'de_node_elgamal.pub');
  });
}

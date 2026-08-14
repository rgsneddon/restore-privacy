import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/country_select.dart';
import 'package:restore_privacy_client/rpt_config.dart';

void main() {
  tearDown(() {
    RptConfig.setRuntimeMultiHop(null);
    RptConfig.setRuntimeEntryCountry(kDefaultEntryCountry);
  });

  test('pub name follows residual dial host (DE; retired IS/US→de)', () {
    expect(residualNodePubNameForHost('82.221.101.241'), 'de_node_elgamal.pub');
    expect(residualNodePubNameForHost('178.105.187.178'), 'de_node_elgamal.pub');
    expect(residualNodePubNameForHost('5.161.242.85'), 'de_node_elgamal.pub');
  });

  test('catalog is Germany only and no retired monopin hosts', () {
    final codes = kProductCountryCatalog.map((o) => o.code).toSet();
    expect(codes, {'DE'});
    expect(kProductCountryCatalog.any((o) => o.name == 'Iceland'), isFalse);
    expect(kProductCountryCatalog.any((o) => o.host == '185.146.232.107'), isFalse);
    expect(kProductCountryCatalog.any((o) => o.host == '5.161.242.85'), isFalse);
    expect(
      kProductCountryCatalog.any((o) => o.host == '178.105.187.178'),
      isTrue,
    );
  });

  test('stale IS prefs normalize to Germany', () {
    expect(normalizeEntryCountry('IS'), 'DE');
    expect(normalizeEntryCountry('Iceland'), 'DE');
    RptConfig.setRuntimeMultiHop(false);
    RptConfig.setRuntimeEntryCountry('IS');
    expect(RptConfig.host, '178.105.187.178');
    expect(RptConfig.residualNodePubName, 'de_node_elgamal.pub');
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

  test('stale US single-hop normalizes to DE with de pub', () {
    RptConfig.setRuntimeMultiHop(false);
    RptConfig.setRuntimeEntryCountry('US');
    expect(normalizeEntryCountry('US'), 'DE');
    expect(RptConfig.host, '178.105.187.178');
    expect(RptConfig.residualNodePubName, 'de_node_elgamal.pub');
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

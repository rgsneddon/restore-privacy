import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/country_select.dart';
import 'package:restore_privacy_client/rpt_config.dart';

void main() {
  tearDown(() {
    RptConfig.setRuntimeMultiHop(null);
    RptConfig.setRuntimeEntryCountry(kDefaultEntryCountry);
  });

  test('pub name follows residual dial host (IS/RO/DE)', () {
    expect(residualNodePubNameForHost('82.221.101.241'), 'node_elgamal.pub');
    expect(residualNodePubNameForHost('185.146.232.107'), 'exit_node_elgamal.pub');
    expect(residualNodePubNameForHost('167.233.224.5'), 'de_node_elgamal.pub');
  });

  test('DE single-hop uses DE host and de_node pub', () {
    RptConfig.setRuntimeMultiHop(false);
    RptConfig.setRuntimeEntryCountry('DE');
    expect(RptConfig.host, '167.233.224.5');
    expect(RptConfig.residualNodePubName, 'de_node_elgamal.pub');
  });

  test('DE multi-hop dials non-DE peer and matches that peer pub', () {
    RptConfig.setRuntimeMultiHop(true);
    RptConfig.setRuntimeEntryCountry('DE');
    // First non-DE catalog peer is IS
    expect(RptConfig.host, '82.221.101.241');
    expect(RptConfig.residualNodePubName, 'node_elgamal.pub');
    // Not the Romania exit pin while dialing IS
    expect(RptConfig.residualNodePubName, isNot('exit_node_elgamal.pub'));
  });

  test('RO single-hop uses exit pub', () {
    RptConfig.setRuntimeMultiHop(false);
    RptConfig.setRuntimeEntryCountry('RO');
    expect(RptConfig.host, '185.146.232.107');
    expect(RptConfig.residualNodePubName, 'exit_node_elgamal.pub');
  });

  test('default Iceland host and node pub', () {
    RptConfig.setRuntimeMultiHop(false);
    RptConfig.setRuntimeEntryCountry(null);
    expect(RptConfig.host, '82.221.101.241');
    expect(RptConfig.residualNodePubName, 'node_elgamal.pub');
  });
}

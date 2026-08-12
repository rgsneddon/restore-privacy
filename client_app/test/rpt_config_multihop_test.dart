import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/rpt_config.dart';

void main() {
  tearDown(() {
    RptConfig.setRuntimeMultiHop(null);
  });

  test('runtime multi-hop override drives residual host and pub name', () {
    // Product default entry is Germany (de_node_elgamal.pub).
    RptConfig.setRuntimeMultiHop(false);
    expect(RptConfig.multiHopEnabled, isFalse);
    expect(RptConfig.host, RptConfig.entryHost);
    expect(RptConfig.residualNodePubName, 'de_node_elgamal.pub');

    // Multi-hop with DE entry stays on DE (exit == entry); pub remains DE pin.
    RptConfig.setRuntimeMultiHop(true);
    expect(RptConfig.multiHopEnabled, isTrue);
    expect(RptConfig.host, RptConfig.exitHost);
    expect(RptConfig.residualNodePubName, 'de_node_elgamal.pub');
  });

  test('productVersion matches paid monopin pin', () {
    // Paid pin tracks monorepo client/VERSION (not a frozen 0.4.x label).
    expect(RptConfig.productVersion, isNot(isEmpty));
    expect(RptConfig.productVersion.contains('.'), isTrue);
    expect(RptConfig.productVersion.startsWith('0.4.'), isFalse);
  });
}


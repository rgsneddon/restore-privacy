import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/rpt_config.dart';

void main() {
  tearDown(() {
    RptConfig.setRuntimeMultiHop(null);
  });

  test('runtime multi-hop override drives residual host and pub name', () {
    RptConfig.setRuntimeMultiHop(false);
    expect(RptConfig.multiHopEnabled, isFalse);
    expect(RptConfig.host, RptConfig.entryHost);
    expect(RptConfig.residualNodePubName, 'node_elgamal.pub');

    RptConfig.setRuntimeMultiHop(true);
    expect(RptConfig.multiHopEnabled, isTrue);
    expect(RptConfig.host, RptConfig.exitHost);
    expect(RptConfig.residualNodePubName, 'exit_node_elgamal.pub');
  });

  test('productVersion is 0.4.0 monopin', () {
    expect(RptConfig.productVersion, '0.4.0');
  });
}

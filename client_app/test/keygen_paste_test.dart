/// Paste into product keygen entry fields (forced sheet + Settings).
///
/// Drives the shipped [KeygenEntryField] / [pasteKeygenFromClipboard] path —
/// not a reimplementation of paste.
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:restore_privacy_client/connect_status.dart';
import 'package:restore_privacy_client/keygen_field.dart';
import 'package:restore_privacy_client/licence_gate.dart';
import 'package:restore_privacy_client/main.dart';
import 'package:restore_privacy_client/theme.dart';

/// Mock system clipboard for tests (Clipboard.setData/getData channel).
void _installClipboardMock({String? initial}) {
  var text = initial ?? '';
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(SystemChannels.platform, (call) async {
    switch (call.method) {
      case 'Clipboard.setData':
        final args = call.arguments as Map<dynamic, dynamic>?;
        text = (args?['text'] as String?) ?? '';
        return null;
      case 'Clipboard.getData':
        return <String, dynamic>{'text': text};
      case 'Clipboard.hasStrings':
        return <String, dynamic>{'value': text.isNotEmpty};
      default:
        return null;
    }
  });
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const sampleKeygen = 'RPT-KEY-BD16-C82F-D94E';
  const channel = MethodChannel('restore_privacy/vpn');

  setUp(() {
    _installClipboardMock();
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
      if (call.method == 'status' ||
          call.method == 'preparePacketTunnelConfiguration') {
        return {
          'ok': false,
          'connected': false,
          'fullTunnelActive': false,
          'message': 'Disconnected',
        };
      }
      return null;
    });
  });

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, null);
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, null);
  });

  test('pasteKeygenFromClipboard applies clipboard text to controller', () async {
    final controller = TextEditingController();
    await Clipboard.setData(const ClipboardData(text: sampleKeygen));
    final ok = await pasteKeygenFromClipboard(controller);
    expect(ok, isTrue);
    expect(controller.text, sampleKeygen);
    // Empty clipboard leaves controller unchanged
    await Clipboard.setData(const ClipboardData(text: ''));
    final emptyOk = await pasteKeygenFromClipboard(controller);
    expect(emptyOk, isFalse);
    expect(controller.text, sampleKeygen);
    controller.dispose();
  });

  test('keygenFieldAllowsPaste rejects readOnly / no-selection / formatters', () {
    final controller = TextEditingController();
    final good = TextField(
      controller: controller,
      enableInteractiveSelection: true,
      readOnly: false,
    );
    expect(keygenFieldAllowsPaste(good), isTrue);

    final readOnly = TextField(controller: controller, readOnly: true);
    expect(keygenFieldAllowsPaste(readOnly), isFalse);

    final noSelect = TextField(
      controller: controller,
      enableInteractiveSelection: false,
    );
    expect(keygenFieldAllowsPaste(noSelect), isFalse);

    final filtered = TextField(
      controller: controller,
      inputFormatters: [FilteringTextInputFormatter.digitsOnly],
    );
    expect(keygenFieldAllowsPaste(filtered), isFalse);
    controller.dispose();
  });

  testWidgets('KeygenEntryField Paste button puts clipboard into field',
      (tester) async {
    final controller = TextEditingController();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: KeygenEntryField(controller: controller, autofocus: true),
        ),
      ),
    );
    await tester.pump();

    final field = tester.widget<TextField>(find.byKey(kKeygenTextFieldKey));
    expect(keygenFieldAllowsPaste(field), isTrue);
    expect(field.enableInteractiveSelection, isTrue);
    expect(field.readOnly, isFalse);
    expect(field.inputFormatters ?? const [], isEmpty);

    await Clipboard.setData(const ClipboardData(text: sampleKeygen));
    await tester.tap(find.byKey(kKeygenPasteButtonKey));
    await tester.pump();

    expect(controller.text, sampleKeygen);
    expect(find.text(sampleKeygen), findsWidgets);
    controller.dispose();
  });

  testWidgets('KeygenEntryField accepts direct text edit (typed or injected)',
      (tester) async {
    final controller = TextEditingController();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: KeygenEntryField(controller: controller),
        ),
      ),
    );
    await tester.pump();

    await tester.enterText(find.byKey(kKeygenTextFieldKey), sampleKeygen);
    await tester.pump();
    expect(controller.text, sampleKeygen);
    controller.dispose();
  });

  testWidgets(
      'forced Enter licence keygen sheet field accepts paste via Paste control',
      (tester) async {
    // Licence accepted, no keygen → needsKeygenUnlock → forced sheet on load.
    SharedPreferences.setMockInitialValues({
      'licence_accepted': true,
      'licence_id': 'FULL-COPYRIGHT-2026',
      'licence_accepted_at': '1',
    });

    await tester.pumpWidget(const RestorePrivacyApp());
    await tester.pump();
    // post-frame callback opens keygen sheet
    await tester.pump(const Duration(milliseconds: 200));
    await tester.pump(const Duration(milliseconds: 200));

    expect(find.text(kKeygenPromptTitle), findsOneWidget);
    expect(find.byKey(kKeygenTextFieldKey), findsOneWidget);

    final field = tester.widget<TextField>(find.byKey(kKeygenTextFieldKey));
    expect(keygenFieldAllowsPaste(field), isTrue);

    await Clipboard.setData(const ClipboardData(text: sampleKeygen));
    await tester.tap(find.byKey(kKeygenPasteButtonKey));
    await tester.pump();

    final editable = tester.widget<TextField>(find.byKey(kKeygenTextFieldKey));
    expect(editable.controller?.text, sampleKeygen);

    expect(find.text('Unlock Connect'), findsOneWidget);
    expect(find.text(kAppTitle), findsWidgets);
  });

  test('shouldDismissKeygenSheetAfterUnlock: active status closes sheet', () {
    expect(
      shouldDismissKeygenSheetAfterUnlock(paymentAllowsConnect: true),
      isTrue,
    );
    expect(
      shouldDismissKeygenSheetAfterUnlock(
        paymentAllowsConnect: false,
        paymentStatus: 'active',
      ),
      isTrue,
    );
    expect(
      shouldDismissKeygenSheetAfterUnlock(
        paymentAllowsConnect: false,
        paymentStatus: 'failed',
      ),
      isFalse,
    );
  });

  test('looksLikeProductKeygen recognizes fulfilment keygens', () {
    expect(looksLikeProductKeygen(sampleKeygen), isTrue);
    expect(looksLikeProductKeygen('  $sampleKeygen  '), isTrue);
    expect(looksLikeProductKeygen('RPT-KEY-'), isFalse);
    expect(looksLikeProductKeygen('not-a-key'), isFalse);
    expect(looksLikeProductKeygen(''), isFalse);
  });
}

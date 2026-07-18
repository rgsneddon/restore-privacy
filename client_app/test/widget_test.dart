import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:restore_privacy_client/main.dart';
import 'package:restore_privacy_client/theme.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const channel = MethodChannel('restore_privacy/vpn');

  setUp(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
      if (call.method == 'connect') {
        return {
          'ok': false,
          'message': 'test harness — VPN not started',
        };
      }
      if (call.method == 'disconnect') {
        return {'ok': true, 'message': 'Disconnected'};
      }
      return null;
    });
  });

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, null);
  });

  testWidgets('retro UI banner and privacy string present; auto-connect path runs',
      (WidgetTester tester) async {
    await tester.pumpWidget(const RestorePrivacyApp());
    await tester.pump(); // first frame
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text(kBannerTitle), findsOneWidget);
    // Scrolling privacy text appears in log on launch and in marquee
    expect(find.textContaining('lightweight vpn to restore your privacy'), findsWidgets);
    // Auto-connect invokes channel — status updated
    expect(find.textContaining('Auto-connect'), findsWidgets);

    // Banner color is product dark blue
    final banner = tester.widget<Container>(
      find.descendant(
        of: find.byType(SafeArea),
        matching: find.byWidgetPredicate(
          (w) => w is Container && w.color == kBannerBg,
        ),
      ).first,
    );
    expect(banner.color, kBannerBg);
  });
}

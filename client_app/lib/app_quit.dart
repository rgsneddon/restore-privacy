/// Discrete main-screen Quit: stop residual tunnel, then fully exit the process.
///
/// Product rule: minimize / background / hide-to-tray keep the Packet Tunnel up.
/// Only **Disconnect** or **Quit** stop protection. Quit always disconnects first
/// so residual is not left running after the UI is gone.
library;

import 'dart:io' show Platform, exit;

import 'package:flutter/foundation.dart'
    show TargetPlatform, defaultTargetPlatform, kIsWeb;
import 'package:flutter/services.dart' show MethodChannel, SystemNavigator;

/// Button label on the main connection screen.
const String kQuitButtonLabel = 'Quit';

/// Layout marker: control sits **lower left** of the main connection screen.
const String kQuitButtonPlacement = 'bottomLeft';

/// Tooltip / accessibility hint (low visual weight).
const String kQuitButtonTooltip =
    'Stop residual VPN and quit the app completely';

/// True when this platform shows the main-screen discrete Quit control.
///
/// Shown on **all** residual client platforms (macOS, iOS, Android, Windows,
/// Linux Flutter shells). Web is excluded.
bool showsMainScreenQuitButton({
  bool? isMacOS,
  bool? isIOS,
  bool? isAndroid,
  bool? isWindows,
  bool? isLinux,
}) {
  if (kIsWeb) return false;
  final mac = isMacOS ?? (!kIsWeb && Platform.isMacOS);
  final ios = isIOS ?? (!kIsWeb && Platform.isIOS);
  final android = isAndroid ?? (!kIsWeb && Platform.isAndroid);
  final win = isWindows ?? (!kIsWeb && Platform.isWindows);
  final linux = isLinux ?? (!kIsWeb && Platform.isLinux);
  return mac || ios || android || win || linux;
}

/// Same as [showsMainScreenQuitButton] using Flutter's target platform
/// (useful when [Platform] is unavailable in some test harnesses).
bool showsMainScreenQuitForTarget(TargetPlatform platform) {
  return platform == TargetPlatform.macOS ||
      platform == TargetPlatform.iOS ||
      platform == TargetPlatform.android ||
      platform == TargetPlatform.windows ||
      platform == TargetPlatform.linux;
}

/// Running-platform helper for UI wiring (no inject).
bool showsMainScreenQuitOnThisDevice() {
  if (kIsWeb) return false;
  return showsMainScreenQuitForTarget(defaultTargetPlatform) ||
      showsMainScreenQuitButton();
}

/// Order of operations for Quit: tunnel stop, then process exit.
///
/// Pure sequence for unit tests — inject [stopTunnel] and [exitApp] so the
/// harness never kills itself. Production wires real [VpnController.disconnect]
/// and [exitAppProcess].
Future<void> performQuitSequence({
  required Future<void> Function() stopTunnel,
  required void Function() exitApp,
}) async {
  await stopTunnel();
  exitApp();
}

/// Method channel for platform full-process exit (Android finishAndRemoveTask).
const MethodChannel kAppQuitChannel = MethodChannel('restore_privacy/vpn');

/// Android channel method: finish activity + remove task + kill process.
const String kAndroidFullExitMethod = 'fullExit';

/// Fully terminate the host process (not hide-to-tray / minimize).
///
/// Call only after [performQuitSequence]'s tunnel stop has completed.
///
/// On Android, [SystemNavigator.pop] alone only finishes the activity and can
/// leave the process idle in the background. We call native [kAndroidFullExitMethod]
/// (`finishAndRemoveTask` + `Process.killProcess`) then hard [exit] as backup.
void exitAppProcess() {
  if (!kIsWeb && Platform.isAndroid) {
    // Fire-and-forget native full exit; still fall through to dart:io exit.
    try {
      kAppQuitChannel.invokeMethod<void>(kAndroidFullExitMethod);
    } catch (_) {}
  } else {
    try {
      SystemNavigator.pop();
    } catch (_) {}
  }
  // dart:io exit — required so UI + host process leave (not idle).
  exit(0);
}

/// Testable Android exit path planner (pure): which steps the platform must run.
///
/// Production Android native implements the same order in MainActivity.fullExit.
List<String> androidFullExitSteps() {
  return const [
    'finishAndRemoveTask',
    'process_killProcess',
  ];
}

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
///
/// [exitApp] is async so Android can **await** native `fullExit` before any
/// dart:io [exit] backup — fire-and-forget invokeMethod + immediate exit(0)
/// kills the isolate before the platform path runs (idle process bug).
Future<void> performQuitSequence({
  required Future<void> Function() stopTunnel,
  required Future<void> Function() exitApp,
}) async {
  await stopTunnel();
  await exitApp();
}

/// Method channel for platform full-process exit (Android finishAndRemoveTask).
const MethodChannel kAppQuitChannel = MethodChannel('restore_privacy/vpn');

/// Android channel method: finish activity + remove task + kill process.
const String kAndroidFullExitMethod = 'fullExit';

/// Grace before dart:io backup exit if native [kAndroidFullExitMethod] did not
/// kill the process (channel missing / tests). Must exceed native
/// [androidFullExitKillDelayMs] so AMS task removal + DISCONNECT can finish.
const Duration kAndroidFullExitBackupDelay = Duration(milliseconds: 500);

/// Mirrors MainActivity.FULL_EXIT_KILL_DELAY_MS (deferred kill after task remove).
const int androidFullExitKillDelayMs = 300;

/// Fully terminate the host process (not hide-to-tray / minimize).
///
/// Call only after [performQuitSequence]'s tunnel stop has completed.
///
/// On Android, [SystemNavigator.pop] alone only finishes the activity and can
/// leave a disconnected shell in the background. We **await** native
/// [kAndroidFullExitMethod], which force-stops the VPN service (no FGS restart),
/// removes all app tasks, then deferred killProcess after
/// [androidFullExitKillDelayMs]. A short backup [exit] runs only if still alive.
///
/// Non-Android: SystemNavigator.pop then dart:io exit.
Future<void> exitAppProcess({
  MethodChannel? channel,
  bool? isAndroid,
  void Function(int code)? exitFn,
  Future<void> Function(Duration duration)? delay,
}) async {
  final android = isAndroid ?? (!kIsWeb && Platform.isAndroid);
  final ch = channel ?? kAppQuitChannel;
  final doExit = exitFn ?? exit;
  final wait = delay ?? Future<void>.delayed;

  if (android) {
    // Deliver fullExit so native can stop VPN FGS, remove tasks, and kill.
    try {
      await ch.invokeMethod<dynamic>(kAndroidFullExitMethod);
    } catch (_) {
      // Channel missing / already dying — fall through to backup exit.
    }
    // If native killProcess ran we never reach here. Backup for test/failure.
    await wait(kAndroidFullExitBackupDelay);
    doExit(0);
    return;
  }

  try {
    SystemNavigator.pop();
  } catch (_) {}
  doExit(0);
}

/// Testable Android exit path planner (pure): which steps the platform must run.
///
/// Production Android native implements the same order in MainActivity.
List<String> androidFullExitSteps() {
  return const [
    'await_fullExit_channel',
    'force_stop_vpn_service',
    'remove_all_app_tasks',
    'finishAffinity',
    'finishAndRemoveTask',
    'deferred_process_kill',
  ];
}

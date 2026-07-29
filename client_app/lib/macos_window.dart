/// Thin method-channel bridge for macOS window hide-to-tray (menu bar status item).
///
/// Native shell: `RptTrayController` / `restore_privacy/window` channel.
/// Product Connect success does **not** auto-hide ([shouldHideToTrayAfterConnect]
/// is always false); hide remains available for explicit close-to-tray UX.
///
/// **Restore:** native `showMainWindow` deminiaturizes + orders front; Flutter
/// `trayShow` only rehydrates UI — never disconnects.

import 'dart:io' show Platform;

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/services.dart';

const String kMacWindowChannelName = 'restore_privacy/window';

/// Pure description of native restore steps after hide/minimize to tray.
///
/// Tests drive this helper so show-from-tray cannot regress to a no-op.
class MacWindowRestorePlan {
  const MacWindowRestorePlan({
    required this.unhideApp,
    required this.activateApp,
    required this.deminiaturize,
    required this.orderFront,
    required this.disconnectTunnel,
  });

  final bool unhideApp;
  final bool activateApp;
  final bool deminiaturize;
  final bool orderFront;

  /// Product policy: restore never stops Packet Tunnel.
  final bool disconnectTunnel;
}

/// Decide native restore actions for a window after tray hide or yellow minimize.
///
/// [isMiniaturized] — yellow traffic-light minimize.
/// [isAppHidden] — `NSApp.hide` / orderOut hide-to-tray path.
MacWindowRestorePlan macWindowRestorePlan({
  required bool isMiniaturized,
  required bool isAppHidden,
}) {
  return MacWindowRestorePlan(
    unhideApp: isAppHidden || isMiniaturized,
    activateApp: true,
    deminiaturize: isMiniaturized,
    orderFront: true,
    disconnectTunnel: false,
  );
}

/// True when dock reopen should call native show (tray keep-alive or no visible windows).
bool shouldHandleDockReopenToShowWindow({
  required bool trayMode,
  required bool hasVisibleWindows,
}) {
  return trayMode || !hasVisibleWindows;
}

class MacWindowController {
  MacWindowController({MethodChannel? channel})
      : _channel = channel ?? const MethodChannel(kMacWindowChannelName);

  final MethodChannel _channel;

  /// Whether this process can use the macOS tray/window channel.
  static bool get isSupported => !kIsWeb && Platform.isMacOS;

  /// Register native → Flutter callbacks (tray menu Disconnect / Show).
  void setHandlers({
    void Function()? onTrayDisconnect,
    void Function()? onTrayShow,
  }) {
    if (!isSupported) return;
    _channel.setMethodCallHandler((call) async {
      switch (call.method) {
        case 'trayDisconnect':
          onTrayDisconnect?.call();
          return null;
        case 'trayShow':
          onTrayShow?.call();
          return null;
        default:
          return null;
      }
    });
  }

  /// Hide the main window; keep process + Packet Tunnel alive (menu bar tray).
  Future<void> hideToTray({bool connected = true}) async {
    if (!isSupported) return;
    try {
      await _channel.invokeMethod<void>('hideToTray', {
        'connected': connected,
      });
    } on PlatformException {
      // Soft-fail: connect already succeeded; missing tray is non-fatal.
    } on MissingPluginException {
      // Non-macOS / tests without plugin.
    }
  }

  /// Restore the main window from the menu bar tray (native deminiaturize/order-front).
  Future<void> showFromTray() async {
    if (!isSupported) return;
    try {
      await _channel.invokeMethod<void>('showFromTray');
    } on PlatformException {
      // ignore
    } on MissingPluginException {
      // ignore
    }
  }

  /// Update tray tooltip / title for connected state.
  Future<void> setTrayConnected(bool connected) async {
    if (!isSupported) return;
    try {
      await _channel.invokeMethod<void>('setTrayConnected', {
        'connected': connected,
      });
    } on PlatformException {
      // ignore
    } on MissingPluginException {
      // ignore
    }
  }
}

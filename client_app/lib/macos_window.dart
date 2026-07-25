/// Thin method-channel bridge for macOS window hide-to-tray (menu bar status item).
///
/// Native shell: `RptTrayController` / `restore_privacy/window` channel.
/// Product Connect success does **not** auto-hide ([shouldHideToTrayAfterConnect]
/// is always false); hide remains available for explicit close-to-tray UX.

import 'dart:io' show Platform;

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/services.dart';

const String kMacWindowChannelName = 'restore_privacy/window';

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

  /// Restore the main window from the menu bar tray.
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

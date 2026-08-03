/// Durable system-tray product text for residual VPN (all platforms).
///
/// User-visible tray / status-item label and tooltip base is always
/// **Privacy, Restored** (comma + capital R). Do not rename casually —
/// this monopin and forward ships use this identity.
library;

/// Exact system-tray display text (Windows, Linux, macOS menu bar).
const String kTrayDisplayName = 'Privacy, Restored';

/// macOS status-item button title (compact bar).
const String kTrayStatusItemTitle = 'Privacy, Restored';

/// Tooltip when residual is connected.
String trayTooltipConnected() => '$kTrayDisplayName - connected (VPN active)';

/// Tooltip when residual is disconnected.
String trayTooltipDisconnected() => '$kTrayDisplayName - disconnected';

/// Tooltip when residual session-only (no full residual path).
String trayTooltipSessionOnly() => '$kTrayDisplayName - session only';

/// Pure: tray hover text from connection flags.
String trayTooltipForState({
  required bool connected,
  bool residual = true,
}) {
  if (connected && residual) return trayTooltipConnected();
  if (connected) return trayTooltipSessionOnly();
  return trayTooltipDisconnected();
}

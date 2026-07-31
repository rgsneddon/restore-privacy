import 'package:flutter/material.dart';

/// Product palette aligned with Windows client (restorebritain Cupertino chrome).
const String kPrivacyMessageText =
    'lightweight vpn to restore your privacy - no user data is retained - your privacy is restored';

const String kAppTitle = 'Restore Privacy';
const String kBannerTitle = 'Restore Privacy — Virtual Private Network';
const String kTrayProductName = 'Privacy Restored';

// Suite branding aliases (see suite_version.dart for monopin source of truth).
const String kSuiteAppTitle = 'Restore Privacy Suite';

// Cupertino / Windows product shell
const Color kChromeBg = Color(0xFFF2F5F7);
const Color kPanelBg = Color(0xFFFFFFFF);
const Color kPrimary = Color(0xFF2779AA);
const Color kPrimaryDark = Color(0xFF0070A3);
const Color kLightAccent = Color(0xFFDEEDF7);
const Color kText = Color(0xFF222222);
const Color kTextMuted = Color(0xFF363636);
const Color kStatusOk = Color(0xFF1B767E);
const Color kStatusError = Color(0xFFCD0A0A);
const Color kBorder = Color(0xFFAED0EA);
const Color kButtonConnectBg = kPrimary;
const Color kButtonDisconnectBg = kStatusOk;
const Color kButtonFg = Color(0xFFFFFFFF);
const Color kWhite = Color(0xFFFFFFFF);

// Legacy aliases used by older tests / docs
const Color kBannerBg = kPrimaryDark;
const Color kWindowBg = kPanelBg;
const Color kWindowFg = kText;
const Color kStatusFg = kTextMuted;
const Color kButtonBg = kButtonConnectBg;
const Color kButtonActiveBg = kButtonDisconnectBg;
const Color kLogBorder = kBorder;

/// Visual corner radius for rounded chrome (Material cards / buttons).
const double kCornerRadius = 14;

/// Asset path for product logo (Flutter pubspec assets).
const String kLogoAsset = 'assets/brand/logo-256.png';

/// Single control label for the Connect / Disconnect button.
String connectButtonLabel(bool connected) =>
    connected ? 'Disconnect' : 'Connect';

/// Plain-language **connected** status card title (not used while connecting).
///
/// When [residual] is true, dual-stack honesty follows [ipv4Residual] /
/// [ipv6Protected]: never claim "IPv6 ISP path blocked" when residual IPv6 is
/// off, and never claim "IPv4 via VPN" when residual IPv4 capture is off.
///
/// For Connecting vs Disconnected while busy, use [statusCardTitle] in
/// `connect_status.dart` so Android long handshakes stay on Connecting.
String plainConnectedStatus({
  String? vpnIp,
  bool residual = true,
  bool? ipv6Protected,
  bool? ipv4Residual,
}) {
  if (!residual) {
    return vpnIp == null || vpnIp.isEmpty
        ? 'Session only — residual IP still on ISP'
        : 'Session only — residual IP still on ISP ($vpnIp)';
  }
  // Full dual-stack honesty when either stack flag is known.
  if (ipv6Protected != null || ipv4Residual != null) {
    final v4 = ipv4Residual ?? true;
    final v6 = ipv6Protected ?? true;
    final ip = (vpnIp ?? '').trim();
    final suffix = ip.isEmpty ? '' : ' ($ip)';
    if (v4 && v6) {
      return 'Connected — VPN active; IPv6 ISP path blocked$suffix';
    }
    if (v4 && !v6) {
      return 'Connected — IPv4 via VPN; IPv6 not protected$suffix';
    }
    if (!v4 && v6) {
      return 'Connected — IPv4 residual off; IPv6 ISP path blocked$suffix';
    }
    return 'Connected — residual dual-stack off$suffix';
  }
  if (vpnIp != null && vpnIp.isNotEmpty) {
    return 'Connected — your traffic uses the VPN ($vpnIp)';
  }
  return 'Connected — protected';
}

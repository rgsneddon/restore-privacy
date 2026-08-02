import 'package:flutter/material.dart';

/// Product palette inherited from the original Evolve app ([AppTheme.dark])
/// with a coherent light variant. Dark is the default product look; light is
/// selected only from Settings.
///
/// Evolve reference tokens: bg `#0D0F14`, card `#151922`, primary `#6C63FF`,
/// secondary `#00D9C0`.
const String kPrivacyMessageText =
    'lightweight vpn to restore your privacy - no user data is retained - your privacy is restored';

const String kAppTitle = 'Restore Privacy';
const String kBannerTitle = 'Restore Privacy — Virtual Private Network';
const String kTrayProductName = 'Privacy Restored';

// Suite branding aliases (see suite_version.dart for monopin source of truth).
const String kSuiteAppTitle = 'Restore Privacy Suite';

// --- Evolve-derived tokens (dark product chrome) ---
const Color kEvolveBg = Color(0xFF0D0F14);
const Color kEvolveCard = Color(0xFF151922);
const Color kEvolvePrimary = Color(0xFF6C63FF);
const Color kEvolveSecondary = Color(0xFF00D9C0);
const Color kEvolveInputFill = Color(0xFF1A1F2B);
const Color kEvolveText = Color(0xFFE8EAED);
const Color kEvolveTextMuted = Color(0xFF9AA0A6);

// Light variant of the same family (not the old Cupertino blue set).
const Color kEvolveLightBg = Color(0xFFF4F5F8);
const Color kEvolveLightCard = Color(0xFFFFFFFF);
const Color kEvolveLightPrimary = Color(0xFF5B54E8);
const Color kEvolveLightSecondary = Color(0xFF00B8A3);
const Color kEvolveLightText = Color(0xFF1A1D24);
const Color kEvolveLightTextMuted = Color(0xFF5C6370);
const Color kEvolveLightBorder = Color(0xFFD0D4DE);

// Product shell constants default to Evolve dark (legacy call sites).
const Color kChromeBg = kEvolveBg;
const Color kPanelBg = kEvolveCard;
const Color kPrimary = kEvolvePrimary;
const Color kPrimaryDark = Color(0xFF5A52E0);
const Color kLightAccent = Color(0xFF2A2650);
const Color kText = kEvolveText;
const Color kTextMuted = kEvolveTextMuted;
const Color kStatusOk = kEvolveSecondary;
const Color kStatusError = Color(0xFFFF6B6B);
const Color kBorder = Color(0xFF2A3140);
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
/// Evolve uses 12; suite chrome stays slightly rounder for VPN panels.
const double kCornerRadius = 12;

/// Asset path for product logo (Flutter pubspec assets).
const String kLogoAsset = 'assets/brand/logo-256.png';

/// Appearance modes selectable only from Settings (persist as strings).
const String kAppearanceDark = 'dark';
const String kAppearanceLight = 'light';
const String kDefaultAppearance = kAppearanceDark;

/// Normalize stored preference → dark | light (default dark).
String normalizeSuiteAppearance(String? raw) {
  final s = (raw ?? '').trim().toLowerCase();
  if (s == kAppearanceLight || s == 'day' || s == 'bright') {
    return kAppearanceLight;
  }
  return kAppearanceDark;
}

/// Map appearance string to Flutter [ThemeMode] (never system-only).
ThemeMode suiteThemeModeFromAppearance(String? raw) {
  return normalizeSuiteAppearance(raw) == kAppearanceLight
      ? ThemeMode.light
      : ThemeMode.dark;
}

/// Dark theme: Evolve AppTheme.dark() tokens as the suite product chrome.
ThemeData buildSuiteThemeDark() {
  const bg = kEvolveBg;
  const card = kEvolveCard;
  const accent = kEvolvePrimary;
  const secondary = kEvolveSecondary;
  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    scaffoldBackgroundColor: bg,
    colorScheme: const ColorScheme.dark(
      primary: accent,
      secondary: secondary,
      surface: card,
      onPrimary: kWhite,
      onSecondary: Color(0xFF0D0F14),
      onSurface: kEvolveText,
      error: kStatusError,
    ),
    cardTheme: CardThemeData(
      color: card,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(kCornerRadius),
      ),
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: bg,
      foregroundColor: kEvolveText,
      elevation: 0,
      centerTitle: false,
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: card,
      indicatorColor: accent.withValues(alpha: 0.28),
      labelTextStyle: WidgetStatePropertyAll(
        const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: kEvolveInputFill,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: BorderSide(color: kWhite.withValues(alpha: 0.08)),
      ),
    ),
    switchTheme: SwitchThemeData(
      thumbColor: WidgetStateProperty.resolveWith((s) {
        if (s.contains(WidgetState.selected)) return kWhite;
        return kEvolveTextMuted;
      }),
      trackColor: WidgetStateProperty.resolveWith((s) {
        if (s.contains(WidgetState.selected)) return accent;
        return kEvolveInputFill;
      }),
    ),
    textTheme: ThemeData.dark().textTheme.apply(
      bodyColor: kEvolveText,
      displayColor: kEvolveText,
    ),
  );
}

/// Light theme: same Evolve family (purple/teal), light scaffolds.
ThemeData buildSuiteThemeLight() {
  const bg = kEvolveLightBg;
  const card = kEvolveLightCard;
  const accent = kEvolveLightPrimary;
  const secondary = kEvolveLightSecondary;
  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.light,
    scaffoldBackgroundColor: bg,
    colorScheme: const ColorScheme.light(
      primary: accent,
      secondary: secondary,
      surface: card,
      onPrimary: kWhite,
      onSecondary: kWhite,
      onSurface: kEvolveLightText,
      error: Color(0xFFC62828),
    ),
    cardTheme: CardThemeData(
      color: card,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(kCornerRadius),
        side: const BorderSide(color: kEvolveLightBorder),
      ),
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: card,
      foregroundColor: kEvolveLightText,
      elevation: 0,
      centerTitle: false,
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: card,
      indicatorColor: accent.withValues(alpha: 0.18),
      labelTextStyle: WidgetStatePropertyAll(
        const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: const Color(0xFFEEF0F5),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: kEvolveLightBorder),
      ),
    ),
    switchTheme: SwitchThemeData(
      thumbColor: WidgetStateProperty.resolveWith((s) {
        if (s.contains(WidgetState.selected)) return kWhite;
        return kEvolveLightTextMuted;
      }),
      trackColor: WidgetStateProperty.resolveWith((s) {
        if (s.contains(WidgetState.selected)) return accent;
        return const Color(0xFFD0D4DE);
      }),
    ),
    textTheme: ThemeData.light().textTheme.apply(
      bodyColor: kEvolveLightText,
      displayColor: kEvolveLightText,
    ),
  );
}

// ---------------------------------------------------------------------------
// Theme-resolved chrome (use these so Settings light/dark recolors the UI).
// Hard-coded kChromeBg/kPanelBg stay as dark Evolve defaults for non-widget
// code and tests that do not mount MaterialApp.
// ---------------------------------------------------------------------------

bool suiteThemeIsDark(BuildContext context) =>
    Theme.of(context).brightness == Brightness.dark;

Color suiteChromeBgOf(BuildContext context) =>
    Theme.of(context).scaffoldBackgroundColor;

Color suitePanelBgOf(BuildContext context) =>
    Theme.of(context).colorScheme.surface;

Color suitePrimaryOf(BuildContext context) =>
    Theme.of(context).colorScheme.primary;

Color suiteSecondaryOf(BuildContext context) =>
    Theme.of(context).colorScheme.secondary;

Color suiteOnPrimaryOf(BuildContext context) =>
    Theme.of(context).colorScheme.onPrimary;

Color suiteTextOf(BuildContext context) =>
    Theme.of(context).colorScheme.onSurface;

Color suiteTextMutedOf(BuildContext context) => suiteThemeIsDark(context)
    ? kEvolveTextMuted
    : kEvolveLightTextMuted;

Color suiteBorderOf(BuildContext context) => suiteThemeIsDark(context)
    ? kBorder
    : kEvolveLightBorder;

Color suiteAccentFillOf(BuildContext context) => suiteThemeIsDark(context)
    ? kLightAccent
    : kEvolveLightPrimary.withValues(alpha: 0.12);

/// VPN status card title color (TunnelHome).
///
/// Idle disconnected uses [suiteTextOf] so light Evolve panels stay readable;
/// never hard-code dark-only [kText] for this surface.
Color vpnStatusTitleColor(
  BuildContext context, {
  required bool connected,
  required bool busyConnecting,
}) {
  if (connected) return suiteSecondaryOf(context);
  if (busyConnecting) return suitePrimaryOf(context);
  return suiteTextOf(context);
}

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

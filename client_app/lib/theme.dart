import 'package:flutter/material.dart';

/// Product palette: dark-blue chrome, black log, high-contrast white text.
const String kScrollingPrivacyText =
    'lightweight vpn to restore your privacy - no user data is retained - your privacy is restored';

const String kAppTitle = 'RESTORE PRIVACY';
const String kBannerTitle = 'Restore Privacy - Tunnel Client';

const Color kChromeBg = Color(0xFF0A1F5C); // dark blue main chrome
const Color kBannerBg = Color(0xFF000080); // classic dark blue
const Color kWindowBg = Color(0xFF000000); // black log area
const Color kWindowFg = Color(0xFFFFFFFF); // white text
const Color kStatusFg = Color(0xFFE0E0E0);
const Color kButtonBg = Color(0xFF1D4ED8);
const Color kButtonActiveBg = Color(0xFF047857);
const Color kLogBorder = Color(0xFF1E3A8A);

/// Visual corner radius for rounded chrome (Material cards / buttons).
const double kCornerRadius = 16;

/// Asset path for product logo (Flutter pubspec assets).
const String kLogoAsset = 'assets/brand/logo-256.png';

/// Single control label for the Connect / Disconnect button.
String connectButtonLabel(bool connected) =>
    connected ? 'Disconnect' : 'Connect';

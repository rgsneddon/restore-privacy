/// In-app "New version available" for Flutter residual shells (macOS / iOS / Android).
///
/// Mirrors [client.ui_theme] version comparison. Catalog latest prefers the public
/// status host ``/api/catalog-version`` so older builds learn about a newer monopin.
/// Free-tier builds never prompt for paid catalog upgrades.
///
/// **Get update** opens a platform-matched monopin installer download
/// (``/upgrade-download`` → ``/download?token=…``), not Stripe ``/pay`` Checkout.
library;

import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import 'free_tier.dart';
import 'licence_gate.dart';
import 'rpt_config.dart';
import 'theme.dart';

/// Public status host (paid catalog).
const String kPublicStatusBaseUrl = 'https://restoreprivacy.online';

/// Paid downloads section (fallback only — not the primary upgrade CTA).
const String kUpgradeDownloadsUrl = '$kPublicStatusBaseUrl/#downloads';

/// Parse dotted version to comparable ints (same idea as Python ``version_tuple``).
List<int> versionTuple(String version) {
  final parts = <int>[];
  final cleaned = version.trim().replaceFirst(RegExp(r'^[vV]'), '');
  for (final seg in cleaned.split('.')) {
    final digits = seg.replaceAll(RegExp(r'[^0-9]'), '');
    parts.add(digits.isEmpty ? 0 : int.parse(digits));
  }
  if (parts.isEmpty) return [0];
  return parts;
}

/// True when [running] is strictly older than [latest].
bool versionIsBehind(String running, String latest) {
  final a = versionTuple(running);
  final b = versionTuple(latest);
  final n = a.length > b.length ? a.length : b.length;
  for (var i = 0; i < n; i++) {
    final ai = i < a.length ? a[i] : 0;
    final bi = i < b.length ? b[i] : 0;
    if (ai < bi) return true;
    if (ai > bi) return false;
  }
  return false;
}

/// Human banner when behind catalog monopin; null if current or free tier.
String? upgradeBannerText({
  required String running,
  required String latest,
}) {
  if (freeTierEnabled) return null;
  final run = running.trim().isEmpty ? RptConfig.productVersion : running.trim();
  final lat = latest.trim().isEmpty ? RptConfig.productVersion : latest.trim();
  if (!versionIsBehind(run, lat)) return null;
  return 'New version available: you have v$run, latest is v$lat';
}

/// Canonical monopin installer basename for [platform] at [version].
String? catalogInstallerFilename({
  required String platform,
  String? version,
}) {
  final p = platform.trim().toLowerCase();
  final ver = (version ?? RptConfig.productVersion).trim().replaceFirst(RegExp(r'^[vV]'), '');
  if (p.isEmpty || ver.isEmpty) return null;
  final suffix = switch (p) {
    'windows' => 'windows-x64-setup.exe',
    'android' => 'android.apk',
    'macos' => 'macos.zip',
    'ios' => 'ios.zip',
    'linux' => 'linux-x64.tar.gz',
    _ => null,
  };
  if (suffix == null) return null;
  return 'restore-privacy-client-$ver-$suffix';
}

/// Relative upgrade path that retrieves the platform monopin installer.
///
/// With [token]: ``/download?token=…`` (browser starts package fetch).
/// Else: ``/upgrade-download?platform=…`` (+ keygen/session) — **not** ``/pay``.
String upgradeDownloadPath({
  String? platform,
  String keygen = '',
  String sessionId = '',
  String token = '',
  String? catalogVersion,
}) {
  final tok = token.trim();
  if (tok.isNotEmpty) {
    return '/download?token=${Uri.encodeQueryComponent(tok)}';
  }
  final p = (platform ?? defaultClientPlatform()).trim().toLowerCase();
  final q = <String, String>{'platform': p.isEmpty ? 'macos' : p};
  final kg = keygen.trim();
  final sid = sessionId.trim();
  if (kg.isNotEmpty) {
    q['keygen'] = kg;
  } else if (sid.isNotEmpty) {
    q['session_id'] = sid;
  }
  final fname = catalogInstallerFilename(
    platform: q['platform']!,
    version: catalogVersion,
  );
  if (fname != null) q['filename'] = fname;
  return Uri(path: '/upgrade-download', queryParameters: q).toString();
}

/// Absolute upgrade URL for [platform] monopin installer (never free GH /pay primary).
String upgradeDownloadUrl({
  String? platform,
  String keygen = '',
  String sessionId = '',
  String token = '',
  String baseUrl = kPublicStatusBaseUrl,
  String? catalogVersion,
}) {
  final base = baseUrl.replaceAll(RegExp(r'/+$'), '');
  final path = upgradeDownloadPath(
    platform: platform,
    keygen: keygen,
    sessionId: sessionId,
    token: token,
    catalogVersion: catalogVersion,
  );
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  return '$base$path';
}

/// Mint a subscriber upgrade grant (active keygen) → direct ``/download?token=`` URL.
Future<String> resolveUpgradeDownloadUrl({
  String? platform,
  String keygen = '',
  String sessionId = '',
  String baseUrl = kPublicStatusBaseUrl,
  Duration timeout = const Duration(seconds: 8),
}) async {
  final p = (platform ?? defaultClientPlatform()).trim().toLowerCase();
  final base = baseUrl.replaceAll(RegExp(r'/+$'), '');
  final kg = keygen.trim();
  final sid = sessionId.trim();
  if (kg.isEmpty && sid.isEmpty) {
    return upgradeDownloadUrl(platform: p, baseUrl: base);
  }
  final client = HttpClient();
  try {
    final q = <String, String>{
      'platform': p,
      'format': 'json',
      if (kg.isNotEmpty) 'keygen': kg,
      if (kg.isEmpty && sid.isNotEmpty) 'session_id': sid,
    };
    final uri = Uri.parse('$base/api/subscriber-upgrade-download').replace(
      queryParameters: q,
    );
    final req = await client.getUrl(uri);
    req.headers.set(HttpHeaders.acceptHeader, 'application/json');
    final resp = await req.close().timeout(timeout);
    if (resp.statusCode == 200) {
      final body = await resp.transform(utf8.decoder).join();
      final data = jsonDecode(body);
      if (data is Map) {
        final url = data['download_url']?.toString().trim() ?? '';
        if (url.startsWith('http') && url.contains('/download?token=')) {
          return url;
        }
        final tok = data['token']?.toString().trim() ?? '';
        if (tok.isNotEmpty) {
          return upgradeDownloadUrl(platform: p, token: tok, baseUrl: base);
        }
      }
    }
  } catch (_) {
    // fall soft
  } finally {
    client.close(force: true);
  }
  return upgradeDownloadUrl(
    platform: p,
    keygen: kg,
    sessionId: sid,
    baseUrl: base,
  );
}

/// Default residual client platform string for pay links.
String defaultClientPlatform() {
  if (kIsWeb) return 'windows';
  try {
    if (defaultTargetPlatform == TargetPlatform.iOS) return 'ios';
    if (defaultTargetPlatform == TargetPlatform.macOS) return 'macos';
    if (defaultTargetPlatform == TargetPlatform.android) return 'android';
    if (defaultTargetPlatform == TargetPlatform.windows) return 'windows';
    if (defaultTargetPlatform == TargetPlatform.linux) return 'linux';
  } catch (_) {}
  return 'macos';
}

/// Fetch live monopin from status host (fail-soft → package pin).
Future<String> fetchCatalogLatestVersion({
  String baseUrl = kPublicStatusBaseUrl,
  Duration timeout = const Duration(seconds: 3),
}) async {
  final client = HttpClient();
  try {
    final uri = Uri.parse('$baseUrl/api/catalog-version');
    final req = await client.getUrl(uri);
    req.headers.set(HttpHeaders.acceptHeader, 'application/json');
    final resp = await req.close().timeout(timeout);
    if (resp.statusCode == 200) {
      final body = await resp.transform(utf8.decoder).join();
      final data = jsonDecode(body);
      if (data is Map && data['catalog_version'] != null) {
        final v = data['catalog_version']
            .toString()
            .trim()
            .replaceFirst(RegExp(r'^[vV]'), '');
        if (v.isNotEmpty && RegExp(r'^\d').hasMatch(v)) return v;
      }
    }
  } catch (_) {
    // fail-soft
  } finally {
    client.close(force: true);
  }
  return RptConfig.productVersion;
}

/// Whether [running] is behind [latest] (or package pin vs remote).
Future<bool> upgradeAvailableAsync({
  String? running,
  String? latest,
}) async {
  if (freeTierEnabled) return false;
  final run = (running ?? RptConfig.productVersion).trim();
  final lat = (latest ?? await fetchCatalogLatestVersion()).trim();
  return versionIsBehind(run, lat);
}

/// Material banner / strip: New version available + open monopin installer download.
class UpgradeBanner extends StatefulWidget {
  const UpgradeBanner({super.key, this.runningVersion});

  final String? runningVersion;

  @override
  State<UpgradeBanner> createState() => _UpgradeBannerState();
}

class _UpgradeBannerState extends State<UpgradeBanner> {
  String? _message;
  bool _loading = true;
  String? _latest;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (freeTierEnabled) {
      if (mounted) {
        setState(() {
          _message = null;
          _loading = false;
        });
      }
      return;
    }
    final run = widget.runningVersion ?? RptConfig.productVersion;
    final lat = await fetchCatalogLatestVersion();
    final msg = upgradeBannerText(running: run, latest: lat);
    if (!mounted) return;
    setState(() {
      _message = msg;
      _latest = lat;
      _loading = false;
    });
  }

  Future<void> _open() async {
    var keygen = '';
    var sessionId = '';
    try {
      final prefs = await SharedPreferences.getInstance();
      final gate = LicenceGate(
        PrefsLicenceBackend(
          (k) async => prefs.getBool(k),
          (k, v) async {
            await prefs.setBool(k, v);
          },
          (k) async => prefs.getString(k),
          (k, v) async {
            await prefs.setString(k, v);
          },
        ),
      );
      keygen = await gate.paymentKeygen();
      sessionId = await gate.paymentSessionId();
    } catch (_) {
      // fail-soft — host form still accepts keygen
    }
    final url = await resolveUpgradeDownloadUrl(
      platform: defaultClientPlatform(),
      keygen: keygen,
      sessionId: sessionId,
    );
    final uri = Uri.parse(url);
    try {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (_) {
      // fail-soft — user can open status host manually
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading || _message == null) return const SizedBox.shrink();
    return Material(
      color: Colors.transparent,
      child: Container(
        width: double.infinity,
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          color: kLightAccent,
          borderRadius: BorderRadius.circular(kCornerRadius),
          border: Border.all(color: kBorder),
        ),
        child: Row(
          children: [
            Expanded(
              child: Text(
                _message!,
                style: const TextStyle(
                  color: kPrimaryDark,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            TextButton(
              onPressed: _open,
              child: const Text(
                'Get update',
                style: TextStyle(
                  color: kPrimary,
                  fontWeight: FontWeight.bold,
                  fontSize: 12,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

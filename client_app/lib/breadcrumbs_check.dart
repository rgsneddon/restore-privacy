/// Settings-gated CHECK BREADCRUMBS → Helsinki monopin self-update path.
///
/// Mirrors shipped `client/breadcrumbs_check.py`: when the user enables
/// [kCheckBreadcrumbsLabel], fetch the Helsinki breadcrumbs manifest and store
/// a pending update directive (version/url) for the UI to surface.
library;

import 'dart:convert';
import 'dart:io';

import 'package:shared_preferences/shared_preferences.dart';

import 'rpt_config.dart';
import 'settings_store.dart';

/// Exact Settings label (must match product string grepped by tests).
const String kBreadcrumbsCheckLabel = kCheckBreadcrumbsLabel;

const String kDefaultBreadcrumbsBase =
    'https://135.181.152.10.sslip.io/breadcrumbs';
const String kDefaultManifestRel = 'current/manifest.json';

/// Pending update keys written after a successful CHECK BREADCRUMBS apply.
const String kPendingUpdateVersionKey = 'pending_update_version';
const String kPendingUpdateUrlKey = 'pending_update_url';
const String kPendingUpdateMessageKey = 'pending_update_message';

typedef BreadcrumbsTransport = Future<String> Function(
  String url,
  Map<String, String> headers,
);

/// True when Settings allows the CHECK BREADCRUMBS path.
bool checkBreadcrumbsEnabled(ProductSettings? settings) {
  // Product push-receive removed — always off
  return false;
}

String monopinFromManifest(Map<String, dynamic>? manifest) {
  if (manifest == null) return '';
  final m = manifest['monopin'] ?? manifest['version'];
  return (m?.toString() ?? '').trim();
}

String downloadUrlForMonopin(String monopin) {
  final pin = monopin.trim();
  if (pin.isEmpty) return 'https://restoreprivacy.online/';
  return 'https://restoreprivacy.online/?monopin=$pin';
}

/// Apply pending update from a vault manifest when Suite self-update is on.
///
/// Same Settings gate as residual push-update receive ([checkBreadcrumbsEnabled]).
Future<Map<String, dynamic>> applyBreadcrumbsUpdate({
  required ProductSettings settings,
  required String productVersion,
  Map<String, dynamic>? manifest,
  SharedPreferences? prefs,
  bool force = false,
}) async {
  if (!checkBreadcrumbsEnabled(settings)) {
    return {
      'ok': true,
      'skipped': true,
      'reason': 'Suite self-update off',
      'store': null,
      'label': kBreadcrumbsCheckLabel,
      'may_unpack': false,
    };
  }
  final pin = monopinFromManifest(manifest);
  final cur = productVersion.trim();
  if (pin.isEmpty) {
    return {
      'ok': false,
      'skipped': false,
      'error': 'manifest missing monopin',
      'store': null,
      'label': kBreadcrumbsCheckLabel,
    };
  }
  if (pin == cur && !force) {
    return {
      'ok': true,
      'skipped': true,
      'reason': 'already on monopin $cur',
      'monopin': pin,
      'store': null,
      'label': kBreadcrumbsCheckLabel,
    };
  }
  final url = downloadUrlForMonopin(pin);
  final msg = 'CHECK BREADCRUMBS: monopin $pin available';
  final store = <String, dynamic>{
    'pending_update_version': pin,
    'pending_update_url': url,
    'pending_update_message': msg,
    'kind': 'rpt_client_update',
  };
  final p = prefs ?? await SharedPreferences.getInstance();
  await p.setString(kPendingUpdateVersionKey, pin);
  await p.setString(kPendingUpdateUrlKey, url);
  await p.setString(kPendingUpdateMessageKey, msg);
  return {
    'ok': true,
    'skipped': false,
    'monopin': pin,
    'product_version': cur,
    'store': store,
    'error': '',
    'label': kBreadcrumbsCheckLabel,
  };
}

Future<Map<String, dynamic>> fetchBreadcrumbsManifest({
  String? baseUrl,
  String relPath = kDefaultManifestRel,
  String? token,
  BreadcrumbsTransport? transport,
  Duration timeout = const Duration(seconds: 8),
}) async {
  final base = (baseUrl ?? kDefaultBreadcrumbsBase).replaceAll(RegExp(r'/+$'), '');
  final url = '$base/${relPath.replaceFirst(RegExp(r'^/+'), '')}';
  final headers = <String, String>{'Accept': 'application/json'};
  final tok = (token ?? '').trim();
  if (tok.isNotEmpty) {
    headers['X-RPT-Asset-Token'] = tok;
  }
  try {
    String body;
    if (transport != null) {
      body = await transport(url, headers);
    } else {
      final client = HttpClient();
      try {
        final req = await client.getUrl(Uri.parse(url)).timeout(timeout);
        headers.forEach(req.headers.set);
        final resp = await req.close().timeout(timeout);
        if (resp.statusCode < 200 || resp.statusCode >= 300) {
          return {
            'ok': false,
            'error': 'HTTP ${resp.statusCode}',
            'manifest': null,
            'url': url,
          };
        }
        body = await resp.transform(utf8.decoder).join();
      } finally {
        client.close(force: true);
      }
    }
    final data = jsonDecode(body);
    if (data is! Map) {
      return {
        'ok': false,
        'error': 'invalid manifest JSON',
        'manifest': null,
        'url': url,
      };
    }
    return {
      'ok': true,
      'error': '',
      'manifest': Map<String, dynamic>.from(data),
      'url': url,
    };
  } catch (e) {
    return {
      'ok': false,
      'error': e.toString().length > 200
          ? e.toString().substring(0, 200)
          : e.toString(),
      'manifest': null,
      'url': url,
    };
  }
}

/// Full Settings path: gate → fetch manifest → apply pending update.
Future<Map<String, dynamic>> checkBreadcrumbsAndApply({
  required ProductSettings settings,
  String? productVersion,
  Map<String, dynamic>? localManifest,
  BreadcrumbsTransport? transport,
  SharedPreferences? prefs,
  String? token,
}) async {
  if (!checkBreadcrumbsEnabled(settings)) {
    return {
      'ok': true,
      'skipped': true,
      'reason': 'CHECK BREADCRUMBS off',
      'store': null,
      'label': kBreadcrumbsCheckLabel,
    };
  }
  Map<String, dynamic>? manifest = localManifest;
  if (manifest == null) {
    final fetched = await fetchBreadcrumbsManifest(
      transport: transport,
      token: token,
    );
    if (fetched['ok'] != true) {
      return {
        'ok': false,
        'skipped': false,
        'error': fetched['error'] ?? 'fetch failed',
        'store': null,
        'label': kBreadcrumbsCheckLabel,
      };
    }
    manifest = fetched['manifest'] as Map<String, dynamic>?;
  }
  return applyBreadcrumbsUpdate(
    settings: settings,
    productVersion: productVersion ?? RptConfig.productVersion,
    manifest: manifest,
    prefs: prefs,
  );
}

/// Settings toggle handler: off → no-op; on → run full check/apply.
Future<Map<String, dynamic>> onCheckBreadcrumbsSettingChanged({
  required bool enabled,
  required ProductSettings settings,
  String? productVersion,
  Map<String, dynamic>? localManifest,
  BreadcrumbsTransport? transport,
  SharedPreferences? prefs,
  String? token,
}) async {
  if (!enabled) {
    return {
      'ok': true,
      'skipped': true,
      'reason': 'CHECK BREADCRUMBS off',
      'store': null,
      'label': kBreadcrumbsCheckLabel,
    };
  }
  final s = settings.copyWith(checkBreadcrumbs: true);
  return checkBreadcrumbsAndApply(
    settings: s,
    productVersion: productVersion,
    localManifest: localManifest,
    transport: transport,
    prefs: prefs,
    token: token,
  );
}

/// Suite self-update honesty path: push-receive, Settings opt-in, unpack + relaunch.
///
/// After KEYGEN unlock, Settings (under “Allow Suite self-update”) explains that
/// the Suite can update itself when required, that the user must click to unpack
/// and relaunch, that this is the one privacy breach in the Suite, and that it
/// can be switched off in VPN Settings. Never call the entry unlock a "paywall".
library;

import 'dart:convert';
import 'dart:io';

import 'package:shared_preferences/shared_preferences.dart';

import 'breadcrumbs_check.dart';
import 'settings_store.dart';
import 'suite_version.dart';

// Re-export pending keys for Suite UI/tests (same store as breadcrumbs / push).
export 'breadcrumbs_check.dart'
    show
        kPendingUpdateVersionKey,
        kPendingUpdateUrlKey,
        kPendingUpdateMessageKey;

// ---------------------------------------------------------------------------
// Product copy (main screen + Settings). Grepped by tests.
// ---------------------------------------------------------------------------

/// Finder / ValueKey markers for the post-unlock update honesty panel.
const String kSuiteUpdateExplainerMarker = 'suite_update_explainer';
const String kSuiteUpdateUnpackButtonMarker = 'suite_update_unpack_button';
const String kSuiteUpdateSettingsSwitchMarker = 'suite_update_settings_switch';

const String kSuiteUpdateExplainerHeading = 'When the Suite needs an update';

/// Full honesty explainer (human cadence). Required facts for tests.
const String kSuiteUpdateExplainerBody =
    'The app will update itself when required — but you must click this button '
    'to unpack the update and relaunch the app. In this, a user’s privacy is '
    'breached. This is the one time this happens, throughout the Restore Privacy '
    'Suite. You can switch it off in Settings of the VPN.';

const String kSuiteUpdateUnpackButtonLabel = 'Unpack update and relaunch';

/// Human Settings title (prefs key remains [kKeyCheckBreadcrumbs]).
const String kSuiteUpdateSettingsTitle = 'Allow Suite self-update';

const String kSuiteUpdateSettingsSubtitle =
    'When on, this device may receive a pushed Suite package and store a pending '
    'update. You still click “Unpack update and relaunch” yourself. That path is '
    'the one privacy breach in the Suite — leave off if you prefer no self-update.';

/// Same preference as CHECK BREADCRUMBS / residual update receive (unified gate).
bool suiteSelfUpdateEnabled(ProductSettings? settings) {
  if (settings == null) return false;
  return settings.checkBreadcrumbs;
}

/// Default is off (opt-in).
bool suiteSelfUpdateDefaultIsOff() =>
    ProductSettings.defaults.checkBreadcrumbs == false;

/// True when product copy is complete and never says "paywall".
bool suiteUpdateCopyIsValid({
  String body = kSuiteUpdateExplainerBody,
  String heading = kSuiteUpdateExplainerHeading,
  String button = kSuiteUpdateUnpackButtonLabel,
  String settingsTitle = kSuiteUpdateSettingsTitle,
}) {
  final all = '$heading $body $button $settingsTitle'.toLowerCase();
  if (all.contains('paywall')) return false;
  const must = [
    'update itself when required',
    'unpack',
    'relaunch',
    'privacy is breached',
    'one time this happens',
    'settings of the vpn',
  ];
  final bodyLow = body.toLowerCase();
  for (final m in must) {
    if (!bodyLow.contains(m)) return false;
  }
  if (!button.toLowerCase().contains('unpack')) return false;
  if (!button.toLowerCase().contains('relaunch')) return false;
  if (!settingsTitle.toLowerCase().contains('self-update') &&
      !settingsTitle.toLowerCase().contains('suite')) {
    return false;
  }
  return true;
}

// ---------------------------------------------------------------------------
// Pending Suite update store (shared keys with breadcrumbs / residual push)
// ---------------------------------------------------------------------------

const String kPendingUpdateKindSuite = 'rpt_suite_update';
const String kPendingUpdateKindClient = 'rpt_client_update';

class PendingSuiteUpdate {
  const PendingSuiteUpdate({
    required this.version,
    this.url = '',
    this.message = '',
    this.kind = kPendingUpdateKindSuite,
    this.localPath = '',
  });

  final String version;
  final String url;
  final String message;
  final String kind;
  final String localPath;

  bool get isPresent => version.trim().isNotEmpty;

  Map<String, dynamic> toStore() => {
        kPendingUpdateVersionKey: version,
        kPendingUpdateUrlKey: url,
        kPendingUpdateMessageKey: message,
        'kind': kind,
        if (localPath.isNotEmpty) 'pending_update_local_path': localPath,
      };

  static PendingSuiteUpdate? fromStore(Map<String, dynamic>? store) {
    if (store == null) return null;
    final ver = (store[kPendingUpdateVersionKey] ?? store['version'] ?? '')
        .toString()
        .trim();
    if (ver.isEmpty) return null;
    return PendingSuiteUpdate(
      version: ver,
      url: (store[kPendingUpdateUrlKey] ?? store['url'] ?? '').toString(),
      message:
          (store[kPendingUpdateMessageKey] ?? store['message'] ?? '').toString(),
      kind: (store['kind'] ?? kPendingUpdateKindSuite).toString(),
      localPath: (store['pending_update_local_path'] ?? '').toString(),
    );
  }
}

/// Load pending update from SharedPreferences (or injectable map backend).
Future<PendingSuiteUpdate?> loadPendingSuiteUpdate({
  SharedPreferences? prefs,
  Map<String, String>? memory,
}) async {
  if (memory != null) {
    final ver = (memory[kPendingUpdateVersionKey] ?? '').trim();
    if (ver.isEmpty) return null;
    return PendingSuiteUpdate(
      version: ver,
      url: memory[kPendingUpdateUrlKey] ?? '',
      message: memory[kPendingUpdateMessageKey] ?? '',
      kind: memory['kind'] ?? kPendingUpdateKindSuite,
      localPath: memory['pending_update_local_path'] ?? '',
    );
  }
  final p = prefs ?? await SharedPreferences.getInstance();
  final ver = (p.getString(kPendingUpdateVersionKey) ?? '').trim();
  if (ver.isEmpty) return null;
  return PendingSuiteUpdate(
    version: ver,
    url: p.getString(kPendingUpdateUrlKey) ?? '',
    message: p.getString(kPendingUpdateMessageKey) ?? '',
    kind: p.getString('pending_update_kind') ?? kPendingUpdateKindSuite,
    localPath: p.getString('pending_update_local_path') ?? '',
  );
}

Future<void> clearPendingSuiteUpdate({
  SharedPreferences? prefs,
  Map<String, String>? memory,
}) async {
  if (memory != null) {
    memory.remove(kPendingUpdateVersionKey);
    memory.remove(kPendingUpdateUrlKey);
    memory.remove(kPendingUpdateMessageKey);
    memory.remove('pending_update_kind');
    memory.remove('pending_update_local_path');
    return;
  }
  final p = prefs ?? await SharedPreferences.getInstance();
  await p.remove(kPendingUpdateVersionKey);
  await p.remove(kPendingUpdateUrlKey);
  await p.remove(kPendingUpdateMessageKey);
  await p.remove('pending_update_kind');
  await p.remove('pending_update_local_path');
}

Future<void> _writePending(
  PendingSuiteUpdate pending, {
  SharedPreferences? prefs,
  Map<String, String>? memory,
}) async {
  if (memory != null) {
    memory[kPendingUpdateVersionKey] = pending.version;
    memory[kPendingUpdateUrlKey] = pending.url;
    memory[kPendingUpdateMessageKey] = pending.message;
    memory['kind'] = pending.kind;
    memory['pending_update_kind'] = pending.kind;
    if (pending.localPath.isNotEmpty) {
      memory['pending_update_local_path'] = pending.localPath;
    }
    return;
  }
  final p = prefs ?? await SharedPreferences.getInstance();
  await p.setString(kPendingUpdateVersionKey, pending.version);
  await p.setString(kPendingUpdateUrlKey, pending.url);
  await p.setString(kPendingUpdateMessageKey, pending.message);
  await p.setString('pending_update_kind', pending.kind);
  if (pending.localPath.isNotEmpty) {
    await p.setString('pending_update_local_path', pending.localPath);
  }
}

// ---------------------------------------------------------------------------
// Push-update receive (mirrors node/update_push.apply_client_update_directive)
// ---------------------------------------------------------------------------

/// Normalize a residual / operator push payload into a pending Suite store.
///
/// When Settings opt-in is **off**, receive does **not** write pending state
/// and does not allow unpack.
Map<String, dynamic> receiveSuiteUpdateDirective({
  required ProductSettings settings,
  Map<String, dynamic>? payload,
}) {
  if (!suiteSelfUpdateEnabled(settings)) {
    return {
      'ok': true,
      'skipped': true,
      'reason': 'Suite self-update off',
      'store': null,
      'may_unpack': false,
    };
  }
  if (payload == null || payload.isEmpty) {
    return {
      'ok': false,
      'skipped': false,
      'error': 'empty',
      'store': null,
      'may_unpack': false,
    };
  }
  final version =
      (payload['version'] ?? payload[kPendingUpdateVersionKey] ?? '')
          .toString()
          .trim();
  if (version.isEmpty) {
    return {
      'ok': false,
      'skipped': false,
      'error': 'version required',
      'store': null,
      'may_unpack': false,
    };
  }
  final url =
      (payload['url'] ?? payload[kPendingUpdateUrlKey] ?? '').toString().trim();
  final message = (payload['message'] ?? payload[kPendingUpdateMessageKey] ?? '')
      .toString()
      .trim();
  final kind = (payload['kind'] ?? kPendingUpdateKindSuite).toString();
  final pending = PendingSuiteUpdate(
    version: version,
    url: url,
    message: message.isEmpty
        ? 'Suite update $version ready — unpack and relaunch when you choose.'
        : message,
    kind: kind.contains('suite') ? kind : kPendingUpdateKindSuite,
  );
  return {
    'ok': true,
    'skipped': false,
    'error': '',
    'store': pending.toStore(),
    'directive': {
      'version': pending.version,
      'url': pending.url,
      'message': pending.message,
      'kind': pending.kind,
    },
    'may_unpack': true,
  };
}

/// Persist a receive result when opt-in allowed a store.
Future<Map<String, dynamic>> receiveAndStoreSuiteUpdate({
  required ProductSettings settings,
  Map<String, dynamic>? payload,
  SharedPreferences? prefs,
  Map<String, String>? memory,
}) async {
  final r = receiveSuiteUpdateDirective(settings: settings, payload: payload);
  if (r['store'] is Map<String, dynamic>) {
    final pending = PendingSuiteUpdate.fromStore(
      Map<String, dynamic>.from(r['store'] as Map),
    );
    if (pending != null) {
      await _writePending(pending, prefs: prefs, memory: memory);
    }
  }
  return r;
}

// ---------------------------------------------------------------------------
// Unpack + relaunch (gated; pure stages for tests)
// ---------------------------------------------------------------------------

/// Whether the UI may offer unpack for [pending] under [settings].
bool mayUnpackSuiteUpdate({
  required ProductSettings settings,
  PendingSuiteUpdate? pending,
}) {
  if (!suiteSelfUpdateEnabled(settings)) return false;
  return pending != null && pending.isPresent;
}

/// Stage an update package for unpack/relaunch (does not silent-install).
///
/// *download* is injectable: tests pass fixture bytes; production may fetch [url].
/// Returns a handoff plan the UI button executes (open package / spawn installer).
Future<Map<String, dynamic>> prepareUnpackAndRelaunch({
  required ProductSettings settings,
  PendingSuiteUpdate? pending,
  Future<List<int>> Function(String url)? download,
  Directory? stageDir,
  String? runningVersion,
}) async {
  if (!suiteSelfUpdateEnabled(settings)) {
    return {
      'ok': false,
      'skipped': true,
      'error': 'Suite self-update off — enable in VPN Settings',
      'may_unpack': false,
      'handoff': null,
    };
  }
  final p = pending;
  if (p == null || !p.isPresent) {
    return {
      'ok': false,
      'skipped': false,
      'error': 'no pending Suite update',
      'may_unpack': false,
      'handoff': null,
    };
  }
  final run = (runningVersion ?? kSuiteVersion).trim();
  final stagedRoot = stageDir ?? Directory.systemTemp.createTempSync('rpt_suite_update_');
  final dest = File(
    '${stagedRoot.path}${Platform.pathSeparator}suite-update-${p.version}.pkg',
  );

  String? localPath = p.localPath.trim().isNotEmpty ? p.localPath.trim() : null;
  if (localPath == null || localPath.isEmpty) {
    final url = p.url.trim();
    if (url.isEmpty && download == null) {
      // Still allow a staged handoff marker so the button can open Settings/host.
      final plan = {
        'action': 'relaunch_after_unpack',
        'version': p.version,
        'running_version': run,
        'url': '',
        'package_path': '',
        'product': kSuiteProductName,
        'requires_user_click': true,
      };
      return {
        'ok': true,
        'skipped': false,
        'error': '',
        'may_unpack': true,
        'handoff': plan,
        'message':
            'Pending Suite ${p.version} — click unpack when the package URL is available.',
      };
    }
    if (download != null && url.isNotEmpty) {
      final bytes = await download(url);
      await dest.writeAsBytes(bytes, flush: true);
      localPath = dest.path;
    } else if (url.isNotEmpty) {
      // No download inject — handoff points at URL for OS open / browser.
      final plan = {
        'action': 'open_url_then_relaunch',
        'version': p.version,
        'running_version': run,
        'url': url,
        'package_path': '',
        'product': kSuiteProductName,
        'requires_user_click': true,
      };
      return {
        'ok': true,
        'skipped': false,
        'error': '',
        'may_unpack': true,
        'handoff': plan,
        'message': kSuiteUpdateUnpackButtonLabel,
      };
    }
  }

  final plan = {
    'action': 'unpack_and_relaunch',
    'version': p.version,
    'running_version': run,
    'url': p.url,
    'package_path': localPath ?? '',
    'product': kSuiteProductName,
    'requires_user_click': true,
  };
  return {
    'ok': true,
    'skipped': false,
    'error': '',
    'may_unpack': true,
    'handoff': plan,
    'message': kSuiteUpdateUnpackButtonLabel,
  };
}

/// Execute handoff after user click (open package path or URL). Injectable openers.
Future<Map<String, dynamic>> executeUnpackAndRelaunchHandoff({
  required ProductSettings settings,
  required Map<String, dynamic> handoff,
  Future<bool> Function(Uri uri)? openUri,
  void Function()? relaunch,
}) async {
  if (!suiteSelfUpdateEnabled(settings)) {
    return {
      'ok': false,
      'error': 'Suite self-update off',
      'launched': false,
    };
  }
  if (handoff['requires_user_click'] != true) {
    return {
      'ok': false,
      'error': 'refusing silent unpack',
      'launched': false,
    };
  }
  final path = (handoff['package_path'] ?? '').toString().trim();
  final url = (handoff['url'] ?? '').toString().trim();
  var launched = false;
  if (openUri != null) {
    if (path.isNotEmpty) {
      launched = await openUri(Uri.file(path));
    } else if (url.isNotEmpty) {
      launched = await openUri(Uri.parse(url));
    }
  } else {
    // Best-effort: mark ready for OS when path exists.
    if (path.isNotEmpty && File(path).existsSync()) {
      launched = true;
    } else if (url.isNotEmpty) {
      launched = true;
    }
  }
  if (launched && relaunch != null) {
    relaunch();
  }
  return {
    'ok': launched,
    'error': launched ? '' : 'could not open package',
    'launched': launched,
    'version': handoff['version'],
    'action': handoff['action'],
  };
}

/// Parse residual UPDATE_PUSH JSON body (same shape as node pack_update_push_json).
Map<String, dynamic> parseSuiteUpdatePushJson(String raw) {
  final blob = jsonDecode(raw.isEmpty ? '{}' : raw);
  if (blob is! Map) {
    throw FormatException('update push JSON must be object');
  }
  return Map<String, dynamic>.from(blob);
}

// ---------------------------------------------------------------------------
// Production residual receive path (host MethodChannel + poll)
// ---------------------------------------------------------------------------

/// Native → Flutter method name for residual operator push (host invokes).
const String kUpdatePushHostMethod = 'updatePush';

/// Flutter → native poll for a queued UPDATE_PUSH payload (best-effort).
const String kPollUpdatePushMethod = 'pollUpdatePush';

/// Normalize host/native arguments into a directive map (or null).
Map<String, dynamic>? coerceUpdatePushPayload(dynamic raw) {
  if (raw == null) return null;
  if (raw is String) {
    final s = raw.trim();
    if (s.isEmpty) return null;
    try {
      return parseSuiteUpdatePushJson(s);
    } catch (_) {
      return null;
    }
  }
  if (raw is Map) {
    final m = Map<String, dynamic>.from(raw);
    // Nested under common host keys
    if (m['directive'] is Map) {
      return Map<String, dynamic>.from(m['directive'] as Map);
    }
    if (m['update'] is Map) {
      return Map<String, dynamic>.from(m['update'] as Map);
    }
    if (m['payload'] is Map) {
      return Map<String, dynamic>.from(m['payload'] as Map);
    }
    if (m['payload'] is String) {
      return coerceUpdatePushPayload(m['payload']);
    }
    return m;
  }
  return null;
}

/// Production entry: residual UPDATE_PUSH (or operator poll result) → pending store.
///
/// Called from [VpnController] MethodChannel handler and post-Connect poll.
/// When Settings opt-in is off, does not write pending (may_unpack false).
Future<Map<String, dynamic>> handleProductionUpdatePush({
  required ProductSettings settings,
  dynamic rawPayload,
  SharedPreferences? prefs,
  Map<String, String>? memory,
}) async {
  final payload = coerceUpdatePushPayload(rawPayload);
  if (payload == null) {
    return {
      'ok': false,
      'skipped': false,
      'error': 'empty or invalid update push payload',
      'store': null,
      'may_unpack': false,
    };
  }
  return receiveAndStoreSuiteUpdate(
    settings: settings,
    payload: payload,
    prefs: prefs,
    memory: memory,
  );
}

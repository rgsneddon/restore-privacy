/// Local end-user licence acceptance gate (must accept before Connect).
///
/// Acceptance is stored only on this device. Never uploaded by the client.
library;

import 'settings_store.dart';

const String kKeyLicenceAccepted = 'licence_accepted';
const String kKeyLicenceAcceptedAt = 'licence_accepted_at';
const String kKeyLicenceId = 'licence_id';
const String kCurrentLicenceId = 'MIT-2026';

const String kConnectBlockedLicenceMsg =
    'Accept the end-user licence before connecting. '
    'Open Settings or the licence prompt, review the licence, then Accept.';

const String kLicencePromptTitle = 'End-user licence';
const String kLicenceAcceptButton = 'Accept licence';

const String kShortLicenceSummary =
    'Restore Privacy is provided under the MIT licence and related third-party '
    'terms (see End user licence / LICENSE). By accepting, you agree to use the '
    'software under those terms. Acceptance is stored only on this device.';

class LicenceAcceptance {
  final bool accepted;
  final double acceptedAt;
  final String licenceId;

  const LicenceAcceptance({
    this.accepted = false,
    this.acceptedAt = 0,
    this.licenceId = '',
  });

  static const LicenceAcceptance defaults = LicenceAcceptance();
}

/// Extends [SettingsBackend] with string storage for licence fields.
abstract class LicenceBackend {
  Future<bool?> getBool(String key);
  Future<void> setBool(String key, bool value);
  Future<String?> getString(String key);
  Future<void> setString(String key, String value);
}

/// Adapts [MemorySettingsBackend] for licence tests (bool + string map).
class MemoryLicenceBackend implements LicenceBackend {
  MemoryLicenceBackend([Map<String, Object>? seed]) : data = seed ?? {};

  final Map<String, Object> data;

  @override
  Future<bool?> getBool(String key) async {
    final v = data[key];
    return v is bool ? v : null;
  }

  @override
  Future<void> setBool(String key, bool value) async {
    data[key] = value;
  }

  @override
  Future<String?> getString(String key) async {
    final v = data[key];
    return v is String ? v : null;
  }

  @override
  Future<void> setString(String key, String value) async {
    data[key] = value;
  }
}

class LicenceGate {
  LicenceGate(this.backend);

  final LicenceBackend backend;

  Future<LicenceAcceptance> load() async {
    final accepted = await backend.getBool(kKeyLicenceAccepted) == true;
    final atRaw = await backend.getString(kKeyLicenceAcceptedAt);
    final id = await backend.getString(kKeyLicenceId) ?? '';
    final at = double.tryParse(atRaw ?? '') ?? 0.0;
    return LicenceAcceptance(
      accepted: accepted,
      acceptedAt: at,
      licenceId: id,
    );
  }

  Future<bool> hasAcceptedLicence({String requiredId = kCurrentLicenceId}) async {
    final st = await load();
    if (!st.accepted) return false;
    if (requiredId.isNotEmpty && st.licenceId != requiredId) return false;
    return true;
  }

  Future<bool> mayConnect() async => hasAcceptedLicence();

  Future<({bool ok, String message})> assertMayConnect() async {
    if (await mayConnect()) {
      return (ok: true, message: '');
    }
    return (ok: false, message: kConnectBlockedLicenceMsg);
  }

  Future<LicenceAcceptance> acceptLicence({
    String licenceId = kCurrentLicenceId,
    double? ts,
  }) async {
    final at = ts ?? DateTime.now().millisecondsSinceEpoch / 1000.0;
    await backend.setBool(kKeyLicenceAccepted, true);
    await backend.setString(kKeyLicenceAcceptedAt, at.toString());
    await backend.setString(kKeyLicenceId, licenceId);
    return LicenceAcceptance(
      accepted: true,
      acceptedAt: at,
      licenceId: licenceId,
    );
  }

  Future<void> clear() async {
    await backend.setBool(kKeyLicenceAccepted, false);
    await backend.setString(kKeyLicenceAcceptedAt, '0');
    await backend.setString(kKeyLicenceId, '');
  }
}

/// SharedPreferences-backed licence store.
class PrefsLicenceBackend implements LicenceBackend {
  PrefsLicenceBackend(this._getBool, this._setBool, this._getString, this._setString);

  final Future<bool?> Function(String key) _getBool;
  final Future<void> Function(String key, bool value) _setBool;
  final Future<String?> Function(String key) _getString;
  final Future<void> Function(String key, String value) _setString;

  @override
  Future<bool?> getBool(String key) => _getBool(key);

  @override
  Future<void> setBool(String key, bool value) => _setBool(key, value);

  @override
  Future<String?> getString(String key) => _getString(key);

  @override
  Future<void> setString(String key, String value) => _setString(key, value);
}

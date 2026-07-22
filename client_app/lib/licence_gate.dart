/// Local end-user licence acceptance gate (must accept before Connect).
///
/// Acceptance is stored only on this device. Never uploaded by the client.
library;

import 'dart:convert';
import 'dart:io';

import 'rpt_config.dart';
import 'settings_store.dart';

const String kKeyLicenceAccepted = 'licence_accepted';
const String kKeyLicenceAcceptedAt = 'licence_accepted_at';
const String kKeyLicenceId = 'licence_id';
const String kCurrentLicenceId = 'FULL-COPYRIGHT-2026';

const String kConnectBlockedLicenceMsg =
    'Accept the end-user licence before connecting. '
    'Open Settings or the licence prompt, review the licence, then Accept.';

const String kConnectBlockedPaymentMsg =
    'Connect is blocked: payment failed or entitlement was revoked for this '
    'install. Successful payment is required. If payment fails at any time, '
    'the ability to Connect with the Restore Privacy app is cancelled until '
    'you complete a successful payment again on https://restoreprivacy.online/ — '
    'then paste the Checkout session id (cs_…) in Settings → Payment entitlement.';

const String kConnectBlockedNoEntitlementMsg =
    'Connect is blocked: no successful payment entitlement on this install. '
    'After paying on https://restoreprivacy.online/, open Settings → Payment '
    'entitlement and paste the Checkout session id (cs_…) from the thank-you '
    'page. Successful payment is required; if payment fails at any time, '
    'Connect is cancelled.';

const String kKeyPaymentStatus = 'payment_entitlement_status';
const String kKeyPaymentSessionId = 'payment_entitlement_session_id';
const String kPaymentStatusActive = 'active';
const String kPaymentStatusFailed = 'failed';
const String kPaymentStatusRevoked = 'revoked';
const String kPaymentStatusUnpaid = 'unpaid';
const String kPaymentStatusUnknown = 'unknown';

const String kDefaultPaymentStatusBaseUrl = 'https://restoreprivacy.online';

const String kLicencePromptTitle = 'End-user licence';
const String kLicenceAcceptButton = 'Accept licence';

const String kPaymentConnectDisclaimerPlain =
    'STRONG DISCLAIMER — PAYMENT REQUIRED FOR CONNECT: Access to Connect and '
    'residual VPN use requires successful payment. If payment fails at any '
    'time (failed checkout, failed charge, refund, dispute, or revoked '
    'entitlement), the ability to Connect with the Restore Privacy app is '
    'cancelled for that purchase/install until a successful payment is completed.';

const String kShortLicenceSummary =
    'Restore Privacy is proprietary full copyright: client packages may be used '
    'only to run a device on the Restore Privacy VPN, with no warranty (AS IS). '
    'Copy or transmission of the product architecture is not permitted. '
    'Third-party components keep their own licences (see LICENSE / CREDITS). '
    'By accepting, you agree to those terms. Acceptance is stored only on this device. '
    '$kPaymentConnectDisclaimerPlain';

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

  Future<String> paymentStatus() async {
    final s = await backend.getString(kKeyPaymentStatus);
    return (s ?? kPaymentStatusUnknown).trim().toLowerCase();
  }

  Future<String> paymentSessionId() async {
    return (await backend.getString(kKeyPaymentSessionId) ?? '').trim();
  }

  Future<void> recordPaymentSuccess(String sessionId) async {
    await backend.setString(kKeyPaymentSessionId, sessionId);
    await backend.setString(kKeyPaymentStatus, kPaymentStatusActive);
  }

  Future<void> recordPaymentFailure({
    String reason = 'payment_failed',
    String status = kPaymentStatusFailed,
  }) async {
    final st = status.trim().toLowerCase();
    final write = (st == kPaymentStatusRevoked || st == kPaymentStatusUnpaid)
        ? st
        : kPaymentStatusFailed;
    await backend.setString(kKeyPaymentStatus, write);
  }

  /// Paste Checkout session id and verify against the status host.
  ///
  /// This is the shipped paid-user path after Stripe success.
  Future<String> importSessionAndVerify(
    String sessionId, {
    String? baseUrl,
    Future<Map<String, dynamic>> Function(String sessionId)? fetch,
  }) async {
    final sid = sessionId.trim();
    if (sid.isEmpty) return kPaymentStatusUnknown;
    await backend.setString(kKeyPaymentSessionId, sid);
    await backend.setString(kKeyPaymentStatus, kPaymentStatusUnknown);
    return refreshEntitlementFromRemote(baseUrl: baseUrl, fetch: fetch);
  }

  Future<String> refreshEntitlementFromRemote({
    String? baseUrl,
    Future<Map<String, dynamic>> Function(String sessionId)? fetch,
  }) async {
    final sid = await paymentSessionId();
    if (sid.isEmpty) return await paymentStatus();
    Map<String, dynamic> remote;
    try {
      if (fetch != null) {
        remote = await fetch(sid);
      } else {
        remote = await fetchRemoteEntitlementStatus(sid, baseUrl: baseUrl);
      }
    } catch (_) {
      return await paymentStatus();
    }
    final st = (remote['status']?.toString() ?? kPaymentStatusUnknown)
        .trim()
        .toLowerCase();
    if (st == kPaymentStatusFailed ||
        st == kPaymentStatusRevoked ||
        st == kPaymentStatusUnpaid) {
      await recordPaymentFailure(reason: remote['reason']?.toString() ?? st, status: st);
      return st;
    }
    if (st == kPaymentStatusActive) {
      await recordPaymentSuccess(sid);
      return kPaymentStatusActive;
    }
    return await paymentStatus();
  }

  static Future<Map<String, dynamic>> fetchRemoteEntitlementStatus(
    String sessionId, {
    String? baseUrl,
    Duration timeout = const Duration(seconds: 8),
  }) async {
    final sid = sessionId.trim();
    if (sid.isEmpty) {
      return {'status': kPaymentStatusUnknown, 'error': 'missing_session_id'};
    }
    final base = (baseUrl ??
            Platform.environment['RPT_PUBLIC_BASE_URL'] ??
            kDefaultPaymentStatusBaseUrl)
        .trim()
        .replaceAll(RegExp(r'/+$'), '');
    final uri = Uri.parse(
      '$base/api/connect-entitlement?session_id=${Uri.encodeQueryComponent(sid)}',
    );
    final client = HttpClient();
    try {
      client.connectionTimeout = timeout;
      final req = await client.getUrl(uri);
      req.headers.set(
        HttpHeaders.userAgentHeader,
        'RestorePrivacy-flutter/${RptConfig.productVersion}',
      );
      req.headers.set(HttpHeaders.acceptHeader, 'application/json');
      final resp = await req.close().timeout(timeout);
      final body = await resp.transform(utf8.decoder).join();
      final data = jsonDecode(body);
      if (data is Map<String, dynamic>) return data;
      if (data is Map) return Map<String, dynamic>.from(data);
      return {'status': kPaymentStatusUnknown, 'error': 'bad_response'};
    } catch (e) {
      return {'status': kPaymentStatusUnknown, 'error': e.toString()};
    } finally {
      client.close(force: true);
    }
  }

  /// Failed / revoked / unpaid always block. Missing entitlement blocks when
  /// product requires payment (default). Active allows.
  Future<bool> paymentAllowsConnect({bool require = true}) async {
    final st = await paymentStatus();
    if (st == kPaymentStatusFailed ||
        st == kPaymentStatusRevoked ||
        st == kPaymentStatusUnpaid) {
      return false;
    }
    if (st == kPaymentStatusActive) return true;
    if (!require) return true;
    return false;
  }

  Future<bool> mayConnect({bool requirePayment = true}) async {
    if (!await hasAcceptedLicence()) return false;
    return paymentAllowsConnect(require: requirePayment);
  }

  Future<({bool ok, String message})> assertMayConnect({
    bool requirePayment = true,
    bool refreshPayment = true,
    String? baseUrl,
    Future<Map<String, dynamic>> Function(String sessionId)? fetch,
  }) async {
    if (!await hasAcceptedLicence()) {
      return (ok: false, message: kConnectBlockedLicenceMsg);
    }
    if (refreshPayment) {
      final sid = await paymentSessionId();
      if (sid.isNotEmpty) {
        await refreshEntitlementFromRemote(baseUrl: baseUrl, fetch: fetch);
      }
    }
    if (!await paymentAllowsConnect(require: requirePayment)) {
      final st = await paymentStatus();
      if (st == kPaymentStatusFailed ||
          st == kPaymentStatusRevoked ||
          st == kPaymentStatusUnpaid) {
        return (ok: false, message: kConnectBlockedPaymentMsg);
      }
      return (ok: false, message: kConnectBlockedNoEntitlementMsg);
    }
    return (ok: true, message: '');
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

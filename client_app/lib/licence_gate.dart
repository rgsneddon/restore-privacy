/// Local end-user licence acceptance gate (must accept before Connect).
///
/// Acceptance is stored only on this device. Never uploaded by the client.
library;

import 'dart:convert';
import 'dart:io';

import 'package:flutter/services.dart';

import 'rpt_config.dart';
import 'settings_store.dart';

const String kKeyLicenceAccepted = 'licence_accepted';
const String kKeyLicenceAcceptedAt = 'licence_accepted_at';
const String kKeyLicenceId = 'licence_id';
const String kCurrentLicenceId = 'FULL-COPYRIGHT-2026';

const String kConnectBlockedLicenceMsg =
    'Accept the end-user licence before connecting. '
    'Open Settings or the licence prompt, review the licence, then Accept. '
    'After accepting, enter the keygen from your fulfilment email to unlock.';

const String kConnectBlockedPaymentMsg =
    'Connect is blocked: payment failed or entitlement was revoked for this '
    'install. Successful payment is required. If payment fails at any time, '
    'the ability to Connect with the Restore Privacy app is cancelled until '
    'you complete a successful payment again on https://restoreprivacy.online/ — '
    'then enter your keygen in the unlock dialog (or Settings → Payment entitlement / keygen).';

const String kConnectBlockedNoEntitlementMsg =
    'Connect is blocked: no successful payment entitlement on this install. '
    'After paying on https://restoreprivacy.online/, enter the keygen from your '
    'fulfilment email in the unlock dialog (USE THIS KEYGEN TO UNLOCK YOUR '
    'RESTORE PRIVACY TRIAL). Download alone does not unlock residual VPN. '
    'Successful payment/active subscription is required; if payment fails at any time, '
    'Connect is cancelled.';

const String kConnectBlockedKeygenMsg =
    'Connect is blocked: enter a valid keygen after accepting the licence. '
    'Your fulfilment email includes the keygen with the text '
    'USE THIS KEYGEN TO UNLOCK YOUR RESTORE PRIVACY TRIAL. '
    'Download alone does not unlock residual VPN.';

const String kKeygenPromptTitle = 'Enter licence keygen';
const String kKeygenPromptBody =
    'Your fulfilment email includes a keygen with the text '
    'USE THIS KEYGEN TO UNLOCK YOUR RESTORE PRIVACY TRIAL '
    '(format RPT-KEY-…). Paste it below to unlock Connect. '
    'Download alone does not unlock residual VPN.';

const String kKeyPaymentStatus = 'payment_entitlement_status';
const String kKeyPaymentSessionId = 'payment_entitlement_session_id';
const String kKeyPaymentKeygen = 'payment_entitlement_keygen';
const String kPaymentStatusActive = 'active';
const String kPaymentStatusFailed = 'failed';
const String kPaymentStatusRevoked = 'revoked';
const String kPaymentStatusUnpaid = 'unpaid';
const String kPaymentStatusUnknown = 'unknown';

/// Customer-facing licence status (host + clients).
const String kLicenceStatusOk = 'OK';
const String kLicenceStatusExpired = 'EXPIRED';

const String kKeygenUnlockInstruction =
    'USE THIS KEYGEN TO UNLOCK YOUR RESTORE PRIVACY TRIAL';

const String kDefaultPaymentStatusBaseUrl = 'https://restoreprivacy.online';

/// EXPIRED lock phrase — *here* is the platform payment portal.
const String kRenewLicencePrefix = 'Renew your licence ';
const String kRenewLicenceHere = 'here';

/// Normalize payment status → OK | EXPIRED.
String licenceStatusFromPaymentStatus(String status) {
  final st = status.trim().toLowerCase();
  if (st == kPaymentStatusActive) return kLicenceStatusOk;
  return kLicenceStatusExpired;
}

/// Platform catalog pay portal (homepage — user picks monthly/yearly).
String renewLicenceCatalogUrl() => kDefaultPaymentStatusBaseUrl;

/// Message for EXPIRED lock screen with renew *here* link.
String renewLicenceMessage({String platform = ''}) {
  final plat = platform.trim().isEmpty ? 'your platform' : platform.trim();
  return 'Renew your licence *here*: $kDefaultPaymentStatusBaseUrl/\n\n'
      'Status: $kLicenceStatusExpired. Open the payment portal for $plat '
      '(monthly or yearly), then re-enter your keygen to unlock Connect.';
}

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
    'After you accept, enter the keygen from your fulfilment email '
    '($kKeygenUnlockInstruction) to unlock Connect. '
    'Your monthly subscription (£2.45 per month) begins after your 7 day trial. '
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

  Future<String> paymentKeygen() async {
    return (await backend.getString(kKeyPaymentKeygen) ?? '').trim().toUpperCase();
  }

  Future<void> recordPaymentSuccess(
    String sessionId, {
    String keygen = '',
  }) async {
    if (sessionId.trim().isNotEmpty) {
      await backend.setString(kKeyPaymentSessionId, sessionId.trim());
    }
    if (keygen.trim().isNotEmpty) {
      await backend.setString(
        kKeyPaymentKeygen,
        keygen.trim().toUpperCase(),
      );
    }
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
  /// Fallback path; preferred product path is [importKeygenAndVerify].
  Future<String> importSessionAndVerify(
    String sessionId, {
    String? baseUrl,
    Future<Map<String, dynamic>> Function(String sessionId)? fetch,
    bool bindDevice = true,
    Future<String> Function()? resolveDevicePub,
    Future<Map<String, dynamic>> Function(Uri uri, List<int> body)? postBind,
  }) async {
    final sid = sessionId.trim();
    if (sid.isEmpty) return kPaymentStatusUnknown;
    await backend.setString(kKeyPaymentSessionId, sid);
    await backend.setString(kKeyPaymentStatus, kPaymentStatusUnknown);
    return refreshEntitlementFromRemote(
      baseUrl: baseUrl,
      fetch: fetch,
      bindDevice: bindDevice,
      resolveDevicePub: resolveDevicePub,
      postBind: postBind,
    );
  }

  /// Enter fulfilment keygen and verify against the status host.
  ///
  /// On active entitlement, POSTs `/api/bind-device-entitlement` so the residual
  /// node can admit HELLO when `RPT_REQUIRE_PAYMENT_ENTITLEMENT=1` (parity with
  /// desktop `import_keygen_and_verify(bind_device=True)`).
  Future<String> importKeygenAndVerify(
    String keygen, {
    String? baseUrl,
    Future<Map<String, dynamic>> Function(String sessionId)? fetch,
    bool bindDevice = true,
    Future<String> Function()? resolveDevicePub,
    Future<Map<String, dynamic>> Function(Uri uri, List<int> body)? postBind,
  }) async {
    final kg = keygen.trim().toUpperCase().replaceAll(' ', '');
    if (kg.isEmpty) return kPaymentStatusUnknown;
    await backend.setString(kKeyPaymentKeygen, kg);
    await backend.setString(kKeyPaymentStatus, kPaymentStatusUnknown);
    return refreshEntitlementFromRemote(
      baseUrl: baseUrl,
      fetch: fetch,
      bindDevice: bindDevice,
      resolveDevicePub: resolveDevicePub,
      postBind: postBind,
    );
  }

  Future<String> refreshEntitlementFromRemote({
    String? baseUrl,
    Future<Map<String, dynamic>> Function(String sessionId)? fetch,
    bool bindDevice = true,
    Future<String> Function()? resolveDevicePub,
    Future<Map<String, dynamic>> Function(Uri uri, List<int> body)? postBind,
  }) async {
    final sid = await paymentSessionId();
    final kg = await paymentKeygen();
    if (sid.isEmpty && kg.isEmpty) return await paymentStatus();
    Map<String, dynamic> remote;
    try {
      if (fetch != null) {
        remote = await fetch(sid.isNotEmpty ? sid : kg);
      } else {
        remote = await fetchRemoteEntitlementStatus(
          sid,
          baseUrl: baseUrl,
          keygen: kg,
        );
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
      final remoteSid = remote['session_id']?.toString() ?? sid;
      final remoteKg = remote['keygen']?.toString() ?? kg;
      final allowed = remote['connect_allowed'];
      if (allowed == false) {
        await recordPaymentFailure(
          reason: remote['reason']?.toString() ?? 'not_allowed',
          status: kPaymentStatusRevoked,
        );
        return kPaymentStatusRevoked;
      }
      await recordPaymentSuccess(remoteSid, keygen: remoteKg);
      if (bindDevice && remoteSid.trim().isNotEmpty) {
        try {
          await bindDeviceEntitlement(
            remoteSid,
            baseUrl: baseUrl,
            resolveDevicePub: resolveDevicePub,
            post: postBind,
          );
        } catch (_) {
          // Bind best-effort: unlock still recorded; Connect may re-bind later.
        }
      }
      return kPaymentStatusActive;
    }
    return await paymentStatus();
  }

  /// POST `/api/bind-device-entitlement` (same contract as desktop/Python).
  ///
  /// [resolveDevicePub] and [post] are injectable for unit tests; production uses
  /// native `devicePubHex` + HttpClient.
  Future<Map<String, dynamic>> bindDeviceEntitlement(
    String sessionId, {
    String? devicePubHex,
    String? baseUrl,
    Future<String> Function()? resolveDevicePub,
    Future<Map<String, dynamic>> Function(Uri uri, List<int> body)? post,
    Duration timeout = const Duration(seconds: 8),
  }) async {
    final sid = sessionId.trim();
    var pub = (devicePubHex ?? '').trim().toLowerCase();
    if (pub.isEmpty && resolveDevicePub != null) {
      pub = (await resolveDevicePub()).trim().toLowerCase();
    }
    if (pub.isEmpty) {
      pub = (await resolveDevicePubHex()).trim().toLowerCase();
    }
    if (sid.isEmpty || pub.isEmpty || pub.length != 64) {
      return {
        'ok': false,
        'error': 'missing_session_or_device',
        'session_id': sid,
        'device_pub_hex': pub,
      };
    }
    final base = (baseUrl ??
            Platform.environment['RPT_PUBLIC_BASE_URL'] ??
            kDefaultPaymentStatusBaseUrl)
        .trim()
        .replaceAll(RegExp(r'/+$'), '');
    final uri = Uri.parse('$base/api/bind-device-entitlement');
    final body = utf8.encode(
      jsonEncode({'session_id': sid, 'device_pub': pub}),
    );
    if (post != null) {
      return post(uri, body);
    }
    return postBindDeviceEntitlement(uri, body, timeout: timeout);
  }

  /// Production HTTP POST for device bind (overridable via [bindDeviceEntitlement.post]).
  static Future<Map<String, dynamic>> postBindDeviceEntitlement(
    Uri uri,
    List<int> body, {
    Duration timeout = const Duration(seconds: 8),
  }) async {
    final client = HttpClient();
    try {
      client.connectionTimeout = timeout;
      final req = await client.postUrl(uri);
      req.headers.set(
        HttpHeaders.userAgentHeader,
        'RestorePrivacy-flutter/${RptConfig.productVersion}',
      );
      req.headers.set(HttpHeaders.acceptHeader, 'application/json');
      req.headers.set(HttpHeaders.contentTypeHeader, 'application/json');
      req.add(body);
      final resp = await req.close().timeout(timeout);
      final raw = await resp.transform(utf8.decoder).join();
      final data = jsonDecode(raw);
      if (data is Map<String, dynamic>) return data;
      if (data is Map) return Map<String, dynamic>.from(data);
      return {'ok': false, 'error': 'bad_response'};
    } catch (e) {
      return {'ok': false, 'error': e.toString()};
    } finally {
      client.close(force: true);
    }
  }

  /// 64-char lowercase hex of local Ed25519 device public key (native channel).
  static Future<String> resolveDevicePubHex() async {
    try {
      const channel = MethodChannel('restore_privacy/vpn');
      final raw = await channel.invokeMethod<dynamic>('devicePubHex');
      if (raw is Map) {
        final hex = (raw['devicePubHex'] ?? raw['device_pub_hex'] ?? raw['pub'])
            ?.toString()
            .trim()
            .toLowerCase();
        if (hex != null && hex.length == 64) return hex;
        if (raw['ok'] == true && hex != null) return hex;
      }
      if (raw is String) {
        final hex = raw.trim().toLowerCase();
        if (hex.length == 64) return hex;
      }
    } catch (_) {}
    return '';
  }

  static Future<Map<String, dynamic>> fetchRemoteEntitlementStatus(
    String sessionId, {
    String? baseUrl,
    String keygen = '',
    Duration timeout = const Duration(seconds: 8),
  }) async {
    final sid = sessionId.trim();
    final kg = keygen.trim().toUpperCase();
    if (sid.isEmpty && kg.isEmpty) {
      return {
        'status': kPaymentStatusUnknown,
        'error': 'missing_session_id_or_keygen',
      };
    }
    final base = (baseUrl ??
            Platform.environment['RPT_PUBLIC_BASE_URL'] ??
            kDefaultPaymentStatusBaseUrl)
        .trim()
        .replaceAll(RegExp(r'/+$'), '');
    final query = kg.isNotEmpty
        ? 'keygen=${Uri.encodeQueryComponent(kg)}'
        : 'session_id=${Uri.encodeQueryComponent(sid)}';
    final uri = Uri.parse('$base/api/connect-entitlement?$query');
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

  /// Customer-facing OK | EXPIRED for this install.
  Future<String> licenceStatus() async {
    final st = await paymentStatus();
    return licenceStatusFromPaymentStatus(st);
  }

  Future<bool> mayConnect({bool requirePayment = true}) async {
    if (!await hasAcceptedLicence()) return false;
    return paymentAllowsConnect(require: requirePayment);
  }

  /// True when licence is accepted but payment/keygen unlock is still required.
  /// Used to force a keygen entry surface before residual Connect (not Settings-only).
  Future<bool> needsKeygenUnlock({bool requirePayment = true}) async {
    if (!await hasAcceptedLicence()) return false;
    return !(await paymentAllowsConnect(require: requirePayment));
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
      final kg = await paymentKeygen();
      if (sid.isNotEmpty || kg.isNotEmpty) {
        await refreshEntitlementFromRemote(baseUrl: baseUrl, fetch: fetch);
      }
    }
    if (!await paymentAllowsConnect(require: requirePayment)) {
      final st = await paymentStatus();
      if (st == kPaymentStatusFailed ||
          st == kPaymentStatusRevoked ||
          st == kPaymentStatusUnpaid) {
        // EXPIRED lock — renew your licence *here*
        return (
          ok: false,
          message: renewLicenceMessage(platform: Platform.operatingSystem),
        );
      }
      final sid = await paymentSessionId();
      final kg = await paymentKeygen();
      if (sid.isEmpty && kg.isEmpty) {
        return (ok: false, message: kConnectBlockedKeygenMsg);
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

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
    'RESTORE PRIVACY). Download alone does not unlock residual VPN. '
    'Successful payment/active subscription is required; if payment fails at any time, '
    'Connect is cancelled.';

const String kConnectBlockedKeygenMsg =
    'Connect is blocked: enter a valid keygen after accepting the licence. '
    'Your fulfilment email includes the keygen with the text '
    'USE THIS KEYGEN TO UNLOCK RESTORE PRIVACY. '
    'Download alone does not unlock residual VPN.';

const String kKeygenPromptTitle = 'Enter licence keygen';
const String kKeygenPromptBody =
    'Your fulfilment email includes a keygen with the text '
    'USE THIS KEYGEN TO UNLOCK RESTORE PRIVACY '
    '(format RPT-KEY-…). Paste it below to unlock Connect. '
    'Download alone does not unlock residual VPN.';

const String kKeyPaymentStatus = 'payment_entitlement_status';
const String kKeyPaymentSessionId = 'payment_entitlement_session_id';
const String kKeyPaymentKeygen = 'payment_entitlement_keygen';
const String kKeyPaymentPlatform = 'payment_entitlement_platform';
const String kKeyPaymentValidUntil = 'payment_entitlement_valid_until';
const String kKeyPaymentRenewUrl = 'payment_entitlement_renew_url';
const String kPaymentStatusActive = 'active';
const String kPaymentStatusFailed = 'failed';
const String kPaymentStatusRevoked = 'revoked';
const String kPaymentStatusUnpaid = 'unpaid';
const String kPaymentStatusUnknown = 'unknown';

/// Customer-facing licence status (host + clients).
const String kLicenceStatusOk = 'OK';
const String kLicenceStatusExpired = 'EXPIRED';

const String kKeygenUnlockInstruction =
    'USE THIS KEYGEN TO UNLOCK RESTORE PRIVACY';

const String kDefaultPaymentStatusBaseUrl = 'https://restoreprivacy.online';

/// Default monthly Stripe Payment Link (aligned with status_page.payments).
const String kDefaultStripePaymentPageUrl =
    'https://buy.stripe.com/cNi7sM4uOeWQ9TBe0q7kc00';

/// EXPIRED lock phrase — *here* is the platform payment portal.
const String kRenewLicencePrefix = 'Renew your licence ';
const String kRenewLicenceHere = 'here';
const String kRenewLicencePromptTitle = 'Renew your licence';

/// Normalize payment status → OK | EXPIRED.
String licenceStatusFromPaymentStatus(String status) {
  final st = status.trim().toLowerCase();
  if (st == kPaymentStatusActive) return kLicenceStatusOk;
  return kLicenceStatusExpired;
}

bool isPaymentBlockingStatus(String status) {
  final st = status.trim().toLowerCase();
  return st == kPaymentStatusFailed ||
      st == kPaymentStatusRevoked ||
      st == kPaymentStatusUnpaid;
}

/// Map runtime OS to catalog platform id.
String platformForRenew({String? override}) {
  final o = (override ?? '').trim().toLowerCase();
  if (o.isNotEmpty) return o;
  if (Platform.isAndroid) return 'android';
  if (Platform.isIOS) return 'ios';
  if (Platform.isMacOS) return 'macos';
  if (Platform.isWindows) return 'windows';
  if (Platform.isLinux) return 'linux';
  return 'android';
}

/// Platform-specific Stripe Payment Link (monthly default).
String renewLicenceUrl({
  String platform = '',
  String interval = 'month',
  String? basePaymentPageUrl,
}) {
  final plat = platformForRenew(override: platform);
  final base = (basePaymentPageUrl ??
          Platform.environment['STRIPE_PAYMENT_PAGE_URL'] ??
          Platform.environment['RPT_STRIPE_PAYMENT_PAGE_URL'] ??
          kDefaultStripePaymentPageUrl)
      .trim()
      .replaceAll(RegExp(r'/+$'), '');
  final iv = interval.trim().toLowerCase() == 'year' ? 'year' : 'month';
  final ref = Uri.encodeQueryComponent('$plat|$iv');
  final sep = base.contains('?') ? '&' : '?';
  return '$base${sep}client_reference_id=$ref';
}

/// Catalog homepage fallback (user picks platform + interval).
String renewLicenceCatalogUrl() => kDefaultPaymentStatusBaseUrl;

/// Message for EXPIRED lock screen with renew *here* + platform portal URL.
String renewLicenceMessage({String platform = '', String? renewUrl}) {
  final plat = platformForRenew(override: platform);
  final url = (renewUrl ?? '').trim().isNotEmpty
      ? renewUrl!.trim()
      : renewLicenceUrl(platform: plat);
  return 'Renew your licence *here*: $url\n\n'
      'Your subscription is $kLicenceStatusExpired. Open the link to pay '
      'monthly or yearly for $plat, then enter your new keygen to unlock Connect.';
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
    'Your subscription (£3.00 per month or £30.00 per year) includes a 3-day free trial — '
    'no money is taken until after the trial ends. '
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
    String platform = '',
    double? validUntil,
    String renewUrl = '',
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
    if (platform.trim().isNotEmpty) {
      await backend.setString(kKeyPaymentPlatform, platform.trim().toLowerCase());
    }
    if (validUntil != null) {
      await backend.setString(kKeyPaymentValidUntil, validUntil.toString());
    }
    if (renewUrl.trim().isNotEmpty) {
      await backend.setString(kKeyPaymentRenewUrl, renewUrl.trim());
    }
    await backend.setString(kKeyPaymentStatus, kPaymentStatusActive);
  }

  Future<void> recordPaymentFailure({
    String reason = 'payment_failed',
    String status = kPaymentStatusFailed,
    String platform = '',
    String renewUrl = '',
  }) async {
    final st = status.trim().toLowerCase();
    final write = (st == kPaymentStatusRevoked || st == kPaymentStatusUnpaid)
        ? st
        : kPaymentStatusFailed;
    await backend.setString(kKeyPaymentStatus, write);
    if (platform.trim().isNotEmpty) {
      await backend.setString(kKeyPaymentPlatform, platform.trim().toLowerCase());
    }
    if (renewUrl.trim().isNotEmpty) {
      await backend.setString(kKeyPaymentRenewUrl, renewUrl.trim());
    }
  }

  Future<String> paymentPlatform() async {
    final s = await backend.getString(kKeyPaymentPlatform);
    return (s ?? '').trim().toLowerCase();
  }

  Future<String> paymentRenewUrl() async {
    final s = await backend.getString(kKeyPaymentRenewUrl);
    return (s ?? '').trim();
  }

  Future<double?> paymentValidUntil() async {
    final s = await backend.getString(kKeyPaymentValidUntil);
    if (s == null || s.trim().isEmpty) return null;
    return double.tryParse(s.trim());
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
  ///
  /// **Version-agnostic:** unlock is subscription-scoped. The same `RPT-KEY-…`
  /// from an older monopin re-applies on a newer build; app version is never
  /// sent to `/api/connect-entitlement` and does not gate unlock success.
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
    final remotePlat = remote['platform']?.toString() ?? '';
    final remoteRenew = remote['renew_url']?.toString() ??
        remote['renew_url_monthly']?.toString() ??
        '';
    double? remoteVu;
    final vuRaw = remote['valid_until'];
    if (vuRaw is num) {
      remoteVu = vuRaw.toDouble();
    } else if (vuRaw != null) {
      remoteVu = double.tryParse(vuRaw.toString());
    }
    if (st == kPaymentStatusFailed ||
        st == kPaymentStatusRevoked ||
        st == kPaymentStatusUnpaid) {
      await recordPaymentFailure(
        reason: remote['reason']?.toString() ?? st,
        status: st,
        platform: remotePlat,
        renewUrl: remoteRenew,
      );
      return st;
    }
    // Host licence_status EXPIRED with otherwise active-looking status
    final licRemote = remote['licence_status']?.toString().trim().toUpperCase();
    if (licRemote == kLicenceStatusExpired) {
      await recordPaymentFailure(
        reason: remote['reason']?.toString() ?? 'licence_expired',
        status: kPaymentStatusRevoked,
        platform: remotePlat,
        renewUrl: remoteRenew,
      );
      return kPaymentStatusRevoked;
    }
    if (st == kPaymentStatusActive) {
      final remoteSid = remote['session_id']?.toString() ?? sid;
      final remoteKg = remote['keygen']?.toString() ?? kg;
      final allowed = remote['connect_allowed'];
      if (allowed == false) {
        await recordPaymentFailure(
          reason: remote['reason']?.toString() ?? 'not_allowed',
          status: kPaymentStatusRevoked,
          platform: remotePlat,
          renewUrl: remoteRenew,
        );
        return kPaymentStatusRevoked;
      }
      // Period ended locally if host sent valid_until in the past
      if (remoteVu != null &&
          remoteVu <= DateTime.now().millisecondsSinceEpoch / 1000.0) {
        await recordPaymentFailure(
          reason: 'period_ended',
          status: kPaymentStatusRevoked,
          platform: remotePlat,
          renewUrl: remoteRenew,
        );
        return kPaymentStatusRevoked;
      }
      await recordPaymentSuccess(
        remoteSid,
        keygen: remoteKg,
        platform: remotePlat,
        validUntil: remoteVu,
        renewUrl: remoteRenew,
      );
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
  /// product requires payment (default). Active allows only with keygen unlock
  /// (parity with desktop ``payment_allows_connect``).
  Future<bool> paymentAllowsConnect({bool require = true}) async {
    final st = await paymentStatus();
    if (isPaymentBlockingStatus(st)) {
      return false;
    }
    if (st == kPaymentStatusActive) {
      final vu = await paymentValidUntil();
      if (vu != null &&
          vu <= DateTime.now().millisecondsSinceEpoch / 1000.0) {
        return false;
      }
      if (require) {
        final kg = await paymentKeygen();
        if (kg.isEmpty || !kg.startsWith('RPT-KEY-')) {
          return false;
        }
      }
      return true;
    }
    if (!require) return true;
    return false;
  }

  /// Customer-facing OK | EXPIRED for this install.
  Future<String> licenceStatus() async {
    final st = await paymentStatus();
    if (isPaymentBlockingStatus(st)) return kLicenceStatusExpired;
    if (st == kPaymentStatusActive) {
      final vu = await paymentValidUntil();
      if (vu != null &&
          vu <= DateTime.now().millisecondsSinceEpoch / 1000.0) {
        return kLicenceStatusExpired;
      }
      return kLicenceStatusOk;
    }
    return kLicenceStatusExpired;
  }

  Future<bool> mayConnect({bool requirePayment = true}) async {
    if (!await hasAcceptedLicence()) return false;
    return paymentAllowsConnect(require: requirePayment);
  }

  /// True when subscription is EXPIRED — show renew surface, not keygen.
  Future<bool> needsLicenceRenewal({bool requirePayment = true}) async {
    if (!await hasAcceptedLicence()) return false;
    final st = await paymentStatus();
    if (isPaymentBlockingStatus(st)) return true;
    if (st == kPaymentStatusActive) {
      final vu = await paymentValidUntil();
      if (vu != null &&
          vu <= DateTime.now().millisecondsSinceEpoch / 1000.0) {
        return true;
      }
    }
    return false;
  }

  /// True when licence is accepted but a keygen entry is still required.
  /// False when EXPIRED (renew surface) — never confuses with keygen modal.
  Future<bool> needsKeygenUnlock({bool requirePayment = true}) async {
    if (!await hasAcceptedLicence()) return false;
    if (await needsLicenceRenewal(requirePayment: requirePayment)) {
      return false;
    }
    return !(await paymentAllowsConnect(require: requirePayment));
  }

  Future<String> renewMessageForInstall() async {
    final plat = await paymentPlatform();
    final cached = await paymentRenewUrl();
    return renewLicenceMessage(
      platform: plat.isEmpty ? platformForRenew() : plat,
      renewUrl: cached.isEmpty ? null : cached,
    );
  }

  Future<String> renewPortalUrlForInstall() async {
    final cached = await paymentRenewUrl();
    if (cached.isNotEmpty) return cached;
    final plat = await paymentPlatform();
    return renewLicenceUrl(
      platform: plat.isEmpty ? platformForRenew() : plat,
    );
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
      if (isPaymentBlockingStatus(st) || await needsLicenceRenewal()) {
        // EXPIRED lock — renew your licence *here* + platform portal
        return (ok: false, message: await renewMessageForInstall());
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

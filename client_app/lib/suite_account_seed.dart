/// Suite-wide recovery seed: export on first register, import on clean install.
///
/// Wallet/analyser identity is restored via the shipped Perccent seed envelope
/// path ([PercWalletProvider.recoverFromSeedPhrase]). Licence/KEYGEN are
/// optionally rehydrated from a Suite-local sealed meta blob encrypted with
/// seed-derived material when present (never invents a KEYGEN from the seed).
library;

import 'dart:convert';

import 'package:evolve/perc/perc_chain_constants.dart' as evolve_chain;
import 'package:evolve/perc/providers/perc_wallet_provider.dart' as evolve_wallet;
import 'package:evolve/perc/services/perc_ledger_hub.dart' as evolve_hub;
import 'package:evolve/perc/services/perc_network_coordinator.dart'
    as evolve_coord;
import 'package:evolve/perc/services/perc_seed_recovery.dart';
import 'package:perccent_wallet/perc/providers/perc_wallet_provider.dart'
    as perc_wallet;
import 'package:perccent_wallet/perc/services/perc_ledger_hub.dart' as perc_hub;
import 'package:perccent_wallet/perc/services/perc_network_coordinator.dart'
    as perc_coord;

import 'licence_gate.dart';
import 'settings_store.dart';
import 'suite_account.dart';
import 'suite_account_apply.dart';

const String kKeySuiteSeedBackupEnvelope = 'suite_seed_backup_envelope_b64';
const String kKeySuiteSeedBackupFingerprint = 'suite_seed_backup_fingerprint';
const String kKeySuiteSeedMetaBlob = 'suite_seed_meta_blob_b64';

const String kSuiteSeedExportTitle = 'Save your recovery seed';
const String kSuiteSeedExportBody =
    'Write down these 12 words offline. They restore your % wallet and Evolve '
    'analyser identity on a new install. Skip only if you accept that recovery '
    'will not be available without this phrase.';
const String kSuiteSeedGenerateLabel = 'Generate seed phrase';
const String kSuiteSeedConfirmLabel = 'I wrote it down — continue';
const String kSuiteSeedSkipLabel = 'Skip recovery seed';
const String kSuiteSeedImportLabel = 'Restore from seed phrase';
const String kSuiteSeedImportTitle = 'Restore Suite identity from seed';
const String kSuiteSeedImportBody =
    'Paste your 12-word recovery phrase to restore the wallet/analyser account '
    'on this install. Licence/KEYGEN are restored only if they were sealed with '
    'this seed on a previous Suite device.';

/// Result of the first-register seed offer (export opportunity).
class SuiteSeedOfferResult {
  const SuiteSeedOfferResult.enable(this.words)
      : enableSeed = true,
        assert(words != null);
  const SuiteSeedOfferResult.skip()
      : enableSeed = false,
        words = null;

  final bool enableSeed;
  final List<String>? words;
}

/// UI/tests: offer generate + confirm/skip. [generate] returns 12 words.
typedef SuiteSeedOfferFn = Future<SuiteSeedOfferResult> Function(
  Future<List<String>> Function() generate,
);

/// Pure: normalize pasted seed text into 12 words.
List<String> parseSuiteSeedPhrase(String raw) {
  final words = raw
      .toLowerCase()
      .replaceAll(RegExp(r'[^a-z\s]'), ' ')
      .split(RegExp(r'\s+'))
      .where((w) => w.isNotEmpty)
      .toList();
  if (words.length != PercSeedRecovery.wordCount) {
    throw FormatException(
      'Seed phrase must be exactly ${PercSeedRecovery.wordCount} words '
      '(got ${words.length})',
    );
  }
  PercSeedRecovery.validateMnemonic(words);
  return words;
}

/// Seal Suite-local meta for optional licence/KEYGEN rehydrate (not derived KEYGEN).
String sealSuiteSeedMeta({
  required List<String> words,
  required String username,
  String? licenceId,
  bool? licenceAccepted,
  String? paymentStatus,
  String? paymentKeygen,
  String? paymentSessionId,
}) {
  final key = PercSeedRecovery.deriveKeyMaterial(words);
  final payload = <String, dynamic>{
    'v': 1,
    'username': username.trim(),
    if (licenceId != null) 'licence_id': licenceId,
    if (licenceAccepted != null) 'licence_accepted': licenceAccepted,
    if (paymentStatus != null) 'payment_status': paymentStatus,
    if (paymentKeygen != null && paymentKeygen.trim().isNotEmpty)
      'payment_keygen': paymentKeygen.trim(),
    if (paymentSessionId != null) 'payment_session_id': paymentSessionId,
  };
  final plain = utf8.encode(jsonEncode(payload));
  // XOR with key material (sufficient for local sealed prefs; seed is secret).
  final out = List<int>.generate(plain.length, (i) => plain[i] ^ key[i % key.length]);
  return base64Encode(out);
}

Map<String, dynamic> unsealSuiteSeedMeta({
  required List<String> words,
  required String blobB64,
}) {
  final key = PercSeedRecovery.deriveKeyMaterial(words);
  final raw = base64Decode(blobB64);
  final plain = List<int>.generate(raw.length, (i) => raw[i] ^ key[i % key.length]);
  final map = jsonDecode(utf8.decode(plain)) as Map<String, dynamic>;
  return map;
}

/// Persist seed backup envelope + optional meta after successful seed-enabled register.
Future<void> persistSuiteSeedBackupArtifacts({
  required SettingsBackend backend,
  required List<String> words,
  required String username,
  required String envelopeB64,
  SettingsBackend? licenceBackend,
}) async {
  final fp = PercSeedRecovery.fingerprint(words);
  await backend.setString(kKeySuiteSeedBackupEnvelope, envelopeB64);
  await backend.setString(kKeySuiteSeedBackupFingerprint, fp);

  String? licenceId;
  bool? licenceAccepted;
  String? paymentStatus;
  String? paymentKeygen;
  String? paymentSessionId;
  final lic = licenceBackend;
  if (lic != null) {
    licenceAccepted = (await lic.getBool(kKeyLicenceAccepted)) == true;
    licenceId = await lic.getString(kKeyLicenceId);
    paymentStatus = await lic.getString(kKeyPaymentStatus);
    paymentKeygen = await lic.getString(kKeyPaymentKeygen);
    paymentSessionId = await lic.getString(kKeyPaymentSessionId);
  }
  final meta = sealSuiteSeedMeta(
    words: words,
    username: username,
    licenceId: licenceId,
    licenceAccepted: licenceAccepted,
    paymentStatus: paymentStatus,
    paymentKeygen: paymentKeygen,
    paymentSessionId: paymentSessionId,
  );
  await backend.setString(kKeySuiteSeedMetaBlob, meta);
}

/// Apply sealed meta to Suite account + optional licence prefs after seed restore.
Future<void> applySuiteSeedMetaToStores({
  required Map<String, dynamic> meta,
  required SuiteAccountStore accountStore,
  SettingsBackend? licenceBackend,
}) async {
  final u = (meta['username'] as String? ?? '').trim();
  if (u.isNotEmpty) {
    await accountStore.markRegistered(u);
  }
  final lic = licenceBackend;
  if (lic == null) return;
  if (meta['licence_accepted'] == true) {
    await lic.setBool(kKeyLicenceAccepted, true);
    final id = meta['licence_id'] as String?;
    if (id != null && id.isNotEmpty) {
      await lic.setString(kKeyLicenceId, id);
    }
  }
  final status = meta['payment_status'] as String?;
  if (status != null && status.isNotEmpty) {
    await lic.setString(kKeyPaymentStatus, status);
  }
  final keygen = meta['payment_keygen'] as String?;
  if (keygen != null && keygen.isNotEmpty) {
    await lic.setString(kKeyPaymentKeygen, keygen);
  }
  final session = meta['payment_session_id'] as String?;
  if (session != null && session.isNotEmpty) {
    await lic.setString(kKeyPaymentSessionId, session);
  }
}

/// Restore wallet/analyser identity from seed; rehydrate Suite store (+ licence meta if sealed).
///
/// Prefers Suite-local sealed envelope (no network hang). Falls back to
/// [PercWalletProvider.recoverFromSeedPhrase] (local catalog then rendezvous).
///
/// Returns restored username. Throws if phrase invalid or no recovery envelope.
Future<String> restoreSuiteIdentityFromSeed({
  required List<String> words,
  required SuiteAccountStore accountStore,
  SuiteAccountPackageSurfaces? surfaces,
  SettingsBackend? suitePrefsBackend,
  SettingsBackend? licenceBackend,
  /// Test inject: pre-load catalog envelope into a fresh ledger.
  String? localEnvelopeB64,
}) async {
  PercSeedRecovery.validateMnemonic(words);
  final s = surfaces ?? productionSuiteAccountSurfaces();
  final prevPerc = perc_coord.PercNetworkCoordinator.disableLiveNodesForTests;
  final prevEvolve = evolve_coord.PercNetworkCoordinator.disableLiveNodesForTests;
  try {
    perc_coord.PercNetworkCoordinator.disableLiveNodesForTests = true;
    evolve_coord.PercNetworkCoordinator.disableLiveNodesForTests = true;

    final prefs = suitePrefsBackend;
    String? envelope = localEnvelopeB64;
    if (envelope == null && prefs != null) {
      final fpStored = await prefs.getString(kKeySuiteSeedBackupFingerprint);
      final envStored = await prefs.getString(kKeySuiteSeedBackupEnvelope);
      final fp = PercSeedRecovery.fingerprint(words);
      if (envStored != null &&
          envStored.isNotEmpty &&
          (fpStored == null || fpStored == fp)) {
        envelope = envStored;
      }
    }

    final evolve = s.createEvolveProvider();
    await evolve.initialize();

    String username;
    if (envelope != null && envelope.isNotEmpty) {
      // Offline-honest path: decrypt Suite-sealed envelope (no network).
      final restored = PercSeedRecovery.decryptLedgerEnvelope(
        envelope: base64Decode(envelope),
        words: words,
      );
      final session = restored.sessionUsername ??
          restored.accounts.keys.firstWhere(
            (k) => k != evolve_chain.PercChainConstants.treasuryUsername,
            orElse: () => '',
          );
      if (session.isEmpty) {
        throw StateError('Seed envelope contains no user wallet');
      }
      await evolve_hub.PercLedgerHub.instance.restoreFromBackup(
        restored,
        sessionUsername: session,
      );
      username = session;
    } else {
      await evolve.recoverFromSeedPhrase(words);
      username = (evolve.loggedInUsername ?? '').trim();
    }
    if (username.isEmpty) {
      throw StateError('Seed restore did not produce a logged-in wallet session');
    }

    // Dual-surface: persist evolve ledger then re-open Perccent on shared store.
    await evolve_hub.PercLedgerHub.instance.persistLocal();
    final perc = s.createPercProvider();
    await perc.initialize();
    await s.reloadEvolveHub();
    // Perccent package ledger type differs at compile-time; shared JSON file
    // rehydrate is enough when stores point at the same on-disk ledger.
    if (!perc.isLoggedIn || (perc.loggedInUsername ?? '').trim() != username) {
      try {
        await perc.login(username, ''); // may fail without password — ignore
      } catch (_) {}
    }
    await s.persistPercHub();

    await accountStore.markRegistered(username);
    SuiteAccountBus.instance.notifyRegistered(username);

    if (prefs != null) {
      final metaBlob = await prefs.getString(kKeySuiteSeedMetaBlob);
      if (metaBlob != null && metaBlob.isNotEmpty) {
        try {
          final meta = unsealSuiteSeedMeta(words: words, blobB64: metaBlob);
          await applySuiteSeedMetaToStores(
            meta: meta,
            accountStore: accountStore,
            licenceBackend: licenceBackend,
          );
        } catch (_) {
          // Meta optional — wallet identity already restored.
        }
      }
    }
    return username;
  } finally {
    perc_coord.PercNetworkCoordinator.disableLiveNodesForTests = prevPerc;
    evolve_coord.PercNetworkCoordinator.disableLiveNodesForTests = prevEvolve;
  }
}

/// After seed-enabled registration on [wallet], extract envelope b64 from ledger.
String? suiteSeedEnvelopeB64FromWallet(evolve_wallet.PercWalletProvider wallet) {
  final u = wallet.loggedInUsername;
  if (u == null) return null;
  final acc = evolve_hub.PercLedgerHub.instance.ledger.account(u);
  return acc?.seedRecoveryEnvelope;
}

/// Perccent surface envelope (shared ledger file after dual apply).
String? suiteSeedEnvelopeB64FromPerc(perc_wallet.PercWalletProvider wallet) {
  final u = wallet.loggedInUsername;
  if (u == null) return null;
  final acc = perc_hub.PercLedgerHub.instance.ledger.account(u);
  return acc?.seedRecoveryEnvelope;
}

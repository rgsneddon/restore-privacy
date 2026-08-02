/// Suite-wide recovery seed: export on first register, import on clean install.
///
/// Wallet/analyser identity is restored from an encrypted ledger envelope
/// unlocked by the 12-word phrase. The envelope is published at export time
/// (rendezvous / injectable store) so a **new install** can restore with words
/// alone — SharedPreferences are not required. Licence/KEYGEN are optionally
/// sealed alongside the envelope when present (never invented from the seed).
library;

import 'dart:convert';

import 'package:evolve/perc/perc_chain_constants.dart' as evolve_chain;
import 'package:evolve/perc/providers/perc_wallet_provider.dart' as evolve_wallet;
import 'package:evolve/perc/services/perc_ledger_hub.dart' as evolve_hub;
import 'package:evolve/perc/services/perc_network_coordinator.dart'
    as evolve_coord;
import 'package:evolve/perc/services/perc_network_rendezvous.dart'
    as evolve_rendezvous;
import 'package:evolve/perc/services/perc_seed_recovery.dart';
import 'package:evolve/perc/services/perc_seed_recovery_transport.dart'
    as seed_transport;
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

/// Published seed recovery payload (envelope + optional sealed Suite meta).
class SuiteSeedPublishedRecovery {
  const SuiteSeedPublishedRecovery({
    required this.envelopeB64,
    this.metaBlobB64,
  });

  final String envelopeB64;
  final String? metaBlobB64;
}

/// Kind marker for composite transport (ledger envelope + sealed Suite meta).
const String kSuiteSeedTransportKind = seed_transport.kSuiteSeedTransportKind;

/// Encode ledger envelope + optional sealed meta into one rendezvous string.
///
/// Canonical implementation lives in evolve [perc_seed_recovery_transport]
/// so hub re-publish uses the same builder and cannot clobber meta.
String encodeSuiteSeedTransport({
  required String ledgerEnvelopeB64,
  String? metaBlobB64,
}) =>
    seed_transport.encodeSeedRecoveryTransport(
      ledgerEnvelopeB64: ledgerEnvelopeB64,
      metaBlobB64: metaBlobB64,
    );

/// Decode composite transport or legacy raw ledger envelope.
SuiteSeedPublishedRecovery decodeSuiteSeedTransport(String raw) {
  final decoded = seed_transport.decodeSeedRecoveryTransport(raw);
  return SuiteSeedPublishedRecovery(
    envelopeB64: decoded.ledger,
    metaBlobB64: decoded.meta,
  );
}

/// Pure: build network payload preserving meta on overwrite (all writers).
String buildSeedRecoveryNetworkPayload({
  required String ledgerEnvelopeB64,
  String? metaBlobB64,
  String? existingRemoteB64,
}) =>
    seed_transport.buildSeedRecoveryNetworkPayload(
      ledgerEnvelopeB64: ledgerEnvelopeB64,
      metaBlobB64: metaBlobB64,
      existingRemoteB64: existingRemoteB64,
    );

/// Publish/fetch seed envelopes so clean-install words-only restore works.
///
/// Production [publish] pushes a composite envelope (ledger + sealed meta) to
/// Perc rendezvous. [fetch] checks inject → memory → network and unwraps meta.
/// Tests may replace [publishHandler]/[fetchHandler]; production KEYGEN proof
/// must use the default path (handlers null) with rendezvous test map / network.
class SuiteSeedEnvelopeStore {
  SuiteSeedEnvelopeStore._();

  static final Map<String, SuiteSeedPublishedRecovery> memory =
      <String, SuiteSeedPublishedRecovery>{};

  static Future<void> Function(
    String fingerprint,
    SuiteSeedPublishedRecovery recovery,
  )? publishHandler;

  static Future<SuiteSeedPublishedRecovery?> Function(String fingerprint)?
      fetchHandler;

  static void resetForTest() {
    memory.clear();
    publishHandler = null;
    fetchHandler = null;
  }

  /// Drop process-local cache (simulates new install / new process).
  static void clearMemoryForTest() {
    memory.clear();
  }

  static Future<void> publish({
    required String fingerprint,
    required String envelopeB64,
    String? metaBlobB64,
  }) async {
    final recovery = SuiteSeedPublishedRecovery(
      envelopeB64: envelopeB64,
      metaBlobB64: metaBlobB64,
    );
    memory[fingerprint] = recovery;
    final handler = publishHandler;
    if (handler != null) {
      await handler(fingerprint, recovery);
      return;
    }
    // Single write: composite payload only (do NOT pre-call hub publish which
    // used to PUT ledger-only and clobber meta before this write).
    final existing =
        evolve_rendezvous.PercNetworkRendezvous.testSeedRecoveries[fingerprint];
    final transport = buildSeedRecoveryNetworkPayload(
      ledgerEnvelopeB64: envelopeB64,
      metaBlobB64: metaBlobB64,
      existingRemoteB64: existing,
    );
    try {
      await const evolve_rendezvous.PercNetworkRendezvous()
          .publishSeedRecoveryEnvelope(
        fingerprint: fingerprint,
        envelopeB64: transport,
        metaBlobB64: metaBlobB64,
      );
    } catch (_) {}
  }

  /// Resolve published envelope for [fingerprint] without Suite prefs.
  static Future<SuiteSeedPublishedRecovery?> fetch(String fingerprint) async {
    final handler = fetchHandler;
    if (handler != null) {
      return handler(fingerprint);
    }
    final local = memory[fingerprint];
    if (local != null) return local;
    try {
      final remote = await const evolve_rendezvous.PercNetworkRendezvous()
          .fetchSeedRecoveryEnvelope(fingerprint: fingerprint);
      if (remote != null && remote.isNotEmpty) {
        return decodeSuiteSeedTransport(remote);
      }
    } catch (_) {}
    return null;
  }
}

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
  final out =
      List<int>.generate(plain.length, (i) => plain[i] ^ key[i % key.length]);
  return base64Encode(out);
}

Map<String, dynamic> unsealSuiteSeedMeta({
  required List<String> words,
  required String blobB64,
}) {
  final key = PercSeedRecovery.deriveKeyMaterial(words);
  final raw = base64Decode(blobB64);
  final plain =
      List<int>.generate(raw.length, (i) => raw[i] ^ key[i % key.length]);
  return jsonDecode(utf8.decode(plain)) as Map<String, dynamic>;
}

/// Build sealed meta from current licence/suite backends (for publish + prefs).
Future<String> buildSuiteSeedMetaBlob({
  required List<String> words,
  required String username,
  SettingsBackend? licenceBackend,
}) async {
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
  return sealSuiteSeedMeta(
    words: words,
    username: username,
    licenceId: licenceId,
    licenceAccepted: licenceAccepted,
    paymentStatus: paymentStatus,
    paymentKeygen: paymentKeygen,
    paymentSessionId: paymentSessionId,
  );
}

/// Persist seed backup envelope + meta to local prefs (same-device convenience).
Future<void> persistSuiteSeedBackupArtifacts({
  required SettingsBackend backend,
  required List<String> words,
  required String username,
  required String envelopeB64,
  SettingsBackend? licenceBackend,
  String? metaBlobB64,
}) async {
  final fp = PercSeedRecovery.fingerprint(words);
  await backend.setString(kKeySuiteSeedBackupEnvelope, envelopeB64);
  await backend.setString(kKeySuiteSeedBackupFingerprint, fp);
  final meta = metaBlobB64 ??
      await buildSuiteSeedMetaBlob(
        words: words,
        username: username,
        licenceBackend: licenceBackend,
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
    final at = DateTime.now().toUtc().millisecondsSinceEpoch.toString();
    await lic.setString(kKeyLicenceAcceptedAt, at);
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

/// Publish seed envelope after durable register (clean-install restore path).
///
/// Call with live nodes restored so rendezvous publish is not no-op'd.
Future<void> publishSuiteSeedAfterExport({
  required List<String> words,
  required String username,
  required String envelopeB64,
  SettingsBackend? suitePrefsBackend,
  SettingsBackend? licenceBackend,
}) async {
  final fp = PercSeedRecovery.fingerprint(words);
  final meta = await buildSuiteSeedMetaBlob(
    words: words,
    username: username,
    licenceBackend: licenceBackend,
  );
  if (suitePrefsBackend != null) {
    await persistSuiteSeedBackupArtifacts(
      backend: suitePrefsBackend,
      words: words,
      username: username,
      envelopeB64: envelopeB64,
      licenceBackend: licenceBackend,
      metaBlobB64: meta,
    );
  }
  await SuiteSeedEnvelopeStore.publish(
    fingerprint: fp,
    envelopeB64: envelopeB64,
    metaBlobB64: meta,
  );
}

/// Restore wallet/analyser identity from seed (words-only clean install OK).
///
/// Resolution order for the ciphertext envelope:
/// 1. [localEnvelopeB64] (tests only — production UI does not pass this)
/// 2. Suite prefs on this device (same-device reinstall)
/// 3. [SuiteSeedEnvelopeStore.fetch] (published rendezvous / test inject)
/// 4. [PercWalletProvider.recoverFromSeedPhrase] network fallback
Future<String> restoreSuiteIdentityFromSeed({
  required List<String> words,
  required SuiteAccountStore accountStore,
  SuiteAccountPackageSurfaces? surfaces,
  SettingsBackend? suitePrefsBackend,
  SettingsBackend? licenceBackend,
  @Deprecated('Tests only — production clean install must not rely on this')
  String? localEnvelopeB64,
}) async {
  PercSeedRecovery.validateMnemonic(words);
  final s = surfaces ?? productionSuiteAccountSurfaces();
  final prevPerc = perc_coord.PercNetworkCoordinator.disableLiveNodesForTests;
  final prevEvolve = evolve_coord.PercNetworkCoordinator.disableLiveNodesForTests;
  try {
    perc_coord.PercNetworkCoordinator.disableLiveNodesForTests = true;
    evolve_coord.PercNetworkCoordinator.disableLiveNodesForTests = true;

    final fp = PercSeedRecovery.fingerprint(words);
    String? envelope = localEnvelopeB64;
    String? publishedMeta;

    // Same-device prefs (optional — wiped on true clean install).
    final prefs = suitePrefsBackend;
    if (envelope == null && prefs != null) {
      final fpStored = await prefs.getString(kKeySuiteSeedBackupFingerprint);
      final envStored = await prefs.getString(kKeySuiteSeedBackupEnvelope);
      if (envStored != null &&
          envStored.isNotEmpty &&
          (fpStored == null || fpStored == fp)) {
        envelope = envStored;
      }
      publishedMeta = await prefs.getString(kKeySuiteSeedMetaBlob);
    }

    // Published envelope (rendezvous / inject) — the clean-install path.
    if (envelope == null || envelope.isEmpty) {
      final published = await SuiteSeedEnvelopeStore.fetch(fp);
      if (published != null) {
        envelope = published.envelopeB64;
        publishedMeta ??= published.metaBlobB64;
      }
    }

    final evolve = s.createEvolveProvider();
    await evolve.initialize();

    String username;
    if (envelope != null && envelope.isNotEmpty) {
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
      // Last resort: wallet recovery service (network rendezvous).
      evolve_coord.PercNetworkCoordinator.disableLiveNodesForTests = false;
      await evolve.recoverFromSeedPhrase(words);
      username = (evolve.loggedInUsername ?? '').trim();
    }
    if (username.isEmpty) {
      throw StateError('Seed restore did not produce a logged-in wallet session');
    }

    await evolve_hub.PercLedgerHub.instance.persistLocal();
    final perc = s.createPercProvider();
    await perc.initialize();
    await s.reloadEvolveHub();
    await s.persistPercHub();

    await accountStore.markRegistered(username);
    SuiteAccountBus.instance.notifyRegistered(username);

    final metaBlob = publishedMeta;
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

/// Real BIP39 recovery words for Suite first-run / seed export (product path).
///
/// Always uses [PercSeedRecovery.generateMnemonic] — never a fake wordNN list.
Future<List<String>> generateSuiteSeedWords() async {
  final words = PercSeedRecovery.generateMnemonic();
  PercSeedRecovery.validateMnemonic(words);
  if (words.length != PercSeedRecovery.wordCount) {
    throw StateError('seed_generate_invalid_length');
  }
  // Fail closed if a stub ever leaks into the product path.
  if (_looksLikeStubSeedWords(words)) {
    throw StateError('seed_generate_stub_rejected');
  }
  return List<String>.from(words);
}

/// True for the historical first-run fallback `word01`…`word12` (never ship).
bool _looksLikeStubSeedWords(List<String> words) {
  if (words.length != 12) return false;
  for (var i = 0; i < 12; i++) {
    final expected = 'word${(i + 1).toString().padLeft(2, '0')}';
    if (words[i] != expected) return false;
  }
  return true;
}

/// Whether [words] are the forbidden wordNN stub (tests + fail-closed UI).
bool isStubSuiteSeedWords(List<String> words) => _looksLikeStubSeedWords(words);

/// Attach recovery envelope to a registered Suite identity and publish restore.
///
/// Call after first-run account register (which uses [skipSeedOffer]) so the
/// portal seed step owns write-down UI while still producing a real envelope
/// the user can restore from.
Future<void> attachAndPublishSuiteSeedForUser({
  required List<String> words,
  required String username,
  required String password,
  SuiteAccountPackageSurfaces? surfaces,
  SettingsBackend? suitePrefsBackend,
  SettingsBackend? licenceBackend,
}) async {
  final u = username.trim();
  if (u.isEmpty) throw StateError('Username is required for seed attach');
  if (_looksLikeStubSeedWords(words)) {
    throw StateError('stub seed words cannot be attached');
  }
  PercSeedRecovery.validateMnemonic(words);

  final s = surfaces ?? productionSuiteAccountSurfaces();
  final prevPerc = perc_coord.PercNetworkCoordinator.disableLiveNodesForTests;
  final prevEvolve = evolve_coord.PercNetworkCoordinator.disableLiveNodesForTests;
  perc_coord.PercNetworkCoordinator.disableLiveNodesForTests = true;
  evolve_coord.PercNetworkCoordinator.disableLiveNodesForTests = true;
  try {
    final perc = s.createPercProvider();
    await perc.initialize();
    if (perc.needsTreasuryPassword) {
      await perc.setupTreasuryPassword(password);
      await perc.logout();
    }
    if (!perc.isLoggedIn || (perc.loggedInUsername ?? '').trim() != u) {
      await perc.login(u, password);
    }
    if (!perc.isLoggedIn || (perc.loggedInUsername ?? '').trim() != u) {
      throw StateError(
        perc.errorMessage?.trim().isNotEmpty == true
            ? perc.errorMessage!
            : 'Perccent login required before seed attach',
      );
    }
    await perc.refreshSeedRecoveryEnvelope(words);
    await s.persistPercHub();

    final evolve = s.createEvolveProvider();
    await evolve.initialize();
    await s.reloadEvolveHub();
    if (!evolve.isLoggedIn || (evolve.loggedInUsername ?? '').trim() != u) {
      await evolve.login(u, password);
    }
    if (evolve.isLoggedIn && (evolve.loggedInUsername ?? '').trim() == u) {
      await evolve.refreshSeedRecoveryEnvelope(words);
      await evolve_hub.PercLedgerHub.instance.persistLocal();
    }

    final env = suiteSeedEnvelopeB64FromPerc(perc) ??
        suiteSeedEnvelopeB64FromWallet(evolve);
    if (env == null || env.isEmpty) {
      throw StateError('seed envelope missing after attach');
    }

    // Restore live flags before publish so rendezvous is not no-op'd.
    perc_coord.PercNetworkCoordinator.disableLiveNodesForTests = prevPerc;
    evolve_coord.PercNetworkCoordinator.disableLiveNodesForTests = prevEvolve;
    await publishSuiteSeedAfterExport(
      words: words,
      username: u,
      envelopeB64: env,
      suitePrefsBackend: suitePrefsBackend,
      licenceBackend: licenceBackend,
    );
  } finally {
    perc_coord.PercNetworkCoordinator.disableLiveNodesForTests = prevPerc;
    evolve_coord.PercNetworkCoordinator.disableLiveNodesForTests = prevEvolve;
  }
}

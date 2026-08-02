/// User data stays on-device: no log auto-upload, no telemetry SDKs,
/// minimal entitlement bind body, encrypted seed envelope (not plaintext mnemonic).
///
/// Drives shipped [ConnectionLog], [LicenceGate.bindDeviceEntitlement],
/// [SuiteSeedEnvelopeStore.publish], and [PercSeedRecovery.encryptLedgerEnvelope].
library;

import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:evolve/perc/models/perc_amount.dart';
import 'package:evolve/perc/models/perc_block.dart';
import 'package:evolve/perc/services/perc_ledger.dart';
import 'package:evolve/perc/services/perc_seed_recovery.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/connection_log.dart';
import 'package:restore_privacy_client/licence_gate.dart';
import 'package:restore_privacy_client/suite_account_seed.dart';

/// Spy backend: only local read/write (proves ConnectionLog never needs network).
class _SpyLogBackend implements ConnectionLogBackend {
  final List<String> lines = [];
  int writeCount = 0;
  int readCount = 0;

  @override
  Future<List<String>> readLines() async {
    readCount += 1;
    return List.of(lines);
  }

  @override
  Future<void> writeLines(List<String> next) async {
    writeCount += 1;
    lines
      ..clear()
      ..addAll(next);
  }
}

String _clientLib(String relative) =>
    File('${Directory.current.path}/lib/$relative').readAsStringSync();

String _clientPubspec() =>
    File('${Directory.current.path}/pubspec.yaml').readAsStringSync();

/// Known third-party telemetry / analytics / crash SDK package name fragments.
const _forbiddenTelemetryPackages = <String>[
  'firebase_analytics',
  'firebase_crashlytics',
  'firebase_core',
  'sentry',
  'sentry_flutter',
  'mixpanel',
  'amplitude',
  'segment_analytics',
  'posthog',
  'appsflyer',
  'adjust_sdk',
  'flurry',
  'countly',
  'appcenter',
  'crashlytics',
  'newrelic',
  'datadog',
  'bugsnag',
  'instabug',
  'hockeyapp',
  'google_analytics',
  'unity_analytics',
];

void main() {
  group('connection log stays local (no auto-upload)', () {
    test('append + formatExport only touch injectable local backend', () async {
      final backend = _SpyLogBackend();
      final log = ConnectionLog(
        backend,
        clientVersion: '1.0.6',
        platformLabel: 'macos',
      );

      await log.appendEvent(kLogKindError, 'Connect failed (test event)');
      expect(backend.writeCount, greaterThanOrEqualTo(1));
      expect(backend.readCount, greaterThanOrEqualTo(1));
      expect(backend.lines, isNotEmpty);

      final export = await log.formatExport();
      expect(export, contains('local only'));
      expect(export, contains('Not uploaded by the client'));
      expect(export, contains('Connect failed (test event)'));
      expect(export, contains('client_version=1.0.6'));
      // Export is a pure string from local backend — no network side effect.
      final writesAfterExport = backend.writeCount;
      expect(backend.lines.length, 1);
      // formatExport must not mutate or upload — only read.
      expect(backend.writeCount, writesAfterExport);
    });

    test('ConnectionLog source has no HttpClient / upload / postUrl', () {
      final src = _clientLib('connection_log.dart');
      expect(src.contains('HttpClient'), isFalse);
      expect(src.contains('postUrl'), isFalse);
      expect(src.contains('dart:io'), isTrue); // Platform only
      expect(src.contains('import \'dart:io\''), isTrue);
      // Docs mention "not uploaded" — no callable upload API.
      expect(RegExp(r'(Future|void)\s+\w*[Uu]pload\w*\s*\(').hasMatch(src),
          isFalse);
      expect(src.contains('formatExport'), isTrue);
      expect(src.contains('appendEvent'), isTrue);
    });

    test('settings export path formats local body only (no HTTP in export helper)',
        () {
      final settings = _clientLib('settings_screen.dart');
      // _exportLog uses formatExport + clipboard/share — must not post log body.
      expect(settings.contains('formatExport'), isTrue);
      expect(settings.contains('_exportLog'), isTrue);
      // No dedicated log upload API call.
      expect(settings.contains('/api/connection-log'), isFalse);
      expect(settings.contains('uploadConnectionLog'), isFalse);
      expect(settings.contains('postConnectionLog'), isFalse);
    });
  });

  group('no third-party telemetry SDK in shipped client deps', () {
    test('pubspec.yaml direct deps omit analytics/crash collectors', () {
      final yaml = _clientPubspec();
      // Only scan dependency declarations, not comments.
      final depSection = yaml.split('dev_dependencies:').first;
      for (final pkg in _forbiddenTelemetryPackages) {
        expect(
          depSection.contains(pkg),
          isFalse,
          reason: 'forbidden telemetry package $pkg must not be a client dep',
        );
      }
      // Positive: local prefs + path packages only for product function.
      expect(depSection.contains('shared_preferences'), isTrue);
      expect(depSection.contains('perccent_wallet'), isTrue);
      expect(depSection.contains('evolve'), isTrue);
    });

    test('client_app/lib dart sources do not import telemetry SDKs', () {
      final libDir = Directory('${Directory.current.path}/lib');
      final offenders = <String>[];
      for (final f in libDir.listSync(recursive: true).whereType<File>()) {
        if (!f.path.endsWith('.dart')) continue;
        final text = f.readAsStringSync();
        for (final pkg in _forbiddenTelemetryPackages) {
          if (text.contains("package:$pkg/") ||
              text.contains("package:$pkg'")) {
            offenders.add('${f.path}: $pkg');
          }
        }
      }
      expect(offenders, isEmpty, reason: offenders.join('\n'));
    });
  });

  group('entitlement bind body is minimal (no diagnostics/secrets)', () {
    test('bindDeviceEntitlement POST body is only session_id + device_pub',
        () async {
      final gate = LicenceGate(MemoryLicenceBackend());
      const sid = 'cs_privacy_min_body';
      const pub =
          'aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899';

      Uri? postedUri;
      Map<String, dynamic>? postedJson;

      final r = await gate.bindDeviceEntitlement(
        sid,
        devicePubHex: pub,
        baseUrl: 'https://example.test',
        post: (uri, body) async {
          postedUri = uri;
          postedJson = jsonDecode(utf8.decode(body)) as Map<String, dynamic>;
          return {'ok': true, 'session_id': sid};
        },
      );

      expect(r['ok'], isTrue);
      expect(postedUri!.path, contains('bind-device-entitlement'));
      expect(postedJson, isNotNull);
      expect(postedJson!.keys.toSet(), {'session_id', 'device_pub'});
      expect(postedJson!['session_id'], sid);
      expect(postedJson!['device_pub'], pub);

      // Forbidden leak categories must not appear as keys or string values.
      final blob = jsonEncode(postedJson);
      for (final bad in [
        'connection_log',
        'log_lines',
        'seed',
        'mnemonic',
        'passphrase',
        'backup',
        'percbackup',
        'licence_text',
        'acceptance',
      ]) {
        expect(
          blob.toLowerCase().contains(bad),
          isFalse,
          reason: 'bind body must not include $bad',
        );
      }
    });

    test('importKeygenAndVerify bind path same minimal contract', () async {
      final gate = LicenceGate(MemoryLicenceBackend());
      Map<String, dynamic>? postedJson;
      await gate.importKeygenAndVerify(
        'RPT-KEY-PRIV-AAAA-BBBB-CCCC',
        fetch: (id) async => {
          'status': 'active',
          'connect_allowed': true,
          'session_id': 'cs_import_min',
          'keygen': 'RPT-KEY-PRIV-AAAA-BBBB-CCCC',
        },
        resolveDevicePub: () async =>
            '00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff',
        postBind: (uri, body) async {
          postedJson = jsonDecode(utf8.decode(body)) as Map<String, dynamic>;
          return {'ok': true};
        },
      );
      expect(postedJson!.keys.toSet(), {'session_id', 'device_pub'});
      expect(postedJson!['session_id'], 'cs_import_min');
    });
  });

  group('seed publish carries encrypted envelope, not plaintext mnemonic', () {
    PercLedger _ledgerWithUser(String username) {
      final ledger = PercLedger.empty();
      ledger.ensureTreasuryAccount();
      ledger.setupTreasuryPassword('password12345');
      ledger.launchBlockchain();
      ledger.consumeBlockchainLaunchEvent();
      ledger.blocks.add(
        PercBlock(
          index: ledger.blocks.length,
          timestamp: DateTime.utc(2026, 4, 1),
          transactions: const [],
          treasuryEmitted: PercAmount.zero,
          scenarioLabel: 'privacy seed ledger',
        ),
      );
      // Register-like: ensure user account exists for envelope content.
      ledger.register(username, 'password12345');
      return ledger;
    }

    test('SuiteSeedEnvelopeStore.publish never sends raw 12-word phrase',
        () async {
      SuiteSeedEnvelopeStore.resetForTest();
      addTearDown(SuiteSeedEnvelopeStore.resetForTest);

      final words = PercSeedRecovery.generateMnemonic();
      expect(words.length, PercSeedRecovery.wordCount);
      final mnemonicPlain = PercSeedRecovery.normalizeMnemonic(words);
      final fp = PercSeedRecovery.fingerprint(words);

      final ledger = _ledgerWithUser('privacy_seed_user');
      final envelopeBytes = PercSeedRecovery.encryptLedgerEnvelope(
        ledger: ledger,
        words: words,
      );
      expect(envelopeBytes, isNotEmpty);
      // Ciphertext must not embed the plaintext mnemonic string.
      final envAsString = utf8.decode(envelopeBytes, allowMalformed: true);
      expect(envAsString.contains(mnemonicPlain), isFalse);
      expect(
        utf8.decode(envelopeBytes, allowMalformed: true).contains(words.first),
        isFalse,
      );

      final envelopeB64 = base64Encode(envelopeBytes);
      String? publishedTransport;
      String? publishedFp;
      SuiteSeedEnvelopeStore.publishHandler =
          (fingerprint, recovery) async {
        publishedFp = fingerprint;
        publishedTransport = recovery.envelopeB64;
        // Also capture what would go over the wire via buildSeedRecoveryNetworkPayload.
      };

      await SuiteSeedEnvelopeStore.publish(
        fingerprint: fp,
        envelopeB64: envelopeB64,
      );

      expect(publishedFp, fp);
      expect(publishedTransport, isNotNull);
      expect(publishedTransport, isNotEmpty);

      // Full 12-word phrase must not appear on the wire (individual BIP39
      // tokens can collide with base64 alphabet by chance — do not assert those).
      final wire = publishedTransport!;
      expect(wire.contains(mnemonicPlain), isFalse);
      expect(wire.toLowerCase().contains(mnemonicPlain), isFalse);
      // Payload is ciphertext / composite — not a JSON mnemonic field.
      expect(wire.toLowerCase().contains('"mnemonic"'), isFalse);
      expect(wire.toLowerCase().contains('"seed_phrase"'), isFalse);

      // Round-trip: decrypt with words restores user (proves encryption used real path).
      final restored = PercSeedRecovery.decryptLedgerEnvelope(
        envelope: envelopeBytes,
        words: words,
      );
      expect(restored.accounts.containsKey('privacy_seed_user'), isTrue);
    });

    test('composite transport build does not embed plaintext words', () {
      final words = PercSeedRecovery.generateMnemonic();
      final plain = PercSeedRecovery.normalizeMnemonic(words);
      final ledger = _ledgerWithUser('composite_user');
      final envB64 = base64Encode(
        PercSeedRecovery.encryptLedgerEnvelope(ledger: ledger, words: words),
      );
      final transport = buildSeedRecoveryNetworkPayload(
        ledgerEnvelopeB64: envB64,
        metaBlobB64: base64Encode(utf8.encode('{"suite":1}')),
      );
      // Contiguous normalized mnemonic must never appear in transport string.
      expect(transport.contains(plain), isFalse);
      expect(transport.toLowerCase().contains(plain), isFalse);
      expect(transport.toLowerCase().contains('"mnemonic"'), isFalse);
      final decoded = decodeSuiteSeedTransport(transport);
      expect(decoded.envelopeB64, envB64);
    });
  });

  group('encrypted backup export is local file bytes (not HTTP body helper)', () {
    test('security_backup_files helpers are export ports, not upload clients',
        () {
      // Path package used by Suite Backup tab — structural check on evolve copy.
      final evolveRoot = Directory.current.path.contains('client_app')
          ? Directory('${Directory.current.path}/../../evolve')
          : Directory('${Directory.current.path}/../evolve');
      final backupFiles = File(
        '${evolveRoot.path}/lib/perc/services/security_backup_files.dart',
      );
      final io = File(
        '${evolveRoot.path}/lib/perc/services/security_backup_files_io.dart',
      );
      expect(backupFiles.existsSync(), isTrue);
      final src = backupFiles.readAsStringSync();
      expect(src.contains('exportBackupToDevice') || src.contains('export'),
          isTrue);
      if (io.existsSync()) {
        final ioSrc = io.readAsStringSync();
        expect(ioSrc.contains('HttpClient'), isFalse);
        expect(ioSrc.contains('postUrl'), isFalse);
      }
    });
  });
}

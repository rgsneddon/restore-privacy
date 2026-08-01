/// App disk footprint and live process usage for Settings notifier.
///
/// Production probes use best-effort OS measurements; tests inject fakes.
library;

import 'dart:io';
import 'dart:math' as math;

/// Snapshot shown in Settings usage notifier.
class SuiteUsageSnapshot {
  const SuiteUsageSnapshot({
    required this.diskBytes,
    required this.processPercent,
  });

  /// Best-effort bytes used by the app install/data footprint.
  final int diskBytes;

  /// Running process resource use as a percentage (0–100 scale).
  final double processPercent;
}

/// Probe app on-disk footprint in bytes.
abstract class SuiteDiskUsageProbe {
  Future<int> measureDiskBytes();
}

/// Probe live process consumption as percent (CPU % preferred).
abstract class SuiteProcessUsageProbe {
  Future<double> measureProcessPercent();
}

/// Formats disk bytes for Settings (IEC-style KiB/MiB/GiB).
String formatSuiteDiskUsage(int bytes) {
  final b = bytes < 0 ? 0 : bytes;
  if (b < 1024) return '$b B';
  final kib = b / 1024;
  if (kib < 1024) return '${kib.toStringAsFixed(1)} KiB';
  final mib = kib / 1024;
  if (mib < 1024) return '${mib.toStringAsFixed(1)} MiB';
  final gib = mib / 1024;
  return '${gib.toStringAsFixed(2)} GiB';
}

/// Formats process percent for Settings (one decimal when needed).
String formatSuiteProcessPercent(double percent) {
  final p = percent.isNaN || percent.isInfinite
      ? 0.0
      : percent.clamp(0.0, 100.0);
  if ((p - p.roundToDouble()).abs() < 0.05) {
    return '${p.round()}%';
  }
  return '${p.toStringAsFixed(1)}%';
}

const String kSuiteUsageNotifierTitle = 'App usage';
const String kSuiteUsageDiskLabel = 'Disk space in use';
const String kSuiteUsageProcessLabel = 'Running process';
const String kSuiteUsageDiskKey = 'suite_usage_disk';
const String kSuiteUsageProcessKey = 'suite_usage_process';

/// Coordinates disk + process probes for Settings.
class SuiteUsageReporter {
  SuiteUsageReporter({
    SuiteDiskUsageProbe? disk,
    SuiteProcessUsageProbe? process,
  })  : diskProbe = disk ?? DefaultSuiteDiskUsageProbe(),
        processProbe = process ?? DefaultSuiteProcessUsageProbe();

  final SuiteDiskUsageProbe diskProbe;
  final SuiteProcessUsageProbe processProbe;

  Future<SuiteUsageSnapshot> measure() async {
    final disk = await diskProbe.measureDiskBytes();
    final proc = await processProbe.measureProcessPercent();
    return SuiteUsageSnapshot(
      diskBytes: disk < 0 ? 0 : disk,
      processPercent: proc.isNaN || proc.isInfinite
          ? 0.0
          : proc.clamp(0.0, 100.0),
    );
  }
}

/// Best-effort disk: sum of resolved executable tree + known home data dirs.
class DefaultSuiteDiskUsageProbe implements SuiteDiskUsageProbe {
  DefaultSuiteDiskUsageProbe({this.extraRoots});

  /// Optional extra roots (tests).
  final List<Directory>? extraRoots;

  @override
  Future<int> measureDiskBytes() async {
    var total = 0;
    final roots = <Directory>[
      ...?extraRoots,
    ];
    try {
      final exe = File(Platform.resolvedExecutable);
      final parent = exe.parent;
      if (parent.existsSync()) {
        roots.add(parent);
      }
    } catch (_) {}
    try {
      final home =
          Platform.environment['HOME'] ?? Platform.environment['USERPROFILE'];
      if (home != null && home.isNotEmpty) {
        for (final rel in const [
          'Library/Application Support/restore_privacy_client',
          'Library/Application Support/Restore Privacy',
          'Library/Containers/com.restoreprivacy.client',
          '.local/share/restore-privacy',
          'AppData/Local/RestorePrivacy',
          'AppData/Roaming/RestorePrivacy',
        ]) {
          final d = Directory('$home${Platform.pathSeparator}$rel');
          if (d.existsSync()) roots.add(d);
        }
      }
    } catch (_) {}

    final seen = <String>{};
    for (final root in roots) {
      final path = root.absolute.path;
      if (!seen.add(path)) continue;
      total += await _dirSize(root);
    }
    return total;
  }

  Future<int> _dirSize(Directory dir) async {
    var n = 0;
    try {
      if (!dir.existsSync()) return 0;
      await for (final ent in dir.list(recursive: true, followLinks: false)) {
        if (ent is File) {
          try {
            n += await ent.length();
          } catch (_) {}
        }
      }
    } catch (_) {}
    return n;
  }
}

/// Best-effort process CPU % via `ps` (desktop) or RSS-scaled fallback.
class DefaultSuiteProcessUsageProbe implements SuiteProcessUsageProbe {
  DefaultSuiteProcessUsageProbe({this.pidOverride});

  /// Override process id (tests).
  final int? pidOverride;

  @override
  Future<double> measureProcessPercent() async {
    final id = pidOverride ?? pid;
    try {
      if (Platform.isMacOS || Platform.isLinux) {
        final r = await Process.run('ps', ['-o', '%cpu=', '-p', '$id']);
        if (r.exitCode == 0) {
          final raw = (r.stdout as String? ?? '').trim();
          final v = double.tryParse(raw);
          if (v != null) {
            return v.clamp(0.0, 100.0);
          }
        }
      }
    } catch (_) {}
    // Fallback: RSS relative to a 2 GiB reference so the notifier is non-empty.
    try {
      final rss = ProcessInfo.currentRss;
      final scaled = (rss / (2 * 1024 * 1024 * 1024)) * 100.0;
      return math.min(100.0, math.max(0.0, scaled));
    } catch (_) {
      return 0.0;
    }
  }
}

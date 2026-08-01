/// Pure Node data clear timer math (matches website weekly fleet wipe cycle).
///
/// Period is **604800** seconds (7 days), aligned with the public homepage
/// ``Node data clear timer`` / ``ALL NODES DATA CLEARED IN`` clock.
library;

/// Weekly sequential fleet wipe period (seconds).
const int kNodeWipePeriodSeconds = 604800;

/// Settings / product heading (exact website wording).
const String kNodeWipeHeading = 'Node data clear timer';

/// Primary countdown label (exact casing/spacing).
const String kAllNodesDataClearedLabel = 'ALL NODES DATA CLEARED IN';

/// Honesty blurb: sequential wipe, hop best-effort, reconnection may be needed.
const String kNodeWipeHonestyBlurb =
    'About every week we wipe and rebuild residual nodes one at a time '
    '(IS then DE). Hop to another peer while one drains is best-effort '
    '(not guaranteed). If hop does not succeed, the client may disconnect or '
    'restart and will require manual reconnection whilst privacy-preserving '
    'weekly node wipedown occurs. This clock is that cycle.';

/// Whole seconds remaining until [deadline] (0 if overdue).
///
/// [now] defaults to UTC wall clock; inject for tests.
int remainingSecondsUntil(DateTime deadline, {DateTime? now}) {
  final n = (now ?? DateTime.now().toUtc()).toUtc();
  final d = deadline.isUtc ? deadline : deadline.toUtc();
  final delta = d.difference(n).inSeconds;
  return delta < 0 ? 0 : delta;
}

/// Split remaining [seconds] into days / hours / minutes / seconds.
Map<String, int> splitCountdownUnits(int seconds) {
  var total = seconds < 0 ? 0 : seconds;
  final days = total ~/ 86400;
  total %= 86400;
  final hours = total ~/ 3600;
  total %= 3600;
  final minutes = total ~/ 60;
  final secs = total % 60;
  return {
    'days': days,
    'hours': hours,
    'minutes': minutes,
    'seconds': secs,
  };
}

/// Compact display string (``D d HH:MM:SS`` or ``HH:MM:SS``).
String formatCountdown(int seconds) {
  final u = splitCountdownUnits(seconds);
  final d = u['days']!;
  final h = u['hours']!;
  final m = u['minutes']!;
  final s = u['seconds']!;
  final hh = h.toString().padLeft(2, '0');
  final mm = m.toString().padLeft(2, '0');
  final ss = s.toString().padLeft(2, '0');
  if (d > 0) return '${d}d $hh:$mm:$ss';
  return '$hh:$mm:$ss';
}

/// Next clear deadline on a fixed period grid (unix epoch aligned + optional phase).
///
/// When *now* lands exactly on a boundary, remaining is a full period (next cycle).
DateTime nextDeadlineOnGrid({
  DateTime? now,
  int periodSeconds = kNodeWipePeriodSeconds,
  int phaseSeconds = 0,
}) {
  final p = periodSeconds;
  if (p <= 0) {
    throw ArgumentError.value(p, 'periodSeconds', 'must be positive');
  }
  final n = (now ?? DateTime.now().toUtc()).toUtc();
  final phase = phaseSeconds % p;
  final epoch = n.millisecondsSinceEpoch ~/ 1000;
  final pos = (epoch - phase) % p;
  final wait = pos == 0 ? p : p - pos;
  return DateTime.fromMillisecondsSinceEpoch(
    (epoch + wait) * 1000,
    isUtc: true,
  );
}

/// Roll [lastClearAt] + period forward until strictly after [now].
DateTime nextClearFromLast(
  DateTime lastClearAt, {
  DateTime? now,
  int periodSeconds = kNodeWipePeriodSeconds,
}) {
  final n = (now ?? DateTime.now().toUtc()).toUtc();
  final p = Duration(seconds: periodSeconds);
  var last = lastClearAt.isUtc ? lastClearAt : lastClearAt.toUtc();
  var nxt = last.add(p);
  for (var i = 0; i < 10000; i++) {
    if (nxt.isAfter(n)) return nxt;
    nxt = nxt.add(p);
  }
  return nxt;
}

/// Snapshot of countdown state for UI / tests.
class NodeWipeCountdownState {
  const NodeWipeCountdownState({
    required this.deadline,
    required this.remainingSeconds,
    required this.units,
  });

  final DateTime deadline;
  final int remainingSeconds;
  final Map<String, int> units;

  factory NodeWipeCountdownState.compute({
    DateTime? now,
    DateTime? nextClearAt,
    DateTime? lastClearAt,
    int periodSeconds = kNodeWipePeriodSeconds,
  }) {
    final n = (now ?? DateTime.now().toUtc()).toUtc();
    DateTime deadline;
    if (nextClearAt != null) {
      deadline = nextClearAt.isUtc ? nextClearAt : nextClearAt.toUtc();
    } else if (lastClearAt != null) {
      deadline = nextClearFromLast(
        lastClearAt,
        now: n,
        periodSeconds: periodSeconds,
      );
    } else {
      deadline = nextDeadlineOnGrid(now: n, periodSeconds: periodSeconds);
    }
    final rem = remainingSecondsUntil(deadline, now: n);
    return NodeWipeCountdownState(
      deadline: deadline,
      remainingSeconds: rem,
      units: splitCountdownUnits(rem),
    );
  }
}

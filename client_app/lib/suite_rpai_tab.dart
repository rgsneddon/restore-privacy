import 'package:flutter/material.dart';

import 'theme.dart';

/// Ned — Restore Privacy Helper (rpAI) tab surface.
///
/// Adaptive learning begins *for the good of all humanity*. Narrative install
/// helper for rpOS (Clippy-class companion, affectionately **Ned**). Core design
/// load-balances across available **rpS** project servers and grows as nodes join
/// **and** as confirmed ChronoFlux blocks are sealed (honest counters / tiers).
class SuiteRpaiTab extends StatelessWidget {
  const SuiteRpaiTab({super.key, this.narrative, this.growthStats});

  /// Optional override narrative (tests).
  final String? narrative;

  /// Optional growth snapshot from `/api/ned-growth` or admin stats (tests + live).
  final Map<String, dynamic>? growthStats;

  static const String kNedName = 'Ned';
  static const String kRpaiLabel = 'rpAI';
  static const String kRpsLabel = 'rpS';
  static const String kMission =
      'Adaptive learning for the good of all humanity.';

  static const String kDefaultNarrative =
      'Hello — I\'m Ned, your Restore Privacy Helper. '
      'I guide Suite installs and the rpOS story with a calm narrative, '
      'like a privacy-first Clippy. My core runs across rpS '
      '(Restore Privacy Server computational power) and grows as project '
      'nodes come online and as ChronoFlux blocks are confirmed. '
      'Let\'s keep residual privacy human and kind.';

  /// Pure formatter for growth counters (unit-testable; no network).
  static String formatGrowthSummary(Map<String, dynamic>? stats) {
    if (stats == null || stats.isEmpty) {
      return 'Growth: waiting for ChronoFlux seals, node heartbeats, or Ned OOBE.';
    }
    final score = stats['growth_score'] ?? stats['growthScore'] ?? 0;
    final blocks =
        stats['chronoflux_blocks_grown'] ?? stats['chronofluxBlocksGrown'] ?? 0;
    final epochs = stats['learning_epochs'] ?? stats['learningEpochs'] ?? 0;
    final tier = stats['capability_tier'] ?? stats['capabilityTier'] ?? 0;
    final nodes = stats['nodes_online'] ?? stats['nodesOnline'] ?? 0;
    final narrative =
        stats['narrative_sessions'] ?? stats['narrativeSessions'] ?? 0;
    return 'Growth score $score · tier $tier · ChronoFlux blocks $blocks · '
        'epochs $epochs · nodes online $nodes · narrative sessions $narrative';
  }

  @override
  Widget build(BuildContext context) {
    final text = narrative ?? kDefaultNarrative;
    final growthLine = formatGrowthSummary(growthStats);
    return ColoredBox(
      color: kChromeBg,
      child: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 28),
          children: [
            Row(
              children: [
                Container(
                  width: 56,
                  height: 56,
                  decoration: BoxDecoration(
                    color: kPrimaryDark,
                    borderRadius: BorderRadius.circular(16),
                    boxShadow: [
                      BoxShadow(
                        color: kPrimary.withValues(alpha: 0.35),
                        blurRadius: 12,
                        offset: const Offset(0, 4),
                      ),
                    ],
                  ),
                  alignment: Alignment.center,
                  child: const Text(
                    'N',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 28,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Ned · Restore Privacy Helper',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w800,
                          color: kText,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        'rpAI · grows on ChronoFlux + nodes',
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: kTextMuted,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: kPanelBg,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: kBorder),
              ),
              child: Text(
                text,
                style: TextStyle(
                  fontSize: 14,
                  height: 1.45,
                  color: kText,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
            const SizedBox(height: 12),
            Text(
              kMission,
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w700,
                color: kPrimaryDark,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              growthLine,
              key: const Key('ned_growth_summary'),
              style: TextStyle(
                fontSize: 12,
                height: 1.4,
                fontWeight: FontWeight.w600,
                color: kText,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              'Load balance: available rpS servers · expands as residual/project '
              'nodes heartbeat. Confirmed ChronoFlux admin seals also raise '
              'growth score. Admin rpS page shows the same durable statistics.',
              style: TextStyle(fontSize: 12, height: 1.4, color: kTextMuted),
            ),
          ],
        ),
      ),
    );
  }
}

import 'package:flutter/material.dart';

import 'theme.dart';

/// Ned — Restore Privacy Helper (rpAI) tab surface.
///
/// Adaptive learning begins *for the good of all humanity*. Narrative install
/// helper for rpOS (Clippy-class companion, affectionately **Ned**). Core design
/// load-balances across available **rpS** project servers and grows as nodes join.
class SuiteRpaiTab extends StatelessWidget {
  const SuiteRpaiTab({super.key, this.narrative});

  /// Optional override narrative (tests).
  final String? narrative;

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
      'nodes come online. Let\'s keep residual privacy human and kind.';

  @override
  Widget build(BuildContext context) {
    final text = narrative ?? kDefaultNarrative;
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
                        'rpAI · begins adaptive learning',
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
              'Load balance: available rpS servers · expands as residual/project '
              'nodes are added. Admin rpS page shows growth statistics.',
              style: TextStyle(fontSize: 12, height: 1.4, color: kTextMuted),
            ),
          ],
        ),
      ),
    );
  }
}

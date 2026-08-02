import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'prefs_backend.dart';
import 'settings_store.dart';
import 'suite_account.dart';
import 'suite_account_apply.dart';
import 'suite_account_prompt.dart';
import 'suite_ned_guide.dart';
import 'suite_ned_icons.dart';
import 'theme.dart';

/// Ned — Restore Privacy Helper (rpAI) tab surface.
///
/// Adaptive learning narrative plus **scripted** help for deferred Suite
/// wallet/Evolve registration and stepped how-tos (wallet, Evolve, optional VPN).
class SuiteRpaiTab extends StatefulWidget {
  const SuiteRpaiTab({
    super.key,
    this.narrative,
    this.growthStats,
    this.accountStore,
    this.applyCredentials,
  });

  /// Optional override narrative (tests).
  final String? narrative;

  /// Optional growth snapshot from `/api/ned-growth` or admin stats (tests + live).
  final Map<String, dynamic>? growthStats;

  /// Injectable Suite account store (tests); production uses SharedPreferences.
  final SuiteAccountStore? accountStore;

  /// Injectable register/login apply (tests).
  final SuiteAccountAuthRunner? applyCredentials;

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
  State<SuiteRpaiTab> createState() => SuiteRpaiTabState();
}

/// Public state for tests that drive Ned controls.
class SuiteRpaiTabState extends State<SuiteRpaiTab> {
  SuiteAccountStore? _store;
  bool _loading = true;
  bool _registered = false;
  bool _deferred = false;
  NedGuideState _guide = const NedGuideState(
    phase: NedGuidePhase.menu,
    partIndex: 0,
    parts: [],
    lines: [],
  );
  var _busy = false;

  @override
  void initState() {
    super.initState();
    _boot();
  }

  Future<void> _boot() async {
    final store = widget.accountStore ?? await _defaultStore();
    final registered = await store.isRegistered();
    final deferred = await store.isDeferred();
    if (!mounted) return;
    setState(() {
      _store = store;
      _registered = registered;
      _deferred = deferred;
      _guide = nedGuideInitial(registered: registered, deferred: deferred);
      _loading = false;
    });
  }

  Future<SuiteAccountStore> _defaultStore() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return SuiteAccountStore(SharedPreferencesBackend(prefs));
    } catch (_) {
      return SuiteAccountStore(MemorySettingsBackend());
    }
  }

  void _setGuide(NedGuideState next) {
    setState(() => _guide = next);
  }

  Future<void> _onResumeSetup() async {
    _setGuide(nedGuideStartContinueSetup(_guide));
  }

  Future<void> _onYesContinueSetup() async {
    final store = _store;
    if (store == null || !mounted) return;
    _setGuide(nedGuideBeginRegistering(_guide));
    setState(() => _busy = true);
    // Same SharedPreferences backend as Suite account + licence keys when available.
    SettingsBackend? prefsBackend;
    try {
      final prefs = await SharedPreferences.getInstance();
      prefsBackend = SharedPreferencesBackend(prefs);
    } catch (_) {
      prefsBackend = MemorySettingsBackend();
    }
    if (!mounted) return;
    final outcome = await showSuiteAccountPrompt(
      context,
      store: store,
      applyCredentials: widget.applyCredentials,
      suitePrefsBackend: prefsBackend,
      licenceBackend: prefsBackend,
    );
    if (!mounted) return;
    setState(() => _busy = false);
    if (outcome == SuiteAccountPromptOutcome.registered ||
        outcome == SuiteAccountPromptOutcome.signedIn) {
      final u = await store.username() ?? 'you';
      setState(() {
        _registered = true;
        _deferred = false;
      });
      _setGuide(nedGuideAfterRegistered(_guide, username: u));
    } else if (outcome == SuiteAccountPromptOutcome.deferred ||
        outcome == SuiteAccountPromptOutcome.dismissed) {
      _setGuide(nedGuideDeclineSetup(_guide));
    }
  }

  void _onNoContinueSetup() {
    _setGuide(nedGuideDeclineSetup(_guide));
  }

  void _onOfferHowTo() {
    // Menu: show the how-to question first. askHowTo Yes: start typed parts.
    if (_guide.phase == NedGuidePhase.menu) {
      _setGuide(nedGuideStartHowToOfferFromMenu(_guide));
      return;
    }
    _setGuide(nedGuideStartHowTo(_guide));
  }

  void _onDeclineHowTo() {
    _setGuide(nedGuideDeclineHowTo(_guide));
  }

  void _onContinue() {
    _setGuide(nedGuideContinue(_guide));
  }

  void _onYesVpnTour() {
    _setGuide(nedGuideStartVpnTour(_guide));
  }

  void _onNoVpnTour() {
    _setGuide(nedGuideDeclineVpnTour(_guide));
  }

  @override
  Widget build(BuildContext context) {
    final text = widget.narrative ?? SuiteRpaiTab.kDefaultNarrative;
    final growthLine = SuiteRpaiTab.formatGrowthSummary(widget.growthStats);
    // Primary menu actions only while idle in menu (avoid stacking with Yes/No).
    final inMenu = !_loading && _guide.phase == NedGuidePhase.menu;
    final showResume = inMenu &&
        shouldShowNedResumeSetupLink(
          registered: _registered,
          deferred: _deferred,
        );
    final showHowToEntry = inMenu &&
        shouldShowNedHowToOffer(registered: _registered);

    return ColoredBox(
      color: suiteChromeBgOf(context),
      child: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 28),
          children: [
            Row(
              children: [
                // Imagine-derived Ned face chrome (default / CONFUSED / SLEEP /
                // EXCITED / ERROR) tracks real [NedGuidePhase] (+ busy).
                _NedIconAvatar(
                  key: const Key('ned_icon_avatar'),
                  stimulus: nedIconStimulusFor(
                    phase: _guide.phase,
                    busy: _busy || _loading,
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
                          color: suiteTextOf(context),
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        'rpAI · grows on ChronoFlux + nodes',
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: suiteTextMutedOf(context),
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        _stimulusCaption(
                          nedIconStimulusFor(
                            phase: _guide.phase,
                            busy: _busy || _loading,
                          ),
                        ),
                        key: const Key('ned_icon_stimulus_label'),
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          color: suitePrimaryOf(context),
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
                color: suitePanelBgOf(context),
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: suiteBorderOf(context)),
              ),
              child: Text(
                text,
                style: TextStyle(
                  fontSize: 14,
                  height: 1.45,
                  color: suiteTextOf(context),
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
            const SizedBox(height: 12),
            Text(
              SuiteRpaiTab.kMission,
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w700,
                color: suitePrimaryOf(context),
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
                color: suiteTextOf(context),
              ),
            ),
            const SizedBox(height: 6),
            Text(
              'Load balance: available rpS servers · expands as residual/project '
              'nodes heartbeat. Confirmed ChronoFlux admin seals also raise '
              'growth score. Admin rpS page shows the same durable statistics.',
              style: TextStyle(fontSize: 12, height: 1.4, color: suiteTextMutedOf(context)),
            ),
            if (_loading) ...[
              const SizedBox(height: 20),
              const Center(child: CircularProgressIndicator()),
            ] else ...[
              const SizedBox(height: 18),
              Text(
                'Ned says',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w800,
                  color: suitePrimaryOf(context),
                ),
              ),
              const SizedBox(height: 8),
              ..._guide.lines.map(
                (line) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: suitePanelBgOf(context),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: suiteBorderOf(context)),
                    ),
                    child: Text(
                      line,
                      style: TextStyle(
                        fontSize: 13,
                        height: 1.45,
                        color: suiteTextOf(context),
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ),
              ),
              if (showResume) ...[
                const SizedBox(height: 4),
                FilledButton(
                  key: const Key('ned_resume_setup'),
                  onPressed: _busy ? null : _onResumeSetup,
                  style: FilledButton.styleFrom(backgroundColor: suitePrimaryOf(context)),
                  child: Text(kNedResumeSetupLabel),
                ),
              ],
              if (showHowToEntry) ...[
                const SizedBox(height: 8),
                FilledButton(
                  key: const Key('ned_offer_howto'),
                  onPressed: _busy ? null : _onOfferHowTo,
                  style: FilledButton.styleFrom(backgroundColor: suitePrimaryOf(context)),
                  child: const Text(kNedOfferHowToLabel),
                ),
              ],
              if (nedGuideShowsContinueSetupChoices(_guide)) ...[
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: FilledButton(
                        key: const Key('ned_setup_yes'),
                        onPressed: _busy ? null : _onYesContinueSetup,
                        style:
                            FilledButton.styleFrom(backgroundColor: suitePrimaryOf(context)),
                        child: const Text(kNedYesLabel),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: OutlinedButton(
                        key: const Key('ned_setup_no'),
                        onPressed: _busy ? null : _onNoContinueSetup,
                        child: const Text(kNedNoLabel),
                      ),
                    ),
                  ],
                ),
              ],
              if (nedGuideShowsHowToChoices(_guide)) ...[
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: FilledButton(
                        key: const Key('ned_howto_yes'),
                        onPressed: _busy ? null : _onOfferHowTo,
                        style:
                            FilledButton.styleFrom(backgroundColor: suitePrimaryOf(context)),
                        child: const Text(kNedOfferHowToLabel),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: OutlinedButton(
                        key: const Key('ned_howto_no'),
                        onPressed: _busy ? null : _onDeclineHowTo,
                        child: const Text(kNedNoLabel),
                      ),
                    ),
                  ],
                ),
              ],
              if (nedGuideShowsContinue(_guide)) ...[
                const SizedBox(height: 8),
                FilledButton(
                  key: const Key('ned_continue'),
                  onPressed: _busy ? null : _onContinue,
                  style: FilledButton.styleFrom(backgroundColor: suitePrimaryOf(context)),
                  child: const Text(kNedContinueLabel),
                ),
              ],
              if (nedGuideShowsVpnTourChoices(_guide)) ...[
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: FilledButton(
                        key: const Key('ned_vpn_tour_yes'),
                        onPressed: _busy ? null : _onYesVpnTour,
                        style:
                            FilledButton.styleFrom(backgroundColor: suitePrimaryOf(context)),
                        child: const Text(kNedYesLabel),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: OutlinedButton(
                        key: const Key('ned_vpn_tour_no'),
                        onPressed: _busy ? null : _onNoVpnTour,
                        child: const Text(kNedNoLabel),
                      ),
                    ),
                  ],
                ),
              ],
            ],
          ],
        ),
      ),
    );
  }

  /// Short chrome caption under the title (tracks face stimulus, not a second script).
  static String _stimulusCaption(NedIconStimulus stimulus) {
    final status = nedFaceStatusLabel(stimulus);
    switch (stimulus) {
      case NedIconStimulus.idle:
        return 'STATUS: $status · at ease';
      case NedIconStimulus.asking:
        return 'STATUS: $status · your call';
      case NedIconStimulus.processing:
        return 'STATUS: $status · working…';
      case NedIconStimulus.explaining:
        return 'STATUS: $status · walking through…';
      case NedIconStimulus.ready:
        return 'STATUS: $status · done';
      case NedIconStimulus.error:
        return 'STATUS: $status';
    }
  }
}

/// Rounded Ned avatar that swaps Imagine icons with guide phase.
class _NedIconAvatar extends StatelessWidget {
  const _NedIconAvatar({
    super.key,
    required this.stimulus,
  });

  final NedIconStimulus stimulus;

  @override
  Widget build(BuildContext context) {
    final asset = nedIconAssetForStimulus(stimulus);
    return Container(
      key: Key('ned_icon_stimulus_${stimulus.name}'),
      width: 64,
      height: 64,
      decoration: BoxDecoration(
        color: const Color(0xFF0A1628),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: suitePrimaryOf(context).withValues(alpha: 0.55), width: 1.5),
        boxShadow: [
          BoxShadow(
            color: suitePrimaryOf(context).withValues(alpha: 0.4),
            blurRadius: 14,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      clipBehavior: Clip.antiAlias,
      child: Image.asset(
        asset,
        key: Key('ned_icon_asset_${stimulus.name}'),
        fit: BoxFit.cover,
        semanticLabel: nedIconSemanticsLabel(stimulus),
        errorBuilder: (_, __, ___) => Center(
          child: Text(
            'N',
            style: TextStyle(
              color: Colors.white.withValues(alpha: 0.9),
              fontSize: 28,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
      ),
    );
  }
}

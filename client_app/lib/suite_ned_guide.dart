/// Ned (rpAI) scripted helper: resume Suite account setup + stepped how-tos.
///
/// Pure state machine — unit-tested without widgets. VPN Connect never depends
/// on Suite account registration.
library;

/// What the rpAI tab should emphasize from Suite account flags.
enum NedAccountBranch {
  /// User deferred post-KEYGEN register — offer resume setup.
  resumeSetup,

  /// User already registered — offer how-to guides.
  offerHowTo,

  /// Neither deferred nor registered (e.g. never saw prompt) — still allow setup.
  offerSetup,
}

/// Interactive Ned script phase.
enum NedGuidePhase {
  /// Waiting for user to pick a primary action (resume / how-to).
  menu,

  /// Ned asked: continue setting up wallet + analyser?
  askContinueSetup,

  /// User is in unified register/login (handled by UI sheet).
  registering,

  /// Ned offered how-to for wallet/Evolve.
  askHowTo,

  /// Stepping through wallet then Evolve explainers.
  howtoParts,

  /// After how-to: offer VPN tour.
  askVpnTour,

  /// Stepping through VPN how-to.
  vpnTourParts,

  /// Script finished.
  done,
}

/// One typed Ned line (or multi-sentence part).
class NedGuidePart {
  const NedGuidePart({
    required this.id,
    required this.title,
    required this.body,
  });

  final String id;
  final String title;
  final String body;
}

/// Wallet section — brief parts.
const List<NedGuidePart> kNedWalletHowToParts = [
  NedGuidePart(
    id: 'wallet_1',
    title: '% wallet — what it is',
    body:
        'The % tab is Perccent wallet. It holds your on-device wallet identity '
        'for send/receive on the Chronoflux Principia chain. '
        'It is separate from residual VPN Connect.',
  ),
  NedGuidePart(
    id: 'wallet_2',
    title: '% wallet — sign-in',
    body:
        'If you registered once for Suite, the same username opens this wallet. '
        'You should not need a second full register only for %. '
        'Open % any time after Suite account setup.',
  ),
  NedGuidePart(
    id: 'wallet_3',
    title: '% wallet — everyday use',
    body:
        'After sign-in you can view balance, receive at your address, and send '
        'when the seed is reachable. Residual VPN can stay connected while you '
        'use the wallet — they are independent features.',
  ),
];

/// Evolve analyser — brief parts.
const List<NedGuidePart> kNedEvolveHowToParts = [
  NedGuidePart(
    id: 'evolve_1',
    title: 'EVOLVE — what it is',
    body:
        'The EVOLVE tab is the Evolve Chronoflux analyser. It runs scenario '
        'analysis and related tools using the same Suite account as the wallet '
        'when you completed unified registration.',
  ),
  NedGuidePart(
    id: 'evolve_2',
    title: 'EVOLVE — sign-in',
    body:
        'One Suite account covers both % and EVOLVE. If Ned helped you register, '
        'open EVOLVE and continue — you should not be forced through a second '
        'independent register wall for the same identity.',
  ),
  NedGuidePart(
    id: 'evolve_3',
    title: 'EVOLVE — everyday use',
    body:
        'Pick analysis modes, run scenarios, and review results in the Evolve '
        'shell. Network/seed reachability may affect some wallet-linked features, '
        'but residual VPN Connect still does not require Evolve registration.',
  ),
];

/// Full residual VPN how-to (typed tour).
const List<NedGuidePart> kNedVpnHowToParts = [
  NedGuidePart(
    id: 'vpn_1',
    title: 'VPN — licence first',
    body:
        'Residual protection starts on the VPN tab. Accept the end-user licence '
        'when prompted. Acceptance is stored only on this device.',
  ),
  NedGuidePart(
    id: 'vpn_2',
    title: 'VPN — KEYGEN unlock',
    body:
        'After payment, your fulfilment email includes a KEYGEN (RPT-KEY-…). '
        'Paste it in the unlock dialog. Download alone does not unlock Connect. '
        'Active entitlement is required.',
  ),
  NedGuidePart(
    id: 'vpn_3',
    title: 'VPN — Connect',
    body:
        'Press Connect on the VPN home when you want residual protection. '
        'On macOS, allow the Packet Tunnel profile under System Settings → '
        'Network → VPN if asked. Do not add L2TP/IKEv2 manually.',
  ),
  NedGuidePart(
    id: 'vpn_4',
    title: 'VPN — while connected',
    body:
        'When residual is up, traffic uses the privacy path. You can open %, '
        'EVOLVE, or rpAI without disconnecting. Disconnect returns traffic to '
        'your normal route.',
  ),
  NedGuidePart(
    id: 'vpn_5',
    title: 'VPN — Settings tips',
    body:
        'Settings hold privacy-scale options (traffic shape, multi-hop, IPv6) '
        'and entry country. Product residual IPv4 capture stays on. Autoconnect '
        'is optional and still requires licence + KEYGEN entitlement.',
  ),
];

/// Combined wallet + Evolve how-to in order.
List<NedGuidePart> nedWalletEvolveHowToParts() => [
      ...kNedWalletHowToParts,
      ...kNedEvolveHowToParts,
    ];

const String kNedAskContinueSetup =
    'Do you want to continue setting up the wallet and analyser?';
const String kNedAskHowTo =
    'You already have a Suite account. Offer how-to guides for % wallet and Evolve?';
const String kNedAskVpnTour =
    'Do you want a tour of the VPN now?';
const String kNedResumeSetupLabel = 'Continue wallet & analyser setup';
const String kNedOfferHowToLabel = 'Offer how-to';
const String kNedContinueLabel = 'Continue…';
const String kNedYesLabel = 'Yes';
const String kNedNoLabel = 'Not now';
const String kNedDoneLabel =
    'That is everything for now. Open VPN, %, or EVOLVE whenever you are ready.';

/// Pure branch from Suite account flags.
NedAccountBranch nedAccountBranch({
  required bool registered,
  required bool deferred,
}) {
  if (registered) return NedAccountBranch.offerHowTo;
  if (deferred) return NedAccountBranch.resumeSetup;
  return NedAccountBranch.offerSetup;
}

/// Whether rpAI shows the resume-setup control.
bool shouldShowNedResumeSetupLink({
  required bool registered,
  required bool deferred,
}) {
  return !registered;
}

/// Whether rpAI emphasizes how-to (registered users).
bool shouldShowNedHowToOffer({required bool registered}) {
  return registered;
}

/// Immutable Ned guide machine state.
class NedGuideState {
  const NedGuideState({
    required this.phase,
    required this.partIndex,
    required this.parts,
    required this.lines,
    this.lastPart,
  });

  final NedGuidePhase phase;

  /// Index into [parts] for howtoParts / vpnTourParts.
  final int partIndex;

  /// Active part list for the current explaining phase.
  final List<NedGuidePart> parts;

  /// Lines Ned has already "typed" (newest last).
  final List<String> lines;

  /// Last part fully shown (for UI title).
  final NedGuidePart? lastPart;

  bool get isExplaining =>
      phase == NedGuidePhase.howtoParts || phase == NedGuidePhase.vpnTourParts;

  bool get canContinue => isExplaining && partIndex < parts.length;

  bool get isDone => phase == NedGuidePhase.done;

  NedGuideState copyWith({
    NedGuidePhase? phase,
    int? partIndex,
    List<NedGuidePart>? parts,
    List<String>? lines,
    NedGuidePart? lastPart,
    bool clearLastPart = false,
  }) {
    return NedGuideState(
      phase: phase ?? this.phase,
      partIndex: partIndex ?? this.partIndex,
      parts: parts ?? this.parts,
      lines: lines ?? this.lines,
      lastPart: clearLastPart ? null : (lastPart ?? this.lastPart),
    );
  }
}

/// Initial menu state from account flags.
NedGuideState nedGuideInitial({
  required bool registered,
  required bool deferred,
}) {
  final branch = nedAccountBranch(registered: registered, deferred: deferred);
  final intro = switch (branch) {
    NedAccountBranch.resumeSetup =>
      'I see you put wallet & analyser setup aside. '
          'I can help you finish with one Suite account for both % and EVOLVE.',
    NedAccountBranch.offerHowTo =>
      'Welcome back — your Suite account is ready for % and EVOLVE. '
          'I can walk you through how each section works.',
    NedAccountBranch.offerSetup =>
      'I can help you set up one Suite account for Perccent wallet and Evolve, '
          'or you can keep using residual VPN only.',
  };
  return NedGuideState(
    phase: NedGuidePhase.menu,
    partIndex: 0,
    parts: const [],
    lines: [intro],
  );
}

NedGuideState nedGuideStartContinueSetup(NedGuideState s) {
  return s.copyWith(
    phase: NedGuidePhase.askContinueSetup,
    lines: [...s.lines, kNedAskContinueSetup],
  );
}

NedGuideState nedGuideDeclineSetup(NedGuideState s) {
  return s.copyWith(
    phase: NedGuidePhase.done,
    lines: [
      ...s.lines,
      'No problem. Residual VPN stays available with your KEYGEN. '
          'Open this rpAI tab anytime to continue setup later.',
      kNedDoneLabel,
    ],
  );
}

/// After user accepts setup — UI opens register sheet; script notes the path.
NedGuideState nedGuideBeginRegistering(NedGuideState s) {
  return s.copyWith(
    phase: NedGuidePhase.registering,
    lines: [
      ...s.lines,
      'Opening the unified Suite account form — one username for % wallet and Evolve.',
    ],
  );
}

NedGuideState nedGuideAfterRegistered(NedGuideState s, {required String username}) {
  return s.copyWith(
    phase: NedGuidePhase.askHowTo,
    lines: [
      ...s.lines,
      'Suite account ready for $username. % and EVOLVE share this identity.',
      kNedAskHowTo,
    ],
  );
}

NedGuideState nedGuideStartHowTo(NedGuideState s) {
  final parts = nedWalletEvolveHowToParts();
  final first = parts.first;
  return NedGuideState(
    phase: NedGuidePhase.howtoParts,
    partIndex: 1,
    parts: parts,
    lines: [
      ...s.lines,
      '${first.title}\n\n${first.body}',
    ],
    lastPart: first,
  );
}

NedGuideState nedGuideDeclineHowTo(NedGuideState s) {
  return s.copyWith(
    phase: NedGuidePhase.done,
    lines: [
      ...s.lines,
      'Alright — skip the guides for now. You can return to Ned anytime.',
      kNedDoneLabel,
    ],
  );
}

/// Advance one how-to or VPN part; transitions to askVpnTour / done as needed.
NedGuideState nedGuideContinue(NedGuideState s) {
  if (s.phase == NedGuidePhase.howtoParts) {
    if (s.partIndex >= s.parts.length) {
      return s.copyWith(
        phase: NedGuidePhase.askVpnTour,
        lines: [...s.lines, kNedAskVpnTour],
        clearLastPart: true,
      );
    }
    final part = s.parts[s.partIndex];
    final next = s.partIndex + 1;
    final after = NedGuideState(
      phase: NedGuidePhase.howtoParts,
      partIndex: next,
      parts: s.parts,
      lines: [...s.lines, '${part.title}\n\n${part.body}'],
      lastPart: part,
    );
    if (next >= s.parts.length) {
      return after.copyWith(
        phase: NedGuidePhase.askVpnTour,
        lines: [...after.lines, kNedAskVpnTour],
        clearLastPart: true,
      );
    }
    return after;
  }
  if (s.phase == NedGuidePhase.vpnTourParts) {
    if (s.partIndex >= s.parts.length) {
      return s.copyWith(
        phase: NedGuidePhase.done,
        lines: [...s.lines, kNedDoneLabel],
        clearLastPart: true,
      );
    }
    final part = s.parts[s.partIndex];
    final next = s.partIndex + 1;
    final after = NedGuideState(
      phase: NedGuidePhase.vpnTourParts,
      partIndex: next,
      parts: s.parts,
      lines: [...s.lines, '${part.title}\n\n${part.body}'],
      lastPart: part,
    );
    if (next >= s.parts.length) {
      return after.copyWith(
        phase: NedGuidePhase.done,
        lines: [...after.lines, kNedDoneLabel],
        clearLastPart: true,
      );
    }
    return after;
  }
  return s;
}

NedGuideState nedGuideStartVpnTour(NedGuideState s) {
  final parts = kNedVpnHowToParts;
  final first = parts.first;
  return NedGuideState(
    phase: NedGuidePhase.vpnTourParts,
    partIndex: 1,
    parts: parts,
    lines: [
      ...s.lines,
      '${first.title}\n\n${first.body}',
    ],
    lastPart: first,
  );
}

NedGuideState nedGuideDeclineVpnTour(NedGuideState s) {
  return s.copyWith(
    phase: NedGuidePhase.done,
    lines: [
      ...s.lines,
      'Skipping the VPN tour. Connect still works from the VPN tab with your KEYGEN.',
      kNedDoneLabel,
    ],
  );
}

/// From menu, stamp the how-to question into lines before starting parts.
NedGuideState nedGuideStartHowToOfferFromMenu(NedGuideState s) {
  if (s.phase != NedGuidePhase.menu && s.phase != NedGuidePhase.askHowTo) {
    return s;
  }
  if (s.phase == NedGuidePhase.askHowTo) return s;
  return s.copyWith(
    phase: NedGuidePhase.askHowTo,
    lines: [...s.lines, kNedAskHowTo],
  );
}

/// Whether the Continue… control should show.
bool nedGuideShowsContinue(NedGuideState s) => s.isExplaining;

/// Whether Yes/No for continue-setup should show.
bool nedGuideShowsContinueSetupChoices(NedGuideState s) =>
    s.phase == NedGuidePhase.askContinueSetup;

bool nedGuideShowsHowToChoices(NedGuideState s) =>
    s.phase == NedGuidePhase.askHowTo;

bool nedGuideShowsVpnTourChoices(NedGuideState s) =>
    s.phase == NedGuidePhase.askVpnTour;

/// Ned (rpAI) icon set + phase→stimulus mapping from the NED Core Package
/// Imagine sheet (chip / satellite / AI gear / package).
///
/// Pure helpers — unit-tested without widgets. Icons decorate the guide only;
/// they never gate Connect or replace [suite_ned_guide] transitions.
library;

import 'suite_ned_guide.dart';

/// Named visual stimulus for Ned chrome (maps 1:1 to a discrete asset).
enum NedIconStimulus {
  /// Menu / idle — NED Core Package (padlock module).
  idle,

  /// Ned is asking a yes/no or primary choice — satellite dish.
  asking,

  /// Register sheet / busy work — neon chip.
  processing,

  /// Typed how-to / VPN tour parts — AI gear.
  explaining,

  /// Script finished — package ready-to-deploy chrome.
  ready,
}

/// Asset paths packaged under [assets/ned/] (see pubspec).
const String kNedIconAssetPackage = 'assets/ned/ned_icon_package.png';
const String kNedIconAssetChip = 'assets/ned/ned_icon_chip.png';
const String kNedIconAssetSatellite = 'assets/ned/ned_icon_satellite.png';
const String kNedIconAssetGear = 'assets/ned/ned_icon_gear.png';

/// All shippable motif paths (order: package, chip, satellite, gear).
const List<String> kNedIconAssetPaths = [
  kNedIconAssetPackage,
  kNedIconAssetChip,
  kNedIconAssetSatellite,
  kNedIconAssetGear,
];

/// Map a stimulus to its asset path.
String nedIconAssetForStimulus(NedIconStimulus stimulus) {
  switch (stimulus) {
    case NedIconStimulus.idle:
    case NedIconStimulus.ready:
      return kNedIconAssetPackage;
    case NedIconStimulus.asking:
      return kNedIconAssetSatellite;
    case NedIconStimulus.processing:
      return kNedIconAssetChip;
    case NedIconStimulus.explaining:
      return kNedIconAssetGear;
  }
}

/// Pure phase (+ busy) → stimulus. Busy/registering wins over ask/explain so
/// the chip shows while the unified register sheet is open.
NedIconStimulus nedIconStimulusFor({
  required NedGuidePhase phase,
  bool busy = false,
}) {
  if (busy || phase == NedGuidePhase.registering) {
    return NedIconStimulus.processing;
  }
  switch (phase) {
    case NedGuidePhase.menu:
      return NedIconStimulus.idle;
    case NedGuidePhase.askContinueSetup:
    case NedGuidePhase.askHowTo:
    case NedGuidePhase.askVpnTour:
      return NedIconStimulus.asking;
    case NedGuidePhase.registering:
      return NedIconStimulus.processing;
    case NedGuidePhase.howtoParts:
    case NedGuidePhase.vpnTourParts:
      return NedIconStimulus.explaining;
    case NedGuidePhase.done:
      return NedIconStimulus.ready;
  }
}

/// Convenience: stimulus from a full [NedGuideState] + optional busy flag.
NedIconStimulus nedIconStimulusForState(
  NedGuideState state, {
  bool busy = false,
}) {
  return nedIconStimulusFor(phase: state.phase, busy: busy);
}

/// Asset path for a guide state (what the avatar should load).
String nedIconAssetForState(
  NedGuideState state, {
  bool busy = false,
}) {
  return nedIconAssetForStimulus(
    nedIconStimulusForState(state, busy: busy),
  );
}

/// Short accessibility / semantics label for the active stimulus.
String nedIconSemanticsLabel(NedIconStimulus stimulus) {
  switch (stimulus) {
    case NedIconStimulus.idle:
      return 'Ned idle — NED Core Package';
    case NedIconStimulus.asking:
      return 'Ned asking — satellite';
    case NedIconStimulus.processing:
      return 'Ned processing — chip';
    case NedIconStimulus.explaining:
      return 'Ned explaining — AI gear';
    case NedIconStimulus.ready:
      return 'Ned ready — package deployed';
  }
}

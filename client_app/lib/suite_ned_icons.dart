/// Ned (rpAI) face icon set + phase→stimulus mapping.
///
/// **Base / resting** face (Imagine resting post) is the idle menu state when
/// Ned is not enacting tasks. Task faces come from the Preview Gallery
/// (ERROR / EXCITED / CONFUSED / SLEEP).
///
/// Pure helpers — unit-tested without widgets. Faces decorate the guide only;
/// they never gate Connect or replace [suite_ned_guide] transitions.
library;

import 'suite_ned_guide.dart';

/// Named visual stimulus for Ned chrome (maps 1:1 to a discrete face asset).
enum NedIconStimulus {
  /// Menu / idle base — resting face (not enacting tasks).
  idle,

  /// Ned is asking a yes/no or primary choice — CONFUSED face.
  asking,

  /// Register sheet / busy work — SLEEP face ("working").
  processing,

  /// Typed how-to / VPN tour parts — EXCITED face.
  explaining,

  /// Script finished — EXCITED face (ready / success).
  ready,

  /// Real failure path only — ERROR face (never faked for normal declines).
  error,
}

/// Resting / at-ease base face (Imagine post 03888eba…) — idle menu avatar.
const String kNedFaceAssetResting = 'assets/ned/ned_face_resting.png';

/// Alias: default base path is the resting face (supersedes prior gallery smile).
const String kNedFaceAssetDefault = kNedFaceAssetResting;

const String kNedFaceAssetError = 'assets/ned/ned_face_error.png';
const String kNedFaceAssetExcited = 'assets/ned/ned_face_excited.png';
const String kNedFaceAssetConfused = 'assets/ned/ned_face_confused.png';
const String kNedFaceAssetSleep = 'assets/ned/ned_face_sleep.png';

/// All shippable face motifs (resting base + task gallery).
const List<String> kNedFaceAssetPaths = [
  kNedFaceAssetResting,
  kNedFaceAssetError,
  kNedFaceAssetExcited,
  kNedFaceAssetConfused,
  kNedFaceAssetSleep,
];

/// Alias: primary packaged Ned chrome paths are the face set.
const List<String> kNedIconAssetPaths = kNedFaceAssetPaths;

// Backward-compatible constants (older tests / secondary chrome).
const String kNedIconAssetPackage = kNedFaceAssetResting;
const String kNedIconAssetChip = kNedFaceAssetSleep;
const String kNedIconAssetSatellite = kNedFaceAssetConfused;
const String kNedIconAssetGear = kNedFaceAssetExcited;

/// Map a stimulus to its face asset path.
String nedIconAssetForStimulus(NedIconStimulus stimulus) {
  switch (stimulus) {
    case NedIconStimulus.idle:
      return kNedFaceAssetResting;
    case NedIconStimulus.asking:
      return kNedFaceAssetConfused;
    case NedIconStimulus.processing:
      return kNedFaceAssetSleep;
    case NedIconStimulus.explaining:
    case NedIconStimulus.ready:
      return kNedFaceAssetExcited;
    case NedIconStimulus.error:
      return kNedFaceAssetError;
  }
}

/// Pure phase (+ busy / error) → face stimulus.
///
/// Menu (not busy) → resting base. Busy/registering → SLEEP. Ask* → CONFUSED.
/// Explaining/done → EXCITED. ERROR only when [error] is true (real failure).
NedIconStimulus nedIconStimulusFor({
  required NedGuidePhase phase,
  bool busy = false,
  bool error = false,
}) {
  if (error) {
    return NedIconStimulus.error;
  }
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

/// Convenience: stimulus from a full [NedGuideState] + optional flags.
NedIconStimulus nedIconStimulusForState(
  NedGuideState state, {
  bool busy = false,
  bool error = false,
}) {
  return nedIconStimulusFor(phase: state.phase, busy: busy, error: error);
}

/// Asset path for a guide state (what the avatar should load).
String nedIconAssetForState(
  NedGuideState state, {
  bool busy = false,
  bool error = false,
}) {
  return nedIconAssetForStimulus(
    nedIconStimulusForState(state, busy: busy, error: error),
  );
}

/// Short accessibility / semantics label for the active face stimulus.
String nedIconSemanticsLabel(NedIconStimulus stimulus) {
  switch (stimulus) {
    case NedIconStimulus.idle:
      return 'Ned idle — resting face';
    case NedIconStimulus.asking:
      return 'Ned asking — confused face';
    case NedIconStimulus.processing:
      return 'Ned processing — sleep face';
    case NedIconStimulus.explaining:
      return 'Ned explaining — excited face';
    case NedIconStimulus.ready:
      return 'Ned ready — excited face';
    case NedIconStimulus.error:
      return 'Ned error — error face';
  }
}

/// Face status label for captions (resting base + Preview Gallery statuses).
String nedFaceStatusLabel(NedIconStimulus stimulus) {
  switch (stimulus) {
    case NedIconStimulus.idle:
      return 'RESTING';
    case NedIconStimulus.asking:
      return 'CONFUSED';
    case NedIconStimulus.processing:
      return 'SLEEP';
    case NedIconStimulus.explaining:
    case NedIconStimulus.ready:
      return 'EXCITED';
    case NedIconStimulus.error:
      return 'ERROR';
  }
}

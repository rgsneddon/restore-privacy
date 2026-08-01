import 'dart:async';

import 'package:flutter/material.dart';

import 'node_wipe_countdown.dart';
import 'theme.dart';

/// Stable markers for Settings Node data clear timer (tests + a11y).
const String kNodeWipeSettingsSectionKey = 'settings_node_wipe_timer';
const String kNodeWipeSettingsHeadingKey = 'settings_node_wipe_heading';
const String kNodeWipeSettingsLabelKey = 'settings_node_wipe_label';
const String kNodeWipeSettingsCountdownKey = 'settings_node_wipe_countdown';
const String kNodeWipeSettingsBlurbKey = 'settings_node_wipe_blurb';
const String kNodeWipeSettingsUnitDaysKey = 'settings_node_wipe_unit_days';
const String kNodeWipeSettingsUnitHoursKey = 'settings_node_wipe_unit_hours';
const String kNodeWipeSettingsUnitMinutesKey = 'settings_node_wipe_unit_minutes';
const String kNodeWipeSettingsUnitSecondsKey = 'settings_node_wipe_unit_seconds';

/// Read-only Settings panel: website-equivalent Node data clear timer.
///
/// Uses pure [NodeWipeCountdownState] math (7-day grid by default). Optional
/// [now] / [nextClearAt] inject clocks for tests; production ticks every second.
class NodeWipeTimerPanel extends StatefulWidget {
  const NodeWipeTimerPanel({
    super.key,
    this.now,
    this.nextClearAt,
    this.lastClearAt,
    this.periodSeconds = kNodeWipePeriodSeconds,
    this.tick = true,
  });

  /// Injected clock (tests). When null, uses wall UTC.
  final DateTime? now;

  /// Explicit next-clear deadline (optional).
  final DateTime? nextClearAt;

  /// Last clear anchor (optional; rolls forward by period).
  final DateTime? lastClearAt;

  final int periodSeconds;

  /// When true (default), refresh remaining time once per second.
  final bool tick;

  @override
  State<NodeWipeTimerPanel> createState() => _NodeWipeTimerPanelState();
}

class _NodeWipeTimerPanelState extends State<NodeWipeTimerPanel> {
  Timer? _timer;
  late NodeWipeCountdownState _state;

  @override
  void initState() {
    super.initState();
    _state = _compute();
    if (widget.tick) {
      _timer = Timer.periodic(const Duration(seconds: 1), (_) {
        if (!mounted) return;
        setState(() => _state = _compute());
      });
    }
  }

  @override
  void didUpdateWidget(covariant NodeWipeTimerPanel oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.now != widget.now ||
        oldWidget.nextClearAt != widget.nextClearAt ||
        oldWidget.lastClearAt != widget.lastClearAt ||
        oldWidget.periodSeconds != widget.periodSeconds) {
      _state = _compute();
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  NodeWipeCountdownState _compute() {
    return NodeWipeCountdownState.compute(
      now: widget.now,
      nextClearAt: widget.nextClearAt,
      lastClearAt: widget.lastClearAt,
      periodSeconds: widget.periodSeconds,
    );
  }

  @override
  Widget build(BuildContext context) {
    final u = _state.units;
    final days = u['days'] ?? 0;
    final hours = u['hours'] ?? 0;
    final minutes = u['minutes'] ?? 0;
    final seconds = u['seconds'] ?? 0;

    return Container(
      key: const Key(kNodeWipeSettingsSectionKey),
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: kPanelBg,
        borderRadius: BorderRadius.circular(kCornerRadius),
        border: Border.all(color: kBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            kNodeWipeHeading,
            key: const Key(kNodeWipeSettingsHeadingKey),
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: kPrimaryDark,
              fontSize: 16,
              fontWeight: FontWeight.w800,
              letterSpacing: 0.02,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            kAllNodesDataClearedLabel,
            key: const Key(kNodeWipeSettingsLabelKey),
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: kPrimary,
              fontSize: 12,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.04,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            key: const Key(kNodeWipeSettingsCountdownKey),
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              _UnitBox(
                key: const Key(kNodeWipeSettingsUnitDaysKey),
                value: days,
                label: 'DAYS',
              ),
              const SizedBox(width: 8),
              _UnitBox(
                key: const Key(kNodeWipeSettingsUnitHoursKey),
                value: hours,
                label: 'HRS',
              ),
              const SizedBox(width: 8),
              _UnitBox(
                key: const Key(kNodeWipeSettingsUnitMinutesKey),
                value: minutes,
                label: 'MIN',
              ),
              const SizedBox(width: 8),
              _UnitBox(
                key: const Key(kNodeWipeSettingsUnitSecondsKey),
                value: seconds,
                label: 'SEC',
              ),
            ],
          ),
          const SizedBox(height: 14),
          Text(
            kNodeWipeHonestyBlurb,
            key: const Key(kNodeWipeSettingsBlurbKey),
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: kTextMuted,
              fontSize: 12,
              height: 1.45,
            ),
          ),
        ],
      ),
    );
  }
}

class _UnitBox extends StatelessWidget {
  const _UnitBox({
    super.key,
    required this.value,
    required this.label,
  });

  final int value;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minWidth: 52),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
      decoration: BoxDecoration(
        color: kLightAccent,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: kBorder),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            value.toString().padLeft(2, '0'),
            style: const TextStyle(
              color: kText,
              fontSize: 18,
              fontWeight: FontWeight.w800,
              fontFeatures: [FontFeature.tabularFigures()],
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: const TextStyle(
              color: kTextMuted,
              fontSize: 10,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.06,
            ),
          ),
        ],
      ),
    );
  }
}

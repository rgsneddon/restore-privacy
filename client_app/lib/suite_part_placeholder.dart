/// Static reinstall surface when an optional Suite part is uninstalled.
library;

import 'package:flutter/material.dart';

import 'suite_parts.dart';
import 'theme.dart';

/// Tab body for an uninstalled optional section — reinstall control only.
class SuitePartReinstallPlaceholder extends StatelessWidget {
  const SuitePartReinstallPlaceholder({
    super.key,
    required this.partId,
    required this.onReinstall,
    this.busy = false,
  });

  final SuitePartId partId;
  final VoidCallback? onReinstall;
  final bool busy;

  @override
  Widget build(BuildContext context) {
    final label = suitePartLabel(partId);
    return ColoredBox(
      color: kChromeBg,
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                kSuitePartReinstallTitle,
                key: Key('suite_part_reinstall_title_${partId.name}'),
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                  color: kText,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                '“$label” is not active on this device.',
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: kTextMuted,
                ),
              ),
              const SizedBox(height: 12),
              Text(
                kSuitePartReinstallBody,
                key: Key('suite_part_reinstall_body_${partId.name}'),
                style: const TextStyle(
                  fontSize: 13,
                  height: 1.45,
                  color: kText,
                ),
              ),
              const SizedBox(height: 24),
              FilledButton(
                key: Key('suite_part_reinstall_btn_${partId.name}'),
                onPressed: busy ? null : onReinstall,
                style: FilledButton.styleFrom(backgroundColor: kPrimary),
                child: Text(kSuitePartReinstallLabel),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

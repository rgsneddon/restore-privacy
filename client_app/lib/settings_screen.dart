import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'settings_store.dart';
import 'theme.dart';

/// Settings surface: run-at-startup + autoconnect-on-launch switches.
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({
    super.key,
    required this.store,
    required this.initial,
    this.onChanged,
  });

  final SettingsStore store;
  final ProductSettings initial;
  final ValueChanged<ProductSettings>? onChanged;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  static const _channel = MethodChannel('restore_privacy/vpn');
  late ProductSettings _settings;
  bool _busy = false;
  String? _note;

  @override
  void initState() {
    super.initState();
    _settings = widget.initial;
  }

  Future<void> _setRunAtStartup(bool value) async {
    setState(() {
      _busy = true;
      _settings = _settings.copyWith(runAtStartup: value);
    });
    await widget.store.save(_settings);
    // Native registration (Android BOOT_COMPLETED / no-op if unsupported)
    try {
      final res = await _channel.invokeMethod<dynamic>('setRunAtStartup', {
        'enabled': value,
      });
      if (res is Map && res['ok'] == false) {
        _note = res['message']?.toString() ?? 'Could not update startup registration';
      } else {
        _note = value
            ? 'Run at startup enabled (best-effort; OEM battery rules may apply).'
            : 'Run at startup disabled.';
      }
    } on MissingPluginException {
      _note = value
          ? 'Run at startup saved (native registration unavailable on this build).'
          : 'Run at startup disabled.';
    } catch (e) {
      _note = 'Saved preference; startup registration: $e';
    }
    widget.onChanged?.call(_settings);
    if (mounted) setState(() => _busy = false);
  }

  Future<void> _setAutoconnect(bool value) async {
    setState(() {
      _busy = true;
      _settings = _settings.copyWith(autoconnectOnLaunch: value);
    });
    await widget.store.save(_settings);
    _note = value
        ? 'Autoconnect on launch enabled — next cold start will Connect.'
        : 'Autoconnect on launch disabled — Connect is manual.';
    widget.onChanged?.call(_settings);
    if (mounted) setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: kChromeBg,
      appBar: AppBar(
        backgroundColor: kPanelBg,
        foregroundColor: kText,
        elevation: 0,
        title: const Text('Settings'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Container(
            decoration: BoxDecoration(
              color: kPanelBg,
              borderRadius: BorderRadius.circular(kCornerRadius),
              border: Border.all(color: kBorder),
            ),
            child: Column(
              children: [
                SwitchListTile(
                  title: const Text(
                    'Run at device startup',
                    style: TextStyle(fontWeight: FontWeight.w600),
                  ),
                  subtitle: const Text(
                    'Start Privacy Restored when the device boots or you sign in',
                  ),
                  value: _settings.runAtStartup,
                  activeThumbColor: kWhite,
                  activeTrackColor: kPrimary,
                  onChanged: _busy ? null : _setRunAtStartup,
                ),
                const Divider(height: 1),
                SwitchListTile(
                  title: const Text(
                    'Autoconnect on launch',
                    style: TextStyle(fontWeight: FontWeight.w600),
                  ),
                  subtitle: const Text(
                    'When the app opens, start Connect automatically',
                  ),
                  value: _settings.autoconnectOnLaunch,
                  activeThumbColor: kWhite,
                  activeTrackColor: kPrimary,
                  onChanged: _busy ? null : _setAutoconnect,
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          Text(
            'Both options default to off. Seamless power-up needs both on '
            '(startup launches the app; autoconnect starts the VPN). '
            'OS VPN permission / Administrator may still be required.',
            style: TextStyle(color: kTextMuted, fontSize: 12),
          ),
          if (_note != null) ...[
            const SizedBox(height: 12),
            Text(_note!, style: const TextStyle(color: kPrimaryDark, fontSize: 12)),
          ],
        ],
      ),
    );
  }
}

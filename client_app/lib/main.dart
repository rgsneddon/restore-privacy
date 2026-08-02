import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import 'app_quit.dart';
import 'connect_status.dart';
import 'connection_log.dart';
import 'country_select.dart';
import 'easter_egg_server.dart';
import 'entry_access.dart';
import 'keygen_field.dart';
import 'licence_gate.dart';
import 'macos_window.dart';
import 'prefs_backend.dart';
import 'registration_copy.dart';
import 'rpt_config.dart';
import 'settings_screen.dart';
import 'settings_store.dart';
import 'suite_account.dart';
import 'suite_account_prompt.dart';
import 'suite_parts.dart';
import 'suite_parts_store.dart';
import 'suite_shell.dart';
import 'suite_update.dart';

import 'suite_version.dart';
import 'theme.dart';
import 'upgrade_banner.dart';
import 'vpn_controller.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.dark,
      systemNavigationBarColor: Colors.transparent,
      systemNavigationBarIconBrightness: Brightness.dark,
    ),
  );
  // Startup identity for operators / logs.
  // ignore: avoid_print
  print(kSuiteDisplayVersion);
  // Loopback loft (http://127.0.0.1:18765) — quiet easter egg while the app runs.
  startEasterEggServer();
  runApp(const RestorePrivacyApp());
}

class RestorePrivacyApp extends StatefulWidget {
  const RestorePrivacyApp({
    super.key,
    this.home,
    this.settingsStore,
    this.licenceGate,
    this.vpnController,
    this.onQuitExit,
    this.walletTab,
    this.evolveTab,
    this.rpaiTab,
    this.initialTabIndex = 0,
    this.entryInitiallyUnlocked,
    this.partsStore,
    this.initialParts,
  });

  /// Injectable full home override (tests); else gated [SuiteShell].
  final Widget? home;

  final SettingsStore? settingsStore;
  final LicenceGate? licenceGate;
  final VpnController? vpnController;
  final void Function()? onQuitExit;
  final Widget? walletTab;
  final Widget? evolveTab;
  final Widget? rpaiTab;
  final int initialTabIndex;

  /// When set, skips async entry unlock check (widget tests).
  final bool? entryInitiallyUnlocked;

  final SuitePartsStore? partsStore;
  final SuitePartsState? initialParts;

  @override
  State<RestorePrivacyApp> createState() => _RestorePrivacyAppState();
}

class _RestorePrivacyAppState extends State<RestorePrivacyApp> {
  final GlobalKey<SuiteShellState> _shellKey = GlobalKey<SuiteShellState>();
  late SuitePartsState _parts;
  /// True after durable prefs (or forced test snapshot) have been applied.
  var _partsReady = false;
  ThemeMode _themeMode = ThemeMode.dark;
  SettingsStore? _appearanceStore;

  @override
  void initState() {
    super.initState();
    // Bootstrap only; cold start loads SuitePartsStore inside SuiteShell unless
    // the test injects [initialParts] with preferInitialParts.
    _parts = widget.initialParts ?? SuitePartsState.allInstalled;
    _partsReady = widget.initialParts != null;
    _bootAppearance();
  }

  Future<void> _bootAppearance() async {
    try {
      final store = widget.settingsStore ??
          SettingsStore(await SharedPreferencesBackend.create());
      final s = await store.load();
      if (!mounted) return;
      setState(() {
        _appearanceStore = store;
        _themeMode = suiteThemeModeFromAppearance(s.appearance);
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _themeMode = ThemeMode.dark);
    }
  }

  void _onAppearanceChanged(ProductSettings next) {
    if (!mounted) return;
    setState(() {
      _themeMode = suiteThemeModeFromAppearance(next.appearance);
    });
  }

  void _onPartsChanged(SuitePartsState next) {
    if (!mounted) return;
    // Shell already applied the state; only sync parent fields (no re-entrant applyParts).
    if (_partsReady && _parts == next) return;
    setState(() {
      _parts = next;
      _partsReady = true;
    });
  }

  @override
  Widget build(BuildContext context) {
    final forceSnapshot = widget.initialParts != null;
    final shell = SuiteShell(
      key: _shellKey,
      initialTabIndex: widget.initialTabIndex,
      // Do not force allInstalled after boot — null lets shell load prefs.
      initialParts: forceSnapshot
          ? widget.initialParts
          : (_partsReady ? _parts : null),
      preferInitialParts: forceSnapshot,
      partsStore: widget.partsStore,
      onPartsChanged: _onPartsChanged,
      vpnTab: TunnelHome(
        settingsStore: widget.settingsStore ?? _appearanceStore,
        licenceGate: widget.licenceGate,
        vpnController: widget.vpnController,
        onQuitExit: widget.onQuitExit,
        partsStore: widget.partsStore,
        initialParts: _partsReady ? _parts : widget.initialParts,
        onPartsChanged: _onPartsChanged,
        onSettingsChanged: _onAppearanceChanged,
      ),
      walletTab: widget.walletTab,
      evolveTab: widget.evolveTab,
      rpaiTab: widget.rpaiTab,
    );
    return MaterialApp(
      title: kSuiteProductName,
      debugShowCheckedModeBanner: false,
      theme: buildSuiteThemeLight(),
      darkTheme: buildSuiteThemeDark(),
      themeMode: _themeMode,
      // All primary entry goes through licence unlock until entitled.
      home: widget.home ??
          AppEntryRoot(
            licenceGate: widget.licenceGate,
            initialUnlocked: widget.entryInitiallyUnlocked,
            child: shell,
          ),
    );
  }
}

/// Seamless product shell: hero status, Connect/Disconnect, Settings transparency.
///
/// Minimize / background does **not** stop the tunnel — only Disconnect or Quit
/// do. Quit (macOS/iOS main screen, bottom-right) stops the tunnel then exits.
/// Licence acceptance is required before Connect; autoconnect cannot bypass it.
class TunnelHome extends StatefulWidget {
  const TunnelHome({
    super.key,
    this.settingsStore,
    this.licenceGate,
    this.vpnController,
    this.onQuitExit,
    this.partsStore,
    this.initialParts,
    this.onPartsChanged,
    this.onSettingsChanged,
  });

  /// Injectable store for tests; production loads SharedPreferences.
  final SettingsStore? settingsStore;
  final LicenceGate? licenceGate;

  /// Injectable VPN controller (tests); production creates [VpnController].
  final VpnController? vpnController;

  /// Injectable process exit after tunnel stop (tests); production uses
  /// [exitAppProcess].
  final void Function()? onQuitExit;

  final SuitePartsStore? partsStore;
  final SuitePartsState? initialParts;
  final ValueChanged<SuitePartsState>? onPartsChanged;

  /// Notified when product settings change (e.g. appearance) so MaterialApp
  /// can switch Evolve light/dark theme without restart.
  final ValueChanged<ProductSettings>? onSettingsChanged;

  @override
  State<TunnelHome> createState() => _TunnelHomeState();
}

class _TunnelHomeState extends State<TunnelHome> with WidgetsBindingObserver {
  late final VpnController _vpn;
  final MacWindowController _macWindow = MacWindowController();
  SettingsStore? _store;
  LicenceGate? _licence;
  ProductSettings _settings = ProductSettings.defaults;
  ConnectionLog? _connectionLog;
  final List<String> _log = [];
  final ScrollController _logScroll = ScrollController();
  String _status = 'Not connected. Press Connect when you want protection.';
  String? _vpnIp;
  bool _connected = false;
  bool _busy = false;
  bool _autoconnectAttempted = false;
  bool _licenceAccepted = false;
  /// Sticky until product Connect succeeds so Open VPN settings survives open feedback.
  bool _needsVpnSystemSettingsApproval = false;
  /// Guards double presentation of the keygen sheet (licence Accept + launch race).
  bool _keygenSheetOpen = false;

  /// Bumps when residual push stores a pending package (Settings panel reloads).
  int _suiteUpdateReloadToken = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _vpn = widget.vpnController ?? VpnController(onStatus: _onStatus);
    // Residual "Push update to clients" → Suite pending package (Settings-gated).
    _vpn.onUpdatePush = _onResidualUpdatePush;
    _vpn.installUpdatePushHandler();
    // macOS menu bar tray → Flutter Disconnect / Show
    _macWindow.setHandlers(
      onTrayDisconnect: () {
        if (!_connected || _busy) return;
        _onToggle();
      },
      onTrayShow: () {
        // Native already deminiaturizes/orders the window front (RptTrayController).
        // Rehydrate connection UI only — never disconnect on show-from-tray.
        _rehydrateSession(from: 'tray_show');
      },
    );
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      await _initSettings();
      if (!mounted) return;
      _append(kSuiteDisplayVersion);
      _append(kAppTitle);
      _append(kPrivacyMessageText);
      _append(kSeamlessHint);
      _append('Version ${RptConfig.displayProductVersion}');
      await _rehydrateSession(from: 'launch');
      if (!_licenceAccepted) {
        await _showLicenceSheet();
      }
      // Single post-licence unlock entry (never from Accept button too — double sheet).
      await _promptPaymentUnlockIfNeeded();
      // macOS: register Packet Tunnel NE profile in OS VPN prefs before Connect
      // (not L2TP / Cisco IPsec / IKEv2 — those are manual System Settings types).
      await _prepareMacosPacketTunnelBeforeConnect();
      await _maybeAutoconnect();
    });
  }

  /// Renew (EXPIRED) or keygen unlock — at most one surface; re-entrant safe.
  Future<void> _promptPaymentUnlockIfNeeded() async {
    if (!mounted) return;
    final gate = _licence;
    if (gate == null) return;
    if (await gate.needsLicenceRenewal()) {
      await _showRenewLicenceSheet();
      return;
    }
    if (await gate.needsKeygenUnlock()) {
      await _showKeygenSheet();
    }
  }

  /// First-run / post-install style prep: save product Packet Tunnel to OS prefs.
  Future<void> _prepareMacosPacketTunnelBeforeConnect() async {
    if (!MacWindowController.isSupported) return;
    if (!mounted) return;
    _append(
      'Preparing system VPN profile (Restore Privacy Packet Tunnel)…',
    );
    final ok = await _vpn.preparePacketTunnelConfiguration();
    if (!mounted) return;
    if (ok) {
      _append(
        'Packet Tunnel configuration ready — Allow if macOS asks, then Connect. '
        'Do not add L2TP, Cisco IPsec, or IKEv2.',
      );
      // Prefer prepared guidance on the card when still disconnected.
      if (!_connected &&
          (_status.toLowerCase().contains('ready') ||
              _status.toLowerCase().contains('press connect') ||
              _status.toLowerCase().contains('not connected'))) {
        setState(() {
          _status = kPacketTunnelPreparedMessage;
        });
      }
    } else if (isNeVpnPermissionFailureMessage(_status) ||
        shouldPromptOpenVpnSystemSettings({
          'ok': false,
          'message': _status,
          'fullTunnelActive': false,
        })) {
      setState(() => _needsVpnSystemSettingsApproval = true);
      _append(
        'Allow Restore Privacy under System Settings → Network → VPN & Filters '
        '(Packet Tunnel), then Connect. Do not choose L2TP / IKEv2 manually.',
      );
    }
  }

  Future<void> _initSettings() async {
    if (widget.settingsStore != null) {
      _store = widget.settingsStore;
    } else {
      try {
        final backend = await SharedPreferencesBackend.create();
        _store = SettingsStore(backend);
      } catch (_) {
        _store = SettingsStore(MemorySettingsBackend());
      }
    }
    if (widget.licenceGate != null) {
      _licence = widget.licenceGate;
    } else {
      try {
        final prefs = await SharedPreferences.getInstance();
        _licence = LicenceGate(
          PrefsLicenceBackend(
            (k) async => prefs.getBool(k),
            (k, v) async {
              await prefs.setBool(k, v);
            },
            (k) async => prefs.getString(k),
            (k, v) async {
              await prefs.setString(k, v);
            },
          ),
        );
      } catch (_) {
        _licence = LicenceGate(MemoryLicenceBackend());
      }
    }
    try {
      final prefs = await SharedPreferences.getInstance();
      _connectionLog = ConnectionLog(
        PrefsConnectionLogBackend(prefs),
        clientVersion: RptConfig.displayProductVersion,
        platformLabel: connectionLogPlatformLabel(),
      );
    } catch (_) {
      _connectionLog = ConnectionLog(
        MemoryConnectionLogBackend(),
        clientVersion: RptConfig.displayProductVersion,
        platformLabel: connectionLogPlatformLabel(),
      );
    }
    final loaded = await _store!.load();
    _vpn.settingsForUpdatePush = loaded;
    RptConfig.setRuntimeMultiHop(loaded.privacyMultihop);
    RptConfig.setRuntimeEntryCountry(loaded.entryCountry);
    // Push Flutter Settings into native App Group so Packet Tunnel / Connect
    // honesty match product switches (cannot desync after cold start).
    await _vpn.syncProductSettingsToNative(
      residualIpv4: kResidualIpv4AlwaysOn,
      residualIpv6: loaded.residualIpv6,
      privacyTrafficShape: loaded.privacyTrafficShape,
      privacyOuterObfuscation: loaded.privacyOuterObfuscation,
      privacyMultihop: loaded.privacyMultihop,
    );
    if (mounted) {
      setState(() => _settings = loaded);
    } else {
      _settings = loaded;
    }
    widget.onSettingsChanged?.call(loaded);
    // Refresh payment if we already have a session id (post-pay recheck)
    final sid = await _licence!.paymentSessionId();
    if (sid.isNotEmpty) {
      try {
        await _licence!.refreshEntitlementFromRemote();
      } catch (_) {}
    }
    final licOk = await _licence!.hasAcceptedLicence();
    final canConnect = await _licence!.mayConnect();
    if (!mounted) return;
    setState(() {
      _settings = loaded;
      _licenceAccepted = licOk;
      if (!canConnect) {
        _status = licOk
            ? 'Enter keygen from your fulfilment email (unlock dialog), then Connect.'
            : 'Accept the licence, enter keygen, then Connect for residual protection.';
      } else {
        _status =
            'Ready. Press Connect when you want residual protection.';
      }
    });
  }

  Future<void> _connLog(String kind, String message) async {
    try {
      await _connectionLog?.appendEvent(kind, message);
    } catch (_) {}
  }

  Future<void> _showLicenceSheet() async {
    if (!mounted) return;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: suitePanelBgOf(context),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) {
        return Padding(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 28),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                kLicencePromptTitle,
                style: TextStyle(
                  color: suitePrimaryOf(context),
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 10),
              Text(kShortLicenceSummary, style: TextStyle(fontSize: 13)),
              const SizedBox(height: 10),
              Text(
                kAnonRegistrationSummary,
                style: TextStyle(fontSize: 12, color: suiteTextMutedOf(context)),
              ),
              const SizedBox(height: 6),
              Text(
                kOsPrivilegeHonesty,
                style: TextStyle(fontSize: 12, color: suiteTextMutedOf(context)),
              ),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: () async {
                  await _licence?.acceptLicence();
                  if (!mounted) return;
                  setState(() {
                    _licenceAccepted = true;
                    _status =
                        'Licence accepted. Enter your keygen from the fulfilment email to unlock Connect.';
                  });
                  _append('Licence accepted (stored locally only).');
                  // Pop only — do not open keygen here. Caller (launch /
                  // assertMayConnect) runs _promptPaymentUnlockIfNeeded once
                  // after this sheet returns so we never stack two keygen sheets.
                  Navigator.of(ctx).pop();
                },
                style: FilledButton.styleFrom(backgroundColor: suitePrimaryOf(context)),
                child: Text(kLicenceAcceptButton),
              ),
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(),
                child: const Text('Not now'),
              ),
            ],
          ),
        );
      },
    );
  }

  /// EXPIRED hard-lock: renew your licence *here* + platform payment portal.
  Future<void> _showRenewLicenceSheet() async {
    if (!mounted) return;
    final gate = _licence;
    final url = await gate?.renewPortalUrlForInstall() ??
        renewLicenceUrl(platform: platformForRenew());
    final body = await gate?.renewMessageForInstall() ??
        renewLicenceMessage(platform: platformForRenew(), renewUrl: url);
    if (!mounted) return;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: suitePanelBgOf(context),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) {
        return Padding(
          padding: EdgeInsets.fromLTRB(
            20,
            16,
            20,
            28 + MediaQuery.of(ctx).viewInsets.bottom,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                kRenewLicencePromptTitle,
                style: TextStyle(
                  color: suitePrimaryOf(context),
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 10),
              Text(
                'Your subscription is EXPIRED. Renew your licence *here*:',
                style: TextStyle(fontSize: 14),
              ),
              const SizedBox(height: 10),
              SelectableText(
                url,
                style: TextStyle(fontSize: 13, color: suitePrimaryOf(context),
                  decoration: TextDecoration.underline,
                ),
              ),
              const SizedBox(height: 12),
              Text(
                body,
                style: TextStyle(fontSize: 12, color: suiteTextMutedOf(context)),
              ),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: () async {
                  final uri = Uri.tryParse(url);
                  if (uri != null) {
                    try {
                      await launchUrl(
                        uri,
                        mode: LaunchMode.externalApplication,
                      );
                    } catch (_) {
                      _append('Could not open browser. Visit: $url');
                    }
                  }
                },
                style: FilledButton.styleFrom(backgroundColor: suitePrimaryOf(context)),
                child: const Text('Open payment portal'),
              ),
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(),
                child: const Text('Close'),
              ),
            ],
          ),
        );
      },
    );
  }

  /// Forced keygen unlock surface (parity with Windows/Linux desktop modals).
  ///
  /// On **valid** keygen the sheet is fully dismissed (returns) **before** any
  /// Packet Tunnel prepare / System Settings Allow path runs — so Network
  /// Settings never opens on top of a stuck keygen window.
  ///
  /// Navigator pairing: sheet uses [useRootNavigator] true and must be popped
  /// with the **same** navigator (root). Popping root while the sheet is on a
  /// nested navigator leaves the keygen window stuck open.
  Future<void> _showKeygenSheet() async {
    // EXPIRED installs must renew — never show keygen in place of renew.
    final bool needsRenew = _licence != null &&
        await _licence!.needsLicenceRenewal();
    if (needsRenew) {
      await _showRenewLicenceSheet();
      return;
    }
    final bool needs = _licence == null
        ? false
        : await _licence!.needsKeygenUnlock();
    if (!shouldPresentKeygenUnlockSheet(
      needsKeygenUnlock: needs,
      keygenSheetAlreadyOpen: _keygenSheetOpen,
    )) {
      return;
    }
    if (!mounted) return;
    _keygenSheetOpen = true;
    final controller = TextEditingController();
    // true = use root navigator for push AND pop (must match).
    const useRoot = true;
    bool unlocked = false;
    try {
      unlocked = await showModalBottomSheet<bool>(
            context: context,
            isScrollControlled: true,
            isDismissible: false,
            enableDrag: false,
            useRootNavigator: useRoot,
            backgroundColor: suitePanelBgOf(context),
            shape: const RoundedRectangleBorder(
              borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
            ),
            builder: (sheetContext) {
              var statusLine = '';
              var busy = false;
              return StatefulBuilder(
                builder: (ctx, setModal) {
                  Future<void> tryUnlock() async {
                    if (busy) return;
                    final raw = controller.text.trim();
                    if (raw.isEmpty) {
                      setModal(() => statusLine = 'Paste the keygen first.');
                      return;
                    }
                    setModal(() {
                      busy = true;
                      statusLine = 'Verifying keygen with status host…';
                    });
                    final st = await _licence?.importKeygenAndVerify(raw) ??
                        kPaymentStatusUnknown;
                    final ok = await _licence?.paymentAllowsConnect() ?? false;
                    // Dismiss only on valid unlock (shipped contract).
                    if (!shouldDismissKeygenSheetAfterUnlock(
                      paymentAllowsConnect: ok,
                      paymentStatus: st,
                    )) {
                      if (ctx.mounted) {
                        setModal(() {
                          busy = false;
                          statusLine =
                              'Keygen not active (status=$st). Check email code / subscription.';
                        });
                      }
                      return;
                    }
                    // Valid key: pop the **same** navigator that owns this sheet.
                    if (sheetContext.mounted) {
                      Navigator.of(sheetContext, rootNavigator: useRoot)
                          .pop(true);
                    } else if (ctx.mounted) {
                      Navigator.of(ctx, rootNavigator: useRoot).pop(true);
                    }
                  }

                  return Padding(
                    padding: EdgeInsets.fromLTRB(
                      20,
                      16,
                      20,
                      28 + MediaQuery.of(ctx).viewInsets.bottom,
                    ),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text(
                          kKeygenPromptTitle,
                          style: TextStyle(
                            color: suitePrimaryOf(context),
                            fontSize: 18,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        const SizedBox(height: 10),
                        Text(
                          kKeygenPromptBody,
                          style: TextStyle(fontSize: 13),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          kConnectBlockedKeygenMsg,
                          style: TextStyle(fontSize: 12, color: suiteTextMutedOf(context)),
                        ),
                        const SizedBox(height: 12),
                        KeygenEntryField(
                          controller: controller,
                          autofocus: true,
                          labelText: 'RPT-KEY-…',
                          enabled: !busy,
                          // Paste of a full product keygen → verify + dismiss automatically.
                          onPasted: (text) {
                            if (looksLikeProductKeygen(text)) {
                              tryUnlock();
                            }
                          },
                          onChanged: (text) {
                            // Enter / submit on field also unlocks when it looks complete.
                            if (looksLikeProductKeygen(text) &&
                                text.trim().endsWith('\n')) {
                              tryUnlock();
                            }
                          },
                        ),
                        if (statusLine.isNotEmpty) ...[
                          const SizedBox(height: 8),
                          Text(statusLine, style: TextStyle(fontSize: 12)),
                        ],
                        const SizedBox(height: 16),
                        FilledButton(
                          onPressed: busy ? null : tryUnlock,
                          style:
                              FilledButton.styleFrom(backgroundColor: suitePrimaryOf(context)),
                          child: Text(busy ? 'Verifying…' : 'Unlock Connect'),
                        ),
                        TextButton(
                          onPressed: busy
                              ? null
                              : () {
                                  Navigator.of(
                                    sheetContext,
                                    rootNavigator: useRoot,
                                  ).pop(false);
                                },
                          child: const Text('Cancel'),
                        ),
                      ],
                    ),
                  );
                },
              );
            },
          ) ??
          false;
    } finally {
      controller.dispose();
      _keygenSheetOpen = false;
    }
    if (!mounted) return;
    if (unlocked == true) {
      // Belt: if entitlement still reads unlock-required, do not re-open.
      setState(() {
        _status =
            'Keygen verified. Press Connect for residual protection.';
      });
      _append('Keygen unlocked.');
      // Sheet is fully closed — safe to register Packet Tunnel / open Settings.
      await _prepareMacosPacketTunnelBeforeConnect();
      // Optional: one Suite account for % wallet + Evolve (VPN already unlocked).
      await _maybeShowSuiteAccountPrompt();
    }
  }

  /// Post-KEYGEN optional register/login for Perccent + Evolve (single prompt).
  ///
  /// Dismissible; never required for [LicenceGate.mayConnect] / residual VPN.
  Future<void> _maybeShowSuiteAccountPrompt() async {
    final store = _store;
    final gate = _licence;
    if (store == null || gate == null || !mounted) return;
    final may = await gate.mayConnect();
    final account = SuiteAccountStore(store.backend);
    final deferred = await account.isDeferred();
    final registered = await account.isRegistered();
    if (!shouldOfferSuiteAccountPrompt(
      vpnUnlocked: may,
      deferred: deferred,
      registered: registered,
    )) {
      return;
    }
    if (!mounted) return;
    final outcome = await showSuiteAccountPrompt(
      context,
      store: account,
    );
    if (!mounted) return;
    switch (outcome) {
      case SuiteAccountPromptOutcome.deferred:
        _append('Suite account deferred — VPN remains available.');
        setState(() {
          _status =
              'Keygen verified. Press Connect anytime. Register for % / Evolve later from those tabs.';
        });
      case SuiteAccountPromptOutcome.registered:
        _append('Suite account created for % wallet and Evolve.');
        setState(() {
          _status =
              'Keygen verified and Suite account ready for % and Evolve. Press Connect for residual VPN.';
        });
      case SuiteAccountPromptOutcome.signedIn:
        _append('Suite account signed in for % wallet and Evolve.');
        setState(() {
          _status =
              'Keygen verified and Suite account signed in. Press Connect for residual VPN.';
        });
      case SuiteAccountPromptOutcome.dismissed:
        // Treated like defer so we do not re-prompt every Connect.
        await account.markDeferred();
        _append('Suite account prompt dismissed — VPN remains available.');
    }
  }

  Future<bool> assertMayConnect() async {
    final gate = _licence;
    if (gate == null) return false;
    // Refreshes remote payment entitlement so refunds cancel Connect.
    final r = await gate.assertMayConnect(refreshPayment: true);
    if (r.ok) return true;
    _append(r.message);
    setState(() => _status = r.message);
    final licOk = await gate.hasAcceptedLicence();
    if (!licOk) {
      await _showLicenceSheet();
    }
    // One renew/keygen prompt after licence sheet (no double keygen from Accept).
    await _promptPaymentUnlockIfNeeded();
    final r2 = await gate.assertMayConnect(refreshPayment: false);
    if (!r2.ok && mounted) {
      setState(() => _status = r2.message);
    }
    return r2.ok;
  }

  Future<void> _maybeAutoconnect() async {
    if (_autoconnectAttempted) return;
    _autoconnectAttempted = true;
    final store = _store;
    if (store == null) return;
    final s = await store.load();
    if (!store.shouldAutoconnectOnLaunch(s)) return;
    if (_connected || _busy) return;
    // Never bypass licence on autoconnect.
    if (!await assertMayConnect()) {
      _append('Settings: autoconnect skipped — accept the end-user licence first.');
      return;
    }
    _append('Settings: autoconnect on launch — starting Connect…');
    await _onToggleConnectOnly();
  }

  Future<void> _onToggleConnectOnly() async {
    // Connect path only (used by autoconnect)
    if (_busy || _connected) return;
    // Gate: valid catalog entry country (empty → Germany/DE default).
    final resolved = resolveEntryCountrySelection(
      _settings.entryCountry,
      allowDefault: true,
    );
    if (!resolved.ok ||
        !entryCountryAllowsConnect(resolved.code, allowDefault: false)) {
      final msg =
          'Choose a valid entry country above Connect (Germany is the default).';
      _append(msg);
      setState(() {
        _status = msg;
        _settings = _settings.copyWith(entryCountry: kDefaultEntryCountry);
      });
      RptConfig.setRuntimeEntryCountry(kDefaultEntryCountry);
      await _store?.save(_settings);
      return;
    }
    RptConfig.setRuntimeEntryCountry(resolved.code);
    RptConfig.setRuntimeMultiHop(_settings.privacyMultihop);
    if (!await assertMayConnect()) return;
    setState(() => _busy = true);
    try {
      _append(
        'Connect — entry ${countryOptionForCode(resolved.code)?.label ?? resolved.code}…',
      );
      await _connLog(kLogKindConnect, 'Connect started (RPT full tunnel)');
      _vpn.settingsForUpdatePush = _settings;
      final ok = await _vpn.connect(
        residualIpv4: kResidualIpv4AlwaysOn,
        residualIpv6: _settings.residualIpv6,
        privacyTrafficShape: _settings.privacyTrafficShape,
        privacyOuterObfuscation: _settings.privacyOuterObfuscation,
        privacyMultihop: _settings.privacyMultihop,
      );
      if (!mounted) return;
      if (ok) {
        // Residual push may have delivered a Suite package while HELLO ran.
        await _pollSuiteUpdatePush();
      }
      if (!mounted) return;
      setState(() {
        _connected = ok;
        if (ok) {
          _needsVpnSystemSettingsApproval = false;
          final ipMatch = RegExp(r'10\.\d+\.\d+\.\d+').firstMatch(_status);
          if (ipMatch != null) _vpnIp = ipMatch.group(0);
          // Dual-stack honesty: keep native message or rebuild from Settings
          // residual IPv4+IPv6 (never IPv6-only overwrite).
          _status = resolveConnectedStatusAfterSuccess(
            nativeStatus: _status,
            vpnIp: _vpnIp,
            residualIpv4: kResidualIpv4AlwaysOn,
            residualIpv6: _settings.residualIpv6,
          );
        } else if (isNeVpnPermissionFailureMessage(_status) ||
            shouldPromptOpenVpnSystemSettings({
              'ok': false,
              'message': _status,
              'fullTunnelActive': false,
            })) {
          // Sticky so Open VPN settings remains after log-only open feedback.
          _needsVpnSystemSettingsApproval = true;
        }
      });
      if (ok) {
        _append(_status);
        await _connLog(kLogKindConnect, 'Connected — residual path active');
        // Keep main window open after Connect (no auto hide-to-tray / minimize).
        // Tray icon may still update for status; user can hide manually via close→tray.
        if (MacWindowController.isSupported) {
          await _macWindow.setTrayConnected(true);
        }
        if (shouldHideToTrayAfterConnectSuccess(ok)) {
          // Policy helper is false: window stays open. Call site kept for tests/docs.
          await _macWindow.hideToTray(connected: true);
          _append('Window hidden to menu bar tray — restore via the RP tray icon.');
        }
      } else {
        // Persist residual-honest native/UI status for support export — never bare
        // "Connect failed" when a detailed status is already on the card.
        final failMsg = connectionLogConnectFailureMessage(_status);
        await _connLog(kLogKindError, failMsg);
        if (_status.trim().isNotEmpty &&
            _status.trim().toLowerCase() != 'connect failed') {
          _append(_status);
        }
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (shouldStopTunnelOnAppLifecycle(state.name)) {
      return;
    }
    if (state == AppLifecycleState.resumed) {
      _rehydrateSession(from: 'resume');
    }
  }

  Future<void> _rehydrateSession({required String from}) async {
    final snap = await _vpn.querySession();
    if (!mounted) return;
    // While Connect is in flight, do not overwrite Connecting… with Disconnected.
    if (_busy && !snap.connected) {
      if (snap.connecting && (snap.message ?? '').isNotEmpty) {
        setState(() => _status = snap.message!);
      }
      return;
    }
    setState(() {
      _connected = snap.connected;
      _vpnIp = snap.vpnIp;
      if (snap.connected) {
        // Prefer already-honest native message (provider dual-stack flags).
        final nativeMsg = snap.message ?? '';
        if (isDualStackHonestConnectedMessage(nativeMsg)) {
          _status = nativeMsg;
        } else {
          final ipv6Flag = snap.ipv6Protected ?? _settings.residualIpv6;
          _status = connectedHonestyMessage(
            vpnIp: snap.vpnIp,
            ipv4Residual: kResidualIpv4AlwaysOn,
            ipv6Protected: ipv6Flag,
          );
        }
      } else if (snap.connecting) {
        _status = snap.message ?? connectingStatusMessage();
      } else if (from == 'resume' && !_busy) {
        if (_status.toLowerCase().contains('connected') && !snap.connected) {
          _status = 'Not connected. Press Connect when you want protection.';
        }
      }
    });
    if (snap.connected && from == 'resume') {
      _append('Resumed — VPN still active (minimize did not disconnect).');
    }
    if (snap.connected) {
      // Pull any residual operator push that arrived while backgrounded.
      unawaited(_pollSuiteUpdatePush());
    }
  }

  void _onStatus(String msg) {
    if (!mounted) return;
    setState(() {
      // Open-settings feedback is log-only — never replace residual failure card text
      // (that would hide the Open VPN settings control).
      if (isOpenVpnSettingsFeedbackMessage(msg)) {
        _log.add(msg);
        return;
      }
      _status = msg;
      _log.add(msg);
      if (isNeVpnPermissionFailureMessage(msg)) {
        _needsVpnSystemSettingsApproval = true;
      }
    });
    _scrollLogToEnd();
  }

  /// Residual UPDATE_PUSH / operator poll result → gated Suite pending store.
  Future<void> _onResidualUpdatePush(dynamic raw) async {
    final r = await handleProductionUpdatePush(
      settings: _settings,
      rawPayload: raw,
    );
    if (!mounted) return;
    if (r['store'] is Map) {
      final store = Map<String, dynamic>.from(r['store'] as Map);
      final ver = store[kPendingUpdateVersionKey] ?? store['version'] ?? '';
      _append(
        'Suite update pending v$ver — click “$kSuiteUpdateUnpackButtonLabel” '
        'when you are ready (Settings self-update is on).',
      );
      setState(() => _suiteUpdateReloadToken++);
    } else if (r['skipped'] == true) {
      _append(
        'Update push ignored — ${r['reason'] ?? 'Suite self-update off'}. '
        'Enable “$kSuiteUpdateSettingsTitle” in Settings to receive packages.',
      );
    } else if (r['ok'] != true) {
      _append('Update push not applied: ${r['error'] ?? 'unknown'}');
    }
  }

  /// After Connect / rehydrate: poll native queue for Suite package directive.
  Future<void> _pollSuiteUpdatePush() async {
    _vpn.settingsForUpdatePush = _settings;
    final r = await _vpn.pollAndApplyUpdatePush(settings: _settings);
    if (!mounted) return;
    if (r['store'] is Map) {
      final store = Map<String, dynamic>.from(r['store'] as Map);
      final ver = store[kPendingUpdateVersionKey] ?? '';
      _append(
        'Received Suite update v$ver from residual push — '
        'use “$kSuiteUpdateUnpackButtonLabel”.',
      );
      setState(() => _suiteUpdateReloadToken++);
    }
  }

  void _append(String msg) {
    setState(() => _log.add(msg));
    _scrollLogToEnd();
  }

  void _scrollLogToEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_logScroll.hasClients) {
        _logScroll.jumpTo(_logScroll.position.maxScrollExtent);
      }
    });
  }

  Future<void> _onToggle() async {
    if (_busy) return;
    if (_connected) {
      setState(() => _busy = true);
      try {
        _append('Disconnect — tearing down system Packet Tunnel…');
        await _connLog(kLogKindDisconnect, 'Disconnect started');
        await _vpn.disconnect();
        if (!mounted) return;
        // Confirm OS VPN is down (native stop + status poll).
        final snap = await _vpn.querySession();
        if (!mounted) return;
        if (snap.connected || snap.connecting) {
          setState(() {
            _connected = true;
            _status = snap.message ??
                'Disconnect issued but system VPN still active — try Disconnect again.';
          });
          _append(_status);
          await _connLog(kLogKindDisconnect, 'System VPN still active after disconnect');
          await _macWindow.setTrayConnected(true);
        } else {
          setState(() {
            _connected = false;
            _vpnIp = null;
            _status =
                'Disconnected — system VPN stopped. Press Connect when you want protection.';
          });
          _append('Disconnected — system Network VPN off.');
          await _connLog(kLogKindDisconnect, 'Disconnected system VPN stopped');
          await _macWindow.setTrayConnected(false);
        }
        // Restore UI after explicit disconnect so status is visible.
        await _macWindow.showFromTray();
      } finally {
        if (mounted) setState(() => _busy = false);
      }
    } else {
      await _onToggleConnectOnly();
    }
  }

  /// Discrete main-screen Quit (macOS/iOS): stop Packet Tunnel, then exit process.
  ///
  /// Does **not** hide-to-tray. Order is enforced by [performQuitSequence].
  Future<void> _onQuit() async {
    if (_busy) return;
    setState(() => _busy = true);
    _append('Quit — stopping residual tunnel, then closing the app…');
    try {
      await performQuitSequence(
        stopTunnel: () async {
          try {
            await _vpn.disconnect();
          } catch (_) {
            // Best-effort stop; still exit so UI does not leave a half-state.
          }
          try {
            await _macWindow.setTrayConnected(false);
          } catch (_) {}
        },
        exitApp: widget.onQuitExit ?? exitAppProcess,
      );
    } finally {
      // Only reached if exit was injected (tests) or exit failed.
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _openSettings() async {
    final store = _store;
    if (store == null) return;
    SuitePartsStore? partsStore = widget.partsStore;
    if (partsStore == null) {
      try {
        final prefs = await SharedPreferences.getInstance();
        partsStore = SuitePartsStore(SharedPreferencesBackend(prefs));
      } catch (_) {
        partsStore = SuitePartsStore(MemorySettingsBackend());
      }
    }
    final updated = await Navigator.of(context).push<ProductSettings>(
      MaterialPageRoute(
        builder: (_) => SettingsScreen(
          store: store,
          initial: _settings,
          connectionLog: _connectionLog,
          licenceGate: _licence,
          residualCaptureActive: _connected,
          residualConnected: _connected,
          ipv6Protected: _connected &&
              (_status.toLowerCase().contains('ipv6 isp path blocked') ||
                  (_settings.residualIpv6 &&
                      !_status.toLowerCase().contains('ipv6 not protected'))),
          partsStore: partsStore,
          initialParts: widget.initialParts,
          onPartsChanged: widget.onPartsChanged,
          suiteUpdateReloadToken: _suiteUpdateReloadToken,
          onLicenceChanged: (accepted) {
            if (mounted) setState(() => _licenceAccepted = accepted);
          },
          onChanged: (s) {
            RptConfig.setRuntimeMultiHop(s.privacyMultihop);
            _vpn.settingsForUpdatePush = s;
            if (mounted) setState(() => _settings = s);
            widget.onSettingsChanged?.call(s);
            // Keep native App Group aligned when Settings change outside Connect.
            unawaited(
              _vpn.syncProductSettingsToNative(
                residualIpv4: kResidualIpv4AlwaysOn,
                residualIpv6: s.residualIpv6,
                privacyTrafficShape: s.privacyTrafficShape,
                privacyOuterObfuscation: s.privacyOuterObfuscation,
                privacyMultihop: s.privacyMultihop,
              ),
            );
          },
        ),
      ),
    );
    if (updated != null && mounted) {
      setState(() => _settings = updated);
      widget.onSettingsChanged?.call(updated);
    }
    if (mounted) {
      final s = await store.load();
      final licOk = await _licence?.hasAcceptedLicence() ?? false;
      setState(() {
        _settings = s;
        _licenceAccepted = licOk;
      });
      widget.onSettingsChanged?.call(s);
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _logScroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final btnLabel = connectButtonLabel(_connected);
    final btnColor = _connected
        ? suiteSecondaryOf(context)
        : suitePrimaryOf(context);
    final statusColor = vpnStatusTitleColor(
      context,
      connected: _connected,
      busyConnecting: _busy && !_connected,
    );
    final cardTitle = statusCardTitle(
      connected: _connected,
      busyConnecting: _busy && !_connected,
      vpnIp: _vpnIp,
      residual: true,
    );

    // Nested under SuiteShell chrome + bottom nav: avoid SafeArea double-padding
    // and allow the body to shrink/scroll when height is tight.
    return Scaffold(
      backgroundColor: suiteChromeBgOf(context),
      body: SafeArea(
        top: false,
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
          child: LayoutBuilder(
            builder: (context, constraints) {
              final tight = constraints.maxHeight < 560;
              return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Expanded(
                child: SingleChildScrollView(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
              Row(
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(12),
                    child: Image.asset(
                      kLogoAsset,
                      width: tight ? 36 : 48,
                      height: tight ? 36 : 48,
                      errorBuilder: (context, error, stackTrace) => Container(
                        width: 48,
                        height: 48,
                        decoration: BoxDecoration(
                          color: suitePrimaryOf(context),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        alignment: Alignment.center,
                        child: Text(
                          'RP',
                          style: TextStyle(
                            color: suiteOnPrimaryOf(context),
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          kAppTitle,
                          style: TextStyle(
                            color: suitePrimaryOf(context),
                            fontWeight: FontWeight.bold,
                            fontSize: 18,
                          ),
                        ),
                        Text(
                          kBannerTitle,
                          style: TextStyle(
                            color: suiteTextMutedOf(context),
                            fontSize: 12,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          kSeamlessTagline,
                          style: TextStyle(
                            color: suitePrimaryOf(context),
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    tooltip: 'Settings',
                    onPressed: _openSettings,
                    icon: Icon(Icons.settings, color: suitePrimaryOf(context)),
                  ),
                ],
              ),
              SizedBox(height: tight ? 8 : 14),
              // Suite self-update honesty + unpack lives under Settings
              // ("Allow Suite self-update"), not on VPN home.
              // Catalog monopin banner only when Suite self-update opt-in is on.
              if (!tight && _settings.checkBreadcrumbs)
                UpgradeBanner(runningVersion: kSuiteVersion),
              Container(
                decoration: BoxDecoration(
                  color: suitePanelBgOf(context),
                  borderRadius: BorderRadius.circular(kCornerRadius),
                  border: Border.all(color: suiteBorderOf(context)),
                ),
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            'VPN status',
                            style: TextStyle(
                              color: suiteTextMutedOf(context),
                              fontSize: 11,
                            ),
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 3,
                          ),
                          decoration: BoxDecoration(
                            color: _licenceAccepted
                                ? kLightAccent
                                : const Color(0xFFFDECEC),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            _licenceAccepted
                                ? 'Licence accepted'
                                : 'Licence required',
                            style: TextStyle(
                              color: _licenceAccepted
                                  ? suitePrimaryOf(context)
                                  : kStatusError,
                              fontSize: 11,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(
                      cardTitle,
                      key: const Key('vpn_status_card_title'),
                      style: TextStyle(
                        color: statusColor,
                        fontWeight: FontWeight.w700,
                        fontSize: 17,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      _status,
                      style: TextStyle(color: suiteTextMutedOf(context),
                        fontSize: 12,
                      ),
                    ),
                    if (!_licenceAccepted) ...[
                      const SizedBox(height: 10),
                      Align(
                        alignment: Alignment.centerLeft,
                        child: FilledButton(
                          onPressed: _showLicenceSheet,
                          style: FilledButton.styleFrom(
                            backgroundColor: suitePrimaryOf(context),
                          ),
                          child: Text(kLicenceAcceptButton),
                        ),
                      ),
                    ],
                    // macOS NE permission / host-only HELLO: open System Settings so user can Allow VPN.
                    // Sticky flag keeps the control after open success/failure feedback (log-only).
                    if (shouldShowOpenVpnSettingsControl(
                      connected: _connected,
                      needsVpnSystemSettingsApproval:
                          _needsVpnSystemSettingsApproval,
                      statusMessage: _status,
                    )) ...[
                      const SizedBox(height: 10),
                      Align(
                        alignment: Alignment.centerLeft,
                        child: OutlinedButton.icon(
                          onPressed: _busy
                              ? null
                              : () async {
                                  _append(
                                    'Opening System Settings → Network / VPN…',
                                  );
                                  // reportStatus: false — keep residual failure on the card.
                                  final opened = await _vpn
                                      .openVpnSystemSettings(
                                    reportStatus: false,
                                  );
                                  if (!mounted) return;
                                  setState(() {
                                    _needsVpnSystemSettingsApproval = true;
                                  });
                                  _append(
                                    opened
                                        ? kOpenVpnSettingsOpenedFeedback
                                        : kOpenVpnSettingsFailedFeedback,
                                  );
                                },
                          icon: const Icon(Icons.settings_ethernet, size: 18),
                          label: const Text(kOpenVpnSettingsLabel),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              SizedBox(height: tight ? 6 : 12),
              Container(
                height: tight ? 96 : 140,
                decoration: BoxDecoration(
                  color: suitePanelBgOf(context),
                  borderRadius: BorderRadius.circular(kCornerRadius),
                  border: Border.all(color: suiteBorderOf(context)),
                ),
                padding: const EdgeInsets.all(10),
                child: ListView.builder(
                  controller: _logScroll,
                  itemCount: _log.length,
                  itemBuilder: (_, i) => Text(
                    _log[i],
                    style: TextStyle(color: suiteTextOf(context),
                      fontSize: 13,
                      height: 1.35,
                    ),
                  ),
                ),
              ),
              SizedBox(height: tight ? 8 : 14),
              // Entry country (flags) — main shell above Connect, not Settings-only
              Text(
                'Entry country',
                style: TextStyle(
                  color: suiteTextMutedOf(context),
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 4),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                decoration: BoxDecoration(
                  color: suitePanelBgOf(context),
                  borderRadius: BorderRadius.circular(kCornerRadius),
                  border: Border.all(color: suiteBorderOf(context)),
                ),
                child: DropdownButtonHideUnderline(
                  child: DropdownButton<String>(
                    isExpanded: true,
                    value: normalizeEntryCountry(_settings.entryCountry),
                    items: [
                      for (final o in kProductCountryCatalog)
                        DropdownMenuItem<String>(
                          value: o.code,
                          child: Text(
                            o.label,
                            style: TextStyle(fontSize: 15),
                          ),
                        ),
                    ],
                    onChanged: _busy
                        ? null
                        : (code) async {
                            if (code == null) return;
                            final next = normalizeEntryCountry(code);
                            final updated =
                                _settings.copyWith(entryCountry: next);
                            setState(() => _settings = updated);
                            RptConfig.setRuntimeEntryCountry(next);
                            await _store?.save(updated);
                            _append(
                              'Entry country: ${countryOptionForCode(next)?.label ?? next} (next Connect)',
                            );
                          },
                  ),
                ),
              ),
              const SizedBox(height: 10),
                    ],
                  ),
                ),
              ),
              SizedBox(
                height: tight ? 44 : 52,
                child: ElevatedButton(
                  onPressed: _busy ? null : _onToggle,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: btnColor,
                    foregroundColor: kButtonFg,
                    disabledBackgroundColor: btnColor.withValues(alpha: 0.5),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(kCornerRadius),
                    ),
                    textStyle: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  child: Text(_busy ? 'Please wait…' : btnLabel),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                _settings.autoconnectOnLaunch
                    ? 'Autoconnect on launch is ON (Settings). Minimize keeps VPN alive.'
                    : 'Manual Connect, or enable seamless power-up in Settings ⚙',
                style: TextStyle(color: suiteTextMutedOf(context),
                  fontSize: 11,
                ),
              ),
              // Discrete Quit — bottom-right of main connection screen (macOS + iOS).
              // Placement marker: kQuitButtonPlacement == bottomRight
              if (showsMainScreenQuitOnThisDevice()) ...[
                const SizedBox(height: 4),
                Align(
                  alignment: Alignment.centerRight, // bottomRight of column
                  child: TextButton(
                    key: const Key('main_quit_button'),
                    onPressed: _busy ? null : _onQuit,
                    style: TextButton.styleFrom(
                      foregroundColor: suiteTextMutedOf(context),
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 4,
                      ),
                      minimumSize: const Size(0, 28),
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      visualDensity: VisualDensity.compact,
                    ),
                    child: const Text(
                      kQuitButtonLabel,
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ),
              ],
            ],
              );
            },
          ),
        ),
      ),
    );
  }
}

typedef RetroTunnelHome = TunnelHome;

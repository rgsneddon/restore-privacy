import 'package:flutter_test/flutter_test.dart';
import 'package:restore_privacy_client/connect_status.dart';

void main() {
  group('connect status mapping (shipped helper)', () {
    test('success only when ok is true', () {
      expect(isConnectSuccess({'ok': true, 'message': 'Connected'}), isTrue);
      expect(isConnectSuccess({'ok': false, 'message': 'fail'}), isFalse);
      expect(isConnectSuccess(null), isFalse);
      expect(isConnectSuccess('x'), isFalse);
    });

    test('connecting map is not product success (Android long HELLO)', () {
      expect(
        isConnectSuccess({
          'ok': true,
          'connecting': true,
          'message': 'VPN still connecting…',
          'fullTunnelActive': false,
        }),
        isFalse,
      );
      expect(
        isConnectSuccess({
          'ok': false,
          'connecting': true,
          'message': 'VPN still connecting — waiting for full tunnel…',
        }),
        isFalse,
      );
      expect(
        isConnectingInProgress({
          'connecting': true,
          'message': 'VPN still connecting…',
        }),
        isTrue,
      );
    });

    test('status card title stays Connecting while busy', () {
      expect(
        statusCardTitle(connected: false, busyConnecting: true),
        kConnectingTitle,
      );
      expect(
        statusCardTitle(connected: false, busyConnecting: false),
        'Disconnected',
      );
      expect(
        statusCardTitle(
          connected: true,
          busyConnecting: false,
          vpnIp: '10.88.0.2',
        ),
        contains('10.88.0.2'),
      );
      final msg = connectingStatusMessage(
        host: '82.221.101.241',
        port: 44044,
        elapsedSeconds: 12,
      );
      expect(msg, contains('Connecting'));
      expect(msg, contains('12s'));
      expect(msg, contains('full tunnel'));
    });

    test('does not invent Connected on failure', () {
      final msg = mapConnectStatusMessage({
        'ok': false,
        'message': kMissingSecretsMessage,
      });
      expect(msg, contains('node_elgamal.pub'));
      expect(msg.toLowerCase(), isNot(equals('connected')));
    });

    test('permission denial message preserved', () {
      final msg = mapConnectStatusMessage({
        'ok': false,
        'message': kVpnPermissionDeniedMessage,
      });
      expect(msg, contains('VPN permission denied'));
    });

    test('NEVPNErrorDomain 5 maps to open-VPN-settings failure class', () {
      const detail =
          'NE preferences failed (NEVPNErrorDomain 5): permission denied. '
          'Approve VPN configuration in System Settings → Network → VPN & Filters';
      expect(isNeVpnPermissionFailureMessage(detail), isTrue);
      final map = buildFullTunnelConnectResult(
        packetTunnelActive: false,
        vpnIp: '10.88.0.2',
        hostOnlyHello: true,
        detailMessage: detail,
        nodeDiagnostic:
            'Node reachable; session assigned 10.88.0.2 via 82.221.101.241:44044 (HELLO-only, transport closed).',
      );
      expect(isConnectSuccess(map), isFalse);
      expect(shouldPromptOpenVpnSystemSettings(map), isTrue);
      final msg = mapConnectStatusMessage(map);
      expect(msg, contains('residual public IP'));
      expect(msg, contains('10.88.0.2'));
      expect(msg.toLowerCase(), contains('system settings'));
      expect(msg.toLowerCase(), contains('vpn'));
      // End-user path is present (not operator-script-only).
      expect(msg, contains('VPN & Filters'));
    });

    test('needsVpnSystemSettingsApproval flag prompts open settings', () {
      expect(
        shouldPromptOpenVpnSystemSettings({
          'ok': false,
          'message': 'something failed',
          'fullTunnelActive': false,
          'needsVpnSystemSettingsApproval': true,
        }),
        isTrue,
      );
      expect(
        shouldPromptOpenVpnSystemSettings({
          'ok': true,
          'message': 'Connected',
          'fullTunnelActive': true,
          'needsVpnSystemSettingsApproval': true,
        }),
        isFalse,
      );
    });

    test('packet tunnel not active message includes Settings then Connect', () {
      expect(kPacketTunnelNotActiveMessage, contains('VPN & Filters'));
      expect(kPacketTunnelNotActiveMessage, contains('Connect again'));
      expect(kPacketTunnelNotActiveMessage, contains('sign_macos_residual_team'));
      expect(kHostOnlyHelloNotFullTunnelMessage, contains('System Settings'));
      expect(kOpenVpnSettingsLabel.toLowerCase(), contains('vpn'));
    });

    test('prepare Packet Tunnel is product tunnel type never L2TP/IKEv2', () {
      final prepared = {
        'ok': true,
        'prepared': true,
        'tunnelType': kProductVpnTunnelType,
        'providerBundleId': kProductVpnProviderBundleId,
        'localizedDescription': kProductVpnLocalizedDescription,
        'message': kPacketTunnelPreparedMessage,
      };
      expect(isProductPacketTunnelPrepareResult(prepared), isTrue);
      expect(isPrepareVpnSuccess(prepared), isTrue);
      expect(prepared['tunnelType'], isNot(equals('l2tp')));
      expect(prepared['tunnelType'], isNot(equals('ikev2')));
      expect(prepared['tunnelType'], isNot(equals('ipsec')));
      final msg = mapPrepareVpnStatusMessage(prepared);
      expect(msg.toLowerCase(), contains('packet tunnel'));
      expect(productCopyDirectsToLegacyVpnTypes(msg), isFalse);
      expect(productCopyDirectsToLegacyVpnTypes(kPacketTunnelPreparedMessage), isFalse);
      // Positive "add L2TP" style is rejected for product copy.
      expect(
        productCopyDirectsToLegacyVpnTypes(
          'Add L2TP over IPsec configuration for Restore Privacy',
        ),
        isTrue,
      );
      expect(
        productCopyDirectsToLegacyVpnTypes(
          'Choose IKEv2 as the VPN type',
        ),
        isTrue,
      );
      // Contrast copy is allowed.
      expect(
        productCopyDirectsToLegacyVpnTypes(
          'Do not add L2TP, Cisco IPsec, or IKEv2',
        ),
        isFalse,
      );
      final failed = {
        'ok': false,
        'prepared': false,
        'tunnelType': kProductVpnTunnelType,
        'providerBundleId': kProductVpnProviderBundleId,
        'message':
            'Could not pre-register Packet Tunnel. Allow under VPN & Filters '
            '(Packet Tunnel — not L2TP / Cisco IPsec / IKEv2).',
      };
      expect(isProductPacketTunnelPrepareResult(failed), isTrue);
      expect(isPrepareVpnSuccess(failed), isFalse);
      expect(
        productCopyDirectsToLegacyVpnTypes(mapPrepareVpnStatusMessage(failed)),
        isFalse,
      );
    });

    test(
      'failed prepare must not debounce to prepared:true (first-run double call)',
      () {
        // Native maps after loadOrCreateManager failure (NEVPNErrorDomain 5 class).
        final priorFailed = {
          'ok': false,
          'prepared': false,
          'tunnelType': kProductVpnTunnelType,
          'providerBundleId': kProductVpnProviderBundleId,
          'needsVpnSystemSettingsApproval': true,
          'message':
              'Could not pre-register Packet Tunnel VPN configuration: '
              'NE preferences failed (NEVPNErrorDomain 5): permission denied.',
        };
        expect(isPrepareVpnSuccess(priorFailed), isFalse);
        // Dishonest old bug: second call within 8s returned prepared:true after failure.
        final dishonestDebounce = {
          'ok': true,
          'prepared': true,
          'debounced': true,
          'tunnelType': kProductVpnTunnelType,
          'message':
              'Restore Privacy Packet Tunnel configuration already registered.',
        };
        expect(
          prepareFollowUpIsHonest(
            priorResult: priorFailed,
            nextResult: dishonestDebounce,
          ),
          isFalse,
        );
        // Honest re-attempt after failure: still failing (user has not Allowed yet).
        final honestRetryFail = {
          'ok': false,
          'prepared': false,
          'tunnelType': kProductVpnTunnelType,
          'message': priorFailed['message'],
        };
        expect(
          prepareFollowUpIsHonest(
            priorResult: priorFailed,
            nextResult: honestRetryFail,
          ),
          isTrue,
        );
        // Honest re-attempt after user Allowed: real success.
        final honestRetryOk = {
          'ok': true,
          'prepared': true,
          'tunnelType': kProductVpnTunnelType,
          'providerBundleId': kProductVpnProviderBundleId,
          'message': kPacketTunnelPreparedMessage,
        };
        expect(isPrepareVpnSuccess(honestRetryOk), isTrue);
        expect(
          prepareFollowUpIsHonest(
            priorResult: priorFailed,
            nextResult: honestRetryOk,
          ),
          isTrue,
        );
        // Prior success: debounce prepared:true is allowed.
        expect(
          prepareFollowUpIsHonest(
            priorResult: honestRetryOk,
            nextResult: {
              'ok': true,
              'prepared': true,
              'debounced': true,
              'tunnelType': kProductVpnTunnelType,
            },
          ),
          isTrue,
        );
        // mapPrepareVpnStatusMessage must not treat ok:false as prepared success.
        expect(
          mapPrepareVpnStatusMessage(priorFailed).toLowerCase(),
          isNot(contains('already registered')),
        );
        expect(
          mapPrepareVpnStatusMessage(priorFailed).toLowerCase(),
          contains('could not pre-register'),
        );
      },
    );

    test(
      'open-result status strings keep Open VPN settings control via sticky flag',
      () {
        // After open attempt, product status must stay residual failure OR sticky
        // keeps the control when only open feedback would be shown.
        const neFailure =
            'NE preferences failed (NEVPNErrorDomain 5): permission denied. '
            'Approve VPN configuration in System Settings → Network → VPN & Filters';
        expect(isNeVpnPermissionFailureMessage(neFailure), isTrue);
        expect(isOpenVpnSettingsFeedbackMessage(kOpenVpnSettingsOpenedFeedback), isTrue);
        expect(isOpenVpnSettingsFeedbackMessage(kOpenVpnSettingsFailedFeedback), isTrue);
        // Open feedback alone is NOT a residual failure class (must not invent NE).
        expect(
          isNeVpnPermissionFailureMessage(kOpenVpnSettingsOpenedFeedback),
          isFalse,
        );
        expect(
          isNeVpnPermissionFailureMessage(kOpenVpnSettingsFailedFeedback),
          isFalse,
        );
        // Without sticky, open feedback must not show the control (avoids false UI).
        expect(
          shouldShowOpenVpnSettingsControl(
            connected: false,
            needsVpnSystemSettingsApproval: false,
            statusMessage: kOpenVpnSettingsOpenedFeedback,
          ),
          isFalse,
        );
        // With sticky (set on Connect NE failure), control survives open success/failure.
        expect(
          shouldShowOpenVpnSettingsControl(
            connected: false,
            needsVpnSystemSettingsApproval: true,
            statusMessage: kOpenVpnSettingsOpenedFeedback,
          ),
          isTrue,
        );
        expect(
          shouldShowOpenVpnSettingsControl(
            connected: false,
            needsVpnSystemSettingsApproval: true,
            statusMessage: kOpenVpnSettingsFailedFeedback,
          ),
          isTrue,
        );
        // Prefer keeping real NE failure as card status; control still shows.
        expect(
          shouldShowOpenVpnSettingsControl(
            connected: false,
            needsVpnSystemSettingsApproval: true,
            statusMessage: neFailure,
          ),
          isTrue,
        );
        // Product Connect success clears the control even if sticky was true.
        expect(
          shouldShowOpenVpnSettingsControl(
            connected: true,
            needsVpnSystemSettingsApproval: true,
            statusMessage: 'Connected — IPv4 via VPN; IPv6 not protected',
          ),
          isFalse,
        );
        // Card status should remain residual-honest after open (log-only feedback).
        final map = buildFullTunnelConnectResult(
          packetTunnelActive: false,
          vpnIp: '10.88.0.2',
          hostOnlyHello: true,
          detailMessage: neFailure,
        );
        final card = mapConnectStatusMessage(map);
        expect(isNeVpnPermissionFailureMessage(card), isTrue);
        expect(isOpenVpnSettingsFeedbackMessage(card), isFalse);
        expect(
          shouldShowOpenVpnSettingsControl(
            connected: false,
            needsVpnSystemSettingsApproval: true,
            statusMessage: card,
          ),
          isTrue,
        );
      },
    );

    test('success includes VPN IP when provided', () {
      final msg = mapConnectStatusMessage({
        'ok': true,
        'message': 'Connected — RPT full tunnel up',
        'vpnIp': '10.88.0.5',
        'fullTunnelActive': true,
      });
      expect(msg, contains('10.88.0.5'));
    });
  });

  group('full-tunnel honesty (residual public IP)', () {
    test('(a) host-only HELLO with vpnIp is not product success', () {
      final map = buildFullTunnelConnectResult(
        packetTunnelActive: false,
        vpnIp: '10.88.0.18',
        hostOnlyHello: true,
      );
      expect(map['ok'], isFalse);
      expect(map['fullTunnelActive'], isFalse);
      expect(map['hostOnlySession'], isTrue);
      expect(map['vpnIp'], '10.88.0.18');
      expect(isConnectSuccess(map), isFalse);
      final msg = mapConnectStatusMessage(map);
      expect(msg.toLowerCase(), contains('residual public ip'));
      expect(msg, isNot(startsWith('Connected')));
      expect(msg, contains('10.88.0.18'));
    });

    test('(b) Packet Tunnel active + vpnIp is product success', () {
      final map = buildFullTunnelConnectResult(
        packetTunnelActive: true,
        vpnIp: '10.88.0.19',
      );
      expect(map['ok'], isTrue);
      expect(map['fullTunnelActive'], isTrue);
      expect(map['hostOnlySession'], isFalse);
      expect(map['ipv6Protected'], isFalse);
      expect(isConnectSuccess(map), isTrue);
      final msg = mapConnectStatusMessage(map);
      expect(msg, contains('10.88.0.19'));
      // Apple residual honesty: IPv4 via VPN; no IPv6 kill-switch claim
      expect(msg, contains('IPv6 not protected'));
      expect(msg.toLowerCase(), isNot(contains('ipv6 isp path blocked')));
      // macOS hide-to-tray only after product full-tunnel success
      expect(shouldHideToTrayAfterConnect(map), isTrue);
      expect(shouldHideToTrayAfterConnectSuccess(true), isTrue);
    });

    test('(c) NE start failed is ok:false with residual-IP honest message', () {
      final map = buildFullTunnelConnectResult(
        packetTunnelActive: false,
        detailMessage: 'Packet Tunnel start pending or failed (status 3).',
      );
      expect(map['ok'], isFalse);
      expect(map['fullTunnelActive'], isFalse);
      expect(isConnectSuccess(map), isFalse);
      final msg = mapConnectStatusMessage(map);
      expect(msg, contains('System VPN (Packet Tunnel) did not become active'));
      expect(msg.toLowerCase(), contains('residual public ip'));
      expect(msg, contains('status 3'));
      // Must NOT hide to tray on failed Packet Tunnel
      expect(shouldHideToTrayAfterConnect(map), isFalse);
      expect(shouldHideToTrayAfterConnectSuccess(false), isFalse);
    });

    test('host-only HELLO does not hide to tray', () {
      final map = buildFullTunnelConnectResult(
        packetTunnelActive: false,
        vpnIp: '10.88.0.18',
        hostOnlyHello: true,
      );
      expect(isConnectSuccess(map), isFalse);
      expect(shouldHideToTrayAfterConnect(map), isFalse);
    });

    test('legacy hostOnlySession flag rejects ok:true maps', () {
      expect(
        isConnectSuccess({
          'ok': true,
          'message': 'Connected — tunnel IP 10.88.0.1',
          'vpnIp': '10.88.0.1',
          'hostOnlySession': true,
        }),
        isFalse,
      );
    });

    test('fullTunnelActive false rejects ok:true maps', () {
      expect(
        isConnectSuccess({
          'ok': true,
          'message': 'Connected — tunnel IP 10.88.0.1',
          'vpnIp': '10.88.0.1',
          'fullTunnelActive': false,
        }),
        isFalse,
      );
    });

    test('disconnect map is not product connect success', () {
      final map = {
        'ok': true,
        'message': kDisconnectedResidualIpMessage,
        'fullTunnelActive': false,
        'hostOnlySession': false,
      };
      expect(isConnectSuccess(map), isFalse);
      expect(mapConnectStatusMessage(map).toLowerCase(), contains('residual public ip'));
    });
  });

  group('app lifecycle must not auto-stop tunnel', () {
    test('close/background/detach never auto-disconnect (user uses Disconnect button)', () {
      // Product roll-back: tunnel stays up until explicit Disconnect.
      expect(shouldStopTunnelOnAppLifecycle('detached'), isFalse);
      expect(shouldStopTunnelOnAppLifecycle('AppLifecycleState.detached'), isFalse);
      expect(shouldStopTunnelOnAppLifecycle('paused'), isFalse);
      expect(shouldStopTunnelOnAppLifecycle('AppLifecycleState.paused'), isFalse);
      expect(shouldStopTunnelOnAppLifecycle('inactive'), isFalse);
      expect(shouldStopTunnelOnAppLifecycle('resumed'), isFalse);
    });

    test('disconnectResultMap contract is not product success (shipped helper)', () {
      // Mirrors native RptFullTunnelResult.disconnectResultMap fields.
      final map = {
        'ok': true,
        'message': kDisconnectedResidualIpMessage,
        'fullTunnelActive': false,
        'hostOnlySession': false,
      };
      expect(isConnectSuccess(map), isFalse);
      expect(mapConnectStatusMessage(map), kDisconnectedResidualIpMessage);
    });
  });
}

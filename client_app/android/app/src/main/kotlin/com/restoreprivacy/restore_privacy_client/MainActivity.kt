package com.restoreprivacy.restore_privacy_client

import android.app.Activity
import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.net.VpnService
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.ResultReceiver
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.File

/**
 * Bridges Flutter retro UI to [RptVpnService].
 * Connect waits for a real handshake result (not a premature "Connected").
 */
class MainActivity : FlutterActivity() {
    private val channelName = "restore_privacy/vpn"
    private var pendingResult: MethodChannel.Result? = null
    private val vpnRequestCode = 0x5250

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channelName)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "connect" -> {
                        val host = call.argument<String>("host") ?: "82.221.101.241"
                        val port = call.argument<Int>("port") ?: 44044
                        val fullTunnel = call.argument<Boolean>("fullTunnel") ?: true
                        val sessionName = call.argument<String>("sessionName") ?: "Restore Privacy"
                        // Lean residual defaults OFF (parity with desktop/Apple privacy scale).
                        val trafficShape = call.argument<Boolean>("trafficShape") ?: false
                        val outerObfs = call.argument<Boolean>("outerObfuscation") ?: false
                        // Fail fast if admission material is missing
                        if (!secretsPresent()) {
                            result.success(
                                mapOf(
                                    "ok" to false,
                                    "message" to (
                                        "Missing node_elgamal.pub - packages ship the public node key; " +
                                            "a unique device Ed25519 key is generated on first run"
                                        ),
                                ),
                            )
                            return@setMethodCallHandler
                        }
                        prepareAndStart(
                            host, port, fullTunnel, sessionName, result,
                            trafficShape = trafficShape,
                            outerObfs = outerObfs,
                        )
                    }
                    "setPrivacyScale" -> {
                        val shape = call.argument<Boolean>("trafficShape") ?: false
                        val obfs = call.argument<Boolean>("outerObfuscation") ?: false
                        RptTrafficShape.applyPrivacyScale(shape)
                        RptObfuscation.applyPrivacyScale(obfs)
                        result.success(
                            mapOf(
                                "ok" to true,
                                "trafficShape" to RptTrafficShape.productPadding,
                                "outerObfuscation" to RptObfuscation.productObfsEnabled,
                            ),
                        )
                    }
                    "disconnect" -> {
                        // ACTION_DISCONNECT runs stopTunnel (close TUN + stopSelf)
                        // rather than only stopService, so OS VPN routes clear fully.
                        // Only explicit Disconnect from UI - never on Activity destroy.
                        sendDisconnect()
                        result.success(
                            mapOf(
                                "ok" to true,
                                "message" to "Disconnected - system VPN stopped; residual public IP restored",
                                "connected" to false,
                                "fullTunnelActive" to false,
                            ),
                        )
                    }
                    "status" -> {
                        // Rehydrate UI after minimize/resume - does not start/stop tunnel.
                        // If session IP is present, residual is up even if a flag race
                        // left isSessionActive briefly false (stops "waiting for full
                        // tunnel" spam every poll).
                        val ip = RptVpnService.activeVpnIp
                        val active =
                            RptVpnService.isSessionActive || ip.isNotEmpty()
                        val connecting =
                            RptVpnService.desiredConnected && !active
                        val v6 = RptVpnService.activeIpv6Protected
                        val statusMsg = when {
                            connecting ->
                                "Connecting - waiting for full tunnel (RPT2 + system VPN)..."
                            !active -> "Disconnected"
                            v6 == false && ip.isNotEmpty() ->
                                "Connected - IPv4 via VPN; IPv6 not protected ($ip)"
                            v6 == false ->
                                "Connected - IPv4 via VPN; IPv6 not protected"
                            v6 == true && ip.isNotEmpty() ->
                                "Connected - VPN active; IPv6 ISP path blocked ($ip)"
                            v6 == true ->
                                "Connected - VPN active; IPv6 ISP path blocked"
                            ip.isNotEmpty() ->
                                "Connected - your traffic uses the VPN ($ip)"
                            else ->
                                "Connected - protected"
                        }
                        result.success(
                            mapOf(
                                "ok" to active,
                                "connected" to active,
                                "connecting" to connecting,
                                "fullTunnelActive" to active,
                                "hostOnlySession" to false,
                                "vpnIp" to ip,
                                "ipv6Protected" to v6,
                                // Live residual/DNS flags for Flutter leak posture + watchdog.
                                "residualCapture" to active,
                                "dnsTunnelGatewayOnly" to active,
                                "dnsTunnelOnly" to active,
                                "message" to statusMsg,
                            ),
                        )
                    }
                    "hasSecrets" -> {
                        result.success(mapOf("ok" to secretsPresent()))
                    }
                    "devicePubHex" -> {
                        // Ensure device Ed25519 exists and return 64-char pub hex for
                        // status-host bind-device-entitlement (node payment HELLO gate).
                        result.success(devicePubHexMap())
                    }
                    "setRunAtStartup" -> {
                        val enabled = call.argument<Boolean>("enabled") ?: false
                        val status = StartupPrefs.setRunAtStartup(this, enabled)
                        result.success(
                            mapOf(
                                "ok" to (status.startsWith("enabled") || status == "disabled"),
                                "message" to status,
                            ),
                        )
                    }
                    "setAutoConnectIfIdle" -> {
                        val enabled = call.argument<Boolean>("enabled") ?: false
                        StartupPrefs.setAutoConnectIfIdle(this, enabled)
                        result.success(
                            mapOf(
                                "ok" to true,
                                "auto_connect_if_idle" to StartupPrefs.autoConnectIfIdleEnabled(this),
                            ),
                        )
                    }
                    "setResidualStack" -> {
                        // Dual-stack residual Settings (defaults both ON).
                        val ipv4 = call.argument<Boolean>("ipv4")
                        val ipv6 = call.argument<Boolean>("ipv6")
                        StartupPrefs.setResidualStack(this, ipv4, ipv6)
                        result.success(
                            mapOf(
                                "ok" to true,
                                "residual_ipv4" to StartupPrefs.residualIpv4Enabled(this),
                                "residual_ipv6" to StartupPrefs.residualIpv6Enabled(this),
                            ),
                        )
                    }
                    "fullExit" -> {
                        // Quit: residual should already be stopped in Dart. Fully tear down:
                        // force-stop VPN service, remove every app task, kill the process.
                        // SystemNavigator.pop / finish alone leave a disconnected shell in
                        // recents. Reply first so Dart await can complete; always post
                        // teardown to the next main-loop message so the channel reply
                        // flushes before killProcess (same-stack kill aborts the reply).
                        result.success(mapOf("ok" to true, "message" to "full_exit"))
                        Handler(Looper.getMainLooper()).post {
                            fullProcessExit()
                        }
                    }
                    else -> result.notImplemented()
                }
            }
    }

    /**
     * Full process takedown for main-screen Quit — no leftover background window.
     *
     * Order:
     * 1. Force residual VPN stop without FGS restart ([forceStopVpnService]).
     * 2. Remove **all** app tasks + finishAffinity / finishAndRemoveTask.
     * 3. **postDelayed** killProcess/System.exit/halt so (1)+(2) can apply —
     *    immediate kill races AMS task removal (blank/disconnected recents) and
     *    can fire before DISCONNECT marks START_NOT_STICKY (sticky revival).
     */
    private fun fullProcessExit() {
        forceStopVpnService()
        removeAllAppTasks()
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.JELLY_BEAN) {
                finishAffinity()
            }
        } catch (_: Exception) {
        }
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                finishAndRemoveTask()
            } else {
                @Suppress("DEPRECATION")
                finish()
            }
        } catch (_: Exception) {
            try {
                finish()
            } catch (_: Exception) {
            }
        }
        // Delay kill so DISCONNECT/stopService and AMS task removal can complete.
        Handler(Looper.getMainLooper()).postDelayed({
            hardKillProcess()
        }, FULL_EXIT_KILL_DELAY_MS)
    }

    /** Last-resort process death after task removal + service stop window. */
    private fun hardKillProcess() {
        try {
            android.os.Process.killProcess(android.os.Process.myPid())
        } catch (_: Exception) {
        }
        try {
            System.exit(0)
        } catch (_: Exception) {
        }
        try {
            Runtime.getRuntime().halt(0)
        } catch (_: Exception) {
        }
    }

    /**
     * Stop residual VPN without FGS contract violations or sticky revival.
     *
     * 1. Plain [startService] + ACTION_DISCONNECT (never [startForegroundService])
     *    so onStartCommand sets userStopped, runs stopTunnel, returns START_NOT_STICKY.
     * 2. [stopService] so the component is unbound even if already stopping.
     *
     * DISCONNECT must not use startForegroundService: it never calls startForeground.
     */
    private fun forceStopVpnService() {
        try {
            val disc = Intent(this, RptVpnService::class.java).apply {
                action = RptVpnService.ACTION_DISCONNECT
            }
            startService(disc)
        } catch (_: Exception) {
        }
        try {
            stopService(Intent(this, RptVpnService::class.java))
        } catch (_: Exception) {
        }
    }

    /** Remove every task for this app from the recents/task switcher. */
    private fun removeAllAppTasks() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.LOLLIPOP) return
        try {
            val am = getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
            for (task in am.appTasks) {
                try {
                    task.finishAndRemoveTask()
                } catch (_: Exception) {
                }
            }
        } catch (_: Exception) {
        }
    }

    companion object {
        /**
         * Delay after task/service teardown before killProcess (ms).
         * Lets ACTION_DISCONNECT set START_NOT_STICKY and AMS drop the task.
         */
        const val FULL_EXIT_KILL_DELAY_MS: Long = 300L
    }

    /** True when node public key is available (device Ed25519 is generated on connect). */
    private fun secretsPresent(): Boolean {
        val dir = File(filesDir, "secrets")
        if (File(dir, "node_elgamal.pub").isFile) {
            return true
        }
        return try {
            assets.open("secrets/node_elgamal.pub").close()
            true
        } catch (_: Exception) {
            false
        }
    }

    /**
     * Ensure per-install `client_ed25519.priv` exists, derive Ed25519 public key,
     * return lowercase hex for Flutter bind-device-entitlement.
     */
    private fun devicePubHexMap(): Map<String, Any> {
        return try {
            val dir = File(filesDir, "secrets")
            dir.mkdirs()
            val privF = File(dir, "client_ed25519.priv")
            if (!privF.isFile || privF.length() != 32L) {
                val seed = ByteArray(32)
                java.security.SecureRandom().nextBytes(seed)
                // Validate as Ed25519 seed
                org.bouncycastle.crypto.params.Ed25519PrivateKeyParameters(seed, 0)
                privF.writeBytes(seed)
            }
            val priv = privF.readBytes()
            if (priv.size != 32) {
                return mapOf("ok" to false, "error" to "bad_priv_len", "devicePubHex" to "")
            }
            val params = org.bouncycastle.crypto.params.Ed25519PrivateKeyParameters(priv, 0)
            val pub = params.generatePublicKey().encoded
            if (pub == null || pub.size != 32) {
                return mapOf("ok" to false, "error" to "bad_pub", "devicePubHex" to "")
            }
            val hex = pub.joinToString("") { b -> "%02x".format(b) }
            mapOf("ok" to true, "devicePubHex" to hex, "device_pub_hex" to hex)
        } catch (e: Exception) {
            mapOf("ok" to false, "error" to (e.message ?: "device_pub_failed"), "devicePubHex" to "")
        }
    }

    /**
     * Tell [RptVpnService] to close TUN and stop so traffic reverts to device IP.
     *
     * Uses plain [startService] only — never [startForegroundService].
     * ACTION_DISCONNECT does not call startForeground; FGS start would crash or
     * leave a sticky shell after Quit.
     */
    private fun sendDisconnect() {
        try {
            val i = Intent(this, RptVpnService::class.java).apply {
                action = RptVpnService.ACTION_DISCONNECT
            }
            startService(i)
        } catch (_: Exception) {
            try {
                stopService(Intent(this, RptVpnService::class.java))
            } catch (_: Exception) {
            }
        }
    }

    override fun onDestroy() {
        // Activity destroy only; tunnel stop is explicit via channel "disconnect".
        super.onDestroy()
    }

    private fun prepareAndStart(
        host: String,
        port: Int,
        fullTunnel: Boolean,
        sessionName: String,
        result: MethodChannel.Result,
        trafficShape: Boolean = false,
        outerObfs: Boolean = false,
    ) {
        val intent = VpnService.prepare(this)
        if (intent != null) {
            pendingResult = result
            pendingHost = host
            pendingPort = port
            pendingFullTunnel = fullTunnel
            pendingSession = sessionName
            pendingTrafficShape = trafficShape
            pendingOuterObfs = outerObfs
            @Suppress("DEPRECATION")
            startActivityForResult(intent, vpnRequestCode)
        } else {
            startVpn(
                host, port, fullTunnel, sessionName, result,
                trafficShape = trafficShape,
                outerObfs = outerObfs,
            )
        }
    }

    private var pendingHost: String = "82.221.101.241"
    private var pendingPort: Int = 44044
    private var pendingFullTunnel: Boolean = true
    private var pendingSession: String = "Restore Privacy"
    private var pendingTrafficShape: Boolean = false
    private var pendingOuterObfs: Boolean = false

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == vpnRequestCode) {
            val res = pendingResult
            pendingResult = null
            if (resultCode == Activity.RESULT_OK && res != null) {
                startVpn(
                    pendingHost, pendingPort, pendingFullTunnel, pendingSession, res,
                    trafficShape = pendingTrafficShape,
                    outerObfs = pendingOuterObfs,
                )
            } else {
                res?.success(
                    mapOf(
                        "ok" to false,
                        "message" to "VPN permission denied - grant once for full tunnel",
                    ),
                )
            }
        }
    }

    private fun startVpn(
        host: String,
        port: Int,
        fullTunnel: Boolean,
        sessionName: String,
        result: MethodChannel.Result,
        trafficShape: Boolean = false,
        outerObfs: Boolean = false,
    ) {
        // Reply only after service reports handshake/TUN outcome
        val receiver = object : ResultReceiver(Handler(Looper.getMainLooper())) {
            override fun onReceiveResult(resultCode: Int, resultData: Bundle?) {
                val connecting =
                    resultData?.getBoolean(RptVpnService.EXTRA_CONNECTING, false) == true
                val ok = resultCode == RptVpnService.RESULT_OK && !connecting
                val message = resultData?.getString(RptVpnService.EXTRA_MESSAGE)
                    ?: when {
                        connecting -> "Connecting - waiting for full tunnel..."
                        ok -> "Connected"
                        else -> "Connect failed"
                    }
                val vpnIp = resultData?.getString(RptVpnService.EXTRA_VPN_IP) ?: ""
                val hasIpv6 = resultData?.containsKey(RptVpnService.EXTRA_IPV6_PROTECTED) == true
                val ipv6Protected = if (hasIpv6) {
                    resultData?.getBoolean(RptVpnService.EXTRA_IPV6_PROTECTED)
                } else {
                    null
                }
                try {
                    result.success(
                        mapOf(
                            "ok" to ok,
                            "message" to message,
                            "vpnIp" to vpnIp,
                            "fullTunnel" to fullTunnel,
                            // Product residual success requires active OS VPN (honest UI).
                            "fullTunnelActive" to ok,
                            "connecting" to connecting,
                            "hostOnlySession" to false,
                            "connected" to ok,
                            "ipv6Protected" to ipv6Protected,
                        ),
                    )
                } catch (_: Exception) {
                    // Result already replied
                }
            }
        }

        val i = Intent(this, RptVpnService::class.java).apply {
            action = RptVpnService.ACTION_CONNECT
            putExtra(RptVpnService.EXTRA_HOST, host)
            putExtra(RptVpnService.EXTRA_PORT, port)
            putExtra(RptVpnService.EXTRA_FULL_TUNNEL, fullTunnel)
            putExtra(RptVpnService.EXTRA_SESSION, sessionName)
            putExtra(RptVpnService.EXTRA_TRAFFIC_SHAPE, trafficShape)
            putExtra(RptVpnService.EXTRA_OUTER_OBFS, outerObfs)
            putExtra(RptVpnService.EXTRA_RECEIVER, receiver)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(i)
        } else {
            @Suppress("DEPRECATION")
            startService(i)
        }
    }
}

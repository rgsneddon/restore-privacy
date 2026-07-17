package com.restoreprivacy.restore_privacy_client

import android.app.Activity
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
                        val host = call.argument<String>("host") ?: "104.156.224.47"
                        val port = call.argument<Int>("port") ?: 44044
                        val fullTunnel = call.argument<Boolean>("fullTunnel") ?: true
                        val sessionName = call.argument<String>("sessionName") ?: "Restore Privacy"
                        // Fail fast if admission material is missing
                        if (!secretsPresent()) {
                            result.success(
                                mapOf(
                                    "ok" to false,
                                    "message" to (
                                        "Missing admission secrets — place client_ed25519.priv and " +
                                            "node_elgamal.pub under app secrets (build injects from " +
                                            "repo secrets/ when present)"
                                        ),
                                ),
                            )
                            return@setMethodCallHandler
                        }
                        prepareAndStart(host, port, fullTunnel, sessionName, result)
                    }
                    "disconnect" -> {
                        stopService(Intent(this, RptVpnService::class.java))
                        result.success(mapOf("ok" to true, "message" to "Disconnected"))
                    }
                    "hasSecrets" -> {
                        result.success(mapOf("ok" to secretsPresent()))
                    }
                    else -> result.notImplemented()
                }
            }
    }

    private fun secretsPresent(): Boolean {
        val dir = File(filesDir, "secrets")
        if (File(dir, "client_ed25519.priv").isFile && File(dir, "node_elgamal.pub").isFile) {
            return true
        }
        return try {
            assets.open("secrets/client_ed25519.priv").close()
            assets.open("secrets/node_elgamal.pub").close()
            true
        } catch (_: Exception) {
            false
        }
    }

    private fun prepareAndStart(
        host: String,
        port: Int,
        fullTunnel: Boolean,
        sessionName: String,
        result: MethodChannel.Result,
    ) {
        val intent = VpnService.prepare(this)
        if (intent != null) {
            pendingResult = result
            pendingHost = host
            pendingPort = port
            pendingFullTunnel = fullTunnel
            pendingSession = sessionName
            @Suppress("DEPRECATION")
            startActivityForResult(intent, vpnRequestCode)
        } else {
            startVpn(host, port, fullTunnel, sessionName, result)
        }
    }

    private var pendingHost: String = "104.156.224.47"
    private var pendingPort: Int = 44044
    private var pendingFullTunnel: Boolean = true
    private var pendingSession: String = "Restore Privacy"

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == vpnRequestCode) {
            val res = pendingResult
            pendingResult = null
            if (resultCode == Activity.RESULT_OK && res != null) {
                startVpn(pendingHost, pendingPort, pendingFullTunnel, pendingSession, res)
            } else {
                res?.success(
                    mapOf(
                        "ok" to false,
                        "message" to "VPN permission denied — grant once for full tunnel",
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
    ) {
        // Reply only after service reports handshake/TUN outcome
        val receiver = object : ResultReceiver(Handler(Looper.getMainLooper())) {
            override fun onReceiveResult(resultCode: Int, resultData: Bundle?) {
                val ok = resultCode == RptVpnService.RESULT_OK
                val message = resultData?.getString(RptVpnService.EXTRA_MESSAGE)
                    ?: if (ok) "Connected" else "Connect failed"
                val vpnIp = resultData?.getString(RptVpnService.EXTRA_VPN_IP) ?: ""
                try {
                    result.success(
                        mapOf(
                            "ok" to ok,
                            "message" to message,
                            "vpnIp" to vpnIp,
                            "fullTunnel" to fullTunnel,
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

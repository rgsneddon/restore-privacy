package com.restoreprivacy.restore_privacy_client

import android.app.Activity
import android.content.Intent
import android.net.VpnService
import android.os.Bundle
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

/**
 * Bridges Flutter retro UI to [RptVpnService] for full-tunnel RPT VPN.
 * Auto-connect is triggered from Flutter on launch via channel "connect".
 */
class MainActivity : FlutterActivity() {
    private val channelName = "restore_privacy/vpn"
    private var pendingResult: MethodChannel.Result? = null
    private val vpnRequestCode = 0x5250 // 'RP'

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
                        prepareAndStart(host, port, fullTunnel, sessionName, result)
                    }
                    "disconnect" -> {
                        stopService(Intent(this, RptVpnService::class.java))
                        result.success(mapOf("ok" to true, "message" to "Disconnected"))
                    }
                    else -> result.notImplemented()
                }
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
        val i = Intent(this, RptVpnService::class.java).apply {
            action = RptVpnService.ACTION_CONNECT
            putExtra(RptVpnService.EXTRA_HOST, host)
            putExtra(RptVpnService.EXTRA_PORT, port)
            putExtra(RptVpnService.EXTRA_FULL_TUNNEL, fullTunnel)
            putExtra(RptVpnService.EXTRA_SESSION, sessionName)
        }
        startForegroundService(i)
        result.success(
            mapOf(
                "ok" to true,
                "message" to "Full VPN starting (RPT2 auto-connect) → $host:$port",
                "fullTunnel" to fullTunnel,
            ),
        )
    }
}

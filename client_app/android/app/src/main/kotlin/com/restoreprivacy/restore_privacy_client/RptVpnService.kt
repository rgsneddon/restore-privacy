package com.restoreprivacy.restore_privacy_client

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Intent
import android.net.VpnService
import android.os.Build
import android.os.ParcelFileDescriptor
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetSocketAddress
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.concurrent.thread

/**
 * Full-tunnel VPN service for Restore Privacy Tunnel (RPT2).
 *
 * Performs authorized CLIENT_HELLO (ElGamal+Pedersen+Ed25519), then seals all
 * TUN IP packets as RPT DATA frames (ChaCha20-Poly1305). Not WireGuard/OpenVPN.
 */
class RptVpnService : VpnService() {
    private var tun: ParcelFileDescriptor? = null
    private val running = AtomicBoolean(false)
    private var worker: Thread? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_CONNECT -> {
                val host = intent.getStringExtra(EXTRA_HOST) ?: "104.156.224.47"
                val port = intent.getIntExtra(EXTRA_PORT, 44044)
                val fullTunnel = intent.getBooleanExtra(EXTRA_FULL_TUNNEL, true)
                val session = intent.getStringExtra(EXTRA_SESSION) ?: "Restore Privacy"
                startForeground(NOTIFICATION_ID, buildNotification(session))
                startTunnel(host, port, fullTunnel, session)
            }
            ACTION_DISCONNECT -> stopTunnel()
        }
        return START_STICKY
    }

    private fun loadSecrets(): Pair<ByteArray, ByteArray>? {
        // Prefer app filesDir/secrets (copied at install); fall back to assets
        val dir = File(filesDir, "secrets")
        val privF = File(dir, "client_ed25519.priv")
        val pubF = File(dir, "node_elgamal.pub")
        if (privF.isFile && pubF.isFile) {
            return privF.readBytes() to pubF.readBytes()
        }
        return try {
            val priv = assets.open("secrets/client_ed25519.priv").readBytes()
            val pub = assets.open("secrets/node_elgamal.pub").readBytes()
            priv to pub
        } catch (_: Exception) {
            null
        }
    }

    private fun startTunnel(host: String, port: Int, fullTunnel: Boolean, sessionName: String) {
        if (running.getAndSet(true)) return
        val secrets = loadSecrets()
        if (secrets == null) {
            running.set(false)
            stopSelf()
            return
        }
        val (clientPriv, nodePub) = secrets

        worker = thread(name = "rpt-dataplane", isDaemon = true) {
            val sock = DatagramSocket()
            try {
                protect(sock)
                val engine = RptClientEngine(clientPriv, nodePub)
                val session = engine.handshake(sock, host, port)
                // Establish TUN with assigned VPN IP (full tunnel routes all traffic)
                val builder = Builder()
                    .setSession(sessionName)
                    .setMtu(1280)
                    .addAddress(session.vpnIp, 32)
                    .addDnsServer("1.1.1.1")
                    .addDnsServer("9.9.9.9")
                if (fullTunnel) {
                    builder.addRoute("0.0.0.0", 0)
                }
                try {
                    builder.addDisallowedApplication(packageName)
                } catch (_: Exception) {
                }
                val pfd = builder.establish()
                if (pfd == null) {
                    running.set(false)
                    stopSelf()
                    return@thread
                }
                tun = pfd
                val inTun = FileInputStream(pfd.fileDescriptor)
                val outTun = FileOutputStream(pfd.fileDescriptor)
                val buf = ByteArray(32767)
                sock.soTimeout = 50
                val endpoint = InetSocketAddress(host, port)
                while (running.get()) {
                    // TUN -> seal RPT DATA -> UDP
                    val avail = inTun.available()
                    if (avail > 0) {
                        val n = inTun.read(buf)
                        if (n > 0) {
                            val ip = buf.copyOf(n)
                            val frame = engine.sealPacket(ip)
                            sock.send(DatagramPacket(frame, frame.size, endpoint))
                        }
                    }
                    // UDP -> open RPT DATA -> TUN
                    try {
                        val pkt = DatagramPacket(buf, buf.size)
                        sock.receive(pkt)
                        if (pkt.length > 5 && buf[4] == 0x03.toByte()) {
                            val frame = buf.copyOf(pkt.length)
                            val plain = engine.openPacket(frame)
                            outTun.write(plain)
                        }
                    } catch (_: Exception) {
                    }
                }
                inTun.close()
                outTun.close()
            } catch (_: Exception) {
            } finally {
                try {
                    sock.close()
                } catch (_: Exception) {
                }
                running.set(false)
            }
        }
    }

    private fun stopTunnel() {
        running.set(false)
        try {
            worker?.join(1500)
        } catch (_: Exception) {
        }
        try {
            tun?.close()
        } catch (_: Exception) {
        }
        tun = null
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        stopTunnel()
        super.onDestroy()
    }

    private fun buildNotification(session: String): Notification {
        val channelId = "rpt_vpn"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val nm = getSystemService(NotificationManager::class.java)
            nm.createNotificationChannel(
                NotificationChannel(channelId, "Restore Privacy VPN", NotificationManager.IMPORTANCE_LOW),
            )
        }
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(this, channelId)
                .setContentTitle(session)
                .setContentText("Full VPN active — no user data retained")
                .setSmallIcon(android.R.drawable.ic_lock_lock)
                .build()
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(this)
                .setContentTitle(session)
                .setContentText("Full VPN active — no user data retained")
                .setSmallIcon(android.R.drawable.ic_lock_lock)
                .build()
        }
    }

    companion object {
        const val ACTION_CONNECT = "com.restoreprivacy.rpt.CONNECT"
        const val ACTION_DISCONNECT = "com.restoreprivacy.rpt.DISCONNECT"
        const val EXTRA_HOST = "host"
        const val EXTRA_PORT = "port"
        const val EXTRA_FULL_TUNNEL = "fullTunnel"
        const val EXTRA_SESSION = "session"
        private const val NOTIFICATION_ID = 0x5250
    }
}

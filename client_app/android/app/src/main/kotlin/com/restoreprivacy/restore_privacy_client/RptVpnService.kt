package com.restoreprivacy.restore_privacy_client

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Intent
import android.net.VpnService
import android.os.Build
import android.os.Bundle
import android.os.ParcelFileDescriptor
import android.os.ResultReceiver
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
 * Reports handshake/TUN success or failure via [ResultReceiver] — no silent fail.
 */
class RptVpnService : VpnService() {
    private var tun: ParcelFileDescriptor? = null
    private val running = AtomicBoolean(false)
    private var worker: Thread? = null
    private var resultReceiver: ResultReceiver? = null
    private var reported = AtomicBoolean(false)

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_CONNECT -> {
                val host = intent.getStringExtra(EXTRA_HOST) ?: "104.156.224.47"
                val port = intent.getIntExtra(EXTRA_PORT, 44044)
                val fullTunnel = intent.getBooleanExtra(EXTRA_FULL_TUNNEL, true)
                val session = intent.getStringExtra(EXTRA_SESSION) ?: "Restore Privacy"
                resultReceiver = extractReceiver(intent)
                reported.set(false)
                try {
                    startForeground(NOTIFICATION_ID, buildNotification(session, connecting = true))
                } catch (e: Exception) {
                    report(false, "Foreground service failed: ${e.message}")
                    stopSelf()
                    return START_NOT_STICKY
                }
                startTunnel(host, port, fullTunnel, session)
            }
            ACTION_DISCONNECT -> {
                stopTunnel()
            }
        }
        return START_STICKY
    }

    private fun extractReceiver(intent: Intent): ResultReceiver? {
        return if (Build.VERSION.SDK_INT >= 33) {
            intent.getParcelableExtra(EXTRA_RECEIVER, ResultReceiver::class.java)
        } else {
            @Suppress("DEPRECATION")
            intent.getParcelableExtra(EXTRA_RECEIVER)
        }
    }

    private fun report(ok: Boolean, message: String, vpnIp: String = "") {
        if (!reported.compareAndSet(false, true)) return
        val b = Bundle()
        b.putString(EXTRA_MESSAGE, message)
        if (vpnIp.isNotEmpty()) b.putString(EXTRA_VPN_IP, vpnIp)
        try {
            resultReceiver?.send(if (ok) RESULT_OK else RESULT_ERR, b)
        } catch (_: Exception) {
        }
    }

    private fun loadSecrets(): Pair<ByteArray, ByteArray>? {
        val dir = File(filesDir, "secrets")
        val privF = File(dir, "client_ed25519.priv")
        val pubF = File(dir, "node_elgamal.pub")
        if (privF.isFile && pubF.isFile) {
            return privF.readBytes() to pubF.readBytes()
        }
        return try {
            val priv = assets.open("secrets/client_ed25519.priv").readBytes()
            val pub = assets.open("secrets/node_elgamal.pub").readBytes()
            // Seed filesDir for later updates
            try {
                dir.mkdirs()
                if (!privF.exists()) privF.writeBytes(priv)
                if (!pubF.exists()) pubF.writeBytes(pub)
            } catch (_: Exception) {
            }
            priv to pub
        } catch (_: Exception) {
            null
        }
    }

    private fun startTunnel(host: String, port: Int, fullTunnel: Boolean, sessionName: String) {
        if (running.getAndSet(true)) {
            report(false, "VPN already connecting or connected")
            return
        }
        val secrets = loadSecrets()
        if (secrets == null) {
            running.set(false)
            report(
                false,
                "Missing admission secrets — place client_ed25519.priv and node_elgamal.pub under app secrets",
            )
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
            return
        }
        val (clientPriv, nodePub) = secrets

        worker = thread(name = "rpt-dataplane", isDaemon = true) {
            // UK public-IP gate before handshake (fail closed with clear notice)
            val gate = UkIpGate.checkUkPublicIp()
            if (!gate.allowed) {
                report(false, gate.message)
                running.set(false)
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf()
                return@thread
            }

            val sock = DatagramSocket()
            try {
                protect(sock)
                val engine = RptClientEngine(clientPriv, nodePub)
                val session = try {
                    engine.handshake(sock, host, port, timeoutMs = 20000)
                } catch (e: Exception) {
                    report(false, "RPT handshake failed: ${e.message ?: e.javaClass.simpleName}")
                    running.set(false)
                    stopForeground(STOP_FOREGROUND_REMOVE)
                    stopSelf()
                    return@thread
                }

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
                    // Keep our app off the VPN loop so UDP to node works
                    builder.addDisallowedApplication(packageName)
                } catch (_: Exception) {
                }
                val pfd = try {
                    builder.establish()
                } catch (e: Exception) {
                    report(false, "VpnService.establish failed: ${e.message}")
                    running.set(false)
                    stopForeground(STOP_FOREGROUND_REMOVE)
                    stopSelf()
                    return@thread
                }
                if (pfd == null) {
                    report(false, "VpnService.establish returned null — VPN permission or policy blocked TUN")
                    running.set(false)
                    stopForeground(STOP_FOREGROUND_REMOVE)
                    stopSelf()
                    return@thread
                }
                tun = pfd
                startForeground(NOTIFICATION_ID, buildNotification(sessionName, connecting = false))
                report(
                    true,
                    "Connected — RPT full tunnel up (VPN IP ${session.vpnIp})",
                    session.vpnIp,
                )

                // Two threads: TUN→UDP and UDP→TUN.
                // Do NOT use FileInputStream.available() — on Android VPN it often
                // stays 0 forever and blackholes all internet traffic.
                val inTun = FileInputStream(pfd.fileDescriptor)
                val outTun = FileOutputStream(pfd.fileDescriptor)
                sock.soTimeout = 200
                val endpoint = InetSocketAddress(host, port)
                val tunToUdp = thread(name = "rpt-tun-up", isDaemon = true) {
                    val buf = ByteArray(32767)
                    while (running.get()) {
                        try {
                            val n = inTun.read(buf) // blocking read of VPN packets
                            if (n > 0) {
                                val frame = engine.sealPacket(buf.copyOf(n))
                                sock.send(DatagramPacket(frame, frame.size, endpoint))
                            } else if (n < 0) {
                                break
                            }
                        } catch (_: Exception) {
                            if (!running.get()) break
                        }
                    }
                }
                val udpToTun = thread(name = "rpt-udp-down", isDaemon = true) {
                    val buf = ByteArray(65535)
                    while (running.get()) {
                        try {
                            val pkt = DatagramPacket(buf, buf.size)
                            sock.receive(pkt)
                            if (pkt.length > 5 && buf[4] == 0x03.toByte()) {
                                val plain = engine.openPacket(buf.copyOf(pkt.length))
                                outTun.write(plain)
                                outTun.flush()
                            }
                        } catch (_: Exception) {
                            if (!running.get()) break
                        }
                    }
                }
                tunToUdp.join(Long.MAX_VALUE)
                udpToTun.join(2_000)
                try {
                    inTun.close()
                } catch (_: Exception) {
                }
                try {
                    outTun.close()
                } catch (_: Exception) {
                }
            } catch (e: Exception) {
                report(false, "VPN tunnel error: ${e.message ?: e.javaClass.simpleName}")
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
        try {
            stopForeground(STOP_FOREGROUND_REMOVE)
        } catch (_: Exception) {
        }
        stopSelf()
    }

    override fun onDestroy() {
        stopTunnel()
        super.onDestroy()
    }

    private fun buildNotification(session: String, connecting: Boolean): Notification {
        val channelId = "rpt_vpn"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val nm = getSystemService(NotificationManager::class.java)
            nm.createNotificationChannel(
                NotificationChannel(channelId, "Restore Privacy VPN", NotificationManager.IMPORTANCE_LOW),
            )
        }
        val text = if (connecting) {
            "Connecting RPT tunnel…"
        } else {
            "Full VPN active — no user data retained"
        }
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(this, channelId)
                .setContentTitle(session)
                .setContentText(text)
                .setSmallIcon(android.R.drawable.ic_lock_lock)
                .build()
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(this)
                .setContentTitle(session)
                .setContentText(text)
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
        const val EXTRA_RECEIVER = "receiver"
        const val EXTRA_MESSAGE = "message"
        const val EXTRA_VPN_IP = "vpnIp"
        const val RESULT_OK = 0
        const val RESULT_ERR = 1
        private const val NOTIFICATION_ID = 0x5250
    }
}

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
import android.system.OsConstants
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetSocketAddress
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong
import kotlin.concurrent.thread

/**
 * Full-tunnel VPN service for Restore Privacy Tunnel (RPT2).
 * Reports handshake/TUN success or failure via [ResultReceiver] — no silent fail.
 */
class RptVpnService : VpnService() {
    private var tun: ParcelFileDescriptor? = null
    private val running = AtomicBoolean(false)
    /** True after intentional disconnect/revoke — do not sticky-restart a dead tunnel. */
    private val userStopped = AtomicBoolean(false)
    private var worker: Thread? = null
    private var resultReceiver: ResultReceiver? = null
    private var reported = AtomicBoolean(false)

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_CONNECT -> {
                userStopped.set(false)
                desiredConnected = true
                val host = intent.getStringExtra(EXTRA_HOST) ?: "82.221.101.241"
                val port = intent.getIntExtra(EXTRA_PORT, 44044)
                val fullTunnel = intent.getBooleanExtra(EXTRA_FULL_TUNNEL, true)
                val session = intent.getStringExtra(EXTRA_SESSION) ?: "Privacy Restored"
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
                // Sticky only while user wants the tunnel up (not after disconnect)
                return if (userStopped.get()) START_NOT_STICKY else START_STICKY
            }
            ACTION_DISCONNECT -> {
                // Intentional stop: full teardown, no sticky resurrection
                userStopped.set(true)
                desiredConnected = false
                stopTunnel()
                return START_NOT_STICKY
            }
            else -> {
                // Null intent / sticky restart: keep foreground if session already active.
                // Do NOT tear down solely because Activity was destroyed (minimize).
                if (userStopped.get() || !desiredConnected) {
                    stopTunnel()
                    return START_NOT_STICKY
                }
                if (isSessionActive && running.get()) {
                    return START_STICKY
                }
                // Process was killed mid-session — cannot rehydrate TUN without credentials path;
                // drop sticky so OS does not loop empty restarts. User taps Connect again.
                isSessionActive = false
                activeVpnIp = ""
                return START_NOT_STICKY
            }
        }
        return if (userStopped.get()) START_NOT_STICKY else START_STICKY
    }

    private fun extractReceiver(intent: Intent): ResultReceiver? {
        return if (Build.VERSION.SDK_INT >= 33) {
            intent.getParcelableExtra(EXTRA_RECEIVER, ResultReceiver::class.java)
        } else {
            @Suppress("DEPRECATION")
            intent.getParcelableExtra(EXTRA_RECEIVER)
        }
    }

    private fun report(
        ok: Boolean,
        message: String,
        vpnIp: String = "",
        ipv6Protected: Boolean? = null,
    ) {
        if (!reported.compareAndSet(false, true)) return
        if (!ok) {
            // Real connect failure only — never call report(false) for â€œalready upâ€
            // (that path must not clear desiredConnected / isSessionActive).
            desiredConnected = false
            isSessionActive = false
            activeVpnIp = ""
            activeIpv6Protected = null
        } else if (ipv6Protected != null) {
            activeIpv6Protected = ipv6Protected
        }
        val b = Bundle()
        b.putString(EXTRA_MESSAGE, message)
        if (vpnIp.isNotEmpty()) b.putString(EXTRA_VPN_IP, vpnIp)
        if (ipv6Protected != null) {
            b.putBoolean(EXTRA_IPV6_PROTECTED, ipv6Protected)
        }
        try {
            resultReceiver?.send(if (ok) RESULT_OK else RESULT_ERR, b)
        } catch (_: Exception) {
        }
    }

    /**
     * Idempotent Connect while session is already up or still handshaking.
     * Must keep [desiredConnected] / [isSessionActive] — never report(false).
     */
    private fun reportAlreadyRunningSession() {
        desiredConnected = true
        userStopped.set(false)
        val decision = alreadyRunningConnectDecision(
            isSessionActive,
            activeVpnIp,
            activeIpv6Protected,
        )
        // decision.first = reportOk, .second = keepSessionFlags, .third = message
        report(decision.first, decision.third, activeVpnIp, ipv6Protected = activeIpv6Protected)
    }

    /**
     * Load device Ed25519 priv + node ElGamal pub.
     * Generates a unique client key on first run (never uses a shared APK-embedded priv).
     * Packages may ship only node_elgamal.pub in assets.
     *
     * **Always** refreshes `node_elgamal.pub` from APK assets (overwrite). Upgrades that
     * fix a stale product key must heal prior installs without uninstall/clear-data.
     * Device Ed25519 private key is never overwritten once generated.
     */
    private fun loadSecrets(): Pair<ByteArray, ByteArray>? {
        val dir = File(filesDir, "secrets")
        dir.mkdirs()
        val privF = File(dir, "client_ed25519.priv")
        val pubF = File(dir, "node_elgamal.pub")

        // Always copy package node pub → filesDir (heals stale key after APK upgrade).
        try {
            assets.open("secrets/node_elgamal.pub").use { inp ->
                if (!refreshNodeElgamalPub(pubF, inp.readBytes())) {
                    return null
                }
            }
        } catch (_: Exception) {
            // Assets missing: keep existing filesDir pub only if still usable.
            if (!pubF.isFile || pubF.length() < 32L) return null
        }
        if (!pubF.isFile || pubF.length() < 32L) return null

        // Per-device key: generate once, reuse forever on this install
        if (!privF.isFile || privF.length() != 32L) {
            try {
                val priv = generateDeviceEd25519PrivateKey()
                privF.writeBytes(priv)
            } catch (_: Exception) {
                return null
            }
        }
        val priv = privF.readBytes()
        val pub = pubF.readBytes()
        if (priv.size != 32) return null
        return priv to pub
    }

    /** Cryptographically random 32-byte Ed25519 seed (BouncyCastle params). */
    private fun generateDeviceEd25519PrivateKey(): ByteArray {
        val seed = ByteArray(32)
        java.security.SecureRandom().nextBytes(seed)
        // Validate as Ed25519 private seed via BC
        org.bouncycastle.crypto.params.Ed25519PrivateKeyParameters(seed, 0)
        return seed
    }

    private fun startTunnel(host: String, port: Int, fullTunnel: Boolean, sessionName: String) {
        // Second Connect / Activity recreate while tunnel is up: keep live session.
        // Never report(false) here — that would clear desiredConnected/isSessionActive
        // and poison UI rehydrate after minimize.
        if (!running.compareAndSet(false, true)) {
            reportAlreadyRunningSession()
            return
        }
        val secrets = loadSecrets()
        if (secrets == null) {
            running.set(false)
            report(
                false,
                "Missing node public key — package must include node_elgamal.pub; device Ed25519 is auto-generated",
            )
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
            return
        }
        val (clientPriv, nodePub) = secrets

        worker = thread(name = "rpt-dataplane", isDaemon = true) {
            // Product connect: device keys + RPT2 handshake only (no public-IP geo gate)
            val sock = DatagramSocket()
            try {
                // Keep UDP to the node off any existing VPN routing loop when a TUN is up.
                // First-run Connect has no VPN yet — protect() may return false; still OK.
                protect(sock)
                val engine = RptClientEngine(clientPriv, nodePub)
                val session = try {
                    // 3 attempts × ~8s — mobile UDP is lossy; node silent-drops bad HELLO
                    engine.handshake(sock, host, port, timeoutMs = 24000, attempts = 3)
                } catch (e: Exception) {
                    val detail = e.message ?: e.javaClass.simpleName
                    val hint =
                        if (detail.contains("timed out", ignoreCase = true) ||
                            detail.contains("timeout", ignoreCase = true) ||
                            detail.contains("Poll timed", ignoreCase = true) ||
                            e is java.net.SocketTimeoutException
                        ) {
                            " No reply from $host:$port — check network/UDP, or that this " +
                                "package’s node_elgamal.pub matches the production node " +
                                "(and that the APK includes PFS + outer obfs wire)."
                        } else {
                            ""
                        }
                    report(false, "RPT handshake failed: $detail$hint")
                    running.set(false)
                    stopForeground(STOP_FOREGROUND_REMOVE)
                    stopSelf()
                    return@thread
                }

                // DNS: node tunnel gateway recursive resolver (10.88.0.1 / unbound on residual node)
                // Kill switch: setBlocking(true) on API 29+ so non-VPN apps cannot bypass the TUN
                // IPv4-only residual: do NOT install ::/0 without a TUN IPv6 address — that
                // blackholes dual-stack apps under setBlocking while the node only routes IPv4.
                val builder = Builder()
                    .setSession(sessionName)
                    .setMtu(1280)
                    .addAddress(session.vpnIp, 32)
                    .addDnsServer("10.88.0.1")
                if (Build.VERSION.SDK_INT >= 29) {
                    builder.setBlocking(true)
                }
                // Prefer IPv4 residual path (product node DATA/TUN is IPv4).
                try {
                    builder.allowFamily(OsConstants.AF_INET)
                } catch (_: Exception) {
                }
                val ipv6RouteOk = false
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

                // Critical: after establish(), re-protect (and prefer a fresh socket).
                // Pre-establish protect() is often a no-op; without post-establish protect,
                // node UDP is routed into the TUN and residual traffic blackholes.
                val endpoint = InetSocketAddress(host, port)
                val dataSock = try {
                    openProtectedNodeSocket(endpoint)
                } catch (e: Exception) {
                    try {
                        pfd.close()
                    } catch (_: Exception) {
                    }
                    tun = null
                    report(
                        false,
                        "Could not protect UDP to $host:$port after VPN establish " +
                            "(${e.message}) — residual traffic would blackhole",
                    )
                    running.set(false)
                    stopForeground(STOP_FOREGROUND_REMOVE)
                    stopSelf()
                    return@thread
                }
                // Close handshake socket; dataplane uses protected dataSock only
                try {
                    sock.close()
                } catch (_: Exception) {
                }

                isSessionActive = true
                activeVpnIp = session.vpnIp
                activeIpv6Protected = if (fullTunnel) ipv6RouteOk else null
                startForeground(NOTIFICATION_ID, buildNotification(sessionName, connecting = false))
                val msg = if (!fullTunnel) {
                    "Connected — RPT tunnel up (VPN IP ${session.vpnIp})"
                } else {
                    // IPv4 residual only (AF_INET); ISP IPv6 is not claimed protected
                    "Connected — IPv4 via VPN; IPv6 not protected (VPN IP ${session.vpnIp})"
                }
                report(true, msg, session.vpnIp, ipv6Protected = if (fullTunnel) ipv6RouteOk else null)

                // Two threads: TUN→UDP and UDP→TUN.
                // Do NOT use FileInputStream.available() — on Android VPN it often
                // stays 0 forever and blackholes all internet traffic.
                // Dup FDs so read/write threads do not share one stream state.
                val pfdIn = ParcelFileDescriptor.dup(pfd.fileDescriptor)
                val pfdOut = ParcelFileDescriptor.dup(pfd.fileDescriptor)
                val inTun = FileInputStream(pfdIn.fileDescriptor)
                val outTun = FileOutputStream(pfdOut.fileDescriptor)
                dataSock.soTimeout = 200
                // Product residual: pad+cover on DATA + outer QUIC-mimic wrap (Python parity)
                val lastCoverMs = AtomicLong(System.currentTimeMillis())
                val tunToUdp = thread(name = "rpt-tun-up", isDaemon = true) {
                    val buf = ByteArray(32767)
                    while (running.get()) {
                        try {
                            val n = inTun.read(buf) // blocking read of VPN packets
                            if (n > 0) {
                                val wire = engine.sealAndWrapPacket(buf.copyOf(n))
                                dataSock.send(DatagramPacket(wire, wire.size))
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
                            dataSock.receive(pkt)
                            // Outer unwrap then open; null = cover (discard)
                            val plain = engine.unwrapAndOpen(buf.copyOf(pkt.length))
                            if (plain != null && plain.isNotEmpty()) {
                                outTun.write(plain)
                                outTun.flush()
                            }
                        } catch (_: Exception) {
                            if (!running.get()) break
                        }
                    }
                }
                val coverThread = thread(name = "rpt-cover", isDaemon = true) {
                    while (running.get()) {
                        try {
                            Thread.sleep(200)
                            val now = System.currentTimeMillis()
                            if (RptTrafficShape.PRODUCT_COVER &&
                                now - lastCoverMs.get() >= RptTrafficShape.PRODUCT_COVER_INTERVAL_MS
                            ) {
                                val wire = engine.sealAndWrapCover()
                                dataSock.send(DatagramPacket(wire, wire.size))
                                lastCoverMs.set(now)
                            }
                        } catch (_: Exception) {
                            if (!running.get()) break
                        }
                    }
                }
                tunToUdp.join(Long.MAX_VALUE)
                udpToTun.join(2_000)
                coverThread.join(500)
                try {
                    inTun.close()
                } catch (_: Exception) {
                }
                try {
                    outTun.close()
                } catch (_: Exception) {
                }
                try {
                    pfdIn.close()
                } catch (_: Exception) {
                }
                try {
                    pfdOut.close()
                } catch (_: Exception) {
                }
                try {
                    dataSock.close()
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

    /**
     * Fresh UDP socket to the product node that is **VpnService.protect**-ed so
     * residual traffic is not looped into the TUN (classic Android blackhole).
     * Must be called **after** [Builder.establish].
     */
    private fun openProtectedNodeSocket(endpoint: InetSocketAddress): DatagramSocket {
        val s = DatagramSocket()
        // protect() after establish is required — pre-establish protect is unreliable.
        if (!protect(s)) {
            try {
                s.close()
            } catch (_: Exception) {
            }
            throw IllegalStateException("VpnService.protect returned false")
        }
        s.connect(endpoint)
        s.soTimeout = 200
        return s
    }

    /**
     * Full teardown: stop dataplane loops, close TUN (clears OS VPN routes so
     * the device reverts to its normal IP path), drop foreground, stop service.
     * Idempotent — safe to call repeatedly from disconnect / onDestroy / onRevoke.
     */
    private fun stopTunnel() {
        running.set(false)
        isSessionActive = false
        activeVpnIp = ""
        activeIpv6Protected = null
        // Closing TUN unblocks FileInputStream.read and clears VpnService routes
        val pfd = tun
        tun = null
        try {
            pfd?.close()
        } catch (_: Exception) {
        }
        try {
            worker?.join(2000)
        } catch (_: Exception) {
        }
        worker = null
        try {
            stopForeground(STOP_FOREGROUND_REMOVE)
        } catch (_: Exception) {
        }
        try {
            stopSelf()
        } catch (_: Exception) {
        }
    }

    override fun onDestroy() {
        // Process/service death only — Activity minimize must not reach here.
        // Do not mark userStopped unless already intentional disconnect/revoke,
        // so a sticky restart path is not permanently poisoned.
        if (userStopped.get() || !desiredConnected) {
            stopTunnel()
        } else if (!running.get()) {
            isSessionActive = false
            activeVpnIp = ""
        }
        super.onDestroy()
    }

    override fun onRevoke() {
        // System revoked VPN permission / another VPN took over — tear down fully
        userStopped.set(true)
        desiredConnected = false
        stopTunnel()
        super.onRevoke()
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
            "Full VPN active — minimize keeps protection on. Use Disconnect to stop."
        }
        val title = if (session.isBlank()) "Privacy Restored" else session
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(this, channelId)
                .setContentTitle(title)
                .setContentText(text)
                .setSmallIcon(android.R.drawable.ic_lock_lock)
                .setOngoing(true)
                .build()
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(this)
                .setContentTitle(title)
                .setContentText(text)
                .setSmallIcon(android.R.drawable.ic_lock_lock)
                .setOngoing(true)
                .build()
        }
    }

    companion object {
        /**
         * Always write package [assetBytes] to [pubFile] (overwrite).
         * Used so APK upgrades replace a stale node_elgamal.pub left in filesDir.
         * @return true when the destination file is present and at least 32 bytes.
         */
        @JvmStatic
        fun refreshNodeElgamalPub(pubFile: File, assetBytes: ByteArray): Boolean {
            if (assetBytes.size < 32) return false
            pubFile.parentFile?.mkdirs()
            pubFile.writeBytes(assetBytes)
            return pubFile.isFile && pubFile.length() >= 32L
        }

        const val ACTION_CONNECT = "com.restoreprivacy.rpt.CONNECT"
        const val ACTION_DISCONNECT = "com.restoreprivacy.rpt.DISCONNECT"
        const val EXTRA_HOST = "host"
        const val EXTRA_PORT = "port"
        const val EXTRA_FULL_TUNNEL = "fullTunnel"
        const val EXTRA_SESSION = "session"
        const val EXTRA_RECEIVER = "receiver"
        const val EXTRA_MESSAGE = "message"
        const val EXTRA_VPN_IP = "vpnIp"
        const val EXTRA_IPV6_PROTECTED = "ipv6Protected"
        const val RESULT_OK = 0
        const val RESULT_ERR = 1
        private const val NOTIFICATION_ID = 0x5250

        /** UI rehydrate after minimize — true while TUN session is up. */
        @Volatile
        var isSessionActive: Boolean = false

        @Volatile
        var activeVpnIp: String = ""

        /** Null when unknown/not full-tunnel; true only if ::/0 was installed. */
        @Volatile
        var activeIpv6Protected: Boolean? = null

        /** User wants tunnel up (Connect) until explicit Disconnect / revoke. */
        @Volatile
        var desiredConnected: Boolean = false

        /**
         * Pure decision for already-running Connect (mirrored in Python tests).
         * Returns (reportOk, keepSessionFlags, message).
         * Must never yield reportOk=false (that poisons live session flags).
         */
        @JvmStatic
        fun alreadyRunningConnectDecision(
            isSessionActive: Boolean,
            vpnIp: String,
            ipv6Protected: Boolean? = activeIpv6Protected,
        ): Triple<Boolean, Boolean, String> {
            val ip = vpnIp.trim()
            val msg = if (isSessionActive) {
                when {
                    ipv6Protected == false && ip.isNotEmpty() ->
                        "Connected — IPv4 via VPN; IPv6 not protected (VPN IP $ip)"
                    ipv6Protected == false ->
                        "Connected — IPv4 via VPN; IPv6 not protected"
                    ipv6Protected == true && ip.isNotEmpty() ->
                        "Connected — VPN active; IPv6 ISP path blocked (VPN IP $ip)"
                    ipv6Protected == true ->
                        "Connected — VPN active; IPv6 ISP path blocked"
                    ip.isNotEmpty() ->
                        "Connected — RPT full tunnel up (VPN IP $ip)"
                    else ->
                        "Connected — full tunnel already active"
                }
            } else {
                "VPN already connecting…"
            }
            return Triple(true, true, msg)
        }
    }
}

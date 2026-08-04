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
    /** Bumped to cancel an in-flight reconnect backoff sleep. */
    private val reconnectGeneration = AtomicLong(0)
    private val reconnectAttempts = AtomicLong(0)
    private var lastHost: String = PRODUCT_ENTRY_HOST
    private var lastPort: Int = 44044
    private var lastFullTunnel: Boolean = true
    private var lastSession: String = "Privacy Restored"

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_CONNECT -> {
                userStopped.set(false)
                desiredConnected = true
                StartupPrefs.setDesiredConnected(this, true)
                // User/explicit Connect cancels any pending idle reconnect timer.
                reconnectGeneration.incrementAndGet()
                reconnectAttempts.set(0)
                val host = intent.getStringExtra(EXTRA_HOST) ?: PRODUCT_ENTRY_HOST
                val port = intent.getIntExtra(EXTRA_PORT, 44044)
                val fullTunnel = intent.getBooleanExtra(EXTRA_FULL_TUNNEL, true)
                val session = intent.getStringExtra(EXTRA_SESSION) ?: "Privacy Restored"
                // Privacy-scale lean defaults OFF unless Flutter Connect extras enable them.
                val shape = intent.getBooleanExtra(EXTRA_TRAFFIC_SHAPE, false)
                val obfs = intent.getBooleanExtra(EXTRA_OUTER_OBFS, false)
                RptTrafficShape.applyPrivacyScale(shape)
                RptObfuscation.applyPrivacyScale(obfs)
                rememberConnectParams(host, port, fullTunnel, session, shape, obfs)
                val recv = extractReceiver(intent)
                // Already handshaking or up: reply to *this* receiver only — do not
                // steal the active connect's ResultReceiver / reported flag (that hung
                // Flutter and looked like an Android timeout).
                if (running.get()) {
                    replyToReceiverOnly(recv, alreadyRunningConnectDecision(
                        isSessionActive,
                        activeVpnIp,
                        activeIpv6Protected,
                    ))
                    return if (userStopped.get()) START_NOT_STICKY else START_STICKY
                }
                resultReceiver = recv
                reported.set(false)
                try {
                    startForeground(NOTIFICATION_ID, buildNotification(session, connecting = true))
                } catch (e: Exception) {
                    report(false, "Foreground service failed: ${e.message}", allowReconnect = false)
                    stopSelf()
                    return START_NOT_STICKY
                }
                startTunnel(host, port, fullTunnel, session)
                // Sticky only while user wants the tunnel up (not after disconnect)
                return if (userStopped.get()) START_NOT_STICKY else START_STICKY
            }
            ACTION_DISCONNECT -> {
                // Intentional stop: full teardown, no sticky resurrection / no idle reconnect
                userStopped.set(true)
                desiredConnected = false
                StartupPrefs.setDesiredConnected(this, false)
                reconnectGeneration.incrementAndGet()
                reconnectAttempts.set(0)
                stopTunnel()
                return START_NOT_STICKY
            }
            else -> {
                // Null intent / sticky restart: keep foreground if session already active.
                // Do NOT tear down solely because Activity was destroyed (minimize).
                if (userStopped.get()) {
                    stopTunnel()
                    return START_NOT_STICKY
                }
                // Rehydrate desired from prefs (process death) when idle auto-reconnect is on.
                if (!desiredConnected && StartupPrefs.isDesiredConnected(this)) {
                    desiredConnected = true
                }
                if (!desiredConnected) {
                    stopTunnel()
                    return START_NOT_STICKY
                }
                if (isSessionActive && running.get()) {
                    return START_STICKY
                }
                // Process killed mid-session or empty sticky restart: re-open residual
                // when Settings "Auto connect if idle" is on.
                if (StartupPrefs.autoConnectIfIdleEnabled(this)) {
                    val last = StartupPrefs.loadLastConnect(this, PRODUCT_ENTRY_HOST)
                    rememberConnectParams(
                        last.host,
                        last.port,
                        last.fullTunnel,
                        last.session,
                        last.trafficShape,
                        last.outerObfs,
                    )
                    RptTrafficShape.applyPrivacyScale(last.trafficShape)
                    RptObfuscation.applyPrivacyScale(last.outerObfs)
                    reported.set(false)
                    try {
                        startForeground(
                            NOTIFICATION_ID,
                            buildNotification(last.session, connecting = true, reconnecting = true),
                        )
                    } catch (_: Exception) {
                        return START_NOT_STICKY
                    }
                    startTunnel(last.host, last.port, last.fullTunnel, last.session)
                    return START_STICKY
                }
                // No auto-reconnect: clear flags; user taps Connect again.
                isSessionActive = false
                activeVpnIp = ""
                desiredConnected = false
                StartupPrefs.setDesiredConnected(this, false)
                return START_NOT_STICKY
            }
        }
        return if (userStopped.get()) START_NOT_STICKY else START_STICKY
    }

    private fun rememberConnectParams(
        host: String,
        port: Int,
        fullTunnel: Boolean,
        session: String,
        shape: Boolean,
        obfs: Boolean,
    ) {
        lastHost = host
        lastPort = port
        lastFullTunnel = fullTunnel
        lastSession = session
        StartupPrefs.saveLastConnect(this, host, port, fullTunnel, session, shape, obfs)
    }

    private fun wantsIdleAutoReconnect(): Boolean {
        if (userStopped.get()) return false
        if (!desiredConnected && !StartupPrefs.isDesiredConnected(this)) return false
        return StartupPrefs.autoConnectIfIdleEnabled(this)
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
        connecting: Boolean = false,
        /** When false on failure, keep desiredConnected so idle auto-reconnect can run. */
        allowReconnect: Boolean = false,
    ) {
        if (!reported.compareAndSet(false, true)) return
        if (!ok && !connecting) {
            // Real connect failure only — never clear session for in-progress replies.
            isSessionActive = false
            activeVpnIp = ""
            activeIpv6Protected = null
            if (!allowReconnect || !wantsIdleAutoReconnect()) {
                desiredConnected = false
                StartupPrefs.setDesiredConnected(this, false)
            }
        } else if (ok && !connecting) {
            reconnectAttempts.set(0)
            desiredConnected = true
            StartupPrefs.setDesiredConnected(this, true)
            if (ipv6Protected != null) {
                activeIpv6Protected = ipv6Protected
            }
        } else if (ipv6Protected != null) {
            activeIpv6Protected = ipv6Protected
        }
        val b = Bundle()
        b.putString(EXTRA_MESSAGE, message)
        b.putBoolean(EXTRA_CONNECTING, connecting)
        if (vpnIp.isNotEmpty()) b.putString(EXTRA_VPN_IP, vpnIp)
        if (ipv6Protected != null) {
            b.putBoolean(EXTRA_IPV6_PROTECTED, ipv6Protected)
        }
        try {
            // RESULT_OK only for residual full-tunnel success
            resultReceiver?.send(if (ok && !connecting) RESULT_OK else RESULT_ERR, b)
        } catch (_: Exception) {
        }
    }

    /**
     * After unexpected tunnel death (or failed handshake while still desired),
     * schedule a gentle backoff re-Connect when Settings auto-connect-if-idle is on.
     * Safe to call once from the worker finally block (generation cancels prior timers).
     */
    private fun scheduleIdleReconnect(reason: String) {
        if (!wantsIdleAutoReconnect()) return
        if (running.get()) return
        val attempt = reconnectAttempts.incrementAndGet().toInt()
        val delayMs = reconnectBackoffMs(attempt)
        val gen = reconnectGeneration.incrementAndGet()
        desiredConnected = true
        StartupPrefs.setDesiredConnected(this, true)
        try {
            startForeground(
                NOTIFICATION_ID,
                buildNotification(lastSession, connecting = true, reconnecting = true),
            )
        } catch (_: Exception) {
            return
        }
        thread(name = "rpt-idle-reconnect", isDaemon = true) {
            try {
                Thread.sleep(delayMs)
            } catch (_: InterruptedException) {
                return@thread
            }
            if (gen != reconnectGeneration.get()) return@thread
            if (userStopped.get() || !wantsIdleAutoReconnect()) return@thread
            if (running.get() || isSessionActive) return@thread
            reported.set(false)
            val last = StartupPrefs.loadLastConnect(this@RptVpnService, lastHost)
            RptTrafficShape.applyPrivacyScale(last.trafficShape)
            RptObfuscation.applyPrivacyScale(last.outerObfs)
            rememberConnectParams(
                last.host,
                last.port,
                last.fullTunnel,
                last.session,
                last.trafficShape,
                last.outerObfs,
            )
            try {
                startForeground(
                    NOTIFICATION_ID,
                    buildNotification(last.session, connecting = true, reconnecting = true),
                )
            } catch (_: Exception) {
                return@thread
            }
            startTunnel(last.host, last.port, last.fullTunnel, last.session)
        }
    }

    /**
     * Reply to a late Connect tap without replacing the active handshake's receiver.
     * [decision]: first=sessionActiveOk, second=keepFlags, third=message.
     */
    private fun replyToReceiverOnly(
        recv: ResultReceiver?,
        decision: Triple<Boolean, Boolean, String>,
    ) {
        desiredConnected = true
        userStopped.set(false)
        val sessionUp = decision.first && isSessionActive
        val connecting = !sessionUp
        val b = Bundle()
        b.putString(EXTRA_MESSAGE, decision.third)
        b.putBoolean(EXTRA_CONNECTING, connecting)
        if (activeVpnIp.isNotEmpty()) b.putString(EXTRA_VPN_IP, activeVpnIp)
        activeIpv6Protected?.let { b.putBoolean(EXTRA_IPV6_PROTECTED, it) }
        try {
            recv?.send(if (sessionUp) RESULT_OK else RESULT_ERR, b)
        } catch (_: Exception) {
        }
    }

    /**
     * Load device Ed25519 priv + node ElGamal pub for residual HELLO.
     * Generates a unique client key on first run (never uses a shared APK-embedded priv).
     * Packages ship `node_elgamal.pub` (IS), `exit_node_elgamal.pub` (RO),
     * `us_node_elgamal.pub` (US).
     *
     * Pub basename is chosen from residual dial *host* (catalog monopin), not entry code alone.
     * **Always** refreshes the chosen pub from APK assets (overwrite). Device Ed25519 private
     * key is never overwritten once generated.
     */
    private fun loadSecrets(residualHost: String = ""): Pair<ByteArray, ByteArray>? {
        val dir = File(filesDir, "secrets")
        dir.mkdirs()
        val privF = File(dir, "client_ed25519.priv")
        val host = residualHost.trim()
        val pubName = residualNodePubNameForHost(host)
        val pubF = File(dir, pubName)

        // Always copy package pub → filesDir (heals stale key after APK upgrade).
        // Fail closed for RO/US residual: never HELLO with Iceland pin to non-IS monopin.
        try {
            assets.open("secrets/$pubName").use { inp ->
                if (!refreshNodeElgamalPub(pubF, inp.readBytes())) {
                    return null
                }
            }
        } catch (_: Exception) {
            if (pubName != "node_elgamal.pub") {
                // Missing RO/US pin — do not fall back to Iceland entry pub
                return null
            }
            if (!pubF.isFile || pubF.length() < 32L) return null
        }
        if (!pubF.isFile || pubF.length() < 32L) return null
        return loadSecretsAfterPub(privF, pubF)
    }

    private fun loadSecretsAfterPub(privF: File, pubF: File): Pair<ByteArray, ByteArray>? {
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
        // Second Connect while tunnel is up/handshaking is handled in onStartCommand
        // (replyToReceiverOnly) so we never steal the active ResultReceiver here.
        if (!running.compareAndSet(false, true)) {
            replyToReceiverOnly(
                resultReceiver,
                alreadyRunningConnectDecision(
                    isSessionActive,
                    activeVpnIp,
                    activeIpv6Protected,
                ),
            )
            return
        }
        val secrets = loadSecrets(host)
        if (secrets == null) {
            running.set(false)
            report(
                false,
                "Missing node public key — package must include node_elgamal.pub " +
                    "(plus exit_node_elgamal.pub / us_node_elgamal.pub for RO/US residual); " +
                    "device Ed25519 is auto-generated",
                allowReconnect = false,
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
                    // Mobile UDP is lossy: longer budget so status stays Connecting
                    // until full residual (HELLO + TUN). Windows is usually faster.
                    engine.handshake(sock, host, port, timeoutMs = 60000, attempts = 5)
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
                    val canRetry = wantsIdleAutoReconnect()
                    report(
                        false,
                        "RPT handshake failed: $detail$hint",
                        allowReconnect = canRetry,
                    )
                    running.set(false)
                    // Reconnect (if opted in) is scheduled from the worker finally block.
                    if (!canRetry) {
                        stopForeground(STOP_FOREGROUND_REMOVE)
                        stopSelf()
                    }
                    return@thread
                }

                // DNS: node tunnel gateway recursive resolver (10.88.0.1 / unbound on residual node)
                // Residual IPv4 always-on full-tunnel capture.
                // Residual IPv6 ON installs ULA + ::/0 (ISP IPv6 blackhole / leak mitigation).
                val residualIpv4 = StartupPrefs.residualIpv4Enabled(this) // always true
                val residualIpv6 = StartupPrefs.residualIpv6Enabled(this)
                // Kill switch removed — product residual does not call setBlocking(true).
                val builder = Builder()
                    .setSession(sessionName)
                    .setMtu(1280)
                    .addAddress(session.vpnIp, 32)
                    .addDnsServer("10.88.0.1")
                try {
                    builder.allowFamily(OsConstants.AF_INET)
                } catch (_: Exception) {
                }
                var ipv6RouteOk = false
                if (fullTunnel && residualIpv4) {
                    // Full-tunnel IPv4 residual capture (always on)
                    builder.addRoute("0.0.0.0", 0)
                }
                if (fullTunnel && residualIpv6) {
                    try {
                        builder.addAddress("fd00:5274:7074::1", 128)
                        builder.addRoute("::", 0)
                        try {
                            builder.allowFamily(OsConstants.AF_INET6)
                        } catch (_: Exception) {
                        }
                        ipv6RouteOk = true
                    } catch (_: Exception) {
                        ipv6RouteOk = false
                    }
                }
                try {
                    // Keep our app off the VPN loop so UDP to node works
                    builder.addDisallowedApplication(packageName)
                } catch (_: Exception) {
                }
                val pfd = try {
                    builder.establish()
                } catch (e: Exception) {
                    report(false, "VpnService.establish failed: ${e.message}", allowReconnect = false)
                    running.set(false)
                    stopForeground(STOP_FOREGROUND_REMOVE)
                    stopSelf()
                    return@thread
                }
                if (pfd == null) {
                    report(
                        false,
                        "VpnService.establish returned null — VPN permission or policy blocked TUN",
                        allowReconnect = false,
                    )
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
                    val canRetry = wantsIdleAutoReconnect()
                    report(
                        false,
                        "Could not protect UDP to $host:$port after VPN establish " +
                            "(${e.message}) — residual traffic would blackhole",
                        allowReconnect = canRetry,
                    )
                    running.set(false)
                    if (!canRetry) {
                        stopForeground(STOP_FOREGROUND_REMOVE)
                        stopSelf()
                    }
                    return@thread
                }
                // Close handshake socket; dataplane uses protected dataSock only
                try {
                    sock.close()
                } catch (_: Exception) {
                }

                isSessionActive = true
                activeVpnIp = session.vpnIp
                // Residual IPv4 capture only when fullTunnel + Settings residual_ipv4 ON
                val residualCapture = fullTunnel && residualIpv4
                activeIpv6Protected = when {
                    !fullTunnel || !residualCapture -> null
                    residualIpv6 -> ipv6RouteOk
                    else -> false
                }
                startForeground(NOTIFICATION_ID, buildNotification(sessionName, connecting = false))
                val msg = when {
                    !fullTunnel ->
                        "Connected — RPT tunnel up (VPN IP ${session.vpnIp})"
                    !residualIpv4 ->
                        "Connected — session only; residual IPv4 off (VPN IP ${session.vpnIp})"
                    residualIpv6 && ipv6RouteOk ->
                        "Connected — VPN active; IPv6 ISP path blocked (VPN IP ${session.vpnIp})"
                    else ->
                        // IPv4 residual capture; ISP IPv6 not claimed protected on IPv4-only TUN
                        "Connected — IPv4 via VPN; IPv6 not protected (VPN IP ${session.vpnIp})"
                }
                report(
                    true,
                    msg,
                    session.vpnIp,
                    ipv6Protected = if (residualCapture) activeIpv6Protected else null,
                )

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
                // Cover only when privacy-scale traffic shaping is ON (lean default OFF).
                val coverThread = thread(name = "rpt-cover", isDaemon = true) {
                    val interval = RptTrafficShape.PRODUCT_COVER_INTERVAL_MS.coerceAtLeast(200L)
                    while (running.get()) {
                        try {
                            if (!RptTrafficShape.productCover) {
                                // Lean residual: sleep long; no cover AEAD/UDP.
                                Thread.sleep(interval)
                                continue
                            }
                            Thread.sleep(interval)
                            if (!running.get() || !RptTrafficShape.productCover) continue
                            val now = System.currentTimeMillis()
                            if (now - lastCoverMs.get() >= interval) {
                                val wire = engine.sealAndWrapCover()
                                dataSock.send(DatagramPacket(wire, wire.size))
                                lastCoverMs.set(now)
                            }
                        } catch (_: Exception) {
                            if (!running.get()) break
                        }
                    }
                }
                // Lean RPT2 KEEPALIVE while tunnel is up — independent of TUN data
                // and independent of traffic-shape cover (node idle prune ~60s).
                val kaFailStreak = AtomicLong(0)
                val keepaliveThread = thread(name = "rpt-keepalive", isDaemon = true) {
                    val intervalMs = KEEPALIVE_INTERVAL_MS
                    while (running.get()) {
                        try {
                            Thread.sleep(intervalMs)
                            if (!running.get()) break
                            val wire = engine.sealAndWrapKeepalive()
                            dataSock.send(DatagramPacket(wire, wire.size))
                            kaFailStreak.set(0)
                        } catch (_: Exception) {
                            // Sustained KA send failure while user still wants residual
                            // → tear TUN so idle auto-reconnect can re-HELLO.
                            val fails = kaFailStreak.incrementAndGet()
                            if (!running.get()) break
                            if (fails >= KEEPALIVE_FAIL_STREAK_RECONNECT && wantsIdleAutoReconnect()) {
                                running.set(false)
                                try {
                                    pfd.close()
                                } catch (_: Exception) {
                                }
                                break
                            }
                        }
                    }
                }
                tunToUdp.join(Long.MAX_VALUE)
                udpToTun.join(2_000)
                coverThread.join(500)
                keepaliveThread.join(500)
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
                val canRetry = wantsIdleAutoReconnect()
                report(
                    false,
                    "VPN tunnel error: ${e.message ?: e.javaClass.simpleName}",
                    allowReconnect = canRetry,
                )
            } finally {
                try {
                    sock.close()
                } catch (_: Exception) {
                }
                val wasUserStop = userStopped.get()
                val hadLiveSession = isSessionActive
                running.set(false)
                isSessionActive = false
                activeVpnIp = ""
                activeIpv6Protected = null
                // Drop TUN so a later re-establish is clean (idle reconnect or next Connect).
                val leftover = tun
                tun = null
                try {
                    leftover?.close()
                } catch (_: Exception) {
                }
                when {
                    wasUserStop -> {
                        // stopTunnel already tearing down; do not resurrect.
                    }
                    wantsIdleAutoReconnect() -> {
                        // Unexpected drop (or failed connect with still-desired): backoff re-HELLO.
                        scheduleIdleReconnect(
                            if (hadLiveSession) "session dropped" else "connect incomplete",
                        )
                    }
                    else -> {
                        desiredConnected = false
                        StartupPrefs.setDesiredConnected(this@RptVpnService, false)
                        try {
                            stopForeground(STOP_FOREGROUND_REMOVE)
                        } catch (_: Exception) {
                        }
                        try {
                            stopSelf()
                        } catch (_: Exception) {
                        }
                    }
                }
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
        reconnectGeneration.incrementAndGet()
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
        StartupPrefs.setDesiredConnected(this, false)
        reconnectGeneration.incrementAndGet()
        stopTunnel()
        super.onRevoke()
    }

    private fun buildNotification(
        session: String,
        connecting: Boolean,
        reconnecting: Boolean = false,
    ): Notification {
        val channelId = "rpt_vpn"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val nm = getSystemService(NotificationManager::class.java)
            nm.createNotificationChannel(
                NotificationChannel(channelId, "Restore Privacy VPN", NotificationManager.IMPORTANCE_LOW),
            )
        }
        val text = when {
            reconnecting ->
                "Reconnecting residual tunnel… (auto connect if idle)"
            connecting ->
                "Connecting RPT tunnel…"
            else ->
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
        /** Product residual monopins (must match Flutter country_select / multihop catalog). */
        /** Default residual entry = Germany monopin. */
        const val PRODUCT_ENTRY_HOST = "178.105.187.178"
        const val PRODUCT_ICELAND_HOST = "82.221.101.241"
        const val PRODUCT_DE_HOST = "178.105.187.178"
        /** Multi-hop exit = Germany (same monopin as DE entry). */
        const val PRODUCT_EXIT_HOST = "178.105.187.178"
        const val PRODUCT_US_HOST = "5.161.242.85"
        /** Retired Romania monopin — never dial; map only for heal of stale strings. */
        const val PRODUCT_RO_LEGACY_HOST = "185.146.232.107"

        /**
         * ElGamal public pin basename for residual HELLO from dial host.
         * IS → node_elgamal.pub; DE → de_node_elgamal.pub; retired US → de_node_elgamal.pub.
         */
        @JvmStatic
        fun residualNodePubNameForHost(host: String): String {
            val h = host.trim()
            if (h == PRODUCT_DE_HOST || h.endsWith(PRODUCT_DE_HOST)
                || h == PRODUCT_EXIT_HOST || h.endsWith(PRODUCT_EXIT_HOST)
            ) {
                return "de_node_elgamal.pub"
            }
            // Retired US monopin — heal to DE pin
            if (h == PRODUCT_US_HOST || h.endsWith(PRODUCT_US_HOST)) {
                return "de_node_elgamal.pub"
            }
            if (h == PRODUCT_ICELAND_HOST || h.endsWith(PRODUCT_ICELAND_HOST)) {
                return "node_elgamal.pub"
            }
            // Stale RO host: exit pin file holds DE material after 0.5.7 reassign
            if (h == PRODUCT_RO_LEGACY_HOST || h.endsWith(PRODUCT_RO_LEGACY_HOST)) {
                return "exit_node_elgamal.pub"
            }
            return "node_elgamal.pub"
        }

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
        /** Privacy-scale: traffic shaping (pad/cover/jitter); default lean OFF. */
        const val EXTRA_TRAFFIC_SHAPE = "trafficShape"
        /** Privacy-scale: outer QUIC-mimic wrap; default lean OFF. */
        const val EXTRA_OUTER_OBFS = "outerObfuscation"
        const val EXTRA_RECEIVER = "receiver"
        const val EXTRA_MESSAGE = "message"
        const val EXTRA_VPN_IP = "vpnIp"
        const val EXTRA_IPV6_PROTECTED = "ipv6Protected"
        /** True while HELLO/TUN is still in progress (not residual success). */
        const val EXTRA_CONNECTING = "connecting"
        const val RESULT_OK = 0
        const val RESULT_ERR = 1
        private const val NOTIFICATION_ID = 0x5250
        /**
         * Lean RPT2 KEEPALIVE period while residual tunnel is up.
         * Must stay under node DEFAULT_SESSION_IDLE_SEC (~60s). Not cover traffic.
         * Mirrors client residual_keepalive_policy.RESIDUAL_KEEPALIVE_INTERVAL_SEC.
         */
        const val KEEPALIVE_INTERVAL_MS: Long = 25_000L

        /**
         * Consecutive KEEPALIVE send failures before tearing the TUN so idle
         * auto-reconnect can re-HELLO (only when that Settings switch is on).
         */
        const val KEEPALIVE_FAIL_STREAK_RECONNECT: Long = 3L

        /**
         * Exponential backoff for idle auto-reconnect (attempt is 1-based).
         * 2s, 4s, 8s, 16s, 32s, then 60s cap. Mirrors Dart residualAutoReconnectBackoffMs.
         */
        @JvmStatic
        fun reconnectBackoffMs(attempt: Int): Long {
            val a = if (attempt < 1) 1 else attempt
            val exp = (a - 1).coerceIn(0, 5)
            val ms = 2_000L * (1L shl exp)
            return if (ms > 60_000L) 60_000L else ms
        }

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
        /**
         * @return Triple(sessionActiveSuccess, keepFlags, message)
         * When not yet residual, first=false so Flutter keeps Connecting…
         */
        fun alreadyRunningConnectDecision(
            isSessionActive: Boolean,
            vpnIp: String,
            ipv6Protected: Boolean? = activeIpv6Protected,
        ): Triple<Boolean, Boolean, String> {
            val ip = vpnIp.trim()
            if (!isSessionActive) {
                return Triple(
                    false,
                    true,
                    "VPN still connecting — waiting for full tunnel (RPT2 + system VPN)…",
                )
            }
            val msg = when {
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
            return Triple(true, true, msg)
        }
    }
}

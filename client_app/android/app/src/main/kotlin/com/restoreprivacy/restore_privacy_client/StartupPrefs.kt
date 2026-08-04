package com.restoreprivacy.restore_privacy_client

import android.content.ComponentName
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build

/**
 * Enable/disable [BootLaunchReceiver] so the app can start after device boot
 * when the user opts into "Run at device startup".
 */
object StartupPrefs {
    const val PREFS = "rpt_product_settings"
    const val KEY_RUN_AT_STARTUP = "run_at_startup"
    const val KEY_AUTOCONNECT = "autoconnect_on_launch"
    /** Re-connect residual after unexpected drop while user still wants VPN. */
    const val KEY_AUTO_CONNECT_IF_IDLE = "auto_connect_if_idle"
    /** Persisted "user wants tunnel up" for sticky / process restart + idle reconnect. */
    const val KEY_DESIRED_CONNECTED = "desired_connected"
    const val KEY_LAST_HOST = "last_connect_host"
    const val KEY_LAST_PORT = "last_connect_port"
    const val KEY_LAST_FULL_TUNNEL = "last_connect_full_tunnel"
    const val KEY_LAST_SESSION = "last_connect_session"
    const val KEY_LAST_TRAFFIC_SHAPE = "last_connect_traffic_shape"
    const val KEY_LAST_OUTER_OBFS = "last_connect_outer_obfs"
    /** Residual IPv4 is product always-on (key kept for migrate only). */
    const val KEY_RESIDUAL_IPV4 = "residual_ipv4"
    /** Residual IPv6 ISP-leak protection; default ON when unset. */
    const val KEY_RESIDUAL_IPV6 = "residual_ipv6"
    /** Product policy: residual IPv4 capture is never user-off. */
    const val RESIDUAL_IPV4_ALWAYS_ON = true

    fun setRunAtStartup(context: Context, enabled: Boolean): String {
        return try {
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit()
                .putBoolean(KEY_RUN_AT_STARTUP, enabled)
                .apply()
            val pm = context.packageManager
            val component = ComponentName(context, BootLaunchReceiver::class.java)
            val state = if (enabled) {
                PackageManager.COMPONENT_ENABLED_STATE_ENABLED
            } else {
                PackageManager.COMPONENT_ENABLED_STATE_DISABLED
            }
            pm.setComponentEnabledSetting(
                component,
                state,
                PackageManager.DONT_KILL_APP,
            )
            if (enabled) "enabled" else "disabled"
        } catch (e: Exception) {
            "failed:${e.message}"
        }
    }

    fun isRunAtStartupEnabled(context: Context): Boolean {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getBoolean(KEY_RUN_AT_STARTUP, false)
    }

    fun setAutoconnect(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_AUTOCONNECT, enabled)
            .apply()
    }

    fun isAutoconnectEnabled(context: Context): Boolean {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getBoolean(KEY_AUTOCONNECT, false)
    }

    fun setAutoConnectIfIdle(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_AUTO_CONNECT_IF_IDLE, enabled)
            .apply()
        // Mirror Flutter SharedPreferences so Dart load() sees the same value.
        try {
            context.getSharedPreferences("FlutterSharedPreferences", Context.MODE_PRIVATE)
                .edit()
                .putBoolean("flutter.$KEY_AUTO_CONNECT_IF_IDLE", enabled)
                .apply()
        } catch (_: Exception) {
        }
    }

    fun autoConnectIfIdleEnabled(context: Context): Boolean {
        return dualStackPref(context, KEY_AUTO_CONNECT_IF_IDLE, default = false)
    }

    fun setDesiredConnected(context: Context, desired: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_DESIRED_CONNECTED, desired)
            .apply()
    }

    fun isDesiredConnected(context: Context): Boolean {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getBoolean(KEY_DESIRED_CONNECTED, false)
    }

    fun saveLastConnect(
        context: Context,
        host: String,
        port: Int,
        fullTunnel: Boolean,
        session: String,
        trafficShape: Boolean,
        outerObfs: Boolean,
    ) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_LAST_HOST, host)
            .putInt(KEY_LAST_PORT, port)
            .putBoolean(KEY_LAST_FULL_TUNNEL, fullTunnel)
            .putString(KEY_LAST_SESSION, session)
            .putBoolean(KEY_LAST_TRAFFIC_SHAPE, trafficShape)
            .putBoolean(KEY_LAST_OUTER_OBFS, outerObfs)
            .apply()
    }

    data class LastConnect(
        val host: String,
        val port: Int,
        val fullTunnel: Boolean,
        val session: String,
        val trafficShape: Boolean,
        val outerObfs: Boolean,
    )

    fun loadLastConnect(context: Context, defaultHost: String): LastConnect {
        val p = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        return LastConnect(
            host = p.getString(KEY_LAST_HOST, null)?.trim().orEmpty().ifEmpty { defaultHost },
            port = p.getInt(KEY_LAST_PORT, 44044).let { if (it in 1..65535) it else 44044 },
            fullTunnel = p.getBoolean(KEY_LAST_FULL_TUNNEL, true),
            session = p.getString(KEY_LAST_SESSION, null)?.trim().orEmpty().ifEmpty { "Privacy Restored" },
            trafficShape = p.getBoolean(KEY_LAST_TRAFFIC_SHAPE, false),
            outerObfs = p.getBoolean(KEY_LAST_OUTER_OBFS, false),
        )
    }

    /**
     * Residual IPv4 is always ON (product policy) — ignore stale false prefs.
     */
    fun residualIpv4Enabled(context: Context): Boolean {
        return RESIDUAL_IPV4_ALWAYS_ON
    }

    fun residualIpv6Enabled(context: Context): Boolean {
        return dualStackPref(context, KEY_RESIDUAL_IPV6, default = true)
    }

    fun setResidualStack(context: Context, ipv4: Boolean?, ipv6: Boolean?) {
        val ed = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
        // Always persist residual IPv4 ON so stale false cannot disable capture.
        ed.putBoolean(KEY_RESIDUAL_IPV4, RESIDUAL_IPV4_ALWAYS_ON)
        if (ipv6 != null) ed.putBoolean(KEY_RESIDUAL_IPV6, ipv6)
        ed.apply()
        // Mirror into Flutter SharedPreferences so Dart load() sees the same values.
        try {
            val flutterPrefs = context.getSharedPreferences(
                "FlutterSharedPreferences",
                Context.MODE_PRIVATE,
            )
            val fed = flutterPrefs.edit()
            fed.putBoolean("flutter.$KEY_RESIDUAL_IPV4", RESIDUAL_IPV4_ALWAYS_ON)
            if (ipv6 != null) fed.putBoolean("flutter.$KEY_RESIDUAL_IPV6", ipv6)
            fed.apply()
        } catch (_: Exception) {
        }
    }

    private fun dualStackPref(context: Context, key: String, default: Boolean): Boolean {
        val native = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (native.contains(key)) {
            return native.getBoolean(key, default)
        }
        // Flutter shared_preferences plugin prefixes keys with "flutter."
        try {
            val flutterPrefs = context.getSharedPreferences(
                "FlutterSharedPreferences",
                Context.MODE_PRIVATE,
            )
            val fk = "flutter.$key"
            if (flutterPrefs.contains(fk)) {
                return flutterPrefs.getBoolean(fk, default)
            }
        } catch (_: Exception) {
        }
        return default
    }
}

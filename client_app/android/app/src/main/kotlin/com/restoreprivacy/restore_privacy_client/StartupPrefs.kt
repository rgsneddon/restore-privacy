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

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
}

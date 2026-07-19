package com.restoreprivacy.restore_privacy_client

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build

/**
 * Launches [MainActivity] after boot when the user enabled run-at-startup.
 * Autoconnect is handled by Flutter Settings once the activity opens.
 */
class BootLaunchReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        val action = intent?.action ?: return
        if (action != Intent.ACTION_BOOT_COMPLETED &&
            action != Intent.ACTION_LOCKED_BOOT_COMPLETED &&
            action != Intent.ACTION_MY_PACKAGE_REPLACED
        ) {
            return
        }
        if (!StartupPrefs.isRunAtStartupEnabled(context)) {
            return
        }
        val launch = Intent(context, MainActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            putExtra("from_boot", true)
        }
        try {
            context.startActivity(launch)
        } catch (_: Exception) {
            // OEM may block background activity starts; preference still honored next manual open
        }
    }
}

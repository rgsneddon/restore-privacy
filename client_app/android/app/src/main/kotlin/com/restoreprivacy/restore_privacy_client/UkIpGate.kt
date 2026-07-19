package com.restoreprivacy.restore_privacy_client

/**
 * Legacy UK geo gate — **removed from product Connect** (privacy: no third-party geo).
 * Retained as a no-network stub so any accidental call cannot phone home.
 * Always allows; does not open HTTPS.
 */
object UkIpGate {
    const val DENIED_MESSAGE =
        "Access denied: Restore Privacy is only available when your public IP " +
            "is located in the United Kingdom. Your current network location is not UK."

    const val LOOKUP_FAILED_MESSAGE =
        "Access denied: could not verify that your public IP is in the United Kingdom. " +
            "Check your network connection and try again."

    data class Result(
        val allowed: Boolean,
        val message: String,
        val countryCode: String = "",
        val publicIp: String = "",
    )

    /** No-op: product Connect never requires UK geo. Never performs network I/O. */
    fun checkUkPublicIp(payloadProvider: (() -> org.json.JSONObject)? = null): Result {
        // Intentionally ignore payloadProvider; no network I/O.
        return Result(
            allowed = true,
            message = "UK geo gate disabled (no third-party lookup)",
            countryCode = "",
            publicIp = "",
        )
    }
}

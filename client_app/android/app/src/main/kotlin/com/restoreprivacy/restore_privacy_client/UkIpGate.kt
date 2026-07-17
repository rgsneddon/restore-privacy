package com.restoreprivacy.restore_privacy_client

import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.Locale

/**
 * UK public-IP security gate (mirrors Python client.uk_gate).
 * Only United Kingdom public IPs may connect; fail closed otherwise.
 */
object UkIpGate {
    const val DENIED_MESSAGE =
        "Access denied: Restore Privacy is only available when your public IP " +
            "is located in the United Kingdom. Your current network location is not UK."

    const val LOOKUP_FAILED_MESSAGE =
        "Access denied: could not verify that your public IP is in the United Kingdom. " +
            "Check your network connection and try again."

    private val UK_CODES = setOf("GB", "UK", "GG", "JE", "IM")
    private const val GEO_URL = "https://ipapi.co/json/"

    data class Result(
        val allowed: Boolean,
        val message: String,
        val countryCode: String = "",
        val publicIp: String = "",
    )

    fun normalizeCountryCode(raw: String?): String {
        if (raw.isNullOrBlank()) return ""
        val s = raw.trim().uppercase(Locale.US)
        if (s in setOf(
                "UNITED KINGDOM",
                "GREAT BRITAIN",
                "ENGLAND",
                "SCOTLAND",
                "WALES",
                "NORTHERN IRELAND",
            )
        ) {
            return "GB"
        }
        return if (s.length >= 2) s.substring(0, 2) else s
    }

    fun isUkCountry(code: String): Boolean = normalizeCountryCode(code) in UK_CODES

    /** Pure decision from geo JSON (testable without network). */
    fun evaluateGeoPayload(json: JSONObject?): Result {
        if (json == null || json.length() == 0) {
            return Result(false, LOOKUP_FAILED_MESSAGE)
        }
        if (json.optBoolean("error", false)) {
            return Result(false, LOOKUP_FAILED_MESSAGE)
        }
        var code = ""
        for (key in listOf("country_code", "countryCode", "country")) {
            if (json.has(key) && !json.isNull(key)) {
                val v = json.optString(key, "")
                code = normalizeCountryCode(v)
                if (code.isNotEmpty()) break
            }
        }
        val publicIp = when {
            json.has("ip") -> json.optString("ip", "")
            json.has("query") -> json.optString("query", "")
            else -> ""
        }
        if (code.isEmpty()) {
            return Result(false, LOOKUP_FAILED_MESSAGE, publicIp = publicIp)
        }
        return if (isUkCountry(code)) {
            Result(true, "UK location verified", countryCode = code, publicIp = publicIp)
        } else {
            Result(false, DENIED_MESSAGE, countryCode = code, publicIp = publicIp)
        }
    }

    /** Live check; inject [payloadProvider] in tests. */
    fun checkUkPublicIp(payloadProvider: (() -> JSONObject)? = null): Result {
        return try {
            val json = if (payloadProvider != null) {
                payloadProvider()
            } else {
                fetchGeoJson()
            }
            evaluateGeoPayload(json)
        } catch (_: Exception) {
            Result(false, LOOKUP_FAILED_MESSAGE)
        }
    }

    private fun fetchGeoJson(): JSONObject {
        val conn = (URL(GEO_URL).openConnection() as HttpURLConnection).apply {
            connectTimeout = 8000
            readTimeout = 8000
            requestMethod = "GET"
            setRequestProperty("User-Agent", "restore-privacy-client/0.0.4")
            setRequestProperty("Accept", "application/json")
        }
        try {
            val code = conn.responseCode
            val stream = if (code in 200..299) conn.inputStream else conn.errorStream
            val body = stream?.bufferedReader()?.use { it.readText() } ?: ""
            if (code !in 200..299) {
                throw IllegalStateException("geo HTTP $code")
            }
            return JSONObject(body)
        } finally {
            conn.disconnect()
        }
    }
}

package com.restoreprivacy.restore_privacy_client

import java.nio.ByteBuffer
import java.security.SecureRandom

/**
 * Product traffic-shape helpers — mirrors `node/traffic_shape.py`.
 *
 * Wire (AEAD plaintext):
 *   Real padded: RPTP || u16_be(len) || plain || random_pad
 *   Cover dummy: RPTC || random_bytes
 *
 * Product residual defaults: padding on (bucket 128), cover available.
 */
object RptTrafficShape {
    val PAD_MAGIC: ByteArray = byteArrayOf(0x52, 0x50, 0x54, 0x50) // RPTP
    val COVER_MAGIC: ByteArray = byteArrayOf(0x52, 0x50, 0x54, 0x43) // RPTC
    const val PRODUCT_PAD_BUCKET: Int = 128
    const val PRODUCT_COVER_SIZE: Int = 128
    const val PRODUCT_COVER_INTERVAL_MS: Long = 2000L
    /** Bounded send-side delay (ms); matches Python product policy (jitter_ms_max=40). */
    const val PRODUCT_JITTER_MS_MAX: Int = 40
    const val PRODUCT_PADDING: Boolean = true
    const val PRODUCT_COVER: Boolean = true

    private val rnd = SecureRandom()

    /** Product residual send jitter (0…PRODUCT_JITTER_MS_MAX). DATA path only. */
    fun applySendJitter() {
        val maxMs = PRODUCT_JITTER_MS_MAX
        if (maxMs <= 0) return
        val ms = rnd.nextInt(maxMs + 1)
        if (ms > 0) {
            try {
                Thread.sleep(ms.toLong())
            } catch (_: InterruptedException) {
                Thread.currentThread().interrupt()
            }
        }
    }

    fun padPayload(plain: ByteArray, bucket: Int = PRODUCT_PAD_BUCKET): ByteArray {
        require(plain.size in 0..65535) { "plain too large for u16 length" }
        val b = bucket.coerceIn(16, 2048)
        val lenBe = ByteBuffer.allocate(2).putShort(plain.size.toShort()).array()
        val body = lenBe + plain
        val padLen = (b - (body.size % b)) % b
        val pad = if (padLen > 0) ByteArray(padLen).also { rnd.nextBytes(it) } else ByteArray(0)
        return PAD_MAGIC + body + pad
    }

    fun makeCoverPayload(size: Int = PRODUCT_COVER_SIZE): ByteArray {
        val n = size.coerceIn(16, 2048)
        val noise = ByteArray(n - COVER_MAGIC.size).also { rnd.nextBytes(it) }
        return COVER_MAGIC + noise
    }

    /** Returns (payload, isCover). Unmarked blobs treated as raw IP (compat). */
    fun unpadPayload(blob: ByteArray): Pair<ByteArray, Boolean> {
        if (blob.size >= 4 && blob.copyOfRange(0, 4).contentEquals(COVER_MAGIC)) {
            return ByteArray(0) to true
        }
        if (blob.size < 4 || !blob.copyOfRange(0, 4).contentEquals(PAD_MAGIC)) {
            return blob to false
        }
        val rest = blob.copyOfRange(4, blob.size)
        if (rest.size < 2) throw IllegalArgumentException("truncated padded payload")
        val n = ((rest[0].toInt() and 0xff) shl 8) or (rest[1].toInt() and 0xff)
        if (rest.size < 2 + n) throw IllegalArgumentException("padded payload length exceeds buffer")
        return rest.copyOfRange(2, 2 + n) to false
    }

    fun prepareOutbound(ipPacket: ByteArray, padding: Boolean = PRODUCT_PADDING): ByteArray {
        return if (padding) padPayload(ipPacket) else ipPacket
    }

    fun interpretInbound(blob: ByteArray): Pair<ByteArray?, Boolean> {
        val (plain, isCover) = unpadPayload(blob)
        return if (isCover) null to true else plain to false
    }
}

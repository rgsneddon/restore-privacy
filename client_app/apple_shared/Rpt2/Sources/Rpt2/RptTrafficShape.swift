import Foundation

/// Product traffic-shape helpers — mirrors `node/traffic_shape.py`.
///
/// Wire (AEAD plaintext):
///   Real padded: RPTP || u16_be(len) || plain || random_pad
///   Cover dummy: RPTC || random_bytes
public enum RptTrafficShape {
    public static let padMagic = Data("RPTP".utf8)
    public static let coverMagic = Data("RPTC".utf8)
    public static let productPadBucket: Int = 128
    public static let productCoverSize: Int = 128
    public static let productCoverIntervalS: TimeInterval = 2.0
    public static let productPadding: Bool = true
    public static let productCover: Bool = true

    public static func padPayload(_ plain: Data, bucket: Int = productPadBucket) throws -> Data {
        guard plain.count <= 65535 else {
            throw RptProtocol.ProtocolError("plain too large for u16 length")
        }
        let b = max(16, min(2048, bucket))
        var lenBe = UInt16(plain.count).bigEndian
        var body = Data(bytes: &lenBe, count: 2)
        body.append(plain)
        let padLen = (b - (body.count % b)) % b
        var out = padMagic
        out.append(body)
        if padLen > 0 {
            var pad = Data(count: padLen)
            _ = pad.withUnsafeMutableBytes {
                SecRandomCopyBytes(kSecRandomDefault, padLen, $0.baseAddress!)
            }
            out.append(pad)
        }
        return out
    }

    public static func makeCoverPayload(size: Int = productCoverSize) -> Data {
        let n = max(16, min(2048, size))
        var noise = Data(count: n - coverMagic.count)
        _ = noise.withUnsafeMutableBytes {
            SecRandomCopyBytes(kSecRandomDefault, noise.count, $0.baseAddress!)
        }
        var out = coverMagic
        out.append(noise)
        return out
    }

    /// Returns (payload, isCover). Unmarked blobs treated as raw IP (compat).
    public static func unpadPayload(_ blob: Data) throws -> (Data, Bool) {
        if blob.count >= 4, blob.prefix(4) == coverMagic {
            return (Data(), true)
        }
        if blob.count < 4 || blob.prefix(4) != padMagic {
            return (blob, false)
        }
        let rest = blob.dropFirst(4)
        guard rest.count >= 2 else {
            throw RptProtocol.ProtocolError("truncated padded payload")
        }
        let n = Int(rest[rest.startIndex]) << 8 | Int(rest[rest.startIndex + 1])
        guard rest.count >= 2 + n else {
            throw RptProtocol.ProtocolError("padded payload length exceeds buffer")
        }
        let start = rest.index(rest.startIndex, offsetBy: 2)
        let end = rest.index(start, offsetBy: n)
        return (Data(rest[start..<end]), false)
    }

    public static func prepareOutbound(_ ipPacket: Data, padding: Bool = productPadding) throws -> Data {
        if padding { return try padPayload(ipPacket) }
        return ipPacket
    }

    public static func interpretInbound(_ blob: Data) throws -> (Data?, Bool) {
        let (plain, isCover) = try unpadPayload(blob)
        if isCover { return (nil, true) }
        return (plain, false)
    }
}

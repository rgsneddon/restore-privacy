import Foundation
import CryptoKit

/// Outer QUIC-mimic layer — mirrors `node/obfuscation.py`.
///
/// Product residual UDP is not bare RPT2 alone; wrap outbound / unwrap inbound.
public enum RptObfuscation {
    public static let obfsVersion: UInt32 = 0x5250_5431 // 'RPT1'
    private static let rptMagic = Data("RPT2".utf8)
    /// Same public product key material as Python `_PRODUCT_OBFS_KEY` (32 bytes).
    private static let productObfsKey: Data = {
        var k = Data("RPT-OBFS-LAYER-v1".utf8)
        k.append(Data(repeating: 0, count: 7))
        k.append(contentsOf: [0x9a, 0x3c, 0x7e, 0x11, 0xd4, 0x55, 0x88, 0x02])
        return k
    }()

    public static let productObfsEnabled: Bool = true

    public static func looksLikeBareRpt(_ data: Data) -> Bool {
        data.count >= 5 && data.prefix(4) == rptMagic
    }

    public static func looksLikeObfs(_ data: Data) -> Bool {
        guard data.count >= 1 + 4 + 1 + 8 + 1 + 2 + 12 else { return false }
        guard (data[0] & 0xC0) == 0xC0 else { return false }
        let ver = data.subdata(in: 1..<5).withUnsafeBytes { $0.load(as: UInt32.self).bigEndian }
        return ver == obfsVersion
    }

    private static func streamMask(nonce: Data, length: Int) -> Data {
        var out = Data()
        var counter: UInt32 = 0
        while out.count < length {
            var material = productObfsKey
            material.append(nonce)
            var c = counter.bigEndian
            material.append(Data(bytes: &c, count: 4))
            let h = Data(SHA256.hash(data: material))
            out.append(h)
            counter += 1
        }
        return Data(out.prefix(length))
    }

    private static func xor(_ data: Data, mask: Data) -> Data {
        precondition(mask.count >= data.count)
        var out = Data(count: data.count)
        for i in 0..<data.count {
            out[i] = data[i] ^ mask[i]
        }
        return out
    }

    public static func wrapFrame(_ inner: Data) throws -> Data {
        guard !inner.isEmpty else {
            throw RptProtocol.ProtocolError("empty inner frame")
        }
        var flagsByte: UInt8 = 0xC0
        var r: UInt8 = 0
        _ = withUnsafeMutableBytes(of: &r) { SecRandomCopyBytes(kSecRandomDefault, 1, $0.baseAddress!) }
        flagsByte |= (r & 0x0F)
        var dcid = Data(count: 8)
        _ = dcid.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, 8, $0.baseAddress!) }
        var nonce = Data(count: 12)
        _ = nonce.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, 12, $0.baseAddress!) }
        let mask = streamMask(nonce: nonce, length: inner.count)
        let body = xor(inner, mask: mask)
        guard body.count <= 0xFFFF else {
            throw RptProtocol.ProtocolError("inner frame too large")
        }
        var out = Data()
        out.append(flagsByte)
        var ver = obfsVersion.bigEndian
        out.append(Data(bytes: &ver, count: 4))
        out.append(8) // dcid_len
        out.append(dcid)
        out.append(0) // scid_len
        var plen = UInt16(body.count).bigEndian
        out.append(Data(bytes: &plen, count: 2))
        out.append(nonce)
        out.append(body)
        return out
    }

    public static func unwrapFrame(_ outer: Data, allowBare: Bool = true) throws -> Data {
        if allowBare, looksLikeBareRpt(outer) { return outer }
        guard looksLikeObfs(outer) else {
            throw RptProtocol.ProtocolError("not an RPT obfuscated frame")
        }
        var o = 0
        o += 1 // flags
        o += 4 // version
        let dcidLen = Int(outer[o]); o += 1
        guard dcidLen == 8 else {
            throw RptProtocol.ProtocolError("unexpected dcid_len")
        }
        o += dcidLen
        let scidLen = Int(outer[o]); o += 1
        o += scidLen
        guard o + 2 + 12 <= outer.count else {
            throw RptProtocol.ProtocolError("truncated outer")
        }
        let plen = Int(outer[o]) << 8 | Int(outer[o + 1])
        o += 2
        let nonce = outer.subdata(in: o..<(o + 12))
        o += 12
        guard o + plen <= outer.count else {
            throw RptProtocol.ProtocolError("truncated body")
        }
        let body = outer.subdata(in: o..<(o + plen))
        let mask = streamMask(nonce: nonce, length: plen)
        return xor(body, mask: mask)
    }

    public static func maybeWrap(_ inner: Data, enabled: Bool = productObfsEnabled) throws -> Data {
        if enabled { return try wrapFrame(inner) }
        return inner
    }

    public static func maybeUnwrap(_ outer: Data, enabled: Bool = productObfsEnabled) throws -> Data {
        try unwrapFrame(outer, allowBare: true)
    }
}

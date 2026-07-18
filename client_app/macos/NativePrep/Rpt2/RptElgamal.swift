import Foundation
import CryptoKit

/// ElGamal over RFC 3526 2048-bit MODP group — mirrors `node/elgamal.py`.
public enum RptElgamal {
    public static let P: BigUInt = BigUInt(
        "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1" +
        "29024E088A67CC74020BBEA63B139B22514A08798E3404DD" +
        "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245" +
        "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED" +
        "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D" +
        "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F" +
        "83655D23DCA3AD961C62F356208552BB9ED529077096966D" +
        "670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B" +
        "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9" +
        "DE2BCBF6955817183995497CEA956AE515D2261898FA0510" +
        "15728E5A8AACAA68FFFFFFFFFFFFFFFF",
        radix: 16
    )!
    public static let G: BigUInt = 2
    public static let Q: BigUInt = (P - 1) / 2

    public static func intToBytes(_ value: BigUInt, length: Int = 256) -> Data {
        var raw = value.serialize()
        if raw.count > length {
            raw = Data(raw.suffix(length))
        } else if raw.count < length {
            raw = Data(repeating: 0, count: length - raw.count) + raw
        }
        return raw
    }

    public static func bytesToInt(_ data: Data) -> BigUInt {
        BigUInt(data)
    }

    public static func randomExponent() -> BigUInt {
        while true {
            var buf = Data(count: 256)
            _ = buf.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, 256, $0.baseAddress!) }
            let x = BigUInt(buf) % Q
            if x >= 1 && x < Q { return x }
        }
    }

    public static func encodeMessage(_ plaintext: Data) throws -> BigUInt {
        guard plaintext.count <= 240 else { throw RptProtocol.ProtocolError("plaintext too long for ElGamal") }
        var pad = Data(count: 16)
        _ = pad.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, 16, $0.baseAddress!) }
        var blob = Data([UInt8(plaintext.count)])
        blob.append(plaintext)
        blob.append(pad)
        let m = bytesToInt(blob)
        guard m < P else { throw RptProtocol.ProtocolError("encoded message out of range") }
        return m
    }

    public static func decodeMessage(_ m: BigUInt) throws -> Data {
        var compact = m.serialize()
        if compact.isEmpty { throw RptProtocol.ProtocolError("empty message") }
        var L = Int(compact[0])
        if L > 240 || compact.count < 1 + L {
            compact = intToBytes(m, length: 256)
            while compact.first == 0 { compact.removeFirst() }
            if compact.isEmpty { throw RptProtocol.ProtocolError("empty message") }
            L = Int(compact[0])
            guard compact.count >= 1 + L else { throw RptProtocol.ProtocolError("truncated message") }
        }
        return Data(compact.dropFirst().prefix(L))
    }

    public struct PublicKey {
        public let y: BigUInt
        public init(y: BigUInt) { self.y = y }

        public func export() -> Data { intToBytes(y, length: 256) }

        public static func importBytes(_ data: Data) throws -> PublicKey {
            guard data.count == 256 else { throw RptProtocol.ProtocolError("ElGamal public key must be 256 bytes") }
            let y = bytesToInt(data)
            guard y > 1 && y < P else { throw RptProtocol.ProtocolError("invalid public key") }
            return PublicKey(y: y)
        }
    }

    public struct Ciphertext {
        public let c1: BigUInt
        public let c2: BigUInt

        public func export() -> Data {
            intToBytes(c1, length: 256) + intToBytes(c2, length: 256)
        }

        public static func importBytes(_ data: Data) throws -> Ciphertext {
            guard data.count == 512 else { throw RptProtocol.ProtocolError("ciphertext must be 512 bytes") }
            return Ciphertext(c1: bytesToInt(data.prefix(256)), c2: bytesToInt(data.suffix(256)))
        }
    }

    public static func encrypt(publicKey: PublicKey, plaintext: Data) throws -> Ciphertext {
        let m = try encodeMessage(plaintext)
        let k = randomExponent()
        let c1 = G.power(k, modulus: P)
        let c2 = (m * publicKey.y.power(k, modulus: P)) % P
        return Ciphertext(c1: c1, c2: c2)
    }

    /// Decrypt (node-side / tests only — clients never hold node private key).
    public static func decrypt(privateX: BigUInt, ct: Ciphertext) throws -> Data {
        let s = ct.c1.power(privateX, modulus: P)
        let sInv = s.inverse(P)!
        let m = (ct.c2 * sInv) % P
        return try decodeMessage(m)
    }
}

import Foundation
import CryptoKit

/// Pedersen commitments over the ElGamal MODP group — mirrors `node/pedersen.py`.
public enum RptPedersen {
    public static let H: BigUInt = {
        var seed = Data("rpt-pedersen-h-v1".utf8)
        seed.append(RptElgamal.intToBytes(RptElgamal.G, length: 256))
        var acc = Data(SHA256.hash(data: seed))
        while acc.count < 256 {
            acc.append(Data(SHA256.hash(data: acc)))
        }
        var x = RptElgamal.bytesToInt(Data(acc.prefix(256))) % RptElgamal.P
        if x <= 1 { x = 3 }
        var h = x.power(2, modulus: RptElgamal.P)
        if h <= 1 {
            h = (x + 2).power(2, modulus: RptElgamal.P)
        }
        return h
    }()

    public struct Commitment {
        public let c: BigUInt
        public func export() -> Data { RptElgamal.intToBytes(c, length: 256) }
        public static func importBytes(_ data: Data) throws -> Commitment {
            guard data.count == 256 else { throw RptProtocol.ProtocolError("commitment must be 256 bytes") }
            let c = RptElgamal.bytesToInt(data)
            guard c > 0 && c < RptElgamal.P else { throw RptProtocol.ProtocolError("invalid commitment") }
            return Commitment(c: c)
        }
    }

    public struct Opening {
        public let message: BigUInt
        public let blinding: BigUInt

        public func export() -> Data {
            RptElgamal.intToBytes(message % RptElgamal.Q, length: 32)
                + RptElgamal.intToBytes(blinding, length: 256)
        }

        public static func importBytes(_ data: Data) throws -> Opening {
            guard data.count == 288 else { throw RptProtocol.ProtocolError("opening must be 288 bytes") }
            let m = RptElgamal.bytesToInt(data.prefix(32)) % RptElgamal.Q
            let r = RptElgamal.bytesToInt(data.suffix(256))
            return Opening(message: m, blinding: r)
        }
    }

    public static func commit(_ message: BigUInt, blinding: BigUInt? = nil) -> (Commitment, Opening) {
        let m = message % RptElgamal.Q
        let r = blinding ?? RptElgamal.randomExponent()
        let c = (RptElgamal.G.power(m, modulus: RptElgamal.P) * H.power(r, modulus: RptElgamal.P)) % RptElgamal.P
        return (Commitment(c: c), Opening(message: m, blinding: r))
    }

    public static func commitBytes(_ payload: Data, blinding: BigUInt? = nil) -> (Commitment, Opening) {
        let digest = Data(SHA256.hash(data: payload))
        let m = RptElgamal.bytesToInt(digest) % RptElgamal.Q
        return commit(m, blinding: blinding)
    }

    public static func verify(commitment: Commitment, opening: Opening) -> Bool {
        let expected =
            (RptElgamal.G.power(opening.message % RptElgamal.Q, modulus: RptElgamal.P)
                * H.power(opening.blinding % RptElgamal.Q, modulus: RptElgamal.P)) % RptElgamal.P
        return expected == commitment.c
    }

    public static func openVerified(commitment: Commitment, opening: Opening) throws -> BigUInt {
        guard verify(commitment: commitment, opening: opening) else {
            throw RptProtocol.ProtocolError("Pedersen opening does not match commitment")
        }
        return opening.message
    }
}

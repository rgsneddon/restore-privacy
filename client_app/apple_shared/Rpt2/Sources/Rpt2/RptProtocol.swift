import Foundation

/// RPT2 wire protocol frames — mirrors `node/protocol.py`.
public enum RptProtocol {
    public static let magic = Data("RPT2".utf8)
    public static let headerLen = 5

    public enum MsgType: UInt8 {
        case clientHello = 0x01
        case serverHello = 0x02
        case data = 0x03
        case keepalive = 0x04
    }

    public struct ProtocolError: Error, LocalizedError {
        public let message: String
        public init(_ message: String) { self.message = message }
        public var errorDescription: String? { message }
    }

    public static func peekType(_ data: Data) -> MsgType? {
        guard data.count >= headerLen,
              data.prefix(4) == magic else { return nil }
        return MsgType(rawValue: data[4])
    }

    public static func packClientHello(
        clientEd25519Pub: Data,
        pedersenCommit: Data,
        hybridBlob: Data,
        signature: Data
    ) throws -> Data {
        guard clientEd25519Pub.count == 32 else { throw ProtocolError("client pub must be 32 bytes") }
        guard pedersenCommit.count == 256 else { throw ProtocolError("commitment must be 256 bytes") }
        guard hybridBlob.count >= 512 + 12 + 16 else { throw ProtocolError("hybrid blob too short") }
        guard signature.count == 64 else { throw ProtocolError("signature must be 64 bytes") }
        var out = Data()
        out.append(magic)
        out.append(MsgType.clientHello.rawValue)
        out.append(clientEd25519Pub)
        out.append(pedersenCommit)
        var hlen = UInt32(hybridBlob.count).bigEndian
        out.append(Data(bytes: &hlen, count: 4))
        out.append(hybridBlob)
        out.append(signature)
        return out
    }

    public static func parseServerHello(_ data: Data) throws -> (commit: Data, sessionId: Data, nonce: Data, sealed: Data) {
        guard data.count >= headerLen + 256 + 8 + 12 + 16,
              data.prefix(4) == magic,
              data[4] == MsgType.serverHello.rawValue else {
            throw ProtocolError("bad SERVER_HELLO")
        }
        let body = data.dropFirst(headerLen)
        let commit = Data(body.prefix(256))
        let sessionId = Data(body.dropFirst(256).prefix(8))
        let nonce = Data(body.dropFirst(256 + 8).prefix(12))
        let sealed = Data(body.dropFirst(256 + 8 + 12))
        return (commit, sessionId, nonce, sealed)
    }

    public static func packData(sessionId: Data, counter: UInt64, nonce: Data, sealed: Data) -> Data {
        var out = Data()
        out.append(magic)
        out.append(MsgType.data.rawValue)
        out.append(sessionId)
        var c = counter.bigEndian
        out.append(Data(bytes: &c, count: 8))
        out.append(nonce)
        out.append(sealed)
        return out
    }

    public static func parseData(_ data: Data) throws -> (sessionId: Data, counter: UInt64, nonce: Data, sealed: Data) {
        guard data.count >= headerLen + 8 + 8 + 12 + 16,
              data.prefix(4) == magic,
              data[4] == MsgType.data.rawValue else {
            throw ProtocolError("bad DATA")
        }
        let body = data.dropFirst(headerLen)
        let sessionId = Data(body.prefix(8))
        let counterBytes = Data(body.dropFirst(8).prefix(8))
        let counter = counterBytes.withUnsafeBytes { $0.load(as: UInt64.self).bigEndian }
        let nonce = Data(body.dropFirst(16).prefix(12))
        let sealed = Data(body.dropFirst(28))
        return (sessionId, counter, nonce, sealed)
    }

    public static func packKeepalive(sessionId: Data) -> Data {
        var out = Data()
        out.append(magic)
        out.append(MsgType.keepalive.rawValue)
        out.append(sessionId)
        return out
    }

    public static func parseKeepalive(_ data: Data) throws -> Data {
        guard data.count >= headerLen + 8,
              data.prefix(4) == magic,
              data[4] == MsgType.keepalive.rawValue else {
            throw ProtocolError("bad KEEPALIVE")
        }
        return Data(data.dropFirst(headerLen).prefix(8))
    }
}

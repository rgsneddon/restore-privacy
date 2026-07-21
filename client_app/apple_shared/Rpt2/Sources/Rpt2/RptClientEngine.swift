import Foundation
import CryptoKit

/// Authorized RPT2 client engine — mirrors Android `RptClientEngine` / Python `client.connect`.
///
/// Important: the node binds the session to the UDP source address of CLIENT_HELLO
/// (`node/server.py`). HELLO and subsequent DATA/KEEPALIVE **must** share one long-lived
/// socket (same as Android DatagramSocket / Python sock).
///
/// Product residual parity with Python path:
/// - **PFS**: ephemeral X25519 (`|pfs-x25519|`)
/// - **Traffic shape**: RPTP pad + RPTC cover on DATA AEAD plaintext
/// - **Outer obfs**: QUIC-mimic wrap/unwrap on UDP
public final class RptClientEngine {
    public struct Session {
        public let sessionId: Data
        public let sessionKey: Data
        public let vpnIp: String
        public let clientPub: Data
        public let clientNonce: Data
        public let pfs: Bool
    }

    private let clientPrivRaw: Data
    private let nodeElgamalPubRaw: Data
    private var sessionId: Data?
    private var sessionKey: Data?
    private var counterOut: UInt64 = 0
    /// Ephemeral X25519 private key for the in-flight HELLO (PFS).
    private var pendingClientEph: Curve25519.KeyAgreement.PrivateKey?

    /// Long-lived UDP transport used for HELLO + DATA + KEEPALIVE (node binds client_addr).
    private(set) public var transport: RptUDPTransport?
    private var endpointHost: String = RptEndpoint.host
    private var endpointPort: UInt16 = RptEndpoint.port

    public init(clientPrivRaw: Data, nodeElgamalPubRaw: Data) throws {
        guard clientPrivRaw.count == 32 else {
            throw RptProtocol.ProtocolError("client_ed25519.priv must be 32 raw bytes")
        }
        guard nodeElgamalPubRaw.count == 256 else {
            throw RptProtocol.ProtocolError("node_elgamal.pub must be 256 bytes")
        }
        self.clientPrivRaw = clientPrivRaw
        self.nodeElgamalPubRaw = nodeElgamalPubRaw
    }

    public var hasSession: Bool { sessionId != nil && sessionKey != nil }
    public var vpnIp: String? {
        // session is stored only via applySession; track last session vpn ip
        return lastVpnIp
    }
    private var lastVpnIp: String?

    public func applySession(_ session: Session) {
        self.sessionId = session.sessionId
        self.sessionKey = session.sessionKey
        self.counterOut = 0
        self.lastVpnIp = session.vpnIp
    }

    // MARK: - Hello construction (shipped)

    public func buildClientHello() throws -> (frame: Data, clientNonce: Data, clientPub: Data) {
        let privateKey = try Curve25519.Signing.PrivateKey(rawRepresentation: clientPrivRaw)
        let clientPub = privateKey.publicKey.rawRepresentation
        var clientNonce = Data(count: 32)
        _ = clientNonce.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, 32, $0.baseAddress!) }
        let (commit, opening) = RptPedersen.commitBytes(clientNonce)
        // PFS: ephemeral X25519 public key (Python build_client_hello with_pfs=True)
        let eph = Curve25519.KeyAgreement.PrivateKey()
        self.pendingClientEph = eph
        let ephPub = eph.publicKey.rawRepresentation
        let payload = clientNonce + opening.export() + ephPub
        let hybrid = try packHybrid(plaintext: payload)
        let commitB = commit.export()
        var transcript = Data("RPT2-CLIENT-HELLO|".utf8)
        transcript.append(clientPub)
        transcript.append(commitB)
        transcript.append(hybrid)
        let sig = try privateKey.signature(for: transcript)
        let frame = try RptProtocol.packClientHello(
            clientEd25519Pub: clientPub,
            pedersenCommit: commitB,
            hybridBlob: hybrid,
            signature: sig
        )
        return (frame, clientNonce, clientPub)
    }

    public func completeServerHello(reply: Data, clientNonce: Data, clientPub: Data) throws -> Session {
        guard RptProtocol.peekType(reply) == .serverHello else {
            throw RptProtocol.ProtocolError("expected SERVER_HELLO")
        }
        guard let clientEph = pendingClientEph else {
            throw RptProtocol.ProtocolError("missing client ephemeral X25519 (call buildClientHello first)")
        }
        let (sCommitB, sessionId, nonce, sealed) = try RptProtocol.parseServerHello(reply)
        var helloSharedMaterial = clientNonce
        helloSharedMaterial.append(clientPub)
        helloSharedMaterial.append(Data("|hello".utf8))
        let helloShared = Data(SHA256.hash(data: helloSharedMaterial))
        let helloKey = RptSessionCrypto.deriveSessionKey(
            sharedSecret: helloShared,
            salt: Data(clientNonce.prefix(16)),
            info: Data("rpt-v2-hello".utf8)
        )
        let helloCrypto = RptSessionCrypto(keyBytes: helloKey)
        var aad = Data("RPT2-SERVER-HELLO".utf8)
        aad.append(sessionId)
        let plain = try helloCrypto.open(nonce: nonce, ciphertext: sealed, aad: aad)
        // Product PFS: server_nonce + opening + vpn_ip + server X25519 pub (32)
        let serverEphOff = 32 + 288 + 4
        guard plain.count >= serverEphOff + 32 else {
            throw RptProtocol.ProtocolError(
                "SERVER_HELLO missing server X25519 pub (product requires PFS)"
            )
        }
        let serverNonce = Data(plain.prefix(32))
        let opening = try RptPedersen.Opening.importBytes(Data(plain.dropFirst(32).prefix(288)))
        let commit = try RptPedersen.Commitment.importBytes(sCommitB)
        _ = try RptPedersen.openVerified(commitment: commit, opening: opening)
        let ipBytes = Data(plain.dropFirst(32 + 288).prefix(4))
        let vpnIp = ipBytes.map { String($0) }.joined(separator: ".")
        let serverEphPub = Data(plain.dropFirst(serverEphOff).prefix(32))
        let peerPub = try Curve25519.KeyAgreement.PublicKey(rawRepresentation: serverEphPub)
        let ephShared = try clientEph.sharedSecretFromKeyAgreement(with: peerPub)
        // Python derive_pfs_session_shared — raw 32-byte ECDH output
        var ephSharedBytes = Data()
        ephShared.withUnsafeBytes { ephSharedBytes.append(contentsOf: $0) }
        var sessionSharedMaterial = clientNonce
        sessionSharedMaterial.append(serverNonce)
        sessionSharedMaterial.append(sessionId)
        sessionSharedMaterial.append(clientPub)
        sessionSharedMaterial.append(Data("|pfs-x25519|".utf8))
        sessionSharedMaterial.append(ephSharedBytes)
        let sessionShared = Data(SHA256.hash(data: sessionSharedMaterial))
        let sessionKey = RptSessionCrypto.deriveSessionKey(
            sharedSecret: sessionShared,
            salt: Data(clientNonce.prefix(16)),
            info: Data("rpt-v2-session".utf8)
        )
        let session = Session(
            sessionId: sessionId,
            sessionKey: sessionKey,
            vpnIp: vpnIp,
            clientPub: clientPub,
            clientNonce: clientNonce,
            pfs: true
        )
        applySession(session)
        self.pendingClientEph = nil
        return session
    }

    /// UDP handshake on a **new** long-lived socket kept open for DATA/KEEPALIVE.
    /// Caller must not expect the socket to close after HELLO (node binds client_addr).
    @discardableResult
    public func handshake(host: String, port: UInt16, timeout: TimeInterval = 15) throws -> Session {
        closeTransport()
        let sock = try RptUDPTransport()
        try sock.connect(host: host, port: port)
        self.transport = sock
        self.endpointHost = host
        self.endpointPort = port
        return try handshake(using: sock, host: host, port: port, timeout: timeout)
    }

    /// Handshake on an existing transport (HELLO + reply). Does **not** close the transport.
    @discardableResult
    public func handshake(
        using sock: RptUDPTransport,
        host: String,
        port: UInt16,
        timeout: TimeInterval = 15
    ) throws -> Session {
        self.transport = sock
        self.endpointHost = host
        self.endpointPort = port
        if !sock.isConnected {
            try sock.connect(host: host, port: port)
        }
        let (frame, clientNonce, clientPub) = try buildClientHello()
        try sock.send(try RptObfuscation.maybeWrap(frame))
        let outerReply = try sock.receive(timeout: timeout)
        let reply = try RptObfuscation.maybeUnwrap(outerReply)
        return try completeServerHello(reply: reply, clientNonce: clientNonce, clientPub: clientPub)
    }

    // MARK: - DATA plane (shipped) — same transport as HELLO
    // Product residual: pad (RPTP) / cover (RPTC) inside AEAD; outer wrap on UDP.

    public func sealPacket(_ ipPacket: Data) throws -> Data {
        guard let sid = sessionId, let keyBytes = sessionKey else {
            throw RptProtocol.ProtocolError("no session")
        }
        counterOut += 1
        var aad = sid
        var c = counterOut.bigEndian
        aad.append(Data(bytes: &c, count: 8))
        let body = try RptTrafficShape.prepareOutbound(ipPacket)
        let crypto = RptSessionCrypto(keyBytes: keyBytes)
        let (nonce, sealed) = try crypto.seal(plaintext: body, aad: aad)
        return RptProtocol.packData(sessionId: sid, counter: counterOut, nonce: nonce, sealed: sealed)
    }

    /// Open DATA after outer unwrap; returns nil if cover (RPTC).
    public func openPacketAllowCover(_ frame: Data) throws -> Data? {
        guard let keyBytes = sessionKey else {
            throw RptProtocol.ProtocolError("no session")
        }
        let (sid, counter, nonce, sealed) = try RptProtocol.parseData(frame)
        if let expected = sessionId, sid != expected {
            throw RptProtocol.ProtocolError("session mismatch")
        }
        var aad = sid
        var c = counter.bigEndian
        aad.append(Data(bytes: &c, count: 8))
        let crypto = RptSessionCrypto(keyBytes: keyBytes)
        let raw = try crypto.open(nonce: nonce, ciphertext: sealed, aad: aad)
        let (plain, isCover) = try RptTrafficShape.interpretInbound(raw)
        if isCover { return nil }
        return plain
    }

    public func openPacket(_ frame: Data) throws -> Data {
        guard let plain = try openPacketAllowCover(frame) else {
            throw RptProtocol.ProtocolError("cover traffic frame")
        }
        return plain
    }

    public func sealCoverFrame(size: Int = RptTrafficShape.productCoverSize) throws -> Data {
        guard let sid = sessionId, let keyBytes = sessionKey else {
            throw RptProtocol.ProtocolError("no session")
        }
        counterOut += 1
        var aad = sid
        var c = counterOut.bigEndian
        aad.append(Data(bytes: &c, count: 8))
        let body = RptTrafficShape.makeCoverPayload(size: size)
        let crypto = RptSessionCrypto(keyBytes: keyBytes)
        let (nonce, sealed) = try crypto.seal(plaintext: body, aad: aad)
        return RptProtocol.packData(sessionId: sid, counter: counterOut, nonce: nonce, sealed: sealed)
    }

    public func packKeepalive() throws -> Data {
        guard let sid = sessionId else { throw RptProtocol.ProtocolError("no session") }
        return RptProtocol.packKeepalive(sessionId: sid)
    }

    /// Seal + outer-wrap one IP packet and send on the HELLO transport.
    /// Product residual: pad + outer obfs + bounded send jitter (default on).
    public func sendSealedPacket(_ ipPacket: Data) throws {
        guard let sock = transport else { throw RptProtocol.ProtocolError("no transport") }
        RptTrafficShape.applySendJitter()
        let frame = try sealPacket(ipPacket)
        try sock.send(try RptObfuscation.maybeWrap(frame))
    }

    /// Cover (RPTC) frame with outer wrap — product residual default (~2s interval in Packet Tunnel).
    public func sendCoverFrame() throws {
        guard let sock = transport else { throw RptProtocol.ProtocolError("no transport") }
        let frame = try sealCoverFrame()
        try sock.send(try RptObfuscation.maybeWrap(frame))
    }

    /// Send KEEPALIVE on the HELLO transport (outer-wrapped).
    public func sendKeepalive() throws {
        guard let sock = transport else { throw RptProtocol.ProtocolError("no transport") }
        try sock.send(try RptObfuscation.maybeWrap(try packKeepalive()))
    }

    /// Receive one UDP frame, outer-unwrap; returns inner RPT frame.
    public func receiveFrame(timeout: TimeInterval = 0.05) throws -> Data {
        guard let sock = transport else { throw RptProtocol.ProtocolError("no transport") }
        let outer = try sock.receive(timeout: timeout)
        return try RptObfuscation.maybeUnwrap(outer)
    }

    /// Receive and open DATA; returns nil for cover or non-DATA.
    public func receiveAndOpenPacket(timeout: TimeInterval = 0.05) throws -> Data? {
        let inner = try receiveFrame(timeout: timeout)
        guard RptProtocol.peekType(inner) == .data else { return nil }
        return try openPacketAllowCover(inner)
    }

    public func closeTransport() {
        transport?.close()
        transport = nil
    }

    // MARK: - Hybrid

    private func packHybrid(plaintext: Data) throws -> Data {
        var key = Data(count: 32)
        _ = key.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, 32, $0.baseAddress!) }
        let pub = try RptElgamal.PublicKey.importBytes(nodeElgamalPubRaw)
        let ct = try RptElgamal.encrypt(publicKey: pub, plaintext: key)
        var nonce = Data(count: 12)
        _ = nonce.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, 12, $0.baseAddress!) }
        let n = try ChaChaPoly.Nonce(data: nonce)
        let sealedBox = try ChaChaPoly.seal(
            plaintext,
            using: SymmetricKey(data: key),
            nonce: n,
            authenticating: Data("RPT2-HYBRID".utf8)
        )
        var sealed = sealedBox.ciphertext
        sealed.append(sealedBox.tag)
        return ct.export() + nonce + sealed
    }

    deinit {
        closeTransport()
    }
}

// MARK: - Long-lived UDP transport (HELLO + DATA + KEEPALIVE)

/// BSD UDP socket. Connect once for HELLO; reuse for all session traffic so the node
/// sees a stable `client_addr` (see `node/server.py` session binding).
public final class RptUDPTransport {
    private var fd: Int32 = -1
    private(set) public var isConnected: Bool = false
    public var host: String = ""
    public var port: UInt16 = 0

    public init() throws {
        fd = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)
        if fd < 0 { throw RptProtocol.ProtocolError("UDP socket failed") }
    }

    public func close() {
        if fd >= 0 {
            Darwin.close(fd)
            fd = -1
        }
        isConnected = false
    }

    deinit { close() }

    /// Resolve and connect the datagram socket so subsequent send/recv use one local port
    /// (matches Python `sock` / Android `DatagramSocket` lifecycle).
    public func connect(host: String, port: UInt16) throws {
        self.host = host
        self.port = port
        var hints = addrinfo(
            ai_flags: 0,
            ai_family: AF_INET,
            ai_socktype: SOCK_DGRAM,
            ai_protocol: IPPROTO_UDP,
            ai_addrlen: 0,
            ai_canonname: nil,
            ai_addr: nil,
            ai_next: nil
        )
        var res: UnsafeMutablePointer<addrinfo>?
        let err = getaddrinfo(host, String(port), &hints, &res)
        guard err == 0, let info = res else {
            throw RptProtocol.ProtocolError("resolve \(host) failed")
        }
        defer { freeaddrinfo(info) }
        let rc = Darwin.connect(fd, info.pointee.ai_addr, info.pointee.ai_addrlen)
        if rc != 0 {
            throw RptProtocol.ProtocolError("UDP connect failed")
        }
        isConnected = true
    }

    public func send(_ data: Data) throws {
        guard fd >= 0, isConnected else { throw RptProtocol.ProtocolError("UDP not connected") }
        let sent = data.withUnsafeBytes { ptr in
            Darwin.send(fd, ptr.baseAddress, data.count, 0)
        }
        if sent < 0 { throw RptProtocol.ProtocolError("UDP send failed") }
    }

    public func receive(timeout: TimeInterval) throws -> Data {
        guard fd >= 0 else { throw RptProtocol.ProtocolError("UDP closed") }
        var buf = [UInt8](repeating: 0, count: 65535)
        let n: Int
        if timeout <= 0 {
            // Non-blocking single read (dataplane poll / DispatchSource readiness)
            let flags = fcntl(fd, F_GETFL)
            _ = fcntl(fd, F_SETFL, flags | O_NONBLOCK)
            n = recv(fd, &buf, buf.count, 0)
            _ = fcntl(fd, F_SETFL, flags)
        } else {
            var tv = timeval(
                tv_sec: Int(timeout),
                tv_usec: Int32((timeout - floor(timeout)) * 1_000_000)
            )
            setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, socklen_t(MemoryLayout<timeval>.size))
            n = recv(fd, &buf, buf.count, 0)
        }
        if n < 0 {
            let e = errno
            if e == EAGAIN || e == EWOULDBLOCK {
                throw RptProtocol.ProtocolError("UDP receive timeout")
            }
            throw RptProtocol.ProtocolError("UDP receive failed or timed out")
        }
        return Data(buf.prefix(n))
    }

    /// File descriptor for select/poll loops (Packet Tunnel dataplane).
    public var fileDescriptor: Int32 { fd }
}

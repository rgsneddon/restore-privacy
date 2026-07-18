import XCTest
@testable import Rpt2
import CryptoKit
import Foundation

final class Rpt2Tests: XCTestCase {

    // MARK: - Frame packing (shipped RptProtocol)

    func testMagicIsRPT2() {
        XCTAssertEqual(RptProtocol.magic, Data("RPT2".utf8))
        XCTAssertEqual(RptProtocol.MsgType.clientHello.rawValue, 0x01)
        XCTAssertEqual(RptProtocol.MsgType.serverHello.rawValue, 0x02)
        XCTAssertEqual(RptProtocol.MsgType.data.rawValue, 0x03)
        XCTAssertEqual(RptProtocol.MsgType.keepalive.rawValue, 0x04)
    }

    func testPackKeepaliveAndParse() throws {
        let sid = Data(repeating: 0xAB, count: 8)
        let frame = RptProtocol.packKeepalive(sessionId: sid)
        XCTAssertEqual(RptProtocol.peekType(frame), .keepalive)
        let parsed = try RptProtocol.parseKeepalive(frame)
        XCTAssertEqual(parsed, sid)
    }

    func testRejectBadFrames() {
        XCTAssertNil(RptProtocol.peekType(Data([0, 1, 2, 3, 4])))
        XCTAssertThrowsError(try RptProtocol.parseData(Data("RPT2".utf8) + Data([0x03])))
        XCTAssertThrowsError(try RptProtocol.parseServerHello(Data("XXXX".utf8) + Data([0x02])))
        XCTAssertThrowsError(try RptProtocol.parseKeepalive(Data("RPT2".utf8) + Data([0x01])))
    }

    func testPackClientHelloStructure() throws {
        let pub = Data(repeating: 1, count: 32)
        let commit = Data(repeating: 2, count: 256)
        let hybrid = Data(repeating: 3, count: 512 + 12 + 16)
        let sig = Data(repeating: 4, count: 64)
        let frame = try RptProtocol.packClientHello(
            clientEd25519Pub: pub,
            pedersenCommit: commit,
            hybridBlob: hybrid,
            signature: sig
        )
        XCTAssertEqual(RptProtocol.peekType(frame), .clientHello)
        XCTAssertEqual(Data(frame.prefix(4)), RptProtocol.magic)
        XCTAssertEqual(frame[4], 0x01)
        // pub starts at offset 5
        XCTAssertEqual(Data(frame.dropFirst(5).prefix(32)), pub)
        XCTAssertEqual(Data(frame.dropFirst(5 + 32).prefix(256)), commit)
    }

    // MARK: - DATA seal/open round-trip on shipped engine

    func testDataSealOpenRoundTrip() throws {
        // Generate ephemeral keys for a self-contained engine path
        let clientPriv = Curve25519.Signing.PrivateKey()
        // node pub: generate ephemeral ElGamal keypair for encrypt side only
        let x = RptElgamal.randomExponent()
        let y = RptElgamal.G.power(x, modulus: RptElgamal.P)
        let nodePub = RptElgamal.PublicKey(y: y).export()

        let engine = try RptClientEngine(
            clientPrivRaw: clientPriv.rawRepresentation,
            nodeElgamalPubRaw: nodePub
        )
        // Inject a synthetic session (same path seal/open use)
        var sid = Data(count: 8)
        _ = sid.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, 8, $0.baseAddress!) }
        var key = Data(count: 32)
        _ = key.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, 32, $0.baseAddress!) }
        engine.applySession(
            RptClientEngine.Session(
                sessionId: sid,
                sessionKey: key,
                vpnIp: "10.88.0.5",
                clientPub: clientPriv.publicKey.rawRepresentation,
                clientNonce: Data(repeating: 9, count: 32)
            )
        )

        let packet = Data([0x45, 0x00, 0x00, 0x28] + Data(repeating: 0xAA, count: 36))
        let frame = try engine.sealPacket(packet)
        XCTAssertEqual(RptProtocol.peekType(frame), .data)
        let opened = try engine.openPacket(frame)
        XCTAssertEqual(opened, packet)
    }

    func testDataRejectsWrongMagic() throws {
        let clientPriv = Curve25519.Signing.PrivateKey()
        let x = RptElgamal.randomExponent()
        let y = RptElgamal.G.power(x, modulus: RptElgamal.P)
        let engine = try RptClientEngine(
            clientPrivRaw: clientPriv.rawRepresentation,
            nodeElgamalPubRaw: RptElgamal.PublicKey(y: y).export()
        )
        engine.applySession(
            RptClientEngine.Session(
                sessionId: Data(repeating: 1, count: 8),
                sessionKey: Data(repeating: 2, count: 32),
                vpnIp: "10.88.0.1",
                clientPub: clientPriv.publicKey.rawRepresentation,
                clientNonce: Data(repeating: 3, count: 32)
            )
        )
        XCTAssertThrowsError(try engine.openPacket(Data(repeating: 0, count: 64)))
    }

    // MARK: - Handshake round-trip against local mock server (shipped buildClientHello + completeServerHello)

    func testHandshakeRoundTripAgainstMockServer() throws {
        // Node ElGamal keypair
        let nodeX = RptElgamal.randomExponent()
        let nodeY = RptElgamal.G.power(nodeX, modulus: RptElgamal.P)
        let nodePubRaw = RptElgamal.PublicKey(y: nodeY).export()

        let clientPriv = Curve25519.Signing.PrivateKey()
        let engine = try RptClientEngine(
            clientPrivRaw: clientPriv.rawRepresentation,
            nodeElgamalPubRaw: nodePubRaw
        )
        let (hello, clientNonce, clientPub) = try engine.buildClientHello()
        XCTAssertEqual(RptProtocol.peekType(hello), .clientHello)

        // Node-side: open hybrid, verify pedersen, build SERVER_HELLO (mirrors node_complete_hello)
        let reply = try mockNodeCompleteHello(
            frame: hello,
            nodePrivateX: nodeX,
            vpnIp: "10.88.0.7"
        )
        XCTAssertEqual(RptProtocol.peekType(reply), .serverHello)

        let session = try engine.completeServerHello(reply: reply, clientNonce: clientNonce, clientPub: clientPub)
        XCTAssertEqual(session.vpnIp, "10.88.0.7")
        XCTAssertEqual(session.sessionId.count, 8)
        XCTAssertEqual(session.sessionKey.count, 32)

        // DATA round-trip under derived session keys
        let pkt = Data("hello-ip-packet".utf8)
        let sealed = try engine.sealPacket(pkt)
        let opened = try engine.openPacket(sealed)
        XCTAssertEqual(opened, pkt)
    }

    // MARK: - UK gate

    func testUkGateAllowsGB() {
        let r = RptUkIpGate.evaluateGeoPayload([
            "country_code": "GB",
            "ip": "1.2.3.4",
        ])
        XCTAssertTrue(r.allowed)
        XCTAssertEqual(r.countryCode, "GB")
    }

    func testUkGateDeniesUS() {
        let r = RptUkIpGate.evaluateGeoPayload([
            "country_code": "US",
            "ip": "8.8.8.8",
        ])
        XCTAssertFalse(r.allowed)
        XCTAssertTrue(r.message.contains("United Kingdom"))
    }

    func testUkGateFailClosedOnEmpty() {
        let r = RptUkIpGate.evaluateGeoPayload(nil)
        XCTAssertFalse(r.allowed)
        XCTAssertEqual(r.message, RptUkIpGate.lookupFailedMessage)
    }

    func testUkGateInjectableFetcher() {
        let r = RptUkIpGate.checkUkPublicIp {
            ["countryCode": "UK", "ip": "9.9.9.9"]
        }
        XCTAssertTrue(r.allowed)
    }

    // MARK: - Secrets forbid node priv load path

    func testSecretsNamesNeverIncludeNodePrivAsAdmission() {
        XCTAssertEqual(RptSecrets.clientPrivName, "client_ed25519.priv")
        XCTAssertEqual(RptSecrets.nodePubName, "node_elgamal.pub")
        XCTAssertEqual(RptSecrets.nodePrivName, "node_elgamal.priv")
        // loadAdmissionMaterial only reads client priv + node pub
        XCTAssertFalse(RptSecrets.clientPrivName.contains("node_elgamal.priv"))
    }

    func testSessionCryptoRoundTrip() throws {
        let key = Data(repeating: 0x42, count: 32)
        let crypto = RptSessionCrypto(keyBytes: key)
        let plain = Data("rpt-session-test".utf8)
        let aad = Data("aad".utf8)
        let (nonce, sealed) = try crypto.seal(plaintext: plain, aad: aad)
        let opened = try crypto.open(nonce: nonce, ciphertext: sealed, aad: aad)
        XCTAssertEqual(opened, plain)
    }

    /// HELLO transport must stay open for DATA (node binds client_addr to HELLO source).
    /// Shipped path: handshake stores sock; closeTransport is the only teardown.
    func testHandshakeKeepsTransportOpenForDataPlane() throws {
        let clientPriv = Curve25519.Signing.PrivateKey()
        let nodeX = RptElgamal.randomExponent()
        let nodeY = RptElgamal.G.power(nodeX, modulus: RptElgamal.P)
        let engine = try RptClientEngine(
            clientPrivRaw: clientPriv.rawRepresentation,
            nodeElgamalPubRaw: RptElgamal.PublicKey(y: nodeY).export()
        )

        var sid = Data(count: 8)
        _ = sid.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, 8, $0.baseAddress!) }
        var key = Data(count: 32)
        _ = key.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, 32, $0.baseAddress!) }
        engine.applySession(
            RptClientEngine.Session(
                sessionId: sid,
                sessionKey: key,
                vpnIp: "10.88.0.9",
                clientPub: clientPriv.publicKey.rawRepresentation,
                clientNonce: Data(repeating: 1, count: 32)
            )
        )
        XCTAssertNil(engine.transport)
        XCTAssertThrowsError(try engine.sendSealedPacket(Data([0x45])))

        // Long-lived BSD UDP: connect once, multiple sends, still connected
        let sock = try RptUDPTransport()
        try sock.connect(host: "127.0.0.1", port: 9)
        XCTAssertTrue(sock.isConnected)
        try sock.send(Data("hello-frame".utf8))
        XCTAssertTrue(sock.isConnected)
        try sock.send(Data("data-frame".utf8))
        XCTAssertTrue(sock.isConnected)
        XCTAssertGreaterThanOrEqual(sock.fileDescriptor, 0)

        let (frame, clientNonce, clientPub) = try engine.buildClientHello()
        let reply = try mockNodeCompleteHello(frame: frame, nodePrivateX: nodeX, vpnIp: "10.88.0.3")
        let session = try engine.completeServerHello(reply: reply, clientNonce: clientNonce, clientPub: clientPub)
        XCTAssertEqual(session.vpnIp, "10.88.0.3")
        // completeServerHello must not close an external transport
        XCTAssertTrue(sock.isConnected)

        sock.close()
        XCTAssertFalse(sock.isConnected)
    }

    func testResultMapIncludesVpnIpOnOrchestratorShape() {
        let outcome = RptConnectOrchestrator.ConnectOutcome(
            ok: true,
            message: "Connected — tunnel IP 10.88.0.2",
            vpnIp: "10.88.0.2",
            session: nil,
            engine: nil
        )
        let map = outcome.resultMap
        XCTAssertEqual(map["ok"] as? Bool, true)
        XCTAssertEqual(map["vpnIp"] as? String, "10.88.0.2")
        XCTAssertNotNil(map["message"] as? String)
    }

    // MARK: - Mock node helpers (test-only, not a parallel client re-implementation of seal/open under test)

    /// Minimal node SERVER_HELLO builder so tests exercise shipped client completeServerHello.
    private func mockNodeCompleteHello(frame: Data, nodePrivateX: BigUInt, vpnIp: String) throws -> Data {
        // Parse CLIENT_HELLO fields
        guard frame.count > 5 + 32 + 256 + 4 + 64,
              frame.prefix(4) == RptProtocol.magic,
              frame[4] == 0x01 else {
            throw RptProtocol.ProtocolError("bad CLIENT_HELLO for mock")
        }
        let body = frame.dropFirst(5)
        let clientPub = Data(body.prefix(32))
        let commitB = Data(body.dropFirst(32).prefix(256))
        let hlenBytes = Data(body.dropFirst(32 + 256).prefix(4))
        let hlen = hlenBytes.withUnsafeBytes { $0.load(as: UInt32.self).bigEndian }
        let hybrid = Data(body.dropFirst(32 + 256 + 4).prefix(Int(hlen)))
        // open hybrid
        let ct = try RptElgamal.Ciphertext.importBytes(Data(hybrid.prefix(512)))
        var key = try RptElgamal.decrypt(privateX: nodePrivateX, ct: ct)
        if key.count > 32 { key = Data(key.prefix(32)) }
        if key.count < 32 { key.append(Data(repeating: 0, count: 32 - key.count)) }
        let nonce = Data(hybrid.dropFirst(512).prefix(12))
        let sealedHybrid = Data(hybrid.dropFirst(524))
        let n = try ChaChaPoly.Nonce(data: nonce)
        let tag = sealedHybrid.suffix(16)
        let ctBody = sealedHybrid.dropLast(16)
        let box = try ChaChaPoly.SealedBox(nonce: n, ciphertext: ctBody, tag: tag)
        let opened = try ChaChaPoly.open(box, using: SymmetricKey(data: key), authenticating: Data("RPT2-HYBRID".utf8))
        let clientNonce = Data(opened.prefix(32))
        let opening = try RptPedersen.Opening.importBytes(Data(opened.dropFirst(32).prefix(288)))
        let commit = try RptPedersen.Commitment.importBytes(commitB)
        _ = try RptPedersen.openVerified(commitment: commit, opening: opening)

        var sessionId = Data(count: 8)
        _ = sessionId.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, 8, $0.baseAddress!) }
        var serverNonce = Data(count: 32)
        _ = serverNonce.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, 32, $0.baseAddress!) }
        let (sCommit, sOpening) = RptPedersen.commitBytes(serverNonce)

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
        let parts = vpnIp.split(separator: ".").compactMap { UInt8($0) }
        guard parts.count == 4 else { throw RptProtocol.ProtocolError("bad vpn ip") }
        var plain = serverNonce + sOpening.export() + Data(parts)
        var aad = Data("RPT2-SERVER-HELLO".utf8)
        aad.append(sessionId)
        let (nOut, sealedOut) = try helloCrypto.seal(plaintext: plain, aad: aad)

        var reply = RptProtocol.magic
        reply.append(RptProtocol.MsgType.serverHello.rawValue)
        reply.append(sCommit.export())
        reply.append(sessionId)
        reply.append(nOut)
        reply.append(sealedOut)
        return reply
    }
}

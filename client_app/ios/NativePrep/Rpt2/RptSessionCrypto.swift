import Foundation
import CryptoKit

/// Session AEAD — mirrors `node/crypto_session.py`.
public struct RptSessionCrypto {
    public let key: SymmetricKey

    public init(keyBytes: Data) {
        self.key = SymmetricKey(data: keyBytes)
    }

    public static func deriveSessionKey(sharedSecret: Data, salt: Data, info: Data = Data("rpt-v2-session".utf8)) -> Data {
        let derived = HKDF<SHA256>.deriveKey(
            inputKeyMaterial: SymmetricKey(data: sharedSecret),
            salt: salt,
            info: info,
            outputByteCount: 32
        )
        return derived.withUnsafeBytes { Data($0) }
    }

    public func seal(plaintext: Data, aad: Data = Data()) throws -> (nonce: Data, sealed: Data) {
        var nonceBytes = Data(count: 12)
        _ = nonceBytes.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, 12, $0.baseAddress!) }
        let nonce = try ChaChaPoly.Nonce(data: nonceBytes)
        let sealedBox = try ChaChaPoly.seal(plaintext, using: key, nonce: nonce, authenticating: aad)
        // CryptoKit sealed box = nonce || ciphertext || tag; wire format is nonce separate + ciphertext||tag
        var sealed = sealedBox.ciphertext
        sealed.append(sealedBox.tag)
        return (Data(nonceBytes), sealed)
    }

    public func open(nonce: Data, ciphertext: Data, aad: Data = Data()) throws -> Data {
        guard nonce.count == 12, ciphertext.count >= 16 else {
            throw RptProtocol.ProtocolError("bad AEAD inputs")
        }
        let n = try ChaChaPoly.Nonce(data: nonce)
        let tag = ciphertext.suffix(16)
        let ct = ciphertext.dropLast(16)
        let box = try ChaChaPoly.SealedBox(nonce: n, ciphertext: ct, tag: tag)
        return try ChaChaPoly.open(box, using: key, authenticating: aad)
    }
}

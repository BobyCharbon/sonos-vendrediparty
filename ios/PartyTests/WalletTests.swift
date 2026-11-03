import Foundation
import PassKit
import Testing
@testable import Party

/// « Ajouter à l'app Cartes Apple » : l'app ne télécharge que les billets préparés par le serveur Party.
struct WalletTests {
    @Test("Lien de billet Party accepté", arguments: [
        "https://party.bobycharbon.ch/api/wallet/pass/AbC-12_x.pkpass",
        "https://partytest.bobycharbon.ch/api/wallet/pass/xyz.pkpass",
    ])
    func acceptsPartyPass(link: String) throws {
        #expect(NativeWallet.isPassURL(try #require(URL(string: link))))
    }

    @Test("Tout autre lien refusé", arguments: [
        "http://party.bobycharbon.ch/api/wallet/pass/x.pkpass",           // pas de https
        "https://evil.example/api/wallet/pass/x.pkpass",                   // autre serveur
        "https://abc.supabase.co/api/wallet/pass/x.pkpass",                // interne, mais pas Party
        "https://party.bobycharbon.ch/api/account/me",                     // pas un billet
        "https://party.bobycharbon.ch/api/wallet/pass/x.pkpass?token=1",   // paramètres
        "https://party.bobycharbon.ch/api/wallet/pass/x.zip",
    ])
    func refusesOthers(link: String) throws {
        #expect(!NativeWallet.isPassURL(try #require(URL(string: link))))
    }

    @Test("Un fichier qui n'est pas un billet signé est refusé sans planter")
    func invalidPassThrows() async throws {
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [FakePassServer.self]
        let session = URLSession(configuration: config)
        await #expect(throws: NativeWallet.Failure.self) {
            _ = try await NativeWallet.pass(at: URL(string: "https://party.bobycharbon.ch/api/wallet/pass/x.pkpass")!, session: session)
        }
        await #expect(throws: NativeWallet.Failure.self) {
            _ = try await NativeWallet.pass(at: URL(string: "https://evil.example/x.pkpass")!, session: session)
        }
    }

    /// Billet réel signé par le serveur (TEST_RUNNER_PARTY_TEST_PKPASS=<fichier> à xcodebuild) : PassKit l'accepte.
    @Test("Un vrai billet du serveur est accepté par PassKit",
          .enabled(if: ProcessInfo.processInfo.environment["PARTY_TEST_PKPASS"] != nil))
    func realPassLoads() throws {
        let path = try #require(ProcessInfo.processInfo.environment["PARTY_TEST_PKPASS"])
        let pass = try PKPass(data: try Data(contentsOf: URL(fileURLWithPath: path)))
        #expect(pass.passTypeIdentifier == "pass.ch.bobycharbon.party.ticket")
        #expect(pass.organizationName == "Party")
    }
}

/// Serveur simulé : répond un zip vide, qui n'est pas un billet valable.
private final class FakePassServer: URLProtocol {
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        let response = HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil,
                                       headerFields: ["Content-Type": "application/vnd.apple.pkpass"])!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data([0x50, 0x4B, 0x05, 0x06] + [UInt8](repeating: 0, count: 18)))
        client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}
}

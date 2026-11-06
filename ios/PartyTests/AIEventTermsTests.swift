import XCTest
@testable import Party

/// Bug de prod (06.11) : CGU exigées (terms_enforced) et pas encore acceptées, « Oui, continuer » échouait avec
/// « L'événement n'a pas pu être créé ». Le serveur répond maintenant 403 {"code": "terms_required"} : l'assistant
/// ouvre la feuille « Avant de publier », puis, une fois acceptées, relance tout seul l'enregistrement.
@MainActor
final class AIEventTermsTests: XCTestCase {
    private final class NoCookies: CookieJar {
        func allCookies() async -> [HTTPCookie] { [] }
        func keep(_ cookies: [HTTPCookie]) async {}
    }

    private final class SignedIn: WebStorage {
        func guestIdentity() async -> GuestIdentity? { nil }
        func readLocal(_ key: String) async -> String? { nil }
        func writeLocal(_ key: String, _ value: String?) {}
        func shareSession() async {}
        func refreshFeedbackBadge() {}
        func openInPage(_ url: URL) {}
        func accountToken() async -> String? { "jeton" }
        func accountChanged() async {}
        func storeSession(key: String, json: String) async {}
        func clearSession() async {}
    }

    static let draftJSON = """
    {"status":"ready","questions":[],"title":"Samedi party chez Boby","description":"","start":"2030-11-09T21:00","end":"",
     "place_query":"Chemin des Vignes 4, 1095 Lutry","place_name":"Chez Boby","price_chf":0,"max_participants":0,
     "category":"","audience":"","pot":false,"bring":[],"summary":"Samedi party."}
    """

    /// Les stores ne gardent la page qu'en référence faible : le test la garde.
    private let web = SignedIn()

    private func makeStore() throws -> (AIEventStore, ModerationStore) {
        TermsServer.reset()
        let api = PartyAPI(base: URL(string: "https://party.test")!, jar: NoCookies(), protocolClasses: [TermsServer.self])
        let store = AIEventStore(api: api, web: web)
        let moderation = ModerationStore(api: api, web: web)
        store.moderation = moderation
        let draft = try JSONDecoder().decode(AIEvent.Draft.self, from: Data(Self.draftJSON.utf8))
        store.showDemoReady(draft, place: AIEvent.Place(name: "Chez Boby", address: "Chemin des Vignes 4, 1095 Lutry",
                                                        url: "", latitude: 46.5, longitude: 6.7))
        XCTAssertTrue(store.canCreate)
        return (store, moderation)
    }

    private func waitFor(_ condition: @MainActor () -> Bool) async throws {
        for _ in 0..<200 where !condition() { try await Task.sleep(nanoseconds: 20_000_000) }
        XCTAssertTrue(condition())
    }

    func testTermsSheetOpensThenTheDraftIsSavedAfterAccepting() async throws {
        let (store, moderation) = try makeStore()
        let saving = Task { await store.create() }
        try await waitFor { store.askingTerms }
        XCTAssertNil(store.created)
        XCTAssertNil(store.error)  // pas de « n'a pas pu être créé » : la feuille, à la place
        // « J'accepte » de TermsAcceptSheet : l'acceptation est enregistrée, puis la feuille répond.
        let accepted = await moderation.acceptTerms()
        XCTAssertTrue(accepted)
        store.answerTerms(true)
        await saving.value
        XCTAssertFalse(store.askingTerms)
        XCTAssertEqual(store.created?.id, "3d966d59-11e2-4785-a543-7c91a9c2b877")
        XCTAssertTrue(store.openInviteSoon)  // l'étape 2 s'ouvre ensuite, comme sans CGU
        XCTAssertNil(store.error)
        XCTAssertEqual(TermsServer.calls.filter { $0 == "/api/account/ai/event/draft/save" }.count, 2)
        XCTAssertTrue(TermsServer.calls.contains("/api/account/moderation/terms/accept"))
    }

    func testLaterKeepsTheDraftAndSaysWhy() async throws {
        let (store, _) = try makeStore()
        let saving = Task { await store.create() }
        try await waitFor { store.askingTerms }
        store.answerTerms(false)  // « Plus tard » ou feuille fermée d'un geste
        await saving.value
        XCTAssertNil(store.created)
        XCTAssertNotNil(store.draft)  // rien de perdu
        XCTAssertEqual(store.error, "Accepte les conditions d'utilisation de Party pour publier (Réglages › Confidentialité).")
        XCTAssertEqual(TermsServer.calls.filter { $0 == "/api/account/ai/event/draft/save" }.count, 1)
    }

    func testTheServerCodeBecomesTermsRequired() {
        XCTAssertEqual(PartyAPIError.termsRequired("Accepte…").errorDescription, "Accepte…")
    }
}

/// Serveur Party simulé : CGU pas acceptées → draft/save répond 403 terms_required ; acceptées → le brouillon.
private final class TermsServer: URLProtocol {
    nonisolated(unsafe) static var accepted = false
    nonisolated(unsafe) static var calls: [String] = []

    static func reset() {
        accepted = false
        calls = []
    }

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        let path = request.url?.path ?? ""
        Self.calls.append(path)
        var status = 200
        var body: [String: Any]
        switch path {
        case "/api/account/ai/event/draft/save" where !Self.accepted:
            status = 403
            body = ["code": "terms_required",
                    "detail": "Accepte les conditions d'utilisation de Party pour publier (Réglages › Confidentialité)."]
        case "/api/account/ai/event/draft/save":
            body = ["id": "3d966d59-11e2-4785-a543-7c91a9c2b877", "status": "draft", "title": "Samedi party chez Boby",
                    "problems": [], "suggested": [], "preset": ["audience": "public", "group_ids": []]]
        case "/api/account/moderation/terms/accept":
            Self.accepted = true
            body = ["version": "2026-11-04", "accepted": true, "accepted_at": "2026-11-06T10:00:00Z", "enforced": true]
        case "/api/account/moderation/terms":
            body = ["version": "2026-11-04", "accepted": Self.accepted, "enforced": true]
        default:
            status = 404
            body = ["detail": "inconnu"]
        }
        let response = HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil,
                                       headerFields: ["Content-Type": "application/json"])!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: (try? JSONSerialization.data(withJSONObject: body)) ?? Data())
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}

import Foundation
import Testing
@testable import Party

/// Vitesse des Discussions (demande de l'admin du 18.11) : envoi optimiste (bulle tout de suite), réseau absent → message
/// gardé « Pas envoyé », jamais perdu (même écran fermé), nouvel essai avec le même identifiant ; refus de la base → le
/// message quitte la conversation (le texte revient dans le champ) ; champs v2 lus avec la conversation (une seule lecture).
@MainActor
@Suite(.serialized)
struct ChatsSendTests {
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

    /// Gardé ici : ChatsStore ne retient la page que faiblement.
    private let web = SignedIn()

    private func store() -> ChatsStore {
        SendServer.reset()
        ChatsStore.retryDelays = [.milliseconds(20), .milliseconds(20)]
        let api = PartyAPI(base: URL(string: "https://party.test")!, jar: NoCookies(), protocolClasses: [SendServer.self])
        return ChatsStore(api: api, web: web)
    }

    @Test("Réseau absent : la bulle reste « Pas envoyé », survit à la fermeture, puis repart avec le même identifiant")
    func offlineMessageIsKeptAndRetried() async throws {
        let store = store()
        await store.open("c1")
        #expect(store.conversation?.messages.map(\.id) == ["m1"])

        SendServer.offline = true
        let kept = await store.send("Salut ! On se voit vendredi ?", replyTo: nil)
        #expect(kept, "réseau absent : pas un refus, le texte ne revient pas dans le champ")
        let failed = try #require(store.conversation?.messages.last)
        #expect(failed.body == "Salut ! On se voit vendredi ?" && failed.failed && !failed.pending && failed.mine)
        // Premier envoi + 2 nouveaux essais automatiques, toujours le même identifiant.
        let tries = SendServer.sends()
        #expect(tries.count == 3 && Set(tries.compactMap { $0["id"] as? String }) == [failed.id])

        // Écran fermé puis rouvert : le message est toujours là (jamais perdu).
        store.close()
        await store.open("c1")
        // (le serveur répond : il repart aussitôt tout seul, encore hors ligne ici)
        #expect(store.conversation?.messages.contains { $0.id == failed.id && $0.body == failed.body } == true)

        // Réseau revenu : « Toucher pour réessayer » renvoie le même message (après le nouvel essai tout seul de la
        // réouverture, encore hors ligne).
        try await Task.sleep(for: .milliseconds(300))
        SendServer.offline = false
        await store.retry(failed)
        #expect(SendServer.sends().last?["id"] as? String == failed.id)
        let sent = try #require(store.conversation?.messages.first { $0.id == failed.id })
        #expect(!sent.failed && !sent.pending)
    }

    @Test("Envoyé : la bulle s'affiche avant la réponse du serveur, puis passe à ✓")
    func optimisticBubble() async throws {
        let store = store()
        await store.open("c1")
        SendServer.delay = 0.3
        let sending = Task { await store.send("Ça part tout de suite", replyTo: nil) }
        try await Task.sleep(for: .milliseconds(100))
        let bubble = try #require(store.conversation?.messages.last)
        #expect(bubble.body == "Ça part tout de suite" && bubble.pending, "bulle affichée pendant l'envoi")
        #expect(await sending.value)
        #expect(store.conversation?.messages.first { $0.id == bubble.id }?.pending == false)
    }

    @Test("Refus de la base (filtre) : le message quitte la conversation, l'explication s'affiche")
    func refusedMessageGoesBackToTheField() async {
        let store = store()
        await store.open("c1")
        SendServer.refuse = "Ce message ne respecte pas les règles de Party."
        let kept = await store.send("texte refusé", replyTo: nil)
        #expect(!kept)
        #expect(store.conversation?.messages.contains { $0.body == "texte refusé" } == false)
        #expect(store.notice == "Ce message ne respecte pas les règles de Party.")
        #expect(SendServer.sends().count == 1, "un refus n'est jamais renvoyé")
    }

    @Test("Champs v2 (carte de soirée, citation privée) lus dans la même réponse que la conversation")
    func extrasComeWithTheConversation() async throws {
        let store = store()
        await store.open("c1")
        #expect(store.error == nil, "\(store.error ?? "")")
        let extras = try #require(store.conversation?.extras)
        #expect(extras.first?.eventID == "e1")
        #expect(SendServer.paths().filter { $0 == "/api/account/chats/open" }.count == 1)
    }
}

/// Serveur Party simulé : conversation c1, envoi (réseau coupé, lent ou refus à la demande).
private final class SendServer: URLProtocol {
    nonisolated(unsafe) static var bodies: [[String: Any]] = []
    nonisolated(unsafe) static var offline = false
    nonisolated(unsafe) static var refuse: String?
    nonisolated(unsafe) static var delay: TimeInterval = 0

    static func reset() {
        bodies = []
        offline = false
        refuse = nil
        delay = 0
    }

    static func sends() -> [[String: Any]] { bodies.filter { $0["path"] as? String == "/api/account/chats/send" } }
    static func paths() -> [String] { bodies.compactMap { $0["path"] as? String } }

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    private static func body(of request: URLRequest) -> [String: Any] {
        var data = request.httpBody ?? Data()
        if data.isEmpty, let stream = request.httpBodyStream {
            stream.open()
            defer { stream.close() }
            var buffer = [UInt8](repeating: 0, count: 4096)
            while stream.hasBytesAvailable {
                let n = stream.read(&buffer, maxLength: buffer.count)
                if n <= 0 { break }
                data.append(buffer, count: n)
            }
        }
        return (try? JSONSerialization.jsonObject(with: data) as? [String: Any]) ?? [:]
    }

    private func reply(_ status: Int, _ json: Any) {
        let response = HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: ["Content-Type": "application/json"])!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: (try? JSONSerialization.data(withJSONObject: json)) ?? Data())
        client?.urlProtocolDidFinishLoading(self)
    }

    override func startLoading() {
        let path = request.url?.path ?? ""
        var sent = Self.body(of: request)
        sent["path"] = path
        Self.bodies.append(sent)
        switch path {
        case "/api/account/chats/send":
            if Self.offline { return client!.urlProtocol(self, didFailWithError: URLError(.notConnectedToInternet)) }
            if let refuse = Self.refuse { return reply(400, ["detail": refuse]) }
            if Self.delay > 0 { Thread.sleep(forTimeInterval: Self.delay) }
            reply(200, ["ok": true])
        case "/api/account/chats/open":
            reply(200, [
                "id": "c1", "name": "Léa", "member": true, "admin": false, "notify": "all", "can_name_admins": false, "me": "me",
                "reactions": [String](), "members": [[String: Any]](), "direct": true, "user_id": "u2",
                "messages": [["id": "m1", "author": "u2", "author_name": "Léa", "author_photo": NSNull(), "mine": false,
                              "at": "2026-11-18T10:00:00Z", "edited": false, "body": "Tu viens ?", "deleted": false, "photo": NSNull(),
                              "pinned": false, "reply": NSNull(), "reactions": [String](), "event_id": "e1", "quote": NSNull()]],
            ])
        case "/api/account/chats/rpc":
            reply(200, ["result": sent["fn"] as? String == "chat_list" ? [String]() as Any : NSNull()])
        case "/api/account/chats":
            reply(200, ["chats": [String](), "realtime": NSNull()])
        default:
            reply(200, ["ok": true])
        }
    }

    override func stopLoading() {}
}

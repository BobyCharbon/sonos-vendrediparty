import Foundation
import Testing
@testable import Party

/// « Ça me garde un message en non lu alors que je suis allé sur la conversation » (admin, 19.11) : la liste précharge
/// les premières conversations ; ouverte ensuite, la conversation n'apportait aucun message nouveau pour le téléphone et
/// l'app n'envoyait jamais « lu » (groupe, message direct). Désormais : « lu » à chaque ouverture, la ligne (non-lus et
/// « non lu » manuel) et la pastille de l'onglet passent à 0 aussitôt.
@MainActor
@Suite(.serialized)
struct ChatsReadTests {
    private final class NoCookies: CookieJar {
        func allCookies() async -> [HTTPCookie] { [] }
        func keep(_ cookies: [HTTPCookie]) async {}
    }

    /// Jeton au format Supabase (champ « sub ») : le préchargement et le cache du téléphone sont actifs, comme dans l'app.
    private final class SignedIn: WebStorage {
        let token: String = {
            let claims = try! JSONSerialization.data(withJSONObject: ["sub": UUID().uuidString.lowercased()])
            let payload = claims.base64EncodedString().replacingOccurrences(of: "=", with: "")
                .replacingOccurrences(of: "+", with: "-").replacingOccurrences(of: "/", with: "_")
            return "e30.\(payload).signature"
        }()
        func guestIdentity() async -> GuestIdentity? { nil }
        func readLocal(_ key: String) async -> String? { nil }
        func writeLocal(_ key: String, _ value: String?) {}
        func shareSession() async {}
        func refreshFeedbackBadge() {}
        func openInPage(_ url: URL) {}
        func accountToken() async -> String? { token }
        func accountChanged() async {}
        func storeSession(key: String, json: String) async {}
        func clearSession() async {}
    }

    private let web = SignedIn()

    private func store() -> ChatsStore {
        ReadServer.reset()
        let api = PartyAPI(base: URL(string: "https://party.test")!, jar: NoCookies(), protocolClasses: [ReadServer.self])
        return ChatsStore(api: api, web: web)
    }

    @Test("Conversation préchargée par la liste puis ouverte : « lu » envoyé, ligne et pastille à 0")
    func prefetchedConversationIsReadWhenOpened() async throws {
        let store = store()
        var told: [Int] = []
        store.onBadge = { told.append($0) }
        await store.loadList()
        #expect(store.chat("c1")?.unread == 1 && store.chat("c1")?.markedUnread == true)
        #expect(store.badge == 1 && told == [1])
        // Le préchargement (lecture seule) a mis le dernier message sur le téléphone.
        let account = try #require(ChatsCache.account(of: web.token))
        let cached = { ChatsCache.load(Conversation.self, account: account, name: "chat-c1") != nil }
        for _ in 0..<100 where !cached() { try await Task.sleep(for: .milliseconds(20)) }
        try await Task.sleep(for: .milliseconds(50))  // gardée en mémoire juste après le fichier
        #expect(ReadServer.paths().contains("prefetch") && cached())
        #expect(!ReadServer.paths().contains("/api/account/chats/read"), "précharger ne lit rien")

        await store.open("c1")
        #expect(store.conversation?.messages.map(\.id) == ["m1"])
        await ReadServer.settle()
        #expect(ReadServer.reads() == ["c1"], "ouvrir la conversation la note lue, même sans message nouveau, une seule fois")
        let row = try #require(store.chat("c1"))
        #expect(row.unread == 0 && !row.markedUnread)
        #expect(store.badge == 0 && told.last == 0, "pastille de l'onglet aussitôt à 0")
    }

    @Test("Rouverte (gardée en mémoire) : lue à chaque ouverture, une seule fois tant qu'elle reste ouverte")
    func reopenedConversationIsReadEachTime() async {
        let store = store()
        await store.open("c1")
        await store.open("c1")  // relecture régulière, rien de nouveau
        #expect(ReadServer.reads() == ["c1"])
        store.close()
        await store.open("c1")
        #expect(ReadServer.reads() == ["c1", "c1"])
    }

    @Test("Réseau absent au moment de lire : « lu » renvoyé à la relecture suivante")
    func readIsRetried() async {
        let store = store()
        ReadServer.readFails = true
        await store.open("c1")
        #expect(ReadServer.reads().isEmpty)
        ReadServer.readFails = false
        await store.open("c1")
        #expect(ReadServer.reads() == ["c1"])
    }

    @Test("Panne passagère de la base (503) : la liste v2 reste (discussions d'événement comprises), pas l'ancienne liste")
    func aPassingOutageKeepsTheListV2() async {
        let store = store()
        await store.loadList()
        #expect(store.chat("e1")?.isEvent == true)
        ReadServer.listDown = true
        await store.loadList()
        #expect(store.chat("e1")?.isEvent == true && store.chat("c1") != nil, "liste affichée gardée")
        ReadServer.listDown = false
        await store.loadList()
        let lists = ReadServer.bodies.filter { $0["fn"] as? String == "chat_list" }.count
        #expect(lists == 3, "la liste v2 est redemandée après la panne")
        #expect(store.chat("e1")?.isEvent == true)
    }

    @Test("Serveur lent, retour avant sa réponse (conversation affichée depuis la mémoire) : « lu » part quand même")
    func leavingBeforeTheServerAnswersStillReads() async throws {
        let store = store()
        await store.loadList()
        #expect(store.chat("c1")?.needsReading == true)
        ReadServer.openDelay = 1
        let opening = Task { await store.open("c1") }
        try await Task.sleep(for: .milliseconds(150))
        opening.cancel()  // « ‹ » : l'écran part, sa relecture est annulée
        store.close()
        await ReadServer.settle()
        #expect(ReadServer.reads() == ["c1"])
        #expect(store.chat("c1")?.unread == 0 && store.chat("c1")?.markedUnread == false && store.badge == 0)
    }
}

/// Serveur Party simulé : liste v2 (c1 : 1 non lu, marquée « non lu »), conversation c1, lecture.
private final class ReadServer: URLProtocol {
    nonisolated(unsafe) static var bodies: [[String: Any]] = []
    nonisolated(unsafe) static var readFails = false
    nonisolated(unsafe) static var openDelay: TimeInterval = 0
    nonisolated(unsafe) static var listDown = false

    static func reset() {
        bodies = []
        readFails = false
        openDelay = 0
        listDown = false
    }

    /// « Lu » envoyé à part (sans attendre la conversation) : laissé arriver.
    @MainActor static func settle() async {
        for _ in 0..<50 where reads().isEmpty { try? await Task.sleep(for: .milliseconds(20)) }
        try? await Task.sleep(for: .milliseconds(100))
    }

    static func paths() -> [String] {
        bodies.compactMap { b in (b["prefetch"] as? Bool == true) ? "prefetch" : b["path"] as? String }
    }

    static func reads() -> [String] {
        bodies.filter { $0["path"] as? String == "/api/account/chats/read" && $0["failed"] == nil }.compactMap { $0["group_id"] as? String }
    }

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

    private func reply(_ json: Any) { replyStatus(200, json) }

    private func replyStatus(_ status: Int, _ json: Any) {
        let response = HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: ["Content-Type": "application/json"])!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: (try? JSONSerialization.data(withJSONObject: json)) ?? Data())
        client?.urlProtocolDidFinishLoading(self)
    }

    override func startLoading() {
        let path = request.url?.path ?? ""
        var sent = Self.body(of: request)
        sent["path"] = path
        if path == "/api/account/chats/read", Self.readFails { sent["failed"] = true }
        Self.bodies.append(sent)
        let read = Self.reads().contains("c1")
        switch path {
        case "/api/account/chats/read":
            if Self.readFails { return client!.urlProtocol(self, didFailWithError: URLError(.notConnectedToInternet)) }
            reply(["ok": true])
        case "/api/account/chats/open":
            if Self.openDelay > 0, sent["prefetch"] as? Bool != true { Thread.sleep(forTimeInterval: Self.openDelay) }
            reply([
                "id": "c1", "name": "Léa", "member": true, "admin": false, "notify": "all", "can_name_admins": false, "me": "me",
                "reactions": [String](), "members": [[String: Any]](), "direct": true, "user_id": "u2",
                "messages": [["id": "m1", "author": "u2", "author_name": "Léa", "author_photo": NSNull(), "mine": false,
                              "at": "2026-11-19T10:00:00Z", "edited": false, "body": "Tu viens ?", "deleted": false, "photo": NSNull(),
                              "pinned": false, "reply": NSNull(), "reactions": [String](), "event_id": NSNull(), "quote": NSNull()]],
            ])
        case "/api/account/chats/rpc":
            switch sent["fn"] as? String {
            case "chat_list":
                if Self.listDown { return replyStatus(503, ["detail": "Ça n'a pas marché. Réessaie dans un instant."]) }
                reply(["result": [["kind": "direct", "id": "c1", "title": "Léa", "user_id": "u2",
                                   "last": ["id": "m1", "at": "2026-11-19T10:00:00Z", "from_me": false, "type": "text",
                                            "author": "Léa", "text": "Tu viens ?"],
                                   "unread": read ? 0 : 1, "marked_unread": !read],
                                  ["kind": "event", "id": "e1", "title": "Soirée", "unread": 0,
                                   "last": ["id": "m9", "at": "2026-11-19T09:00:00Z", "from_me": true, "type": "text", "text": "Salut"]]],
                       "realtime": NSNull()])
            case "chat_badge": reply(["result": read ? 0 : 1])
            default: reply(["result": NSNull()])
            }
        case "/api/account/chats":
            reply(["chats": [String](), "realtime": NSNull()])
        default:
            reply(["ok": true])
        }
    }

    override func stopLoading() {}
}

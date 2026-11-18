import Foundation
import Testing
@testable import Party

/// Discussions v2 (18.11.2026), conversation iPhone : modifier (15 min), répondre en privé, demandes de message, « Vu »,
/// « écrit… » (diffusion Supabase sans base) et appels du relais /api/account/chats/rpc.
@MainActor
@Suite(.serialized)
struct ConversationV2Tests {
    private func message(_ id: String, mine: Bool, at: Date, body: String = "Salut", pending: Bool = false,
                         announcement: Bool? = nil, author: String = "u2") -> Conversation.Message {
        Conversation.Message(id: id, author: mine ? "me" : author, authorName: mine ? "Moi" : "Léa", authorPhoto: nil, mine: mine,
                             at: ISO8601DateFormatter().string(from: at), edited: false, body: body, deleted: false, photo: nil,
                             pinned: announcement == true, reply: nil, reactions: [], announcement: announcement, pending: pending)
    }

    private func chat(_ id: String = "c1", direct: Bool = false, event: Bool = false, messages: [Conversation.Message] = []) -> Conversation {
        Conversation(id: id, name: "Raclette", member: true, admin: false, notify: .all, canNameAdmins: false, me: "me",
                     reactions: [], members: [], messages: messages, direct: direct ? true : nil, event: event ? true : nil)
    }

    @Test("Modifier : mon message texte, 15 minutes au plus, jamais dans une soirée ni une annonce")
    func editWindow() {
        let now = Date()
        #expect(ConversationRules.canEdit(message("a", mine: true, at: now.addingTimeInterval(-14 * 60)), isEvent: false, now: now))
        #expect(!ConversationRules.canEdit(message("b", mine: true, at: now.addingTimeInterval(-16 * 60)), isEvent: false, now: now))
        #expect(!ConversationRules.canEdit(message("c", mine: false, at: now), isEvent: false, now: now))
        #expect(!ConversationRules.canEdit(message("d", mine: true, at: now), isEvent: true, now: now))
        #expect(!ConversationRules.canEdit(message("e", mine: true, at: now, pending: true), isEvent: false, now: now))
        #expect(!ConversationRules.canEdit(message("f", mine: true, at: now, body: ""), isEvent: false, now: now))
        #expect(!ConversationRules.canEdit(message("g", mine: true, at: now, announcement: true), isEvent: false, now: now))
        #expect(ConversationRules.editRefusal(PartyAPIError.server("edit_window: trop tard")).hasPrefix("Ce message ne peut plus être modifié"))
        #expect(ConversationRules.editRefusal(PartyAPIError.server("Autre")) == "Autre")
    }

    @Test("Répondre en privé : d'où, quel nom, l'auteur et 140 caractères au plus")
    func privateQuote() {
        let long = String(repeating: "a", count: 300)
        let q = ConversationRules.quote(of: message("m", mine: false, at: Date(), body: long), in: chat())
        #expect(q.from == "group" && q.title == "Raclette" && q.author == "Léa")
        #expect(q.excerpt.count == 140 && q.excerpt.hasSuffix("…"))
        #expect(ConversationRules.quote(of: message("m", mine: false, at: Date()), in: chat(event: true)).from == "event")
        #expect(q.json["excerpt"] as? String == q.excerpt)
    }

    @Test("Demande : je l'ai écrite (ou rien encore) = envoyée ; l'autre a écrit = reçue ; sinon aucune")
    func requestSide() {
        let now = Date()
        #expect(ConversationRules.request(status: "active", messages: []) == nil)
        #expect(ConversationRules.request(status: "request", messages: []) == .outgoing)
        #expect(ConversationRules.request(status: "request", messages: [message("a", mine: true, at: now)]) == .outgoing)
        #expect(ConversationRules.request(status: "request", messages: [message("a", mine: false, at: now)]) == .incoming)
        #expect(ConversationRules.refusal("blocked") == "Tu ne peux pas écrire à cette personne.")
    }

    @Test("Vu : seulement sous mon dernier message, lu après son envoi")
    func seen() {
        let now = Date()
        let mine = message("a", mine: true, at: now)
        #expect(ConversationRules.seen(mine, lastMine: "a", seenAt: now.addingTimeInterval(5)))
        #expect(!ConversationRules.seen(mine, lastMine: "a", seenAt: now.addingTimeInterval(-5)))
        #expect(!ConversationRules.seen(mine, lastMine: "b", seenAt: now.addingTimeInterval(5)))
        #expect(!ConversationRules.seen(mine, lastMine: "a", seenAt: nil))
        #expect(!ConversationRules.seen(message("c", mine: false, at: now), lastMine: "c", seenAt: now.addingTimeInterval(5)))
    }

    @Test("« écrit… » : texte, canal partagé avec le web, message envoyé et signal reçu")
    func typing() throws {
        #expect(ConversationRules.typingLabel([], direct: false) == nil)
        #expect(ConversationRules.typingLabel(["Léa"], direct: true) == "écrit…")
        #expect(ConversationRules.typingLabel(["Léa"], direct: false) == "Léa écrit…")
        #expect(ConversationRules.typingLabel(["Léa", "Tom"], direct: false) == "Léa et Tom écrivent…")
        #expect(ConversationRules.typingLabel(["Léa", "Tom", "Noé"], direct: false) == "3 personnes écrivent…")
        #expect(ConversationRules.typingChannel(chat("d1", direct: true)) == "typing:direct:d1")
        #expect(ConversationRules.typingChannel(chat("g1")) == "typing:group:g1")
        #expect(ConversationRules.typingChannel(chat("e1", event: true)) == "typing:event:e1")

        let sent = ChatRealtime.typingMessage(topic: "realtime:typing:group:g1", payload: ["user": "me", "name": "Ludo"], ref: "4", joinRef: "1")
        let payload = try #require(sent["payload"] as? [String: Any])
        #expect(sent["event"] as? String == "broadcast" && sent["join_ref"] as? String == "1")
        #expect(payload["type"] as? String == "broadcast" && payload["event"] as? String == "typing")
        #expect((payload["payload"] as? [String: String])?["name"] == "Ludo")

        let received = #"{"event":"broadcast","topic":"realtime:typing:group:g1","payload":{"type":"broadcast","event":"typing","payload":{"user":"u2","name":"Léa"}}}"#
        #expect(ChatRealtime.typingPayload(received) == ["user": "u2", "name": "Léa"])
        #expect(ChatRealtime.typingPayload(#"{"event":"broadcast","payload":{"event":"other","payload":{"user":"u2"}}}"#) == nil)
        #expect(ChatRealtime.typingPayload(#"{"event":"phx_reply","payload":{"status":"ok"}}"#) == nil)
    }

    @Test("Champs v2 lus dans /chats/open : carte de soirée et citation privée, absents tolérés")
    func extrasDecode() throws {
        struct Open: Decodable { let messages: [MessageExtra] }
        let open = try JSONDecoder().decode(Open.self, from: Data("""
        {"messages":[{"id":"m1","event_id":"e1","quote":null},
                     {"id":"m2","quote":{"from":"group","title":"Foot","author":"Léa","excerpt":"On joue ?"}},
                     {"id":"m3"},
                     {"id":"m4","event_id":"e2","event_card":{"id":"e2","title":"Paintball","start":null,"place":null,"cover":null,"going":3,"mine":null}}]}
        """.utf8))
        #expect(open.messages.map(\.id) == ["m1", "m2", "m3", "m4"])
        #expect(open.messages[3].eventCard?.title == "Paintball" && open.messages[0].eventCard == nil)
        #expect(open.messages[0].eventID == "e1" && open.messages[0].quote == nil)
        #expect(open.messages[1].quote?.title == "Foot" && open.messages[2].eventID == nil)
        let card = try JSONDecoder().decode(ChatEventCard.self, from: Data("""
        {"id":"e1","title":"Raclette","start":"2026-11-21T18:30:00Z","place":"Chailly","cover":null,"going":8,"mine":"yes"}
        """.utf8))
        #expect(card.date != nil && card.going == 8 && card.mine == "yes")
    }

    // MARK: Relais (serveur simulé)

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

    @Test("Relais : session de ChatsStore, fonctions de la base, envoi avec citation, signalement avec contexte")
    func relay() async throws {
        ChatsServer.reset()
        let web = SignedIn()
        let api = PartyAPI(base: URL(string: "https://party.test")!, jar: NoCookies(), protocolClasses: [ChatsServer.self])
        let store = ChatsStore(api: api, web: web)
        let relay = try #require(ConversationRelay.of(store))
        #expect(relay.api === api)

        let opening = try await relay.openDirect("u2")
        #expect(opening == DirectOpening(chat: "d1", status: "request", reason: nil))
        #expect(try await relay.seen("d1") != nil)
        try await relay.run("accept_message_request", ["chat": "d1"])
        try await relay.run("mark_event_chat_read", ["e": "e1"])
        try await relay.edit("m1", body: "Corrigé", direct: true)
        try await relay.send(chat: "d1", direct: true, body: "Oui !", id: "x1",
                             quote: PrivateQuote(from: "group", title: "Foot", author: "Léa", excerpt: "On joue ?"))
        try await relay.report(ReportTarget(kind: .groupMessage, id: "m9", label: "le message"), reason: .spam, comment: "", context: true)
        let cards = try await relay.eventCards(["e1"])
        #expect(cards.first?.title == "Raclette")

        let rpc = ChatsServer.bodies.filter { $0["path"] as? String == "/api/account/chats/rpc" }
        #expect(rpc.map { $0["fn"] as? String } == ["open_direct_chat", "direct_seen", "accept_message_request", "mark_event_chat_read", "edit_direct_message",
                                                 "chat_event_cards"])
        #expect((rpc[0]["args"] as? [String: Any])?["target"] as? String == "u2")
        #expect((rpc[3]["args"] as? [String: Any])?["e"] as? String == "e1")
        #expect((rpc[4]["args"] as? [String: Any])?["new_body"] as? String == "Corrigé")
        #expect(rpc.allSatisfy { $0["token"] as? String == "jeton" })
        let send = try #require(ChatsServer.bodies.first { $0["path"] as? String == "/api/account/chats/send" })
        #expect((send["quote"] as? [String: Any])?["author"] as? String == "Léa" && send["direct"] as? Bool == true)
        let report = try #require(ChatsServer.bodies.first { $0["path"] as? String == "/api/account/moderation/report" })
        #expect(report["context"] as? Bool == true && report["kind"] as? String == "group_message")
    }
}

/// Serveur Party simulé : relais des Discussions, envoi, signalement.
private final class ChatsServer: URLProtocol {
    nonisolated(unsafe) static var bodies: [[String: Any]] = []

    static func reset() { bodies = [] }

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

    override func startLoading() {
        let path = request.url?.path ?? ""
        var sent = Self.body(of: request)
        sent["path"] = path
        Self.bodies.append(sent)
        var reply: Any = ["ok": true]
        if path == "/api/account/chats/rpc" {
            switch sent["fn"] as? String {
            case "open_direct_chat": reply = ["result": ["chat": "d1", "status": "request", "reason": NSNull()]]
            case "direct_seen": reply = ["result": "2026-11-18T10:00:00Z"]
            case "chat_event_cards":
                reply = ["result": [["id": "e1", "title": "Raclette", "start": "2026-11-21T18:30:00Z", "place": "Chailly",
                                     "cover": NSNull(), "going": 8, "mine": "yes"]]]
            default: reply = ["result": NSNull()]
            }
        }
        let response = HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: ["Content-Type": "application/json"])!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: (try? JSONSerialization.data(withJSONObject: reply)) ?? Data())
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}

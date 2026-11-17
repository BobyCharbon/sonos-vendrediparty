import Foundation
import SwiftUI
import Testing
@testable import Party

/// Discussion d'un événement façon WhatsApp (16.11.2026) : forme envoyée par le serveur (app/event_chats.py), fil
/// (jours, séries), @citations de l'organisation, bandeau des annonces et épinglés, notification → discussion.
struct EventChatTests {
    private func message(_ id: String, _ author: String, _ at: String, body: String = "x", pinned: Bool = false,
                         announcement: Bool? = nil) -> Conversation.Message {
        Conversation.Message(id: id, author: author, authorName: author, authorPhoto: nil, mine: false, at: at, edited: false,
                             body: body, deleted: false, photo: nil, pinned: pinned, reply: nil, reactions: [], announcement: announcement)
    }

    @Test("Le serveur : discussion d'événement, citations de l'organisation, réponse avec son message et son auteur")
    func decodesAnEventConversation() throws {
        let c = try JSONDecoder().decode(Conversation.self, from: Data("""
        {"id":"e1","name":"Raclette","member":true,"admin":true,"organizer":true,"event":true,"notify":"all","can_name_admins":false,
         "reactions":["👍"],"tags":[{"tag":"toutlemonde","hint":"Tout le monde"},{"tag":"present","hint":"Présents"}],
         "realtime":{"url":"wss://x/realtime/v1/websocket","key":"k"},
         "members":[{"id":"u1","name":"Léa","photo":null,"admin":false,"creator":false,"organizer":true,"rsvp":"maybe","invited":false}],
         "messages":[{"id":"m1","author":"u1","author_name":"Léa","author_photo":null,"mine":false,"at":"2026-11-16T10:00:00Z",
          "edited":false,"body":"Oui","deleted":false,"photo":null,"pinned":false,"reactions":[],
          "reply":{"id":"m0","author":"u2","name":"Tom","text":"On y va ?"}}]}
        """.utf8))
        #expect(c.isEvent && c.isStaff && c.tags?.map(\.tag) == ["toutlemonde", "present"] && c.realtime?.key == "k")
        #expect(c.members.first?.rsvp == "maybe" && c.messages.first?.reply?.id == "m0" && c.messages.first?.reply?.author == "u2")
    }

    @Test("Fil : un séparateur par jour, messages d'une personne regroupés à moins de 5 min, annonce toujours seule")
    func timelineGroupsSeries() {
        let rows = ChatTimeline.rows([
            message("a", "léa", "2026-11-15T20:00:00Z"),
            message("b", "léa", "2026-11-16T09:00:00Z"),
            message("c", "léa", "2026-11-16T09:03:00Z"),
            message("d", "léa", "2026-11-16T09:20:00Z"),
            message("e", "léa", "2026-11-16T09:21:00Z", pinned: true, announcement: true),
            message("f", "tom", "2026-11-16T09:22:00Z"),
        ], now: ISO8601DateFormatter().date(from: "2026-11-16T12:00:00Z")!)
        let shape = rows.map { row -> String in
            switch row.kind {
            case .day(let label): return "[\(label)]"
            case .message(let m, let first, let last): return "\(m.id)\(first ? "<" : "")\(last ? ">" : "")"
            }
        }
        #expect(shape == ["[Hier]", "a<>", "[Aujourd'hui]", "b<", "c>", "d<>", "e<>", "f<>"])
    }

    @Test("Citations : en couleur dans la bulle, mot entier ; @toutlemonde / @present repérés comme la base")
    func mentionsAreHighlighted() {
        let text = Mentions.highlighted("Salut @Léa et @toutlemonde, écris à lea@exemple.ch", names: ["Léa"], color: .pink)
        let bold = text.runs.filter { $0.inlinePresentationIntent == .stronglyEmphasized }.map { String(text[$0.range].characters) }
        #expect(bold == ["@Léa", "@toutlemonde"])
        #expect(Mentions.eventTag(in: "Rappel @présents : 19 h") != nil && Mentions.eventTag(in: "@toutlemonde!") != nil)
        #expect(Mentions.eventTag(in: "mail@toutlemonde.ch") == nil && Mentions.eventTag(in: "Salut @Léa") == nil)
    }

    @Test("Suggestions de l'@ : les citations de l'organisation d'un événement à la place de @tout")
    func eventTagsAreSuggested() {
        let tags = [Conversation.Tag(tag: "toutlemonde", hint: "Tout le monde"), Conversation.Tag(tag: "present", hint: "Présents")]
        let found = Mentions.suggestions(for: "to", members: [], me: nil, tags: tags).map(\.label)
        #expect(found == ["toutlemonde"])
        #expect(Mentions.suggestions(for: "pré", members: [], me: nil, tags: tags).map(\.label) == ["present"])
        #expect(Mentions.suggestions(for: "to", members: [], me: nil, tags: []).isEmpty)  // un invité : aucune
    }

    @Test("Bandeau : annonces d'abord, puis épinglés, les plus récents en tête")
    func pinsPutAnnouncementsFirst() throws {
        var c = try JSONDecoder().decode(Conversation.self, from: Data("""
        {"id":"e1","name":"R","member":true,"admin":true,"notify":"all","can_name_admins":false,"reactions":[],"members":[],"messages":[],
         "highlights":[{"id":"p1","author_name":"A","at":"1","text":"Code 4521","announcement":false},
                       {"id":"a1","author_name":"B","at":"2","text":"@annonce Parking","announcement":true},
                       {"id":"p2","author_name":"C","at":"3","text":"Plan","announcement":false}]}
        """.utf8))
        #expect(c.pins.map(\.id) == ["a1", "p2", "p1"])
        c = c.with(messages: [])
        #expect(ConversationView.clean("@annonce Parking derrière") == "Parking derrière")
    }

    @Test("Notification d'un message d'événement : la discussion native s'ouvre")
    func notificationOpensTheEventChat() {
        let id = "32f18a3b-827f-4123-8cf4-33de06c9a5aa"
        #expect(WebModel.eventChatRequested(in: URL(string: "https://x/?tab=events&event=\(id)&chat=1")!) == id)
        #expect(WebModel.eventChatRequested(in: URL(string: "https://x/?tab=events&event=\(id)")!) == nil)
        #expect(WebModel.eventChatRequested(in: URL(string: "https://x/?tab=events&event=pas-un-id&chat=1")!) == nil)
    }

    // MARK: Discussion native du 17.11 : réglages, non-lus, pages plus anciennes, médias, recherche

    private static let base = """
    "id":"e1","name":"Raclette","member":true,"admin":false,"notify":"all","can_name_admins":false,"reactions":[],"members":[],
    "event":true
    """

    private func conversation(_ extra: String = "", messages: [String] = ["m3", "m4"]) throws -> Conversation {
        let list = messages.map {
            #"{"id":"\#($0)","author":"u","author_name":"U","author_photo":null,"mine":false,"at":"2026-11-17T10:00:00Z","edited":false,"body":"\#($0)","deleted":false,"photo":null,"pinned":false,"reactions":[],"reply":null}"#
        }
        let json = "{\(Self.base),\"messages\":[\(list.joined(separator: ","))]\(extra)}"
        return try JSONDecoder().decode(Conversation.self, from: Data(json.utf8))
    }

    @Test("Serveur du 17.11 : niveau, sourdine, non-lus, qui écrit, description et carte de l'événement")
    func decodesTheNewFields() throws {
        let c = try conversation("""
        ,"level":"mentions","muted_until":"2030-01-01T00:00:00Z","unread":4,"write_mode":"staff","description":"Code 4521",
        "can_write":false,"event_card":{"title":"Raclette","starts_at":"2026-11-20T19:00:00Z","ends_at":null,"place":"Lutry",
        "cover":"https://x/c.jpg","going":12,"maybe":3,"organizer_name":"Boby"}
        """)
        #expect(c.level == .mentions && c.mutedUntil == "2030-01-01T00:00:00Z" && c.unread == 4)
        #expect(c.writeMode == "staff" && c.description == "Code 4521" && c.canWrite == false)
        #expect(c.eventCard == Conversation.EventCard(title: "Raclette", startsAt: "2026-11-20T19:00:00Z", endsAt: nil,
                                                      place: "Lutry", cover: "https://x/c.jpg", going: 12, maybe: 3,
                                                      organizerName: "Boby"))
        // Cache du téléphone : les nouveaux champs reviennent tels quels.
        let cached = try JSONDecoder().decode(Conversation.self, from: JSONEncoder().encode(c))
        #expect(cached == c)
    }

    @Test("Ancien serveur : sans les nouveaux champs, rien ne casse ; niveau inconnu = Mentions seulement")
    func oldServerStillDecodes() throws {
        let c = try conversation()
        #expect(c.level == nil && c.unread == nil && c.eventCard == nil && c.canWrite == nil && c.messages.count == 2)
        #expect(c.effectiveLevel() == .all)  // ancien « notify: all »
        #expect(try conversation(#","level":"bientot""#).level == .mentions)
    }

    @Test("Niveau effectif : rien pendant la sourdine (date à venir ou toujours), sinon le niveau choisi")
    func effectiveLevelFollowsTheMute() throws {
        let now = ISO8601DateFormatter().date(from: "2026-11-17T12:00:00Z")!
        #expect(try conversation(#","level":"all","muted_until":"2026-11-17T20:00:00Z""#).effectiveLevel(now: now) == ChatNotifyLevel.none)
        #expect(try conversation(#","level":"all","muted_until":"infinity""#).effectiveLevel(now: now) == ChatNotifyLevel.none)
        #expect(try conversation(#","level":"all","muted_until":"2026-11-17T08:00:00.123Z""#).effectiveLevel(now: now) == .all)
        #expect(try conversation(#","level":"mentions","muted_until":null"#).isMuted(now: now) == false)
    }

    @Test("Pages plus anciennes : ajoutées au-dessus, sans doublon, dans l'ordre")
    func olderPagesMergeWithoutDuplicates() throws {
        let c = try conversation(#","unread":2"#, messages: ["m3", "m4"])
        let older = try conversation(messages: ["m1", "m2", "m3", "m2"]).messages
        #expect(Conversation.merge(older: older, into: c.messages).map(\.id) == ["m1", "m2", "m3", "m4"])
        #expect(c.with(messages: []).unread == 2)  // with(messages:) garde tous les autres champs
    }

    @Test("Médias et recherche : forme du serveur, lien absent toléré")
    func decodesMediaAndSearch() throws {
        let media = try JSONDecoder().decode([ChatMediaItem].self, from: Data("""
        [{"message_id":"m1","kind":"photo","url":"https://x/p.jpg","at":"1","author_name":"Léa","text":null},
         {"message_id":"m1","kind":"link","url":"https://exemple.ch","at":"1","author_name":"Léa","text":"Le plan"},
         {"message_id":"m2","kind":"audio","url":null,"at":"2","author_name":"Tom"}]
        """.utf8))
        #expect(media.map(\.kind) == ["photo", "link", "audio"] && Set(media.map(\.id)).count == 3 && media[2].url.isEmpty)
        let found = try JSONDecoder().decode([ChatSearchResult].self, from: Data("""
        [{"message_id":"m9","at":"3","author_name":"Léa","snippet":"…la raclette…"}]
        """.utf8))
        #expect(found.first?.id == "m9" && found.first?.snippet == "…la raclette…")
    }

    /// Le magasin ne garde la page qu'en référence faible : le test la garde (second élément).
    @MainActor
    private func store(events: Bool = true) throws -> (ChatsStore, EventChatSignedIn) {
        let web = EventChatSignedIn()
        let api = PartyAPI(base: URL(string: "https://party.test")!, jar: EventChatNoCookies(), protocolClasses: [EventChatServer.self])
        let store = ChatsStore(api: api, web: web, forEvents: events)
        store.showDemo(conversation: try conversation(#","level":"mentions","unread":3"#, messages: ["m3", "m4"]))
        return (store, web)
    }

    @MainActor @Test("Niveau changé tout de suite et gardé ; sourdine refusée par le serveur : remise comme avant")
    func optimisticPrefsAndRollback() async throws {
        let (store, web) = try store()
        await store.setLevel(.all)
        #expect(store.conversation?.level == .all && store.effectiveLevel == .all)
        await store.mute(until: .distantFuture)  // le serveur simulé refuse la sourdine
        #expect(store.conversation?.mutedUntil == nil && !store.isMuted && store.notice != nil)
        withExtendedLifetime(web) {}
    }

    @MainActor @Test("Lu : non-lus à 0 ; plus anciens : ajoutés au-dessus, puis fin ; recherche puis jumpTo")
    func markReadAndLoadOlder() async throws {
        let (store, web) = try store()
        await store.markRead()
        #expect(store.conversation?.unread == 0)
        await store.loadOlder()
        #expect(store.conversation?.messages.map(\.id) == ["m1", "m2", "m3", "m4"] && store.hasOlder)
        await store.loadOlder()  // le serveur simulé ne rend plus rien de neuf
        #expect(store.conversation?.messages.count == 4 && !store.hasOlder)
        await store.reveal("m2")
        #expect(store.jumpTo == "m2")
        let found = await store.search("raclette")
        #expect(found.map(\.id) == ["m2"])
        withExtendedLifetime(web) {}
    }

    @MainActor @Test("Discussion de groupe : les gestes d'événement ne font rien")
    func groupChatsIgnoreEventCalls() async throws {
        let (store, web) = try store(events: false)
        await store.setLevel(.none)
        await store.markRead()
        await store.loadOlder()
        #expect(store.conversation?.level == .mentions && store.conversation?.unread == 3 && store.conversation?.messages.count == 2)
        let media = await store.media()
        let found = await store.search("x")
        #expect(media.isEmpty && found.isEmpty && store.notice == nil)
        withExtendedLifetime(web) {}
    }
}

private final class EventChatNoCookies: CookieJar {
    func allCookies() async -> [HTTPCookie] { [] }
    func keep(_ cookies: [HTTPCookie]) async {}
}

private final class EventChatSignedIn: WebStorage {
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

/// Serveur simulé des routes /api/account/event-chat/* (sans état : les tests tournent en parallèle).
private final class EventChatServer: URLProtocol {
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    private static func message(_ id: String) -> [String: Any] {
        ["id": id, "author": "u", "author_name": "U", "author_photo": NSNull(), "mine": false, "at": "2026-11-17T09:00:00Z",
         "edited": false, "body": id, "deleted": false, "photo": NSNull(), "pinned": false, "reactions": [Any](), "reply": NSNull()]
    }

    override func startLoading() {
        var status = 200
        var body: [String: Any] = [:]
        switch request.url?.path ?? "" {
        case "/api/account/event-chat/mute": status = 500; body = ["detail": "Réessaie"]
        case "/api/account/event-chat/older": body = ["messages": [Self.message("m1"), Self.message("m2")]]
        case "/api/account/event-chat/search":
            body = ["results": [["message_id": "m2", "at": "2026-11-17T09:00:00Z", "author_name": "U", "snippet": "raclette"]]]
        case "/api/account/event-chat/notify", "/api/account/event-chat/read": body = ["ok": true]
        default: status = 404; body = ["detail": "Not Found"]
        }
        let response = HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: nil)!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: (try? JSONSerialization.data(withJSONObject: body)) ?? Data())
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}

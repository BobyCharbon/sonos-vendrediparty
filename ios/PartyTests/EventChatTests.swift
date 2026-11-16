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
}

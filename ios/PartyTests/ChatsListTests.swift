import Foundation
import Testing
@testable import Party

/// Discussions v2 (liste « Néon club ») : chat_list, tri, filtres, Demandes / Archivées, pastille, textes.
struct ChatsListTests {
    private func decode<T: Decodable>(_ json: String) throws -> T {
        try JSONDecoder().decode(T.self, from: Data(json.utf8))
    }

    private func row(_ id: String, kind: String = "group", at: String? = "2026-11-18T10:00:00Z", unread: Int = 0,
                     pinned: String? = nil, archived: Bool = false, request: String? = nil, notify: String = "all",
                     muted: String? = nil, marked: Bool = false) throws -> ChatSummary {
        var json: [String: Any] = ["kind": kind, "id": id, "title": "Discussion \(id)", "unread": unread, "archived": archived,
                                   "notify": notify, "marked_unread": marked]
        if let at { json["last"] = ["id": "m-\(id)", "at": at, "from_me": false, "author": "Léa", "type": "text", "text": "Salut"] }
        if let pinned { json["pinned_at"] = pinned }
        if let request { json["request"] = request }
        if let muted { json["muted_until"] = muted }
        return try JSONDecoder().decode(ChatSummary.self, from: JSONSerialization.data(withJSONObject: json))
    }

    @Test("chat_list : direct, groupe, soirée, Membres Vendredi Party ; le cache relit la même ligne")
    func decodesChatList() throws {
        let list: [ChatSummary] = try decode("""
        [{"kind":"direct","id":"d1","title":"Léa Martin","photo":"https://x/lea.jpg","emoji":null,"color":null,"user_id":"u-lea",
          "event_start":null,"event_past":false,
          "last":{"id":"m1","at":"2026-11-18T20:48:00Z","from_me":true,"author":"Boby","type":"text","text":"À ce soir"},
          "unread":0,"mention":false,"marked_unread":true,"pinned_at":"2026-11-18T09:00:00Z","archived":false,
          "notify":"all","muted_until":null,"request":null,"seen_by_other":true,"members":2,"is_vp":false,"blocked":false},
         {"kind":"group","id":"g1","title":"Les Copains du Jura","photo":null,"emoji":"🥾","color":"mint","user_id":null,
          "last":{"id":"m2","at":"2026-11-18T20:40:00Z","from_me":false,"author":"Noé","type":"text","text":"@Sam tu prends la voiture ?"},
          "unread":3,"mention":true,"notify":"mentions","members":12,"is_vp":false},
         {"kind":"event","id":"e1","title":"Raclette chez Léa","event_start":"2026-11-21T19:00:00Z","event_past":false,
          "last":{"id":"m3","at":"2026-11-18T19:00:00Z","from_me":false,"author":"Julien","type":"photo","text":null},
          "unread":12,"notify":"all"},
         {"kind":"group","id":"vp","title":"Membres Vendredi Party","is_vp":true,"last":null,"unread":0}]
        """)
        let (d, g, e, vp) = (list[0], list[1], list[2], list[3])
        #expect(d.direct && d.userID == "u-lea" && d.name == "Léa Martin" && d.member)
        #expect(d.pinned && d.markedUnread && d.needsReading && d.seenByOther == true && d.members == 2)
        #expect(d.last == "Toi : À ce soir" && d.lastAt == "2026-11-18T20:48:00Z")
        #expect(g.kind == .group && g.emoji == "🥾" && g.mention && g.notify == .mentions)
        #expect(g.last == "Noé : @Sam tu prends la voiture ?")
        #expect(e.isEvent && !e.direct && e.eventStart == "2026-11-21T19:00:00Z" && e.last == "Julien : 📷 Photo")
        #expect(vp.system && vp.last == nil && vp.lastAt == nil)
        for item in list {
            #expect(try JSONDecoder().decode(ChatSummary.self, from: JSONEncoder().encode(item)) == item)
        }
    }

    @Test("Ancien format (my_chats) : toujours lu, et le cache le garde")
    func oldFormatStillReads() throws {
        let old: ChatSummary = try decode("""
        {"id":"g1","name":"Les amis","kind":"group","member":true,"notify":"all","last":"Léa : Salut","last_at":"2026-11-04T10:00:00Z","unread":2}
        """)
        #expect(old.kind == .group && old.last == "Léa : Salut" && old.lastMessage == nil && !old.pinned && !old.archived)
        #expect(try JSONDecoder().decode(ChatSummary.self, from: JSONEncoder().encode(old)) == old)
    }

    @Test("Tri : épinglées (la plus récemment épinglée d'abord), puis le dernier message le plus récent")
    func sortsPinnedThenRecent() throws {
        let list = [try row("a", at: "2026-11-18T08:00:00Z"),
                    try row("b", at: "2026-11-18T12:00:00Z"),
                    try row("c", at: "2026-11-17T08:00:00Z", pinned: "2026-11-10T00:00:00Z"),
                    try row("d", at: "2026-11-16T08:00:00Z", pinned: "2026-11-12T00:00:00Z"),
                    try row("e", at: nil)]
        #expect(ChatListLogic.sorted(list).map(\.id) == ["d", "c", "b", "a", "e"])
    }

    @Test("Liste principale sans archivées ni demandes reçues ; Demandes et Archivées à part ; épinglées en tuiles")
    func splitsTheList() throws {
        let list = [try row("a"), try row("p", pinned: "2026-11-18T00:00:00Z"), try row("arch", archived: true),
                    try row("in", kind: "direct", request: "incoming"), try row("out", kind: "direct", request: "outgoing")]
        #expect(ChatListLogic.main(list).map(\.id).sorted() == ["a", "out", "p"])
        #expect(ChatListLogic.pinned(list, filter: .all).map(\.id) == ["p"])
        #expect(ChatListLogic.rows(list, filter: .all).map(\.id).sorted() == ["a", "out"])
        #expect(ChatListLogic.requests(list).map(\.id) == ["in"])
        #expect(ChatListLogic.archived(list).map(\.id) == ["arch"])
    }

    @Test("Filtres : Non lus (non lus ou marquée), Personnes, Groupes, Soirées")
    func filters() throws {
        let list = [try row("g", unread: 2), try row("d", kind: "direct"), try row("m", kind: "direct", marked: true),
                    try row("e", kind: "event")]
        #expect(ChatListLogic.rows(list, filter: .unread).map(\.id).sorted() == ["g", "m"])
        #expect(ChatListLogic.rows(list, filter: .people).map(\.id).sorted() == ["d", "m"])
        #expect(ChatListLogic.rows(list, filter: .groups).map(\.id) == ["g"])
        #expect(ChatListLogic.rows(list, filter: .events).map(\.id) == ["e"])
        #expect(ChatListLogic.unreadChats(list) == 2)
        #expect(ChatFilter.allCases.map(\.label) == ["Tout", "Non lus", "Personnes", "Groupes", "Soirées"])
    }

    @Test("Pastille : non lus hors archivées et hors sourdine, + 1 par demande reçue")
    func badge() throws {
        let now = ChatDates.parse("2026-11-18T12:00:00Z")!
        let list = [try row("a", unread: 3), try row("arch", unread: 5, archived: true), try row("rien", unread: 4, notify: "none"),
                    try row("1h", unread: 6, muted: "2026-11-18T13:00:00Z"), try row("fini", unread: 2, muted: "2026-11-18T11:00:00Z"),
                    try row("in", kind: "direct", unread: 1, request: "incoming")]
        #expect(ChatListLogic.badge(list, now: now) == 3 + 2 + 1)
        #expect(try row("1h", muted: "2026-11-18T13:00:00Z").isMuted(now: now))
        #expect(try !row("fini", muted: "2026-11-18T11:00:00Z").isMuted(now: now))
    }

    @Test("Aperçu : « Toi : », auteur dans un groupe (jamais dans un direct), photo, vocal, soirée, supprimé")
    func previews() {
        #expect(ChatListText.preview(of: ChatLast(fromMe: true, author: "Boby", type: "text", text: "Coucou"), kind: .group) == "Toi : Coucou")
        #expect(ChatListText.preview(of: ChatLast(author: "Léa", type: "text", text: "Salut"), kind: .group) == "Léa : Salut")
        #expect(ChatListText.preview(of: ChatLast(author: "Léa", type: "text", text: "Salut"), kind: .direct) == "Salut")
        #expect(ChatListText.preview(of: ChatLast(author: "Léa", type: "audio"), kind: .direct) == "🎤 Message vocal")
        #expect(ChatListText.preview(of: ChatLast(type: "photo", text: "Le lac"), kind: .direct) == "📷 Le lac")
        #expect(ChatListText.preview(of: ChatLast(fromMe: true, type: "event", text: "Raclette"), kind: .direct) == "Toi : 📅 Raclette")
        #expect(ChatListText.preview(of: ChatLast(author: "Léa", type: "deleted", text: "x"), kind: .group) == "Message supprimé")
    }

    @Test("Deuxième ligne : demande envoyée, personne bloquée, aucun message")
    func subtitles() throws {
        #expect(ChatListText.subtitle(try row("o", kind: "direct", request: "outgoing")) == "Demande envoyée")
        let blocked: ChatSummary = try decode(#"{"kind":"direct","id":"b","title":"Tom","blocked":true,"last":null}"#)
        #expect(ChatListText.subtitle(blocked) == "Tu as bloqué cette personne")
        #expect(ChatListText.subtitle(try row("v", at: nil)) == "Aucun message pour l'instant")
    }

    @Test("Heure : 21:48 aujourd'hui, Hier, jour de la semaine, puis 28.10 (28.10.25 une autre année)")
    func times() {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "Europe/Zurich")!
        let now = ChatDates.parse("2026-11-18T20:00:00Z")!  // mercredi 21:00 en Suisse
        #expect(ChatListText.time("2026-11-18T20:48:00Z", now: now, calendar: calendar) == "21:48")
        #expect(ChatListText.time("2026-11-17T10:00:00Z", now: now, calendar: calendar) == "Hier")
        #expect(ChatListText.time("2026-11-16T10:00:00Z", now: now, calendar: calendar) == "Lun.")
        #expect(ChatListText.time("2026-10-28T10:00:00Z", now: now, calendar: calendar) == "28.10")
        #expect(ChatListText.time("2025-10-28T10:00:00Z", now: now, calendar: calendar) == "28.10.25")
        #expect(ChatListText.time(nil, now: now, calendar: calendar) == "")
    }

    @Test("Recherche « Discussions » : sans accents ni majuscules, jamais les demandes reçues")
    func searchesTitles() throws {
        let list: [ChatSummary] = try decode("""
        [{"kind":"group","id":"g","title":"Soirée Raclette"},{"kind":"direct","id":"d","title":"Élodie"},
         {"kind":"direct","id":"r","title":"Raclette Fan","request":"incoming"}]
        """)
        #expect(ChatListLogic.matching(list, query: "RACLETTE").map(\.id) == ["g"])
        #expect(ChatListLogic.matching(list, query: "elo").map(\.id) == ["d"])
        #expect(ChatListLogic.matching(list, query: "  ").isEmpty)
    }

    @Test("Sourdine : 1 h, 8 h, 1 semaine ; « Toujours » sans fin (réglage Rien)")
    func muteSpans() {
        let now = ChatDates.parse("2026-11-18T12:00:00Z")!
        #expect(ChatListLogic.muteEnd(.hour, now: now) == "2026-11-18T13:00:00Z")
        #expect(ChatListLogic.muteEnd(.week, now: now) == "2026-11-25T12:00:00Z")
        #expect(ChatListLogic.muteEnd(.always, now: now) == nil)
        let forever: ChatSummary = try! decode(#"{"kind":"group","id":"g","title":"G","notify":"all","muted_until":"infinity"}"#)
        #expect(forever.isMuted(now: now))
        #expect(ChatMuteSpan.allCases.map(\.label) == ["1 heure", "8 heures", "1 semaine", "Toujours"])
    }

    @Test("Personnes, messages trouvés, ouverture d'un message direct, demande : formats et textes")
    func peopleAndRequests() throws {
        let s: ChatPeopleSuggestions = try decode("""
        {"recent":[],"crossed":[{"id":"u1","name":"Léa Martin","nickname":"lea","photo":null,"sub":"Raclette chez Léa","link":"direct","met_count":2},
                               {"id":"u2","name":"Noé","sub":"","link":"request","met_count":3}]}
        """)
        #expect(s.crossed.count == 2 && s.groups.isEmpty)
        #expect(s.crossed[0].detail == "Raclette chez Léa" && s.crossed[0].firstName == "Léa")
        #expect(s.crossed[1].detail == "Déjà vu 3 fois" && s.crossed[1].link == "request")
        #expect(ChatPerson.metText(1) == "Déjà vu 1 fois" && ChatPerson.metText(0) == nil)

        let hits: [ChatMessageHit] = try decode(#"[{"kind":"event","id":"e1","title":"Raclette","message_id":"m9","excerpt":"on amène le fromage","at":"2026-11-18T10:00:00Z"}]"#)
        #expect(hits[0].kind == .event && hits[0].chatID == "e1" && hits[0].id == "m9")

        let refused: ChatOpenResult = try decode(#"{"chat":null,"status":"none","reason":"closed"}"#)
        #expect(refused.refusal == "Cette personne ne reçoit pas de demandes de message.")
        let opened: ChatOpenResult = try decode(#"{"chat":"c1","status":"request","reason":null}"#)
        #expect(opened.chat == "c1" && opened.status == "request")

        let who: ChatRequester = try decode(#"{"id":"u3","name":"Tom","met_count":0,"groups_count":2,"events_count":1,"since":null}"#)
        #expect(who.facts == ["Jamais rencontré", "2 groupes en commun", "1 soirée à venir ensemble"])
    }

    @Test("VoiceOver : sorte, état et dernier message dans la lecture de la ligne")
    func accessibility() throws {
        let now = ChatDates.parse("2026-11-18T12:00:00Z")!
        let g = try row("g", at: "2026-11-18T11:00:00Z", unread: 3, pinned: "2026-11-18T00:00:00Z", notify: "none")
        let text = ChatListText.accessibility(g, now: now)
        #expect(text.hasPrefix("Groupe, Discussion g, épinglée, 3 non lus, en sourdine, Léa : Salut"))
    }
}

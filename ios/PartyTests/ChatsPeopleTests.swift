import Foundation
import Testing
@testable import Party

/// Discussions v2 (18.11), personnes : mini-profil (member_mini), personnes proposées (P), « Déjà vu », choix
/// conversation / groupe de « Nouveau message », réponse d'open_direct_chat, pont PartyNative.chat.
struct ChatsPeopleTests {
    private func decode<T: Decodable>(_ json: String, as: T.Type = T.self) throws -> T {
        try PeopleStore.decoder.decode(T.self, from: Data(json.utf8))
    }

    private func person(_ id: String, _ name: String, link: String = "direct") -> ChatPerson {
        ChatPerson(id: id, name: name, nickname: nil, photo: nil, sub: nil, link: link, metCount: nil)
    }

    @Test("member_mini : tout le contrat, 3 dernières soirées au plus, compteurs")
    func decodesMemberMini() throws {
        let m: MemberMini = try decode("""
        {"id":"u-noe","name":"Noé Gaillard","nickname":"Noé","photo":"https://x/noe.jpg","since":"2026-03-01T10:00:00Z",
         "link":"request","blocked":false,"blocked_me":false,"chat":null,"met_count":4,
         "met":[{"id":"e1","title":"Raclette","start":"2026-11-14T19:00:00Z"},{"id":"e2","title":"Paintball","start":"2026-11-01T13:00:00Z"},
                {"id":"e3","title":"Karaoké","start":"2026-10-20T20:00:00Z"},{"id":"e4","title":"Pique-nique","start":"2026-09-01T12:00:00Z"}],
         "events":[{"id":"e5","title":"Soirée raclette chez Léa","start":"2026-11-21T19:00:00Z","mine":"yes","theirs":"yes"}],
         "groups":[{"id":"g1","name":"Les Copains du Jura","emoji":"🥾","color":"mint","photo":null}],
         "events_count":1,"groups_count":2}
        """, as: MemberMini.self)
        #expect(m.name == "Noé Gaillard" && m.nickname == "Noé" && m.link == "request" && m.canWrite && !m.restricted)
        #expect(m.metCount == 4 && m.met.map(\.id) == ["e1", "e2", "e3"])
        #expect(m.events.first?.mine == "yes" && m.groups.first?.emoji == "🥾" && m.groupsCount == 2 && m.chat == nil)
        #expect(m.person.short == "Noé" && m.person.metCount == 4)
    }

    @Test("member_mini restreint (l'autre m'a bloqué) : nom et photo seulement, personne à qui écrire")
    func decodesRestrictedMini() throws {
        let m: MemberMini = try decode(#"{"id":"u-x","name":"Max","photo":null,"link":"none","blocked_me":true}"#, as: MemberMini.self)
        #expect(m.restricted && !m.canWrite && !m.blocked && m.metCount == 0 && m.met.isEmpty && m.events.isEmpty && m.groups.isEmpty)
    }

    @Test("P : décodage, « Croisés récemment » sans doublon, sous-titre « Déjà vu » quand sub est vide")
    func decodesPeople() throws {
        let s: PeopleSuggestions = try decode("""
        {"recent":[{"id":"u1","name":"Léa Rochat","nickname":"Léa","photo":null,"sub":"","link":"direct","met_count":3}],
         "crossed":[{"id":"u1","name":"Léa Rochat","nickname":"Léa","photo":null,"sub":"Raclette","link":"direct","met_count":3},
                    {"id":"u2","name":"Chloé Blanc","nickname":null,"photo":null,"sub":"Anniv' Bastien","link":"request","met_count":0}],
         "groups":[{"id":"u3","name":"Kevin Monnier","nickname":"Kev","photo":null,"sub":"Basket du mardi","link":"direct","met_count":1}]}
        """, as: PeopleSuggestions.self)
        #expect(s.row.map(\.id) == ["u1", "u2"])
        #expect(PeopleText.sub(s.recent[0]) == "Déjà vu 3 fois")
        #expect(PeopleText.sub(s.crossed[1]) == "Anniv' Bastien")
        #expect(s.crossed[1].isRequest && s.crossed[1].short == "Chloé")
        let empty: PeopleSuggestions = try decode("{}", as: PeopleSuggestions.self)
        #expect(empty.isEmpty)
    }

    @Test("« Jamais rencontré », « Déjà vu 1 fois », « Déjà vu N fois »")
    func metTexts() {
        #expect(PeopleText.met(0) == "Jamais rencontré")
        #expect(PeopleText.met(1) == "Déjà vu 1 fois")
        #expect(PeopleText.met(4) == "Déjà vu 4 fois")
        #expect(PeopleText.sub(person("u", "Zoé")) == nil)
    }

    @Test("Nouveau message : 1 personne = conversation (ou demande), plusieurs = groupe")
    func plan() {
        let lea = person("u1", "Léa Rochat"), noe = person("u2", "Noé Gaillard", link: "request")
        #expect(NewMessagePlan([]) == .none && NewMessagePlan([]).title == nil)
        #expect(NewMessagePlan([lea]) == .direct(lea, request: false))
        #expect(NewMessagePlan([lea]).title == "Écrire à Léa" && NewMessagePlan([lea]).note == nil)
        #expect(NewMessagePlan([noe]) == .direct(noe, request: true))
        #expect(NewMessagePlan([noe]).note?.hasPrefix("Ce sera une demande de message") == true)
        #expect(NewMessagePlan([lea, noe]) == .group([lea, noe]))
        #expect(NewMessagePlan([lea, noe]).title == "Créer un groupe avec Léa et Noé")
        #expect(NewMessagePlan([lea, noe]).note == "2 personnes : ce sera un groupe")
        let five = (1...5).map { person("p\($0)", "P\($0)") }
        #expect(NewMessagePlan(five).title == "Créer un groupe avec P1, P2 et 3 autres")
    }

    @Test("open_direct_chat : une conversation qui existe s'ouvre ; sinon les règles ou la raison, sans dire qui a bloqué")
    func directOutcome() throws {
        let opened: DirectOpen = try decode(#"{"chat":"c1","status":"request","reason":null}"#, as: DirectOpen.self)
        #expect(opened.outcome == .chat("c1"))
        let old: DirectOpen = try decode(#"{"chat":"c2","status":"none","reason":"blocked"}"#, as: DirectOpen.self)
        #expect(old.outcome == .chat("c2"))
        let terms: DirectOpen = try decode(#"{"chat":null,"status":"none","reason":"terms_required"}"#, as: DirectOpen.self)
        #expect(terms.outcome == .terms)
        let blocked: DirectOpen = try decode(#"{"chat":null,"status":"none","reason":"blocked"}"#, as: DirectOpen.self)
        guard case .refused(let text) = blocked.outcome else { Issue.record("refus attendu"); return }
        #expect(!text.localizedCaseInsensitiveContains("bloqu"))
        #expect(PeopleText.refusal("limit").contains("demain"))
        #expect(WriteDirectResult.opened.problem == nil)
    }

    @Test("À venir ensemble : « Vous venez tous les deux », « Noé vient · toi : peut-être »")
    func together() throws {
        let both: MemberMini.Upcoming = try decode(#"{"id":"e","title":"T","mine":"organizer","theirs":"yes"}"#, as: MemberMini.Upcoming.self)
        #expect(PeopleText.together(both, them: "Noé") == "Vous venez tous les deux")
        let maybe: MemberMini.Upcoming = try decode(#"{"id":"e","title":"T","mine":"maybe","theirs":"yes"}"#, as: MemberMini.Upcoming.self)
        #expect(PeopleText.together(maybe, them: "Noé") == "Noé vient · toi : peut-être")
    }

    @Test("Pont PartyNative.chat : openDirect et newMessage seulement avec un vrai identifiant")
    func bridge() {
        let id = "8F1C2A3B-1111-4222-8333-944455556666"
        #expect(PeopleRoute.bridge("direct:\(id)")?.direct == id.lowercased())
        #expect(PeopleRoute.bridge("new")?.newMessage == .newMessage(event: nil))
        #expect(PeopleRoute.bridge("new:\(id)")?.newMessage == .newMessage(event: id.lowercased()))
        #expect(PeopleRoute.bridge("direct:../../x") == nil)
        #expect(PeopleRoute.bridge("new:pas-un-id") == nil)
        #expect(PeopleRoute.bridge("group:\(id)") == nil)
    }

    @Test("Nouveau groupe : mêmes 16 emojis et 6 couleurs que la base")
    func closedLists() {
        #expect(NewChatGroupView.emojis.count == 16 && Set(NewChatGroupView.emojis).count == 16)
        #expect(NewChatGroupView.colors.map(\.key) == PronoTheme.groupColors)
    }
}

import Foundation
import Testing
@testable import Party

/// Écran de la discussion DANS un événement (17.11.2026) : sous-titre de l'en-tête, cloche des notifications, sourdine,
/// glissé de retour et liens qui ouvrent l'écran.
struct EventChatScreenTests {
    private func member(_ id: String, rsvp: String?) -> Conversation.Member {
        Conversation.Member(id: id, name: id, photo: nil, admin: false, creator: false, rsvp: rsvp)
    }

    private let now = ChatDates.parse("2026-11-17T12:00:00Z")!

    @Test("Sous-titre : « sam. 21 nov. · 12 participants », à l'heure de Suisse")
    func subtitleShowsDayAndParticipants() {
        #expect(EventChatScreen.subtitle(startsAt: "2026-11-21T19:00:00Z", participants: 12, now: now) == "sam. 21 nov. · 12 participants")
        // 23 h 30 UTC le vendredi = samedi 0 h 30 en Suisse.
        #expect(EventChatScreen.subtitle(startsAt: "2026-11-20T23:30:00Z", participants: 1, now: now) == "sam. 21 nov. · 1 participant")
    }

    @Test("Sous-titre : l'année si ce n'est pas celle d'aujourd'hui, « Date à définir » sans date, la date seule sans participant")
    func subtitleEdgeCases() {
        #expect(EventChatScreen.subtitle(startsAt: "2027-01-09T19:00:00Z", participants: 3, now: now) == "sam. 9 janv. 2027 · 3 participants")
        #expect(EventChatScreen.subtitle(startsAt: nil, participants: 4, now: now) == "Date à définir · 4 participants")
        #expect(EventChatScreen.subtitle(startsAt: "2026-11-21T19:00:00Z", participants: 0, now: now) == "sam. 21 nov.")
    }

    @Test("Participants : Présent + Peut-être de la fiche, sinon les réponses des personnes de la discussion")
    func participantsCount() {
        let people = [member("a", rsvp: "yes"), member("b", rsvp: "maybe"), member("c", rsvp: "no"), member("d", rsvp: nil)]
        #expect(EventChatScreen.participants(going: 10, maybe: 2, members: people) == 12)
        #expect(EventChatScreen.participants(going: 5, maybe: nil, members: people) == 5)
        #expect(EventChatScreen.participants(going: nil, maybe: nil, members: people) == 2)
    }

    @Test("Cloche : bell (Tout), bell.badge (Mentions seulement), bell.slash (Rien ou en sourdine)")
    func bellSymbol() {
        #expect(EventChatScreen.bellSymbol(level: .all, muted: false) == "bell")
        #expect(EventChatScreen.bellSymbol(level: .mentions, muted: false) == "bell.badge")
        #expect(EventChatScreen.bellSymbol(level: .none, muted: false) == "bell.slash")
        #expect(EventChatScreen.bellSymbol(level: .all, muted: true) == "bell.slash")
        #expect(EventChatScreen.bellLabel(level: .mentions, muted: false) == "Notifications : mentions seulement")
        #expect(EventChatScreen.bellLabel(level: .all, muted: true) == "Notifications en sourdine")
    }

    @Test("Sourdine : jusqu'à une heure aujourd'hui, jusqu'à un jour, toujours ; rien si finie ou absente")
    func muteNote() {
        #expect(EventChatScreen.muteNote(mutedUntil: "2026-11-17T19:30:00Z", now: now) == "jusqu'à 20:30")
        #expect(EventChatScreen.muteNote(mutedUntil: "2026-11-24T12:00:00Z", now: now) == "jusqu'au mar. 24 nov.")
        #expect(EventChatScreen.muteNote(mutedUntil: "infinity", now: now) == "toujours")
        #expect(EventChatScreen.muteNote(mutedUntil: "9999-12-31T00:00:00Z", now: now) == "toujours")
        #expect(EventChatScreen.muteNote(mutedUntil: "2026-11-17T08:00:00Z", now: now) == nil)
        #expect(EventChatScreen.muteNote(mutedUntil: nil, now: now) == nil)
    }

    @Test("Glissé depuis le bord : retour au-delà du tiers, ou lancé vers la droite ; sinon l'écran revient")
    func edgeSwipe() {
        #expect(EventChatScreen.closesOnRelease(translation: 140, predicted: 150, width: 390))
        #expect(EventChatScreen.closesOnRelease(translation: 60, predicted: 260, width: 390))
        #expect(!EventChatScreen.closesOnRelease(translation: 60, predicted: 90, width: 390))
        #expect(!EventChatScreen.closesOnRelease(translation: 10, predicted: 400, width: 390))
    }

    @Test("Lien /events/event/<id>/chat : l'écran de la discussion ; pas un autre chemin")
    func eventChatPath() {
        let id = "0b3f4a52-1c2d-4e5f-8a9b-0c1d2e3f4a5b"
        #expect(WebModel.eventChatPath(in: URL(string: "https://party.example/events/event/\(id.uppercased())/chat")!) == id)
        #expect(WebModel.eventChatPath(in: URL(string: "https://party.example/events/event/\(id)")!) == nil)
        #expect(WebModel.eventChatPath(in: URL(string: "https://party.example/events/event/\(id)/invite")!) == nil)
        #expect(WebModel.eventChatPath(in: URL(string: "https://party.example/events/event/nope/chat")!) == nil)
    }
}

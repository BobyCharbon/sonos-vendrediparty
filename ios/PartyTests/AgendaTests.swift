import EventKit
import Foundation
import Testing
@testable import Party

/// Agenda (17.11) : plages « pris » calculées sur l'iPhone (seulement début et fin, arrondis à 30 min, 60 jours,
/// fusionnés, sans les soirées Party), préférences locales, pastille, notification d'une demande de rendez-vous.
struct AgendaTests {
    private static let host = "partytest.bobycharbon.ch"
    /// Lundi 17.11.2026, 10:10 UTC.
    private static let now = ISO8601DateFormatter().date(from: "2026-11-17T10:10:00Z")!

    private static func at(_ text: String) -> Date { ISO8601DateFormatter().date(from: text)! }

    private static func entry(_ start: String, _ end: String, calendar: String = "perso", allDay: Bool = false,
                              availability: EKEventAvailability = .busy, url: String? = nil, uid: String? = nil) -> AgendaBusy.Entry {
        AgendaBusy.Entry(calendarID: calendar, start: at(start), end: at(end), allDay: allDay, availability: availability,
                         url: url.flatMap(URL.init(string:)), externalID: uid)
    }

    private static func blocks(_ entries: [AgendaBusy.Entry], busy: Set<String> = ["perso"]) -> [AgendaBusy.Block] {
        AgendaBusy.blocks(entries, busyCalendars: busy, now: now, partyHost: host)
    }

    @Test("Arrondi vers l'extérieur à 30 min : 14:10–15:05 devient 14:00–15:30")
    func roundsOutward() {
        let result = Self.blocks([Self.entry("2026-11-18T14:10:00Z", "2026-11-18T15:05:00Z")])
        #expect(result == [AgendaBusy.Block(start: Self.at("2026-11-18T14:00:00Z"), end: Self.at("2026-11-18T15:30:00Z"))])
    }

    @Test("Plages qui se chevauchent ou se touchent : une seule")
    func mergesOverlapsAndNeighbours() {
        let result = Self.blocks([
            Self.entry("2026-11-18T09:00:00Z", "2026-11-18T10:00:00Z"),
            Self.entry("2026-11-18T09:45:00Z", "2026-11-18T10:20:00Z"),  // chevauche → 9:00–10:30
            Self.entry("2026-11-18T10:30:00Z", "2026-11-18T11:00:00Z"),  // touche → 9:00–11:00
            Self.entry("2026-11-18T13:00:00Z", "2026-11-18T14:00:00Z"),
        ])
        #expect(result.count == 2)
        #expect(result.first == AgendaBusy.Block(start: Self.at("2026-11-18T09:00:00Z"), end: Self.at("2026-11-18T11:00:00Z")))
        #expect(AgendaBusy.payload(result).last == ["s": "2026-11-18T13:00:00Z", "e": "2026-11-18T14:00:00Z"])
    }

    @Test("Coupé à [maintenant, +60 jours] : le passé et l'au-delà ne partent pas")
    func clipsToSixtyDays() {
        let result = Self.blocks([
            Self.entry("2026-11-17T08:00:00Z", "2026-11-17T11:00:00Z"),  // en cours → dès 10:00
            Self.entry("2026-11-10T08:00:00Z", "2026-11-10T09:00:00Z"),  // passé
            Self.entry("2027-01-20T08:00:00Z", "2027-01-20T09:00:00Z"),  // > 60 jours
        ])
        #expect(result == [AgendaBusy.Block(start: Self.at("2026-11-17T10:00:00Z"), end: Self.at("2026-11-17T11:00:00Z"))])
        let far = Self.blocks([Self.entry("2027-01-15T08:00:00Z", "2027-01-20T09:00:00Z")])
        #expect(far.last?.end == Self.at("2027-01-16T10:00:00Z"))  // 17.11 10:00 + 60 jours
    }

    @Test("Seuls les calendriers cochés comptent ; « disponible » et durée nulle ne comptent pas")
    func onlyCheckedCalendarsAndBusyTime() {
        let result = Self.blocks([
            Self.entry("2026-11-18T09:00:00Z", "2026-11-18T10:00:00Z", calendar: "travail"),
            Self.entry("2026-11-18T11:00:00Z", "2026-11-18T12:00:00Z", availability: .free),
            Self.entry("2026-11-18T13:00:00Z", "2026-11-18T13:00:00Z"),
            Self.entry("2026-11-18T15:00:00Z", "2026-11-18T16:00:00Z", availability: .tentative),
        ])
        #expect(result == [AgendaBusy.Block(start: Self.at("2026-11-18T15:00:00Z"), end: Self.at("2026-11-18T16:00:00Z"))])
        #expect(Self.blocks([Self.entry("2026-11-18T09:00:00Z", "2026-11-18T10:00:00Z")], busy: []).isEmpty)
    }

    @Test("Journée entière : seulement marquée occupée (vacances), jamais un jour férié « disponible »")
    func allDayOnlyWhenBusy() {
        let holiday = Self.entry("2026-12-25T00:00:00Z", "2026-12-26T00:00:00Z", allDay: true, availability: .free)
        let unknown = Self.entry("2026-12-24T00:00:00Z", "2026-12-25T00:00:00Z", allDay: true, availability: .notSupported)
        let holidays = Self.entry("2026-12-28T00:00:00Z", "2026-12-30T00:00:00Z", allDay: true, availability: .busy)
        #expect(Self.blocks([holiday, unknown, holidays]).count == 1)
    }

    @Test("Les soirées Party déjà dans l'iPhone ne comptent pas deux fois")
    func partyEntriesAreExcluded() {
        let feed = Self.entry("2026-11-20T19:00:00Z", "2026-11-20T23:00:00Z", uid: "6f1c…@vendredi-party")
        let agendaFeed = Self.entry("2026-11-21T19:00:00Z", "2026-11-21T23:00:00Z", uid: "x@vendredi-party-agenda")
        let poll = Self.entry("2026-11-22T19:00:00Z", "2026-11-22T22:00:00Z",
                              url: "https://\(Self.host)/events/event/11111111-2222-3333-4444-555555555555")
        let other = Self.entry("2026-11-23T19:00:00Z", "2026-11-23T22:00:00Z", url: "https://example.com/events/event/1")
        #expect(AgendaBusy.isParty(feed, partyHost: Self.host) && AgendaBusy.isParty(agendaFeed, partyHost: Self.host))
        #expect(AgendaBusy.isParty(poll, partyHost: Self.host))
        #expect(!AgendaBusy.isParty(other, partyHost: Self.host))
        #expect(Self.blocks([feed, agendaFeed, poll, other]).count == 1)
    }

    @Test("1000 plages au plus")
    func capsTheNumberOfBlocks() {
        let many = (0..<1200).map { i -> AgendaBusy.Entry in
            let start = AgendaBusy.floor(Self.now).addingTimeInterval(3600 + Double(i) * 3600)  // 30 min, puis 30 min libres
            return AgendaBusy.Entry(calendarID: "perso", start: start, end: start.addingTimeInterval(1800), allDay: false,
                                    availability: .busy, url: nil, externalID: nil)
        }
        #expect(Self.blocks(many).count == AgendaBusy.maxBlocks)
    }

    @Test("Calendriers exclus d'office : « Vendredi Party » (abonné) et les anniversaires")
    func excludedCalendars() {
        #expect(AgendaCalendars.excluded(type: .subscription, title: "Vendredi Party") == "party")
        #expect(AgendaCalendars.excluded(type: .birthday, title: "Anniversaires") == "birthdays")
        #expect(AgendaCalendars.excluded(type: .subscription, title: "Jours fériés") == nil)
        #expect(AgendaCalendars.excluded(type: .calDAV, title: "Vendredi Party") == nil)
        #expect(AgendaCalendars.source(type: .local, title: "Default") == "Sur l'iPhone")
        #expect(AgendaCalendars.source(type: .calDAV, title: "moi@gmail.com") == "Google")
        #expect(AgendaCalendars.source(type: .calDAV, title: "iCloud") == "iCloud")
    }

    @Test("Préférences sur l'iPhone : affiché, ne compte pas par défaut ; Vendredi Party ne compte jamais")
    func localPreferences() {
        let defaults = UserDefaults(suiteName: "AgendaTests-\(UUID().uuidString)")!
        let prefs = AgendaPrefs(defaults: defaults)
        #expect(prefs.get("a", excluded: nil) == AgendaPrefs.Calendar(shown: true, countsBusy: false))
        #expect(prefs.get("vp", excluded: "party") == AgendaPrefs.Calendar(shown: false, countsBusy: false))
        prefs.set("a", shown: nil, countsBusy: true)
        prefs.set("vp", shown: true, countsBusy: true)
        #expect(prefs.get("a", excluded: nil) == AgendaPrefs.Calendar(shown: true, countsBusy: true))
        #expect(prefs.get("vp", excluded: "party").countsBusy == false)
        #expect(!prefs.synced)
        prefs.synced = true
        #expect(AgendaPrefs(defaults: defaults).synced)
    }

    @Test("Partage actif : un groupe coché ou un lien de dispo actif ; sinon rien ne part")
    func sharingDecidesTheSync() throws {
        let json = #"{"share_party": false, "share_manual": false, "busy_count": 0, "links_active": 0,"#
            + #" "groups": [{"id": "g1", "name": "Les potes", "shared": false, "system": false}]}"#
        let off = try JSONSerialization.jsonObject(with: Data(json.utf8)) as! [String: Any]
        #expect(!AgendaStore.isSharing(off))
        var group = off
        group["groups"] = [["id": "g1", "shared": true]]
        #expect(AgendaStore.isSharing(group))
        var link = off
        link["links_active"] = 2
        #expect(AgendaStore.isSharing(link))
    }

    @Test("Pastille : agenda_badge décodé, « 99+ » au-delà, rien à zéro")
    func badge() throws {
        let reply = try JSONSerialization.jsonObject(with: Data(#"{"result": {"pending": 1}, "realtime": {"url": "wss://x", "key": "k"}}"#.utf8)) as! [String: Any]
        #expect(AgendaStore.pending(reply["result"]) == 1)
        #expect(AgendaStore.pending(nil) == 0)
        #expect(AgendaRow.badge(1) == "1" && AgendaRow.badge(0) == nil && AgendaRow.badge(150) == "99+")
    }

    @Test("Statut d'accès d'iOS → texte du contrat")
    func accessStatus() {
        #expect(AgendaStore.access(.notDetermined) == "notDetermined")
        #expect(AgendaStore.access(.denied) == "denied")
        #expect(AgendaStore.access(.restricted) == "restricted")
        if #available(iOS 17.0, *) {
            #expect(AgendaStore.access(.fullAccess) == "full")
            #expect(AgendaStore.access(.writeOnly) == "writeOnly")
        }
    }

    @Test("Notification booking_request : la demande s'ouvre dans l'Agenda")
    func notificationRouting() {
        let id = "11111111-2222-3333-4444-555555555555"
        #expect(WebModel.bookingRequested(in: URL(string: "https://\(Self.host)/?tab=events&booking=\(id.uppercased())")!) == id)
        #expect(WebModel.bookingRequested(in: URL(string: "https://\(Self.host)/?tab=events&booking=../admin")!) == nil)
        #expect(WebModel.bookingRequested(in: URL(string: "https://\(Self.host)/?tab=chats&booking=\(id)")!) == nil)
        #expect(WebModel.agendaPath(booking: id) == "/events/agenda?booking=\(id)")
        #expect(WebModel.agendaPath(booking: nil) == "/events/agenda")
        #expect(WebModel.agendaPath(booking: "');alert(1);('") == nil)
    }

    @Test("« Ajouter à mon iPhone » : la demande de la page est validée")
    func phoneItem() {
        let item = AgendaPhoneItem(["title": "  Rendez-vous · Léa M.  ", "start": "2026-11-25T13:00:00Z", "location": ""])
        #expect(item?.title == "Rendez-vous · Léa M." && item?.location == nil)
        #expect(item?.end == Self.at("2026-11-25T14:00:00Z"))  // sans fin : une heure
        #expect(AgendaPhoneItem(["title": "", "start": "2026-11-25T13:00:00Z"]) == nil)
        #expect(AgendaPhoneItem(["title": "X", "start": "demain"]) == nil)
    }

    @Test("Réglages › Notifications : « Demandes de rendez-vous » a son interrupteur (allumé avant la migration)")
    @MainActor
    func notificationSwitch() throws {
        let p = try JSONDecoder().decode(EventNotificationPrefs.self, from: Data(#"""
        {"push_enabled": true, "new_event": "all", "event_changed": true, "poll_new": true, "date_fixed": true,
         "poll_nudge": true, "waitlist": true, "reminders": [], "chat": "all", "rsvp_mine": true, "proposals": false}
        """#.utf8))
        #expect(p.bookingRequests == nil)
        #expect(SettingsStore.applying("booking_requests", false, to: p).bookingRequests == false)
    }
}

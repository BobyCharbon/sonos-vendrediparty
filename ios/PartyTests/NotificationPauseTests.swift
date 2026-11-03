import Foundation
import Testing
@testable import Party

/// Pause des notifications : lune des Réglages (tout sauf l'admin) et pause des Discussions.
struct NotificationPauseTests {
    private final class NoCookies: CookieJar {
        func allCookies() async -> [HTTPCookie] { [] }
        func keep(_ cookies: [HTTPCookie]) async {}
    }

    private func prefs(muted: String?, chats: String?) throws -> EventNotificationPrefs {
        var fields = #""push_enabled": true, "quiet_start": null, "quiet_end": null, "new_event": "all", "event_changed": true,"#
            + #""poll_new": true, "date_fixed": true, "poll_nudge": true, "waitlist": true, "reminders": [], "chat": "all","#
            + #""rsvp_mine": true, "proposals": false"#
        if let muted { fields += #", "muted_until": "\#(muted)""# }
        if let chats { fields += #", "chats_muted_until": "\#(chats)""# }
        return try JSONDecoder().decode(EventNotificationPrefs.self, from: Data("{\(fields)}".utf8))
    }

    @Test("Durées : la lune 1 h, 2 h, 8 h du matin ; les deux sourdines de discussions aussi 30 minutes")
    func spans() {
        #expect(NotificationPause.spans(.all).map(\.key) == ["1h", "2h", "morning"])
        #expect(NotificationPause.spans(.chats).map(\.key) == ["30m", "1h", "2h", "morning"])
        #expect(NotificationPause.spans(.eventChats).map(\.key) == ["30m", "1h", "2h", "morning"])
        #expect(NotificationPause.Scope.eventChats.rawValue == "event_chats" && NotificationPause.Scope.chats.subject == "Discussions des groupes")
        #expect(NotificationPause.spans(.all).last?.label == "Jusqu'à 8 h du matin")
    }

    @Test("Dates Postgres lues avec ou sans fractions de seconde ; une pause passée ne compte plus")
    func readsPostgresDates() throws {
        let now = try #require(NotificationPause.date("2026-11-03T06:00:00+00:00"))
        #expect(NotificationPause.date("2026-11-03T06:29:48.495527+00:00") == now.addingTimeInterval(29 * 60 + 48))
        #expect(NotificationPause.activeUntil("2026-11-03T07:00:00+00:00", now: now) == now.addingTimeInterval(3600))
        #expect(NotificationPause.activeUntil("2026-11-03T05:59:00+00:00", now: now) == nil)
        #expect(NotificationPause.activeUntil(nil, now: now) == nil && NotificationPause.activeUntil("n'importe quoi") == nil)
    }

    @Test("Heure de fin à Zurich : « 08:00 » le jour même, « demain 08:00 » sinon")
    func labelsInZurichTime() throws {
        let evening = try #require(NotificationPause.date("2026-11-03T21:00:00+00:00"))  // 22:00 à Zurich
        let sameDay = try #require(NotificationPause.date("2026-11-03T22:30:00+00:00"))
        let tomorrow = try #require(NotificationPause.date("2026-11-04T07:00:00+00:00"))
        #expect(NotificationPause.label(sameDay, now: evening) == "23:30")
        #expect(NotificationPause.label(tomorrow, now: evening) == "demain 08:00")
    }

    @Test("Les préférences du compte portent les deux pauses ; sans migration, rien n'est en pause")
    @MainActor
    func storeAppliesBothPauses() throws {
        let store = PauseStore(api: PartyAPI(base: URL(string: "https://party.invalid")!, jar: NoCookies()), web: nil)
        store.apply(try prefs(muted: "2999-01-01T07:00:00+00:00", chats: nil))
        #expect(store.active(.all) != nil && store.active(.chats) == nil)
        store.apply(try prefs(muted: nil, chats: "2999-01-01T07:00:00.123+00:00"))
        #expect(store.active(.all) == nil && store.active(.chats) != nil)
        store.apply(try prefs(muted: "2000-01-01T07:00:00+00:00", chats: nil))
        #expect(store.active(.all) == nil)
        #expect(store.active(.eventChats) == nil)
    }

    @Test("Chaque type de notification a son interrupteur : les nouveaux réglages s'appliquent au bon champ")
    @MainActor
    func everyTypeHasItsSwitch() throws {
        let p = try prefs(muted: nil, chats: nil)
        #expect(p.announcements == nil && p.groupMessages == nil)  // avant la migration : reçus (interrupteur allumé)
        let keys: [(String, KeyPath<EventNotificationPrefs, Bool?>)] = [
            ("announcements", \.announcements), ("rsvp_set", \.rsvpSet), ("invites", \.invites),
            ("proposal_result", \.proposalResult), ("link_join", \.linkJoin), ("group_messages", \.groupMessages),
            ("group_invites", \.groupInvites), ("group_joins", \.groupJoins),
        ]
        for (key, path) in keys {
            #expect(SettingsStore.applying(key, false, to: p)[keyPath: path] == false, "\(key)")
        }
        let decoded = try JSONDecoder().decode(EventNotificationPrefs.self, from: Data(#"""
        {"push_enabled": true, "new_event": "all", "event_changed": true, "poll_new": true, "date_fixed": true,
         "poll_nudge": true, "waitlist": true, "reminders": [], "chat": "all", "rsvp_mine": true, "proposals": false,
         "event_chats_muted_until": "2999-01-01T07:00:00+00:00", "group_joins": false}
        """#.utf8))
        #expect(decoded.groupJoins == false && NotificationPause.activeUntil(decoded.eventChatsMutedUntil) != nil)
    }
}

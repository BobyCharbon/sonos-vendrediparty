import Foundation
import Testing
@testable import Party

/// Réglages › Notifications : réponses du serveur et règles appliquées avant chaque enregistrement.
struct SettingsTests {
    private func decode<T: Decodable>(_ json: String) throws -> T {
        try JSONDecoder().decode(T.self, from: Data(json.utf8))
    }

    @Test("Invité et hôte : un oui/non par type (GET /api/notify, /api/admin/notify)")
    func decodesPartyPrefs() throws {
        let guest: GuestNotifyState = try decode(#"{"prefs": {"track": true, "feedback": false, "games": true}, "subscribed": true}"#)
        #expect(guest.prefs == ["track": true, "feedback": false, "games": true] && guest.subscribed)
        let host: AdminNotifyState = try decode(#"{"admin_notify": {"messages": true, "games": false, "feedback": true}}"#)
        #expect(host.prefs["feedback"] == true && host.prefs["games"] == false)
    }

    @Test("Événements : la ligne notification_prefs de Supabase, heures de silence en heure Postgres")
    func decodesEventPrefs() throws {
        let state: EventNotifyState = try decode("""
        {"approver": true, "prefs": {"user_id": "u1", "push_enabled": true, "quiet_start": "23:00:00", "quiet_end": "08:00:00",
         "new_event": "subscribed", "event_changed": true, "poll_new": false, "date_fixed": true, "poll_nudge": true,
         "waitlist": false, "reminders": ["1d", "2h"], "chat": "mentions", "rsvp_mine": true, "proposals": false}}
        """)
        #expect(state.approver && state.prefs.hasQuietHours && state.prefs.newEvent == "subscribed")
        #expect(state.prefs.reminders == ["1d", "2h"] && !state.prefs.pollNew && state.prefs.chat == "mentions")
        #expect(QuietTime.text(QuietTime.date(state.prefs.quietStart)) == "23:00")
    }

    @Test("Rappels : cochés dans l'ordre du temps, jamais en double")
    func remindersStayOrdered() {
        #expect(EventChoices.reminders(["0h", "1d"], toggling: "7d", on: true) == ["7d", "1d", "0h"])
        #expect(EventChoices.reminders(["7d", "1d"], toggling: "1d", on: true) == ["7d", "1d"])
        #expect(EventChoices.reminders(["7d", "1d"], toggling: "7d", on: false) == ["1d"])
    }

    @Test("Heures de silence : début et fin identiques refusés, secondes Postgres ignorées")
    func quietHoursMustDiffer() {
        #expect(QuietTime.same("23:00", "23:00:00"))
        #expect(!QuietTime.same("23:00", "08:00"))
        #expect(!QuietTime.same(nil, "08:00"))
    }

    @Test("Un choix change le seul champ visé, avec le bon type")
    @MainActor
    func applyingChangesOneField() throws {
        let state: EventNotifyState = try decode("""
        {"approver": false, "prefs": {"push_enabled": true, "quiet_start": null, "quiet_end": null, "new_event": "all",
         "event_changed": true, "poll_new": true, "date_fixed": true, "poll_nudge": true, "waitlist": true,
         "reminders": [], "chat": "all", "rsvp_mine": true, "proposals": false}}
        """)
        let changed = SettingsStore.applying("chat", "none", to: state.prefs)
        #expect(changed.chat == "none" && changed.newEvent == "all")
        #expect(SettingsStore.applying("waitlist", false, to: state.prefs).waitlist == false)
        // Type inattendu : rien ne change.
        #expect(SettingsStore.applying("waitlist", "non", to: state.prefs) == state.prefs)
    }

    @Test("Compte relié : lu dans vp_account, absent si déconnecté")
    func parsesAccount() {
        #expect(AccountSummary.parse(#"{"name": "Boby", "photo": null, "beta": true, "admin": true}"#)
                == AccountSummary(name: "Boby", photo: nil, admin: true))
        #expect(AccountSummary.parse(nil) == nil)
        #expect(AccountSummary.parse("") == nil)
        #expect(AccountSummary.parse("null") == nil)
    }

    @Test("Onglet Réglages déclaré natif par la page : affiché en natif")
    func accountTabIsNative() throws {
        let state = try #require(TabBarState(message: [
            "hidden": false, "native": ["music", "feedback", "account"], "host": false,
            "tabs": [["id": "music", "label": "Musique", "active": false, "badge": NSNull(), "soon": false],
                     ["id": "account", "label": "Réglages", "active": true, "badge": NSNull(), "soon": false]],
        ] as [String: Any]))
        #expect(state.nativeScreen == "account")
    }
}

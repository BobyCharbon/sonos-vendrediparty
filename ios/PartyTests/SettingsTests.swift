import Foundation
import Testing
import UIKit
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

    @Test("Mon profil : décodé, statut lisible, téléphone facultatif")
    func decodesProfile() throws {
        let p: MemberProfile = try decode(#"{"id": "u1", "display_name": "Boby", "first_name": null, "last_name": "T", "phone": null, "avatar_url": null, "role": "member", "status": "active", "photo": null}"#)
        #expect(p.firstName == "" && p.roleLabel == "Membre VIP" && p.phone == nil)
        let banned: MemberProfile = try decode(#"{"id": "u2", "role": "admin", "status": "banned"}"#)
        #expect(banned.roleLabel == "Accès retiré")
    }

    @Test("Mon profil : tout obligatoire, surnom 40 caractères au plus, espaces nettoyés")
    func profileRules() {
        #expect(ProfileRules.isComplete(first: "Ludo", last: "T", nickname: "Boby", hasPhoto: true))
        #expect(!ProfileRules.isComplete(first: "Ludo", last: "T", nickname: "Boby", hasPhoto: false))
        #expect(!ProfileRules.isComplete(first: "  ", last: "T", nickname: "Boby", hasPhoto: true))
        #expect(!ProfileRules.isComplete(first: "Ludo", last: "T", nickname: String(repeating: "x", count: 41), hasPhoto: true))
        #expect(ProfileRules.clean("  Jean   Paul ") == "Jean Paul")
    }

    @Test("Photo : carré centré, 1024 px au plus, JPEG")
    func photoIsASquareJPEG() throws {
        #expect(ProfilePhoto.square(of: CGSize(width: 3000, height: 2000)) == CGRect(x: 500, y: 0, width: 2000, height: 2000))
        #expect(ProfilePhoto.square(of: CGSize(width: 1000, height: 2000), offset: CGPoint(x: 0, y: -1)).minY == 0)
        let image = UIGraphicsImageRenderer(size: CGSize(width: 1600, height: 1200)).image { ctx in
            UIColor.systemPink.setFill(); ctx.fill(CGRect(x: 0, y: 0, width: 1600, height: 1200))
        }
        let data = try #require(ProfilePhoto.jpeg(from: image))
        #expect(data.starts(with: [0xFF, 0xD8, 0xFF]))
        let out = try #require(UIImage(data: data))
        #expect(out.size.width == out.size.height && out.size.width <= ProfilePhoto.side)
    }
}

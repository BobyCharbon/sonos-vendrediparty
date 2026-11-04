import Foundation
import Testing
@testable import Party

/// Modération commune (4.11, Apple 1.2 / Google UGC) : Signaler, Personnes bloquées, conditions d'utilisation,
/// file des modérateurs, fiche réduite d'un membre qui m'a bloqué, interrupteurs de notification.
struct ModerationTests {
    private func decode<T: Decodable>(_ json: String) throws -> T {
        try JSONDecoder().decode(T.self, from: Data(json.utf8))
    }

    @Test("Les raisons et les types de contenu ont les clés attendues par la base")
    func reasonsAndKinds() {
        #expect(ReportReason.allCases.map(\.rawValue) == ["harassment", "shocking", "spam", "scam", "other"])
        #expect(ReportReason.scam.label == "Arnaque ou vente")
        #expect(ReportTarget.Kind.profilePhoto.rawValue == "profile_photo")
        #expect(ReportTarget.Kind.directMessage.rawValue == "direct_message")
        #expect(ReportTarget.Kind.petOffer.rawValue == "pet_offer")  // point d'accroche du Compagnon
    }

    @Test("Conditions : version, acceptation et contact ; un ancien serveur sans champ ne casse rien")
    func decodesTerms() throws {
        let t: TermsStatus = try decode(#"{"version":"2026-11-04","accepted":true,"accepted_at":"2026-11-04T10:00:00Z","contact_email":"x@y.ch","enforced":false,"url":"/events/terms"}"#)
        #expect(t.accepted && t.version == "2026-11-04" && t.contactEmail == "x@y.ch" && !t.enforced)
        let empty: TermsStatus = try decode("{}")
        #expect(!empty.accepted && empty.contactEmail == nil)
    }

    @Test("File des modérateurs : copie du contenu, compte visé, sanctions et réglages")
    func decodesQueue() throws {
        let q: ModerationQueue = try decode("""
        {"reports":[{"id":"r1","kind":"group_message","target_id":"m1","reason":"harassment","reason_label":"Harcèlement",
          "comment":"insultes","status":"open","resolution":null,"note":null,"created_at":"2026-11-04T10:00:00Z",
          "handled_at":null,"handled_by":null,"reporter":"Tom","text":"t'es un •••••••","place":"Les amis",
          "photo":null,"photo_path":null,"user":{"id":"u-lea","name":"Léa","photo":null,"status":"banned"},
          "same_target":2,"user_reports":3,"sanctions":[{"kind":"suspend","ends_at":"2026-11-11T10:00:00Z","lifted_at":null,"at":"2026-11-04T10:00:00Z"}]}],
         "settings":{"terms_version":"2026-11-04","contact_email":null,"terms_enforced":true}}
        """)
        let r = try #require(q.reports.first)
        #expect(r.kindLabel == "Message de groupe" && r.reasonLabel == "Harcèlement" && r.banned)
        #expect(r.sameTarget == 2 && r.userReports == 3 && r.sanctions.first?.endsAt != nil)
        #expect(q.settings.termsEnforced && q.settings.contactEmail == nil)
        #expect(ModerationReport.resolutions["dismiss"] == "Classé sans suite")
    }

    @Test("Fiche : un membre qui m'a bloqué ne montre que son surnom ; « blocked » : je l'ai bloqué")
    func decodesRestrictedCard() throws {
        let restricted: MemberCard = try decode(#"{"id":"u1","display_name":"Léa","role":"member","groups":[],"restricted":true,"blocked":false}"#)
        #expect(restricted.restricted && !restricted.blocked && restricted.phone == nil)
        let blocked: MemberCard = try decode(#"{"id":"u2","display_name":"Tom","role":"guest","blocked":true}"#)
        #expect(blocked.blocked && !blocked.restricted)
        let old: MemberCard = try decode(#"{"id":"u3","display_name":"Max","role":"guest"}"#)
        #expect(!old.blocked && !old.restricted)
    }

    @Test("Personnes bloquées : nom et photo")
    func decodesBlocked() throws {
        let p: BlockedPerson = try decode(#"{"id":"u1","name":"Léa","photo":"https://x/lea.jpg","at":"2026-11-04T10:00:00Z"}"#)
        #expect(p.name == "Léa" && p.photo == "https://x/lea.jpg")
    }

    @Test("Interrupteurs : message de la modération et nouveau signalement")
    @MainActor
    func moderationToggles() throws {
        let state: EventNotifyState = try decode(#"{"prefs":{"push_enabled":true,"new_event":"all","event_changed":true,"poll_new":true,"date_fixed":true,"poll_nudge":true,"waitlist":true,"reminders":[],"chat":"mentions","rsvp_mine":true,"proposals":true,"moderation_reports":false},"approver":false,"moderator":true}"#)
        #expect(state.moderator == true && state.prefs.moderationReports == false && state.prefs.moderationNotices == nil)
        let next = SettingsStore.applying("moderation_notices", false, to: state.prefs)
        #expect(next.moderationNotices == false)
        let old: EventNotifyState = try decode(#"{"prefs":{"push_enabled":true,"new_event":"all","event_changed":true,"poll_new":true,"date_fixed":true,"poll_nudge":true,"waitlist":true,"reminders":[],"chat":"mentions","rsvp_mine":true,"proposals":true},"approver":true}"#)
        #expect(old.moderator == nil)
    }
}

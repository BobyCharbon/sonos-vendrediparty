import Foundation
import Testing
@testable import Party

/// Compagnon (avis 243907b1981a) : ses deux notifications ont chacune leur interrupteur dans les Réglages natifs,
/// lus et modifiés comme les autres (absents avant la migration 20261104130000 : reçus).
struct PetNotificationTests {
    private let base = #"{"push_enabled":true,"new_event":"all","event_changed":true,"poll_new":true,"date_fixed":true,"poll_nudge":true,"waitlist":true,"reminders":[],"chat":"all","rsvp_mine":true,"proposals":true"#

    @Test("Décodage : rappel du jour et alertes, absents = reçus")
    func decoding() throws {
        let off = try JSONDecoder().decode(EventNotificationPrefs.self, from: Data((base + #","pet_daily":false,"pet_alerts":true}"#).utf8))
        #expect(off.petDaily == false && off.petAlerts == true)
        let before = try JSONDecoder().decode(EventNotificationPrefs.self, from: Data((base + "}").utf8))
        #expect(before.petDaily == nil && before.petAlerts == nil)
    }

    @MainActor @Test("Un interrupteur touché change seulement son réglage")
    func applying() throws {
        let prefs = try JSONDecoder().decode(EventNotificationPrefs.self, from: Data((base + "}").utf8))
        let daily = SettingsStore.applying("pet_daily", false, to: prefs)
        #expect(daily.petDaily == false && daily.petAlerts == nil)
        let alerts = SettingsStore.applying("pet_alerts", false, to: daily)
        #expect(alerts.petAlerts == false && alerts.petDaily == false)
    }
}

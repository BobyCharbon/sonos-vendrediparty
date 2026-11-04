import Foundation
import Testing
@testable import Party

/// Compagnon (avis 243907b1981a, lot 1 du 4.11) : ses quatre notifications (rappel du jour, alertes vitales, cadeau d'un
/// ami, paliers de série) ont chacune leur interrupteur dans les Réglages natifs, lus et modifiés comme les autres
/// (absents avant les migrations 20261104130000 / 20261104150000 : reçus).
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
        let gifts = SettingsStore.applying("pet_gifts", false, to: alerts)
        #expect(gifts.petGifts == false && gifts.petStreaks == nil && gifts.petDaily == false)
        let streaks = SettingsStore.applying("pet_streaks", false, to: gifts)
        #expect(streaks.petStreaks == false && streaks.petGifts == false)
    }

    @Test("Décodage : cadeau d'un ami et paliers de série, absents = reçus")
    func decodingLot1() throws {
        let off = try JSONDecoder().decode(EventNotificationPrefs.self, from: Data((base + #","pet_gifts":false,"pet_streaks":true}"#).utf8))
        #expect(off.petGifts == false && off.petStreaks == true)
        let before = try JSONDecoder().decode(EventNotificationPrefs.self, from: Data((base + "}").utf8))
        #expect(before.petGifts == nil && before.petStreaks == nil)
    }
}

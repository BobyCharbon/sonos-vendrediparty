import XCTest
@testable import Party

/// Réglages › Notifications (campagne 2, rapport 07) : un Membre ou un Guest ne voit pas les interrupteurs que la base
/// ne lui envoie jamais ; la liste vient du serveur (« hidden »), un ancien serveur affiche tout.
final class NotificationHiddenTests: XCTestCase {
    private func state(_ extra: String) throws -> EventNotifyState {
        let json = """
        {"prefs":{"push_enabled":true,"new_event":"all","event_changed":true,"poll_new":true,"date_fixed":true,
        "poll_nudge":true,"waitlist":true,"reminders":["1d"],"chat":"all","rsvp_mine":true,"proposals":true},
        "approver":false\(extra)}
        """
        return try JSONDecoder().decode(EventNotifyState.self, from: Data(json.utf8))
    }

    func testServerHiddenSwitchesAreNotShown() throws {
        let member = try state(#","member":false,"hidden":["chat","new_event","poll_new","ticket_issued"]"#)
        XCTAssertFalse(member.shows("poll_new"))
        XCTAssertFalse(member.shows("ticket_issued"))
        XCTAssertFalse(member.shows("chat"))
        XCTAssertTrue(member.shows("event_changed"))
        XCTAssertTrue(member.shows("invites"))
    }

    func testVipAndOldServerShowEverything() throws {
        XCTAssertTrue(try state(#","member":true,"hidden":[]"#).shows("poll_new"))
        XCTAssertTrue(try state("").shows("poll_new"))
    }
}

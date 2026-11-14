import XCTest
@testable import Party

/// Avis eb710b132330 : le message pour tout le monde décrit par la page (notice.js → PartyNative.notice.update).
/// Maintenance : écran qui couvre l'app, sauf pour l'admin ; information / annonce : bandeau qu'on ferme ;
/// serveur qui redémarre : jamais « injoignable », « Mise à jour en cours ».
@MainActor
final class PartyNoticeTests: XCTestCase {
    private func state(_ kind: String, admin: Bool = false) -> PartyNoticeState? {
        PartyNoticeState(message: ["id": "abc123", "kind": kind, "title": "Titre", "message": "Texte", "admin": admin])
    }

    func testMaintenanceCoversTheAppExceptForTheAdmin() throws {
        XCTAssertTrue(try XCTUnwrap(state("maintenance")).blocks)
        XCTAssertFalse(try XCTUnwrap(state("maintenance", admin: true)).blocks)
        XCTAssertTrue(try XCTUnwrap(state("down", admin: true)).blocks)
    }

    func testInformationAndAnnounceAreBannersThatClose() throws {
        for kind in ["info", "announce"] {
            let s = try XCTUnwrap(state(kind))
            XCTAssertFalse(s.blocks)
            XCTAssertTrue(s.closable)
        }
        XCTAssertFalse(try XCTUnwrap(state("maintenance", admin: true)).closable)
    }

    func testNothingOrSomethingUnknownShowsNothing() {
        XCTAssertNil(PartyNoticeState(message: NSNull()))
        XCTAssertNil(PartyNoticeState(message: ["id": "x", "kind": "pub", "title": "t"]))
        XCTAssertNil(PartyNoticeState(message: ["id": "", "kind": "info", "title": "t"]))
    }

    func testAServerRestartingIsAnUpdateNotAnError() {
        XCTAssertEqual(OfflineView.busyStatuses, [502, 503, 504])
    }
}

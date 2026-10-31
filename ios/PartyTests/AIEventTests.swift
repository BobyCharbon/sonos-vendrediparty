import XCTest
@testable import Party

/// Créer avec l'IA : le brouillon se lit même si le serveur n'a pas (encore) tous les champs, et les dates s'affichent
/// sans répéter le jour.
final class AIEventTests: XCTestCase {
    func testDraftFromAnOlderServerStillDecodes() throws {
        let json = """
        {"status":"ready","questions":[],"title":"Bowling","description":"","start":"2026-11-06T20:00","end":"",
         "place_query":"Fun Planet, Villeneuve","place_name":"Fun Planet","price_chf":25,"max_participants":0,
         "category":"Sport","audience":"Vendredi Party","pot":false,"bring":[],"summary":"Bowling vendredi."}
        """
        let draft = try JSONDecoder().decode(AIEvent.Draft.self, from: Data(json.utf8))
        XCTAssertTrue(draft.ready)
        XCTAssertEqual(draft.invitees, [])
        XCTAssertEqual(draft.not_understood, [])
        XCTAssertEqual(draft.price_chf, 25)
    }

    func testSameDayEndShowsOnlyTheHour() {
        XCTAssertTrue(AIEvent.span("2026-11-14T20:00", "2026-11-14T23:30").hasSuffix("jusqu'à 23:30"))
        XCTAssertTrue(AIEvent.span("2026-11-14T20:00", "2026-11-15T02:00").contains("15 novembre"))
    }
}

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
        XCTAssertEqual(draft.place_kind, "venue")  // ancien serveur : un lieu sans type = établissement
    }

    /// Retour du 02.11 : soirée chez soi, l'adresse est cherchée parmi les adresses et le type repart avec le brouillon.
    func testAHomeAddressKeepsItsKindBackAndForth() throws {
        let json = """
        {"status":"ready","questions":[],"title":"Soirée chez Boby","start":"2026-11-07T21:00","place_kind":"home",
         "place_query":"420 Route des Rosselets, 01170 Ségny, France","place_name":"Chez Boby","address_complete":true}
        """
        let draft = try JSONDecoder().decode(AIEvent.Draft.self, from: Data(json.utf8))
        XCTAssertEqual(draft.place_kind, "home")
        let encoded = try JSONSerialization.jsonObject(with: JSONEncoder().encode(draft)) as? [String: Any]
        XCTAssertEqual(encoded?["place_kind"] as? String, "home")
    }

    /// Modifier avec l'IA : la réponse n'a pas de statut, mais la liste des changements.
    func testAnEditedEventAnswerDecodesWithItsChanges() throws {
        let json = #"{"id":"e1","title":"Raclette","changes":["Début : 2026-11-07 à 21:00"],"problems":[]}"#
        let saved = try JSONDecoder().decode(AIEvent.Created.self, from: Data(json.utf8))
        XCTAssertEqual(saved.status, "updated")
        XCTAssertEqual(saved.changes, ["Début : 2026-11-07 à 21:00"])
    }

    func testSameDayEndShowsOnlyTheHour() {
        XCTAssertTrue(AIEvent.span("2026-11-14T20:00", "2026-11-14T23:30").hasSuffix("jusqu'à 23:30"))
        XCTAssertTrue(AIEvent.span("2026-11-14T20:00", "2026-11-15T02:00").contains("15 novembre"))
    }
}

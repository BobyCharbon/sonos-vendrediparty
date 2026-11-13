import XCTest
@testable import Party

/// Avis 2237524ab14b (13.11) : « lieu à définir » dit à l'IA réserve la date ; « Oui, continuer » n'attend plus
/// de lieu confirmé sur la carte. Un lieu dit doit toujours, lui, être confirmé.
@MainActor
final class AIEventPlaceLaterTests: XCTestCase {
    private final class NoCookies: CookieJar {
        func allCookies() async -> [HTTPCookie] { [] }
        func keep(_ cookies: [HTTPCookie]) async {}
    }

    private func draft(kind: String, query: String) throws -> AIEvent.Draft {
        let json = """
        {"status":"ready","questions":[],"title":"Raclette","description":"","start":"2030-11-09T20:00","end":"",
         "place_kind":"\(kind)","place_query":"\(query)","place_name":"","price_chf":0,"max_participants":0,
         "category":"","audience":"","pot":false,"bring":[],"summary":"Raclette."}
        """
        return try JSONDecoder().decode(AIEvent.Draft.self, from: Data(json.utf8))
    }

    private func store(with d: AIEvent.Draft) -> AIEventStore {
        let api = PartyAPI(base: URL(string: "https://party.test")!, jar: NoCookies())
        let store = AIEventStore(api: api, web: nil)
        store.showDemoReady(d, place: AIEvent.Place(name: "x", address: "", url: "", latitude: 0, longitude: 0))
        store.choose(nil)  // aucun lieu confirmé sur la carte
        return store
    }

    func testPlaceToBeDefinedNeedsNoPlaceOnTheMap() throws {
        let d = try draft(kind: "later", query: "")
        XCTAssertTrue(d.placeLater)
        XCTAssertTrue(store(with: d).canCreate)
    }

    func testASaidPlaceStillNeedsToBeConfirmed() throws {
        let d = try draft(kind: "venue", query: "Café de Collex, Collex-Bossy")
        XCTAssertFalse(d.placeLater)
        XCTAssertFalse(store(with: d).canCreate)
    }
}

import XCTest
@testable import Party

/// Créer avec l'IA : le brouillon se lit même si le serveur n'a pas (encore) tous les champs, et les dates s'affichent
/// sans répéter le jour.
final class AIEventTests: XCTestCase {
    private final class NoCookies: CookieJar {
        func allCookies() async -> [HTTPCookie] { [] }
        func keep(_ cookies: [HTTPCookie]) async {}
    }

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

    /// Demande de l'admin (04.11) : avant publication, un bandeau dit pour qui l'événement est publié ; public par défaut.
    func testAudienceBannerSaysWhoSeesTheEvent() {
        let pub = AIEvent.audienceBanner(AIEvent.publicAudience, invitees: [])
        XCTAssertTrue(pub.isPublic)
        XCTAssertEqual(pub.text, "🌍 Public + lien public : tout le monde peut le voir et le lien peut être partagé")
        XCTAssertTrue(AIEvent.audienceBanner("", invitees: []).isPublic)  // rien de dit : public
        XCTAssertEqual(AIEvent.audienceBanner(AIEvent.vipAudience, invitees: ["Léa"]).text, "👥 Membres Vendredi Party seulement + Léa")
        XCTAssertEqual(AIEvent.audienceBanner(AIEvent.onlyInvitees, invitees: ["Léa", "Tom"]).text, "✉️ Invités seulement : Léa, Tom")
        XCTAssertEqual(AIEvent.audienceBanner("Ski", invitees: []).text, "👥 Groupe « Ski » seulement")
        XCTAssertFalse(AIEvent.audienceBanner("Ski", invitees: []).isPublic)
    }

    @MainActor
    func testChangingTheAudienceKeepsTheRestOfTheDraft() throws {
        let json = """
        {"status":"ready","questions":[],"title":"Bowling","start":"2026-11-06T20:00","audience":"Public (lien)"}
        """
        let draft = try JSONDecoder().decode(AIEvent.Draft.self, from: Data(json.utf8))
        let changed = AIEvent.withAudience(draft, AIEvent.vipAudience)
        XCTAssertEqual(changed.audience, AIEvent.vipAudience)
        XCTAssertEqual(changed.title, "Bowling")
        let store = AIEventStore(api: PartyAPI(base: URL(string: "https://party.invalid")!, jar: NoCookies()), web: nil)
        store.askForAudience()
        XCTAssertEqual(store.unsent, "Seulement pour ")
    }
}

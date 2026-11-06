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
}

/// Demande de l'admin (06.11) : deux étapes. 1 « La soirée » (l'IA ne demande jamais qui inviter), 2 « Les invités »
/// (brouillon enregistré, la page web d'invitation s'ouvre avec les personnes citées cochées), 3 « C'est en ligne ».
final class AIEventStepsTests: XCTestCase {
    private final class NoCookies: CookieJar {
        func allCookies() async -> [HTTPCookie] { [] }
        func keep(_ cookies: [HTTPCookie]) async {}
    }

    private let eventId = "11111111-2222-4333-8444-555555555555"
    private let tom = "aaaaaaaa-0000-4000-8000-000000000001"

    func testTheStepsFollowTheDraftThenThePublication() throws {
        XCTAssertEqual(AIEvent.steps, ["La soirée", "Qui est invité", "C'est en ligne"])
        XCTAssertEqual(AIEvent.step(nil), 1)
        let draft = try JSONDecoder().decode(AIEvent.Created.self, from: Data(#"{"id":"\#(eventId)","status":"draft","title":"Raclette"}"#.utf8))
        XCTAssertTrue(draft.isDraft)
        XCTAssertEqual(AIEvent.step(draft), 2)
        XCTAssertEqual(AIEvent.step(AIEvent.Created(id: eventId, status: "published", title: "Raclette")), 3)
    }

    func testTheSavedDraftCarriesThePeopleNamedToTheAIAsSuggestions() throws {
        let json = #"{"id":"\#(eventId)","status":"draft","title":"Raclette","problems":[],"suggested":[{"id":"\#(tom)","name":"Tom"}]}"#
        let saved = try JSONDecoder().decode(AIEvent.Created.self, from: Data(json.utf8))
        XCTAssertEqual(saved.suggested, [AIEvent.Suggested(id: tom, name: "Tom")])
        XCTAssertEqual(AIEvent.invitePath(saved.id, suggested: saved.suggested.map(\.id)),
                       "/events/event/\(eventId)/invite?suggested=\(tom)")
    }

    func testTheInvitePathNeverCarriesAnythingButIds() {
        XCTAssertNil(AIEvent.invitePath("'); alert(1); ('", suggested: []))
        XCTAssertEqual(AIEvent.invitePath(eventId, suggested: ["x'); alert(1)", tom]), "/events/event/\(eventId)/invite?suggested=\(tom)")
        XCTAssertEqual(AIEvent.invitePath(eventId, suggested: []), "/events/event/\(eventId)/invite")
    }

    /// Retour de l'admin (06.11) : qui voit se choisit à l'étape 2 ; ce qui a été dit à l'IA n'est qu'un pré-réglage.
    func testWhatWasSaidAboutWhoSeesItIsOnlyAPresetForStepTwo() throws {
        let ski = "bbbbbbbb-0000-4000-8000-000000000001"
        let json = #"{"id":"\#(eventId)","status":"draft","title":"Raclette","preset":{"audience":"group","group_ids":["\#(ski)","x'); alert(1)"]}}"#
        let saved = try JSONDecoder().decode(AIEvent.Created.self, from: Data(json.utf8))
        XCTAssertEqual(saved.preset?.audience, "group")
        XCTAssertEqual(AIEvent.invitePath(saved.id, suggested: [tom], preset: saved.preset),
                       "/events/event/\(eventId)/invite?audience=group&groups=\(ski)&suggested=\(tom)")
        // Public (le défaut) : rien à pré-régler ; un mot inconnu n'est jamais repris.
        let pub = AIEvent.Preset(audience: "public")
        XCTAssertEqual(AIEvent.invitePath(eventId, suggested: [], preset: pub), "/events/event/\(eventId)/invite")
        XCTAssertEqual(AIEvent.invitePath(eventId, suggested: [], preset: AIEvent.Preset(audience: "tout&x=1")), "/events/event/\(eventId)/invite")
        XCTAssertEqual(AIEvent.invitePath(eventId, suggested: [], preset: AIEvent.Preset(audience: "vip")), "/events/event/\(eventId)/invite?audience=vip")
        // Ancien serveur, sans pré-réglage.
        let old = try JSONDecoder().decode(AIEvent.Created.self, from: Data(#"{"id":"\#(eventId)","status":"draft","title":"R"}"#.utf8))
        XCTAssertNil(old.preset)
    }

    @MainActor
    func testTheDraftStepNoLongerOpensOnceHandledAndResetsToStepOne() {
        let store = AIEventStore(api: PartyAPI(base: URL(string: "https://party.invalid")!, jar: NoCookies()), web: nil)
        XCTAssertFalse(store.openInviteSoon)
        store.showDemoCreated(AIEvent.Created(id: eventId, status: "draft", title: "Raclette"))
        XCTAssertEqual(AIEvent.step(store.created), 2)
        store.inviteOpened()
        XCTAssertFalse(store.openInviteSoon)
        store.reset()
        XCTAssertNil(store.created)
        XCTAssertEqual(AIEvent.step(store.created), 1)
    }
}

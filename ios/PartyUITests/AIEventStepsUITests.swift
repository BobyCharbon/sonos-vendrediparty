import XCTest

/// « Créer avec l'IA » en deux étapes (demande de l'admin, 06.11), sur des états figés sans serveur :
/// 1. « La soirée » : récapitulatif, « C'est juste ? », « Oui, continuer » / « Corriger » ;
/// 2. « Les invités » : brouillon enregistré, « Choisir les invités » et « Ouvrir l'événement » (aussi en haut).
/// Captures dans $AI_STEPS_SHOTS (TEST_RUNNER_AI_STEPS_SHOTS) si la variable est définie.
final class AIEventStepsUITests: XCTestCase {
    private static let draft = """
    {"status":"ready","questions":[],"title":"Raclette chez Camille","description":"Raclette entre amis, chacun amène une salade.",
     "date_mode":"fixed","start":"2030-11-14T19:00","end":"","place_kind":"home","place_query":"Chemin des Vignes 4, 1095 Lutry",
     "place_name":"Chez Camille","address_complete":true,"max_participants":12,"audience":"Public (lien)","invitees":["Tom","Léa"],
     "bring":["Salade","Dessert"],"pot":true,"summary":"Raclette chez toi le 14 novembre à 19 h, 12 places, pot commun."}
    """
    private static let created = """
    {"id":"11111111-2222-4333-8444-555555555555","status":"draft","title":"Raclette chez Camille","problems":[],
     "suggested":[{"id":"aaaaaaaa-0000-4000-8000-000000000001","name":"Tom"},{"id":"aaaaaaaa-0000-4000-8000-000000000002","name":"Léa"}]}
    """

    override func setUp() {
        continueAfterFailure = false
    }

    private func shot(_ app: XCUIApplication, _ name: String) {
        guard let dir = ProcessInfo.processInfo.environment["AI_STEPS_SHOTS"] else { return }
        try? FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
        try? app.screenshot().pngRepresentation.write(to: URL(fileURLWithPath: dir).appendingPathComponent("\(name).png"))
    }

    func testStepOneAsksIfItIsRightThenCorrectOpensTheField() {
        let app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_AI_EVENT"] = Self.draft
        app.launchEnvironment["PARTY_DEBUG_AI_SAID"] = "Raclette chez moi le 14 novembre à 19 heures, chemin des Vignes 4 à Lutry. J'invite Tom et Léa."
        app.launchEnvironment["PARTY_DEBUG_AI_PICK"] = "1"
        app.launch()
        let steps = app.descendants(matching: .any).matching(NSPredicate(format: "label == %@", "Étape 1 sur 3 : La soirée")).firstMatch
        XCTAssertTrue(steps.waitForExistence(timeout: 20))
        shot(app, "01-ios-la-soiree-haut")
        let proceed = app.buttons["ai-continue"]
        let correct = app.buttons["ai-correct"]
        for _ in 0..<8 where !(correct.exists && correct.isHittable) { app.swipeUp() }
        app.swipeUp()  // tout en bas : la carte « C'est juste ? » entière au-dessus de la barre de saisie
        XCTAssertTrue(proceed.waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["C'est juste ?"].exists)
        XCTAssertTrue(app.staticTexts["Proposés à l'étape suivante : Tom, Léa (tu confirmes)"].exists)
        // Le lieu est confirmé (PARTY_DEBUG_AI_PICK) : « Oui, continuer » est actif.
        let deadline = Date().addingTimeInterval(15)
        while !proceed.isEnabled && Date() < deadline { RunLoop.current.run(until: Date().addingTimeInterval(0.3)) }
        XCTAssertTrue(proceed.isEnabled)
        shot(app, "01b-ios-la-soiree-c-est-juste")
        correct.tap()
        // « Corriger » : le champ prend la main pour dire ce qui ne va pas (clavier matériel du simulateur : pas de clavier affiché).
        let field = app.textViews["ai-text"]
        let focused = NSPredicate(format: "hasKeyboardFocus == true")
        XCTAssertEqual(XCTWaiter().wait(for: [expectation(for: focused, evaluatedWith: field)], timeout: 5), .completed)
    }

    func testStepTwoOffersTheInvitationsAndOpeningTheEvent() {
        let app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_AI_EVENT"] = "tips"
        app.launchEnvironment["PARTY_DEBUG_AI_CREATED"] = Self.created
        app.launch()
        let steps = app.descendants(matching: .any).matching(NSPredicate(format: "label == %@", "Étape 2 sur 3 : Les invités")).firstMatch
        XCTAssertTrue(steps.waitForExistence(timeout: 20))
        XCTAssertTrue(app.buttons["ai-invite"].exists)
        XCTAssertTrue(app.staticTexts["Déjà cochés : Tom, Léa"].exists)
        XCTAssertTrue(app.buttons["ai-open-event-toolbar"].exists)
        shot(app, "02-ios-brouillon-enregistre")
        app.buttons["ai-open-event"].tap()
        // « Ouvrir l'événement » : l'assistant se ferme, la fiche s'ouvre dans Événements.
        XCTAssertTrue(app.buttons["ai-open-event"].waitForNonExistence(timeout: 5))
    }
}

import XCTest

/// VRAI bout en bout de « Créer avec l'IA » (bugs de prod du 06.11), lancé à la main contre un serveur Party local
/// branché sur la base de TEST : app construite avec PARTY_BASE_URL=http://127.0.0.1:<port>, session du compte de test
/// et brouillon passés par l'environnement (TEST_RUNNER_AI_E2E_SESSION, TEST_RUNNER_AI_E2E_DRAFT). Ignoré sinon.
/// « Oui, continuer » → (CGU exigées : feuille « Avant de publier », « J'accepte », nouvel essai) → brouillon enregistré
/// → l'étape 2 « Qui est invité » s'ouvre dans Événements ET y reste → « Sur invitation seulement » → « Publier sans
/// inviter pour l'instant » → la fiche « C'est en ligne ! ». Captures dans $AI_E2E_SHOTS.
final class AIEventRealE2EUITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment

    override func setUpWithError() throws {
        continueAfterFailure = false
        try XCTSkipUnless(env["AI_E2E_SESSION"] != nil && env["AI_E2E_DRAFT"] != nil, "Essai réel : serveur local et base de TEST")
    }

    private func shot(_ app: XCUIApplication, _ name: String) {
        guard let dir = env["AI_E2E_SHOTS"] else { return }
        try? FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
        let file = URL(fileURLWithPath: dir).appendingPathComponent("\(env["AI_E2E_CASE"] ?? "ios")-\(name).png")
        try? app.screenshot().pngRepresentation.write(to: file)
    }

    private func label(_ app: XCUIApplication, _ text: String) -> XCUIElement {
        app.descendants(matching: .any).matching(NSPredicate(format: "label == %@", text)).firstMatch
    }

    func testOuiContinuerThenStepTwoStaysOpenThenPublish() throws {
        let app = XCUIApplication()
        let session = env["AI_E2E_SESSION"]!
        app.launchEnvironment["PARTY_DEBUG_JS"] =
            "localStorage.setItem('sb-ewromqfsmcqsthftyhzm-auth-token', \(session));localStorage.setItem('vp_tab','events');"
            + "localStorage.setItem('vp_install_dismissed','1');localStorage.setItem('vp_name','Admin test')"
        app.launchEnvironment["PARTY_DEBUG_AI_EVENT"] = env["AI_E2E_DRAFT"]
        app.launchEnvironment["PARTY_DEBUG_AI_SAID"] = "Samedi party chez Boby, rue du Lac 12 à Vevey."
        app.launchEnvironment["PARTY_DEBUG_AI_PICK"] = "1"
        app.launch()

        let proceed = app.buttons["ai-continue"]
        for _ in 0..<10 where !(proceed.exists && proceed.isHittable) { app.swipeUp() }
        XCTAssertTrue(proceed.waitForExistence(timeout: 40))
        let deadline = Date().addingTimeInterval(30)
        while !proceed.isEnabled && Date() < deadline { RunLoop.current.run(until: Date().addingTimeInterval(0.3)) }
        shot(app, "01-etape-1-c-est-juste")
        proceed.tap()

        // CGU exigées et pas encore acceptées : la feuille, puis l'enregistrement repart tout seul.
        let accept = app.buttons["terms-accept"]
        if env["AI_E2E_TERMS"] == "1" {
            XCTAssertTrue(accept.waitForExistence(timeout: 30), "La feuille des CGU devait s'ouvrir")
            shot(app, "02-feuille-cgu")
            accept.tap()
        }
        XCTAssertFalse(app.staticTexts["L'événement n'a pas pu être créé. Réessaie, ou crée-le à la main."].exists)

        // Brouillon enregistré, puis l'étape 2 s'ouvre d'elle-même dans Événements (l'assistant se ferme).
        let step = label(app, "Étape 2 sur 3 : Qui est invité")
        XCTAssertTrue(step.waitForExistence(timeout: 60), "L'étape 2 « Qui est invité » ne s'est pas ouverte")
        XCTAssertTrue(app.buttons["ai-continue"].waitForNonExistence(timeout: 20))
        shot(app, "03-etape-2-ouverte")
        Thread.sleep(forTimeInterval: 6)  // le bug : la page revenait aussitôt à la liste
        XCTAssertTrue(step.exists, "L'étape 2 s'est refermée")
        shot(app, "04-etape-2-toujours-ouverte")

        let invitedOnly = app.webViews.descendants(matching: .any).matching(NSPredicate(format: "label CONTAINS 'Sur invitation seulement'")).firstMatch
        XCTAssertTrue(invitedOnly.waitForExistence(timeout: 10))
        invitedOnly.tap()  // personne de réel n'est prévenu
        let publish = app.webViews.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Publier sans inviter'")).firstMatch
        for _ in 0..<8 where !(publish.exists && publish.isHittable) { app.webViews.firstMatch.swipeUp() }
        shot(app, "05-sur-invitation")
        publish.tap()
        XCTAssertTrue(label(app, "C’est en ligne !").waitForExistence(timeout: 30)
                      || app.staticTexts["C’est en ligne !"].waitForExistence(timeout: 5), "La fiche publiée ne s'est pas ouverte")
        shot(app, "06-publie-fiche")
    }
}

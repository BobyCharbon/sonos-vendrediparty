import XCTest

/// Recette RÉELLE de la discussion d'un événement native (demande de l'admin du 16.11.2026), dans le simulateur
/// (configuration Release, comme l'App Store) : serveur Party local branché sur la base de TEST, compte « Admin test »
/// (code fixe, aucun SMS). L'événement RECETTE_EVENT est préparé avant (message d'une invitée, annonce épinglée).
///   TEST_RUNNER_RECETTE_DIR=… TEST_RUNNER_RECETTE_EVENT=<id> xcodebuild test -configuration Release ENABLE_TESTABILITY=YES
///   PARTY_SWIFT_CONDITIONS=E2E_HOOKS PARTY_BASE_URL=http://127.0.0.1:<port> -only-testing:PartyUITests/RecetteDiscussionUITests
final class RecetteDiscussionUITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment
    private var dir: URL!
    private var app: XCUIApplication!
    private var step = 0

    override func setUpWithError() throws {
        guard let path = env["RECETTE_DIR"], env["RECETTE_EVENT"] != nil else { throw XCTSkip("Recette à la demande (RECETTE_DIR, RECETTE_EVENT)") }
        dir = URL(fileURLWithPath: path)
        continueAfterFailure = true
        addUIInterruptionMonitor(withDescription: "Alertes d'iOS") { alert in
            for label in ["Autoriser", "Allow", "Ne pas autoriser", "Don’t Allow"] where alert.buttons[label].exists {
                alert.buttons[label].tap()
                return true
            }
            return false
        }
    }

    private func shot(_ name: String) {
        step += 1
        try? app.screenshot().pngRepresentation.write(to: dir.appendingPathComponent(String(format: "discussion-%02d-%@.png", step, name)))
    }

    private func launch(_ js: String = "") {
        app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_JS"] = "localStorage.setItem('vp_install_dismissed','1');" + js
        app.launch()
    }

    private func signInAdminIfNeeded() {
        let tab = app.tabBars.buttons.matching(NSPredicate(format: "label IN {'Réglages', 'Se connecter'}")).firstMatch
        XCTAssertTrue(tab.waitForExistence(timeout: 30), "onglet Réglages")
        tab.tap()
        sleep(2)
        guard app.staticTexts["Se connecter"].exists else { return }
        app.staticTexts["Se connecter"].firstMatch.tap()
        let field = app.textFields["login-phone"]
        XCTAssertTrue(field.waitForExistence(timeout: 10), "champ du numéro")
        field.tap()
        app.typeText("0790000004")
        app.buttons["login-send"].tap()
        let code = app.textFields["login-code"]
        XCTAssertTrue(code.waitForExistence(timeout: 20), "champ du code")
        code.tap()
        app.typeText("123456")
        XCTAssertTrue(app.staticTexts["Admin test"].waitForExistence(timeout: 30), "connecté en Admin test")
    }

    func testNativeEventDiscussion() {
        let event = env["RECETTE_EVENT"]!
        launch()
        signInAdminIfNeeded()
        // La notification d'un message ouvre la discussion native (?tab=events&event=…&chat=1), la fiche derrière.
        app.terminate()
        launch("if(!sessionStorage.recette){sessionStorage.recette='1';location.replace('/?tab=events&event=\(event)&chat=1');}")
        let field = app.textViews["chat-message"].exists ? app.textViews["chat-message"] : app.textFields["chat-message"]
        let anyField = app.descendants(matching: .any).matching(identifier: "chat-message").firstMatch
        XCTAssertTrue(anyField.waitForExistence(timeout: 40), "discussion native ouverte (champ Message)")
        _ = field
        sleep(3)
        shot("ouverte")
        XCTAssertTrue(app.descendants(matching: .any).matching(identifier: "chat-banner").firstMatch.exists, "bandeau de l'annonce")
        XCTAssertTrue(app.buttons["chat-announce"].exists, "📣 pour l'organisation (Admin test)")

        // @toutlemonde proposé après l'@, puis envoyé.
        anyField.tap()
        app.typeText("@tou")
        let mention = app.descendants(matching: .any).matching(identifier: "chat-mentions").firstMatch
        XCTAssertTrue(mention.waitForExistence(timeout: 5), "suggestions de l'@")
        shot("suggestions")
        app.buttons.matching(NSPredicate(format: "label BEGINSWITH '@toutlemonde'")).firstMatch.tap()
        app.typeText("on se retrouve à 20 h")
        app.buttons["chat-send"].tap()
        sleep(3)
        shot("toutlemonde-envoye")

        // Annonce avec 📣 : carte dans le fil et bandeau.
        app.buttons["chat-announce"].tap()
        anyField.tap()
        app.typeText("Parking derrière la salle")
        shot("annonce-en-cours")
        app.buttons["chat-send"].tap()
        sleep(4)
        shot("annonce-publiee")
        XCTAssertTrue(app.descendants(matching: .any).matching(identifier: "chat-announcement").firstMatch.exists, "annonce en carte")
        let banner = app.descendants(matching: .any).matching(identifier: "chat-banner").firstMatch
        XCTAssertTrue(banner.label.hasPrefix("Annonce 1 sur") && banner.label.contains("Parking"), "bandeau : la nouvelle annonce en tête (1 sur N, N = annonces de la recette)")

        // Infos : participants et notifications.
        app.buttons.matching(NSPredicate(format: "label == 'Participants et notifications'")).firstMatch.tap()
        XCTAssertTrue(app.switches["event-chat-notify"].waitForExistence(timeout: 10), "notifications de l'événement")
        sleep(1)
        shot("infos")
        app.buttons["OK"].tap()
        sleep(1)

        // « ‹ » : retour à la fiche de l'événement.
        app.buttons["event-chat-close"].tap()
        sleep(2)
        XCTAssertFalse(anyField.exists, "discussion refermée")
        shot("fiche")
    }
}

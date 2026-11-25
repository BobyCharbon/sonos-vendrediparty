import XCTest

/// Recette RÉELLE de la couverture d'un événement (demande de l'admin du 25.11) dans le simulateur en configuration
/// Release : serveur Party local branché sur la base de TEST (vraie recherche Openverse, sans clé Pexels ni Anthropic),
/// compte « Admin test » (code fixe), organisateur de RECETTE_EVENT. La fiche est la page web du module, dans la vue web
/// de l'app : bulle « Nouveau », photos proposées + crédit, ma photo (Photothèque du simulateur : `simctl addmedia`
/// avant), affiche Party.
///   TEST_RUNNER_RECETTE_DIR=… TEST_RUNNER_RECETTE_EVENT=<id> xcodebuild test -configuration Release ENABLE_TESTABILITY=YES
///   PARTY_SWIFT_CONDITIONS=E2E_HOOKS PARTY_BASE_URL=http://127.0.0.1:<port> -only-testing:PartyUITests/RecetteCouvertureUITests
final class RecetteCouvertureUITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment
    private var dir: URL!
    private var app: XCUIApplication!
    private var step = 0

    override func setUpWithError() throws {
        guard let path = env["RECETTE_DIR"], env["RECETTE_EVENT"] != nil else { throw XCTSkip("Recette à la demande (RECETTE_DIR, RECETTE_EVENT)") }
        dir = URL(fileURLWithPath: path)
        continueAfterFailure = true
        addUIInterruptionMonitor(withDescription: "Alertes d'iOS") { alert in
            for label in ["Autoriser l'accès complet", "Autoriser", "Allow", "OK"] where alert.buttons[label].firstMatch.exists {
                alert.buttons[label].firstMatch.tap()
                return true
            }
            return false
        }
    }

    private func shot(_ name: String) {
        step += 1
        try? app.screenshot().pngRepresentation.write(to: dir.appendingPathComponent(String(format: "couverture-%02d-%@.png", step, name)))
    }

    private func launch(_ js: String = "") {
        app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_JS"] = "localStorage.setItem('vp_install_dismissed','1');" + js
        app.launch()
    }

    private func any(_ predicate: String, _ args: CVarArg...) -> XCUIElement {
        app.descendants(matching: .any).matching(NSPredicate(format: predicate, argumentArray: args)).firstMatch
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
        app.sendLoginCode()
        let code = app.textFields["login-code"]
        XCTAssertTrue(code.waitForExistence(timeout: 20), "champ du code")
        code.tap()
        app.typeText("123456")
        XCTAssertTrue(app.staticTexts["Admin test"].waitForExistence(timeout: 30), "connecté en Admin test")
    }

    private func openSheet() {
        let button = any("label BEGINSWITH %@", "🖼️")
        XCTAssertTrue(button.waitForExistence(timeout: 30), "« Changer / Ajouter une couverture »")
        button.tap()
        XCTAssertTrue(any("label == %@", "Couverture de l’événement").waitForExistence(timeout: 15), "feuille de la couverture")
        sleep(1)
    }

    private func sheetClosed(_ what: String) {
        let gone = NSPredicate(format: "exists == false")
        expectation(for: gone, evaluatedWith: any("label == %@", "Couverture de l’événement"))
        waitForExpectations(timeout: 60)
        sleep(3)
        shot(what)
    }

    func testChangeTheCover() {
        let event = env["RECETTE_EVENT"]!
        launch()
        signInAdminIfNeeded()
        app.terminate()
        launch("if(!sessionStorage.recette){sessionStorage.recette='1';location.replace('/?tab=events&event=\(event)');}")

        XCTAssertTrue(any("label CONTAINS %@", "Change la couverture quand tu veux").waitForExistence(timeout: 45), "bulle « Nouveau »")
        sleep(2)
        shot("fiche-bulle-nouveau")
        openSheet()
        shot("feuille")

        // 🔎 Photos proposées (Openverse), choisies par leur numéro ; le crédit s'affiche sous la couverture.
        any("label == %@", "🔎 Proposées").tap()
        any("label == %@", "🔎 Proposer des photos").tap()
        let first = any("label BEGINSWITH %@", "Photo 1")
        XCTAssertTrue(first.waitForExistence(timeout: 60), "photos proposées")
        sleep(2)
        shot("photos-proposees")
        first.tap()
        any("label == %@", "Utiliser cette photo").tap()
        sheetClosed("fiche-photo-proposee")
        XCTAssertTrue(any("label CONTAINS %@", "· Openverse").waitForExistence(timeout: 20), "crédit sous la couverture")

        // 📷 Ma photo : menu de la vue web → Photothèque → la photo ajoutée au simulateur → recadrage 16:9.
        openSheet()
        any("label CONTAINS %@", "Choisir une photo").tap()
        let library = any("label IN {'Photothèque', 'Photo Library'}")
        if library.waitForExistence(timeout: 10) { library.tap() }
        sleep(10)  // le sélecteur de photos d'iOS (hors de l'app) charge la photothèque
        shot("phototheque")
        // Sélecteur hors processus : la 1re vignette (la photo ajoutée par `simctl addmedia`), touchée à sa place.
        app.coordinate(withNormalizedOffset: CGVector(dx: 0.16, dy: 0.42)).tap()
        sleep(2)
        shot("photo-choisie")
        // iOS 27 : « 1 photo sélectionnée », puis ✓ en haut à droite pour la rendre à la page.
        app.coordinate(withNormalizedOffset: CGVector(dx: 0.905, dy: 0.125)).tap()
        let validate = any("label == %@", "Valider la photo")
        XCTAssertTrue(validate.waitForExistence(timeout: 30), "recadrage de la photo")
        sleep(1)
        shot("recadrage-16-9")
        validate.tap()
        sheetClosed("fiche-ma-photo")

        // 🎨 Affiche Party.
        openSheet()
        any("label == %@", "🎨 Affiche").tap()
        any("label == %@", "🎨 Utiliser l’affiche Party").tap()
        sheetClosed("fiche-affiche-party")
    }
}

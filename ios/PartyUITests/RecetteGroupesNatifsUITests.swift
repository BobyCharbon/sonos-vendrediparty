import XCTest

/// Recette RÉELLE des groupes en natif (18.11, « tout en natif ») dans le simulateur, configuration Release : serveur Party
/// local branché sur la base de TEST, compte « Admin test » (code fixe). Réglages › Groupes (liste native), Membres
/// Vendredi Party, « Nouveau groupe » (étape 1, puis Inviter avec le code QR), page du groupe, réglages, suppression.
///   TEST_RUNNER_RECETTE_DIR=… xcodebuild test -configuration Release ENABLE_TESTABILITY=YES PARTY_SWIFT_CONDITIONS=E2E_HOOKS
///   PARTY_BASE_URL=http://127.0.0.1:<port> -only-testing:PartyUITests/RecetteGroupesNatifsUITests
final class RecetteGroupesNatifsUITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment
    private var dir: URL!
    private var app: XCUIApplication!
    private var step = 0

    override func setUpWithError() throws {
        guard let path = env["RECETTE_DIR"] else { throw XCTSkip("Recette à la demande (RECETTE_DIR)") }
        dir = URL(fileURLWithPath: path)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
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
        sleep(1)
        try? app.screenshot().pngRepresentation.write(to: dir.appendingPathComponent(String(format: "%02d-%@.png", step, name)))
    }

    private func any(_ predicate: String, _ args: CVarArg...) -> XCUIElement {
        app.descendants(matching: .any).matching(NSPredicate(format: predicate, argumentArray: args)).firstMatch
    }

    private func signInAdminIfNeeded() {
        let tab = app.tabBars.buttons.matching(NSPredicate(format: "label IN {'Réglages', 'Se connecter'}")).firstMatch
        XCTAssertTrue(tab.waitForExistence(timeout: 40), "onglet Réglages")
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

    func testNativeGroupsFromTheListToDeletion() {
        app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_JS"] = "localStorage.setItem('vp_install_dismissed','1');"
        app.launch()
        signInAdminIfNeeded()

        // 1. Réglages › Groupes : la liste native.
        let groups = app.buttons["settings-groups"]
        XCTAssertTrue(groups.waitForExistence(timeout: 20), "ligne Groupes")
        groups.tap()
        XCTAssertTrue(app.navigationBars["Groupes"].waitForExistence(timeout: 20), "liste native des groupes")
        sleep(3)
        shot("liste")

        // 2. Membres Vendredi Party : logo officiel, ni Inviter, ni photo.
        let vp = any("label BEGINSWITH 'Membres Vendredi Party'")
        if vp.waitForExistence(timeout: 10) {
            vp.tap()
            XCTAssertTrue(app.staticTexts["group-page-name"].waitForExistence(timeout: 20), "page de Membres Vendredi Party")
            sleep(2)
            shot("membres-vendredi-party")
            XCTAssertFalse(app.buttons["group-invite"].exists, "jamais « Inviter » sur Membres Vendredi Party")
            app.buttons["group-settings"].tap()
            sleep(2)
            shot("membres-vendredi-party-reglages")
            XCTAssertFalse(app.buttons["group-settings-leave"].exists, "jamais « Quitter » Membres Vendredi Party")
            app.navigationBars.buttons.firstMatch.tap()
            sleep(1)
            app.navigationBars.buttons.firstMatch.tap()
            sleep(1)
        }

        // 3. Nouveau groupe : étape 1 (nom, emoji, couleur), puis Inviter (lien, code QR, personnes croisées).
        app.buttons["groups-new"].tap()
        let name = app.textFields["group-new-name"]
        XCTAssertTrue(name.waitForExistence(timeout: 10), "champ du nom")
        name.tap()
        app.typeText("Recette natif")
        app.buttons["🎸"].tap()
        app.buttons["Bleu"].tap()
        shot("nouveau-groupe")
        app.buttons["group-new-continue"].tap()
        XCTAssertTrue(app.images["group-invite-qr"].waitForExistence(timeout: 30), "code QR du lien du groupe")
        sleep(2)
        shot("inviter-qr")
        app.swipeUp()
        shot("inviter-personnes")
        app.buttons["new-group-later"].tap()

        // 4. Page du groupe, puis ses réglages.
        XCTAssertTrue(app.staticTexts["group-page-name"].waitForExistence(timeout: 20), "page du groupe créé")
        sleep(2)
        shot("page-du-groupe")
        app.swipeUp()
        shot("page-du-groupe-bas")
        app.swipeDown()
        app.buttons["group-settings"].tap()
        XCTAssertTrue(app.textFields["group-settings-name"].waitForExistence(timeout: 20), "réglages du groupe")
        sleep(2)
        shot("reglages")
        for _ in 0..<3 { app.swipeUp() }
        shot("reglages-bas")

        // 5. Supprimer le groupe : il disparaît de la liste.
        let delete = app.buttons["group-settings-delete"]
        for _ in 0..<3 where !delete.isHittable { app.swipeUp() }
        delete.tap()
        let confirm = app.sheets.buttons["Supprimer le groupe"].exists ? app.sheets.buttons["Supprimer le groupe"]
            : app.buttons.matching(NSPredicate(format: "label == 'Supprimer le groupe'")).element(boundBy: 1)
        XCTAssertTrue(confirm.waitForExistence(timeout: 5), "confirmation")
        confirm.tap()
        sleep(3)
        shot("apres-suppression")
    }
}

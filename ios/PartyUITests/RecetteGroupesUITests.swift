import XCTest

/// Recette RÉELLE des groupes du 17.11 (nouveau graphisme + « Réunir les invités dans un groupe »), dans le simulateur en
/// configuration Release : serveur Party local branché sur la base de TEST, compte « Admin test » (code fixe). L'événement
/// RECETTE_EVENT est préparé avant : organisé par un autre compte, « Admin test » invité, option groupe allumée.
///   TEST_RUNNER_RECETTE_DIR=… TEST_RUNNER_RECETTE_EVENT=<id> TEST_RUNNER_RECETTE_GROUP=<nom> xcodebuild test
///   -configuration Release ENABLE_TESTABILITY=YES PARTY_SWIFT_CONDITIONS=E2E_HOOKS PARTY_BASE_URL=http://127.0.0.1:<port>
///   -only-testing:PartyUITests/RecetteGroupesUITests
final class RecetteGroupesUITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment
    private var dir: URL!
    private var app: XCUIApplication!
    private var step = 0

    override func setUpWithError() throws {
        guard let path = env["RECETTE_DIR"], env["RECETTE_EVENT"] != nil, env["RECETTE_GROUP"] != nil else {
            throw XCTSkip("Recette à la demande (RECETTE_DIR, RECETTE_EVENT, RECETTE_GROUP)")
        }
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
        try? app.screenshot().pngRepresentation.write(to: dir.appendingPathComponent(String(format: "groupes-%02d-%@.png", step, name)))
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

    func testGuestJoinsTheEventGroupAndSeesTheNewGroups() {
        let event = env["RECETTE_EVENT"]!, group = env["RECETTE_GROUP"]!
        launch()
        signInAdminIfNeeded()

        // 1. La fiche de l'événement : case « Rejoindre aussi le groupe » DÉCOCHÉE, cochée, puis « Absent ».
        app.terminate()
        launch("if(!sessionStorage.recette){sessionStorage.recette='1';location.replace('/?tab=events&event=\(event)');}")
        let box = any("label BEGINSWITH 'Rejoindre aussi le groupe'")
        if !box.waitForExistence(timeout: 40) {
            shot("fiche-sans-case")
            for _ in 0..<3 where !box.exists { app.swipeUp(); sleep(1) }
        }
        XCTAssertTrue(box.exists, "case du groupe sur la fiche")
        // Amène toute la case au-dessus de la barre d'onglets native, puis attend la fin de l'élan du défilement
        // (sinon le toucher ne fait qu'arrêter le défilement).
        for _ in 0..<4 where box.frame.maxY > app.frame.height - 130 { app.swipeUp(velocity: .slow); sleep(1) }
        sleep(3)
        shot("fiche-case-decochee")
        box.tap()
        sleep(2)
        shot("fiche-case-cochee")
        let absent = app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Absent' OR label BEGINSWITH 'Pas présent'")).firstMatch
        XCTAssertTrue(absent.exists, "bouton Absent")
        absent.tap()
        XCTAssertTrue(any("label CONTAINS 'Tu es dans le groupe'").waitForExistence(timeout: 20), "entré dans le groupe malgré « Absent »")
        sleep(1)
        shot("fiche-absent-dans-le-groupe")

        // 2. Discussions (natif) : la ligne du groupe avec son emoji, puis le bandeau « Tu es dans le groupe » + Quitter.
        app.tabBars.buttons["Discussions"].tap()
        let row = any("label CONTAINS %@", group)
        XCTAssertTrue(row.waitForExistence(timeout: 20), "le groupe dans Discussions")
        sleep(2)
        if app.buttons["Plus tard"].exists { app.buttons["Plus tard"].tap(); sleep(1) }  // « Reconnais tes amis » (1re fois)
        shot("discussions-ligne-du-groupe")
        row.tap()
        XCTAssertTrue(app.descendants(matching: .any)["group-join-note"].waitForExistence(timeout: 20), "bandeau natif")
        XCTAssertTrue(app.buttons["group-join-leave"].exists, "Quitter")
        sleep(1)
        shot("discussion-bandeau")
        app.navigationBars.buttons.firstMatch.tap()
        sleep(1)

        // 3. Réglages › Groupes : la liste native (18.11, « tout en natif » ; la grande carte « Crée le groupe de ta bande »
        // ne s'affiche plus que sans groupe) avec le groupe.
        app.tabBars.buttons["Réglages"].tap()
        let groups = app.buttons["settings-groups"]
        XCTAssertTrue(groups.waitForExistence(timeout: 10), "ligne Groupes")
        groups.tap()
        XCTAssertTrue(app.navigationBars["Groupes"].waitForExistence(timeout: 30) || app.staticTexts["Groupes"].waitForExistence(timeout: 5),
                      "liste native des groupes")
        XCTAssertTrue(any("label CONTAINS %@", group).exists, "le groupe dans la liste")
        sleep(2)
        shot("liste-des-groupes")
        any("label CONTAINS %@", group).tap()
        sleep(3)
        shot("page-du-groupe")
    }
}

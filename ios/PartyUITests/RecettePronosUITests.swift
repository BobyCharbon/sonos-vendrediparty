import XCTest

/// Recette RÉELLE des Pronos (avis f071c5f46e3d, 17.11) dans le simulateur en configuration Release : serveur Party local
/// branché sur la base de TEST, compte « Admin test » (code fixe). Préparé avant : le groupe RECETTE_GROUP (Admin test et
/// Guest A) et le prono RECETTE_PRONO de Guest A dans ce groupe (choix « Léa » / « Marc », réponses cachées).
///   TEST_RUNNER_RECETTE_DIR=… TEST_RUNNER_RECETTE_GROUP=<nom> TEST_RUNNER_RECETTE_PRONO=<id> xcodebuild test
///   -configuration Release ENABLE_TESTABILITY=YES PARTY_SWIFT_CONDITIONS=E2E_HOOKS PARTY_BASE_URL=http://127.0.0.1:<port>
///   -only-testing:PartyUITests/RecettePronosUITests
final class RecettePronosUITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment
    private var dir: URL!
    private var app: XCUIApplication!
    private var step = 0

    override func setUpWithError() throws {
        guard let path = env["RECETTE_DIR"], env["RECETTE_GROUP"] != nil, env["RECETTE_PRONO"] != nil else {
            throw XCTSkip("Recette à la demande (RECETTE_DIR, RECETTE_GROUP, RECETTE_PRONO)")
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
        try? app.screenshot().pngRepresentation.write(to: dir.appendingPathComponent(String(format: "pronos-ios-%02d-%@.png", step, name)))
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

    func testPlayFromANotificationThenCreateCloseAndReveal() {
        let prono = env["RECETTE_PRONO"]!, group = env["RECETTE_GROUP"]!
        launch()
        signInAdminIfNeeded()

        // 1. Toucher de la notification « Nouveau prono » (?tab=events&prono=<id>) : l'écran natif du prono s'ouvre.
        app.terminate()
        launch("if(!sessionStorage.recette){sessionStorage.recette='1';location.replace('/?tab=events&prono=\(prono)');}")
        let choice = app.buttons["prono-choice-1"]
        XCTAssertTrue(choice.waitForExistence(timeout: 40), "prono ouvert par la notification")
        shot("notification-prono")
        choice.tap()
        app.buttons["prono-seal"].tap()  // v2 : choisir, puis sceller
        XCTAssertTrue(any("label BEGINSWITH 'Ta réponse est enregistrée et cachée'").waitForExistence(timeout: 15), "réponse cachée enregistrée")
        shot("joue-cache")
        app.buttons["pronos-close"].tap()

        // 2. Réglages › Autres apps › Pronos : la liste native, puis « ＋ » : un prono pour le groupe.
        app.tabBars.buttons["Réglages"].tap()
        sleep(2)
        let row = any("identifier == 'settings-pronos' OR label BEGINSWITH 'Pronos'")
        for _ in 0..<6 where !(row.exists && row.isHittable) { app.swipeUp(velocity: .slow); sleep(1) }
        if !row.exists { shot("reglages-sans-pronos") }
        XCTAssertTrue(row.waitForExistence(timeout: 10), "ligne Pronos des Autres apps")
        row.tap()
        let waiting = any("identifier == 'prono-tab-wait'")  // v2 : un prono joué et encore ouvert est « En attente »
        XCTAssertTrue(waiting.waitForExistence(timeout: 20), "onglet En attente")
        waiting.tap()
        XCTAssertTrue(any("identifier == 'prono-card-\(prono)'").waitForExistence(timeout: 20), "le prono joué est dans la liste")
        shot("liste")
        let plus = app.buttons["pronos-new"]
        for _ in 0..<3 where !plus.isHittable { app.swipeDown(); sleep(1) }
        try? app.debugDescription.write(to: dir.appendingPathComponent("arbre-liste.txt"), atomically: true, encoding: .utf8)
        plus.tap()
        let scratch = app.buttons["prono-kind-choice"]  // v2 : « Partir de zéro › Choix »
        for _ in 0..<6 where !(scratch.exists && scratch.isHittable) { app.swipeUp(velocity: .slow); sleep(1) }
        XCTAssertTrue(scratch.waitForExistence(timeout: 15), "modèles et Partir de zéro")
        shot("modeles")
        scratch.tap()
        let question = app.textFields["prono-question"]
        XCTAssertTrue(question.waitForExistence(timeout: 10), "écran Nouveau prono")
        question.tap()
        app.typeText("Qui arrive en dernier au paintball ?")
        app.textFields["prono-option-0"].tap()
        app.typeText("Max")
        app.textFields["prono-option-1"].tap()
        app.typeText("Jo")
        app.typeText("\n")  // « Suivant » du dernier choix : le clavier se ferme
        sleep(1)
        XCTAssertEqual(app.keyboards.count, 0, "le clavier se ferme après le dernier choix")
        shot("question")
        app.buttons["prono-next"].tap()
        let item = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", group)).firstMatch
        XCTAssertTrue(item.waitForExistence(timeout: 10), "le groupe dans « Qui joue »")
        item.tap()
        sleep(1)
        shot("reglages")
        let publish = app.buttons["prono-publish"]
        for _ in 0..<6 where !(publish.exists && publish.isHittable) { app.swipeUp(velocity: .slow); sleep(1) }
        publish.tap()
        let playNow = app.buttons["prono-play-now"]
        XCTAssertTrue(playNow.waitForExistence(timeout: 20), "« C'est lancé ! »")
        shot("lance")
        playNow.tap()

        // 3. Le prono créé : je joue, je ferme maintenant, je donne le résultat, le dévoilement.
        let mine = app.buttons["prono-choice-0"]
        XCTAssertTrue(mine.waitForExistence(timeout: 20), "prono créé ouvert")
        mine.tap()
        shot("fiche")
        app.buttons["prono-seal"].tap()
        sleep(2)
        shot("scelle")
        let org = app.buttons["prono-org-toggle"]
        for _ in 0..<6 where !(org.exists && org.isHittable) { app.swipeUp(); sleep(1) }
        org.tap()
        sleep(1)
        let close = app.buttons["Fermer maintenant"]
        for _ in 0..<4 where !close.isHittable { app.swipeUp(); sleep(1) }
        close.tap()
        let result = app.buttons["prono-result-0"]
        XCTAssertTrue(result.waitForExistence(timeout: 20), "écran du résultat")
        shot("resultat")
        result.tap()
        app.buttons["prono-reveal-button"].tap()
        XCTAssertTrue(any("identifier == 'prono-reveal'").waitForExistence(timeout: 20), "dévoilement")
        // Seul joueur, et juste : « Unanimes ! » (tout le monde avait vu juste, confettis rendus).
        XCTAssertTrue(any("label CONTAINS 'Unanimes' OR label BEGINSWITH 'Tu avais vu juste'").waitForExistence(timeout: 10), "résultat")
        sleep(1)
        shot("devoilement")
        sleep(3)
        shot("devoilement-fin")
    }
}

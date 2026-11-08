import XCTest

/// Banc des bots : « Ton avis » dans l'app iPhone (Release), contre le serveur local branché sur la base de TEST.
/// Le bot (BOTS_IOS_PHONE, code fixe 123456) se connecte, ouvre Réglages › Ton avis, envoie un avis, le modifie
/// (« Modifier » › Enregistrer) et voit la nouvelle version avec « modifié le … ». Copié par tests/bots/ios_run.sh.
final class BotsFeedbackEditUITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment
    private var out: URL { URL(fileURLWithPath: env["BOTS_IOS_OUT"] ?? NSTemporaryDirectory()) }
    private var step = 0

    override func setUpWithError() throws {
        continueAfterFailure = false
        try XCTSkipUnless(env["BOTS_IOS_PHONE"] != nil, "Banc des bots : numéro du bot et serveur local nécessaires")
        try? FileManager.default.createDirectory(at: out, withIntermediateDirectories: true)
    }

    private func shot(_ app: XCUIApplication, _ name: String) {
        step += 1
        let file = out.appendingPathComponent(String(format: "avis-%02d-%@.png", step, name))
        try? app.screenshot().pngRepresentation.write(to: file)
        print("BOTS: capture \(file.lastPathComponent)")
    }

    /// Lance l'app, onglet Événements, connexion par le vrai écran (numéro de test, code fixe).
    private func launchSignedIn() -> XCUIApplication {
        let app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_JS"] = "localStorage.setItem('vp_tab','events');localStorage.setItem('vp_install_dismissed','1')"
        app.launch()
        let tab = app.tabBars.buttons["Événements"].firstMatch
        XCTAssertTrue(tab.waitForExistence(timeout: 20), "onglet natif « Événements »")
        tab.tap()
        Thread.sleep(forTimeInterval: 4)
        let phoneField = app.webViews.textFields["Ton numéro de téléphone"].firstMatch
        if phoneField.waitForExistence(timeout: 10) {
            phoneField.tap()
            phoneField.typeText(env["BOTS_IOS_PHONE"]!)
            app.webViews.buttons["Recevoir un code par SMS"].firstMatch.tap()
            let code = app.webViews.textFields.matching(NSPredicate(format: "placeholderValue == '123456' OR label CONTAINS 'Code'")).firstMatch
            XCTAssertTrue(code.waitForExistence(timeout: 60), "champ du code SMS")
            code.tap()
            code.typeText("123456")
            app.webViews.buttons["Se connecter"].firstMatch.tap()
            Thread.sleep(forTimeInterval: 5)
        }
        return app
    }

    func testAMemberSendsThenEditsHisFeedback() {
        let app = launchSignedIn()
        app.tabBars.buttons.element(boundBy: app.tabBars.buttons.count - 1).tap()   // Réglages
        let entry = app.buttons["settings-feedback"]
        for _ in 0..<4 where !entry.isHittable { app.swipeUp() }
        XCTAssertTrue(entry.waitForExistence(timeout: 15), "ligne « Ton avis » des Réglages")
        entry.tap()

        let stamp = Int(Date().timeIntervalSince1970) % 100000
        let original = "Recette du banc \(stamp) : avis envoyé depuis l'app iPhone, à modifier ensuite."
        let editor = app.textViews.firstMatch
        XCTAssertTrue(editor.waitForExistence(timeout: 15), "zone de texte de l'avis")
        editor.tap()
        editor.typeText(original)
        shot(app, "ecrit")
        app.buttons["Envoyer"].firstMatch.tap()

        let edit = app.buttons["feedback-edit"].firstMatch
        XCTAssertTrue(edit.waitForExistence(timeout: 30), "« Modifier » sur l'avis envoyé")
        shot(app, "envoye")
        edit.tap()
        let sheetEditor = app.textViews.firstMatch
        XCTAssertTrue(sheetEditor.waitForExistence(timeout: 10), "feuille « Modifier mon avis »")
        sheetEditor.tap()
        sheetEditor.typeText(" Modifié \(stamp).")
        shot(app, "modifie")
        app.buttons["Enregistrer"].firstMatch.tap()

        let updated = app.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", "Modifié \(stamp).")).firstMatch
        XCTAssertTrue(updated.waitForExistence(timeout: 20), "nouvelle version affichée")
        let mark = app.staticTexts.containing(NSPredicate(format: "label CONTAINS 'modifié le'")).firstMatch
        XCTAssertTrue(mark.waitForExistence(timeout: 5), "« modifié le … »")
        shot(app, "apres")
        print("BOTS: ✅ avis \(stamp) envoyé puis modifié dans l'app iPhone")
    }
}

import XCTest

/// Vitesse des Discussions natives (demande de l'admin du 18.11 : « le plus rapide possible »), dans le simulateur,
/// configuration Release : serveur Party local branché sur la base de TEST, compte « Admin test » (code fixe).
/// L'app note chaque étape (ChatTiming, PARTY_TIMING_FILE) ; ce test touche, écrit, et fait écrire l'autre personne
/// (VIP de test, par le serveur) en notant l'heure d'envoi. Le script de mesure lit les deux fichiers.
///   TEST_RUNNER_VITESSE_DIR=… TEST_RUNNER_VITESSE_CHAT=<conversation> TEST_RUNNER_VITESSE_SERVER=http://127.0.0.1:<port>
///   TEST_RUNNER_VITESSE_VIP_TOKEN=<jeton> xcodebuild test -configuration Release ENABLE_TESTABILITY=YES
///   PARTY_SWIFT_CONDITIONS=E2E_HOOKS PARTY_BASE_URL=http://127.0.0.1:<port> -only-testing:PartyUITests/VitesseDiscussionsUITests
final class VitesseDiscussionsUITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment
    private var dir: URL!
    private var app: XCUIApplication!

    override func setUpWithError() throws {
        guard let path = env["VITESSE_DIR"], env["VITESSE_CHAT"] != nil else { throw XCTSkip("Mesure à la demande (VITESSE_DIR, VITESSE_CHAT)") }
        dir = URL(fileURLWithPath: path)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        continueAfterFailure = true
        addUIInterruptionMonitor(withDescription: "Alertes d'iOS") { alert in
            for label in ["Autoriser", "Allow", "Ne pas autoriser", "Don’t Allow", "Plus tard", "Not Now"] where alert.buttons[label].exists {
                alert.buttons[label].tap()
                return true
            }
            return false
        }
    }

    private func note(_ name: String) {
        let line = "\(name) \(Int64((Date().timeIntervalSince1970 * 1000).rounded()))\n"
        let file = dir.appendingPathComponent("runner-timing.txt")
        if let handle = try? FileHandle(forWritingTo: file) {
            handle.seekToEndOfFile()
            handle.write(line.data(using: .utf8)!)
            try? handle.close()
        } else {
            try? line.data(using: .utf8)!.write(to: file)
        }
    }

    private func signInAdminIfNeeded() {
        let tab = app.tabBars.buttons.matching(NSPredicate(format: "label IN {'Réglages', 'Se connecter'}")).firstMatch
        XCTAssertTrue(tab.waitForExistence(timeout: 40), "onglet Réglages")
        // Au lancement, l'onglet dit « Se connecter » le temps que la page relise la session : on attend « Réglages ».
        if app.tabBars.buttons["Réglages"].waitForExistence(timeout: 8) { return }
        tab.tap()
        sleep(2)
        // Ligne « Se connecter » des Réglages (libellé combiné « Se connecter, Avec ton numéro… »), pas l'onglet.
        let entry = app.descendants(matching: .any).matching(NSPredicate(format: "label BEGINSWITH 'Se connecter, '")).firstMatch
        if entry.waitForExistence(timeout: 10) { entry.tap() } else {
            try? app.screenshot().pngRepresentation.write(to: dir.appendingPathComponent("echec-connexion.png"))
            app.staticTexts["Se connecter"].firstMatch.tap()
        }
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

    private func label(_ value: String) -> XCUIElement {
        app.descendants(matching: .any).matching(NSPredicate(format: "label CONTAINS %@", value)).firstMatch
    }

    /// L'autre personne écrit (relais du serveur, avec son jeton) ; l'heure de l'envoi est notée.
    private func otherWrites(_ id: String, _ text: String) {
        guard let server = env["VITESSE_SERVER"], let token = env["VITESSE_VIP_TOKEN"],
              let url = URL(string: server + "/api/account/chats/send") else { return }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONSerialization.data(withJSONObject: [
            "token": token, "group_id": env["VITESSE_CHAT"]!, "body": text, "direct": true, "id": id, "mentions": [String](),
        ])
        note("remote.send.\(id)")
        let done = expectation(description: "envoi de l'autre personne")
        URLSession.shared.dataTask(with: request) { _, _, _ in done.fulfill() }.resume()
        wait(for: [done], timeout: 20)
    }

    func testChatsSpeed() {
        let chat = env["VITESSE_CHAT"]!
        let rounds = Int(env["VITESSE_ROUNDS"] ?? "") ?? 5
        for round in 1...rounds {
            app = XCUIApplication()
            app.launchEnvironment["PARTY_DEBUG_JS"] = "localStorage.setItem('vp_install_dismissed','1');"
            app.launchEnvironment["PARTY_TIMING_FILE"] = dir.appendingPathComponent("app-timing.txt").path
            app.launchEnvironment["PARTY_CLEAR_CHATS_CACHE"] = "1"
            app.launch()
            note("round.\(round)")
            signInAdminIfNeeded()
            sleep(3)

            // 1. Onglet Discussions → liste ; toucher la conversation → messages et champ.
            let tab = app.tabBars.buttons["Discussions"]
            XCTAssertTrue(tab.waitForExistence(timeout: 20), "onglet Discussions")
            tab.tap()
            let row = app.buttons["chat-row-\(chat)"]
            XCTAssertTrue(row.waitForExistence(timeout: 20), "ligne de la conversation")
            sleep(1)
            row.tap()
            let field = app.descendants(matching: .any)["chat-message"]
            if !field.waitForExistence(timeout: 20) {
                try? app.screenshot().pngRepresentation.write(to: dir.appendingPathComponent("echec-conversation-\(round).png"))
                XCTFail("champ de saisie")
            }
            sleep(2)

            // 2. Envoyer : bulle tout de suite.
            field.tap()
            let mine = "Vitesse iPhone \(round) " + UUID().uuidString.prefix(6)
            app.typeText(mine)
            app.buttons["chat-send"].tap()
            XCTAssertTrue(label(mine).waitForExistence(timeout: 10), "bulle envoyée")
            sleep(2)

            // 3. L'autre personne répond : affiché sans rien toucher.
            let id = UUID().uuidString.lowercased()
            let theirs = "Réponse \(round) " + id.prefix(6)
            otherWrites(id, theirs)
            XCTAssertTrue(label(theirs).waitForExistence(timeout: 20), "message reçu")
            sleep(1)

            // 4. Retour, Événements, puis Discussions : 2e ouverture de la liste et de la conversation.
            app.navigationBars.buttons.firstMatch.tap()
            sleep(1)
            app.tabBars.buttons["Événements"].tap()
            sleep(2)
            tab.tap()
            XCTAssertTrue(row.waitForExistence(timeout: 20), "ligne de la conversation (2e)")
            sleep(1)
            note("second.\(round)")
            row.tap()
            XCTAssertTrue(field.waitForExistence(timeout: 20), "champ de saisie (2e)")
            sleep(1)
            app.navigationBars.buttons.firstMatch.tap()
            sleep(1)

            // 5. Nouveau message : recherche « VIP ».
            let new = app.buttons["chats-new-message"]
            if new.waitForExistence(timeout: 10) {
                new.tap()
                let search = app.textFields["new-message-search"]
                if search.waitForExistence(timeout: 10) {
                    search.tap()
                    app.typeText("VIP")
                    _ = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'new-message-person-'")).firstMatch.waitForExistence(timeout: 10)
                    sleep(1)
                    try? app.screenshot().pngRepresentation.write(to: dir.appendingPathComponent("recherche-\(round).png"))
                }
            }
            app.terminate()
        }
    }
}

import XCTest

/// Captures brutes des visuels App Store (tools/appstore_visuels, docs/app-store/visuels/README.md) : simulateur 6,9"
/// (1320 × 2868), configuration Release, serveur Party local branché sur la base de TEST, données de démonstration de
/// tools/appstore_visuels/demo_data.py (spectatrice « Léa », numéro de test à code fixe). Rien ne s'exécute sans VISUELS_DIR.
///   TEST_RUNNER_VISUELS_DIR=… TEST_RUNNER_VISUELS_JS=… TEST_RUNNER_VISUELS_SERVER=http://127.0.0.1:<port>
///   xcodebuild test -configuration Release ENABLE_TESTABILITY=YES PARTY_SWIFT_CONDITIONS=E2E_HOOKS
///   PARTY_BASE_URL=http://127.0.0.1:<port> -only-testing:PartyUITests/VisuelsAppStoreUITests
final class VisuelsAppStoreUITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment
    private var dir: URL!
    private var app: XCUIApplication!

    override func setUpWithError() throws {
        guard let path = env["VISUELS_DIR"] else { throw XCTSkip("Captures à la demande (VISUELS_DIR)") }
        dir = URL(fileURLWithPath: path)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        continueAfterFailure = true
        addUIInterruptionMonitor(withDescription: "Alertes d'iOS") { alert in
            for label in ["Ne pas autoriser", "Don’t Allow", "Plus tard", "OK"] where alert.buttons[label].exists {
                alert.buttons[label].tap()
                return true
            }
            return false
        }
    }

    /// Capture de tout l'écran (barre d'état comprise, réglée par `simctl status_bar`).
    private func shot(_ name: String, wait: UInt32 = 2) {
        sleep(wait)
        try? XCUIScreen.main.screenshot().pngRepresentation.write(to: dir.appendingPathComponent("\(name).png"))
    }

    private func any(_ predicate: String) -> XCUIElement {
        app.descendants(matching: .any).matching(NSPredicate(format: predicate)).firstMatch
    }

    /// Onglet : barre du bas, ou barre verticale du système sur l'écran extérieur de l'iPhone Duo (une « toolbar »).
    private func tab(_ label: String, timeout: TimeInterval = 40) -> XCUIElement {
        let predicate = NSPredicate(format: "label IN %@", label.components(separatedBy: "|"))
        let deadline = Date().addingTimeInterval(timeout)
        repeat {
            for bar in [app.tabBars, app.toolbars] {
                let t = bar.buttons.matching(predicate).firstMatch
                if t.exists { return t }
            }
            usleep(500_000)
        } while Date() < deadline
        XCTFail("onglet \(label)")
        return app.tabBars.buttons.matching(predicate).firstMatch
    }

    private func launch(_ js: String = "") {
        app = XCUIApplication()
        // Jamais rouvert au milieu d'une partie (salle de jeux d'une capture précédente) : la barre d'onglets reste là.
        app.launchEnvironment["PARTY_DEBUG_JS"] = "localStorage.setItem('vp_install_dismissed','1');"
            + "localStorage.removeItem('vp_game');localStorage.removeItem('vp_room');" + (env["VISUELS_JS"] ?? "") + js
        app.launch()
    }

    private func signIn() {
        tab("Réglages|Se connecter").tap()
        sleep(2)
        guard app.staticTexts["Se connecter"].exists else { return }
        app.staticTexts["Se connecter"].firstMatch.tap()
        let field = app.textFields["login-phone"]
        XCTAssertTrue(field.waitForExistence(timeout: 10), "champ du numéro")
        field.tap()
        app.typeText(env["VISUELS_PHONE"] ?? "0790000210")
        app.buttons["login-send"].tap()
        let code = app.textFields["login-code"]
        XCTAssertTrue(code.waitForExistence(timeout: 20), "champ du code")
        code.tap()
        app.typeText("123456")
        XCTAssertTrue(app.staticTexts["Léa"].waitForExistence(timeout: 30), "connectée en Léa")
    }

    /// Requête au serveur local (joueurs inventés qui rejoignent la salle de jeux).
    @discardableResult
    private func post(_ path: String, _ body: [String: Any]) -> Int {
        guard let server = env["VISUELS_SERVER"], let url = URL(string: server + path) else { return 0 }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try? JSONSerialization.data(withJSONObject: body)
        let done = DispatchSemaphore(value: 0)
        var status = 0
        URLSession.shared.dataTask(with: req) { _, r, _ in
            status = (r as? HTTPURLResponse)?.statusCode ?? 0
            done.signal()
        }.resume()
        _ = done.wait(timeout: .now() + 15)
        return status
    }

    func testCaptures() {
        launch()
        signIn()
        let only = env["VISUELS_ONLY"] ?? "events,event,eventchat,poll,ticket,chats,chat,pot,ia,games,music"
        let steps = Set(only.split(separator: ",").map(String.init))

        if steps.contains("events") || steps.contains("event") {
            tab("Événements").tap()
            XCTAssertTrue(any("label BEGINSWITH 'Raclette chez Inès'").waitForExistence(timeout: 90), "liste des événements")
            shot("brut-evenements", wait: 8)
            if steps.contains("event") {
                any("label BEGINSWITH 'Anniversaire de Zoé'").tap()
                XCTAssertTrue(any("label CONTAINS 'Rue de la Fabrique'").waitForExistence(timeout: 60), "fiche de l'événement")
                // Bandeau « Ne rate rien de cet événement » (notifications de l'appareil éteintes) : « Plus tard ».
                let later = app.buttons["Plus tard"]
                if later.waitForExistence(timeout: 3) { later.tap() }
                shot("brut-fiche", wait: 4)
                app.swipeUp(velocity: .slow)
                shot("brut-fiche-2")
                app.swipeUp(velocity: .slow)
                shot("brut-fiche-3")
                app.swipeUp(velocity: .slow)
                shot("brut-fiche-4")
            }
        }

        // Fiche d'un événement depuis la liste (retour à la liste à la fin).
        func openEvent(_ title: String, until text: String) -> Bool {
            if !tab("Événements").isSelected { tab("Événements").tap() }
            let card = any("label BEGINSWITH '\(title)'")
            guard card.waitForExistence(timeout: 60) else { return false }
            card.tap()
            let ok = any("label CONTAINS '\(text)'").waitForExistence(timeout: 60)
            let later = app.buttons["Plus tard"]
            if later.waitForExistence(timeout: 2) { later.tap() }
            return ok
        }
        func backToList() {
            let back = app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Événements'")).firstMatch
            if back.exists { back.tap() }
            sleep(2)
        }

        if steps.contains("eventchat") {
            // Discussion native de l'événement, ouverte depuis Discussions (comme une notification l'ouvrirait).
            tab("Discussions").tap()
            let later = app.buttons["Plus tard"]
            if later.waitForExistence(timeout: 4) { later.tap() }
            let row = any("label CONTAINS 'Anniversaire de Zoé'")
            XCTAssertTrue(row.waitForExistence(timeout: 30), "discussion de l'événement dans la liste")
            row.tap()
            XCTAssertTrue(any("label CONTAINS 'trop forts'").waitForExistence(timeout: 30), "discussion de l'événement")
            shot("brut-discussion-evenement", wait: 3)
            let close = app.buttons["event-chat-close"]
            if close.exists { close.tap() } else { app.navigationBars.buttons.firstMatch.tap() }
            sleep(2)
        }

        if steps.contains("poll") {
            // Pastille « Sondages » : la carte du sondage en tête.
            tab("Événements").tap()
            let pill = any("label BEGINSWITH 'Sondages'")
            if pill.waitForExistence(timeout: 60) { pill.tap() }
            sleep(2)
        }
        if steps.contains("poll"), openEvent("Week-end au chalet", until: "Chalet des Mélèzes") {
            shot("brut-sondage", wait: 3)
            app.swipeUp(velocity: .slow)
            shot("brut-sondage-2")
            backToList()
        }

        if steps.contains("ticket"), openEvent("Raclette chez Inès", until: "Chemin des Lilas") {
            shot("brut-raclette", wait: 3)
            let ticket = any("label CONTAINS[c] 'billet'")
            if ticket.waitForExistence(timeout: 5) {
                ticket.tap()
                shot("brut-billet", wait: 3)
            }
            app.swipeUp(velocity: .slow)
            shot("brut-raclette-2")
            backToList()
        }

        if steps.contains("chats") || steps.contains("chat") {
            tab("Discussions").tap()
            let later = app.buttons["Plus tard"]
            if later.waitForExistence(timeout: 6) { later.tap() }
            XCTAssertTrue(any("label CONTAINS 'Les Lucioles'").waitForExistence(timeout: 30), "liste des discussions")
            shot("brut-discussions", wait: 4)
            if steps.contains("chat") {
                any("label CONTAINS 'Les Lucioles'").tap()
                XCTAssertTrue(any("label CONTAINS 'On répète la choré'").waitForExistence(timeout: 30), "conversation")
                shot("brut-conversation", wait: 3)
                app.navigationBars.buttons.firstMatch.tap()
                sleep(1)
            }
        }

        if steps.contains("groups") {
            tab("Réglages").tap()
            let groups = app.buttons["settings-groups"]
            if groups.waitForExistence(timeout: 15) {
                groups.tap()
                XCTAssertTrue(any("label BEGINSWITH 'Les Lucioles'").waitForExistence(timeout: 30), "liste des groupes")
                shot("brut-groupes", wait: 3)
                any("label BEGINSWITH 'Les Lucioles'").tap()
                XCTAssertTrue(app.staticTexts["group-page-name"].waitForExistence(timeout: 30), "page du groupe")
                shot("brut-groupe", wait: 4)
                app.swipeUp(velocity: .slow)
                shot("brut-groupe-2")
            }
        }

        if steps.contains("pot") {
            tab("Réglages").tap()
            let pot = any("identifier == 'settings-tricount' OR label BEGINSWITH 'Pot commun'")
            if pot.waitForExistence(timeout: 15) {
                pot.tap()
                let g = any("label CONTAINS 'Week-end au chalet'")
                XCTAssertTrue(g.waitForExistence(timeout: 30), "pot commun")
                shot("brut-pot-liste", wait: 3)
                g.tap()
                _ = any("label CONTAINS 'Location du chalet'").waitForExistence(timeout: 30)
                shot("brut-pot", wait: 3)
            }
        }

        if steps.contains("ia") {
            app.terminate()
            app = XCUIApplication()
            app.launchEnvironment["PARTY_DEBUG_JS"] = "localStorage.setItem('vp_install_dismissed','1');"
                + "localStorage.removeItem('vp_game');localStorage.removeItem('vp_room');" + (env["VISUELS_JS"] ?? "")
            app.launchEnvironment["PARTY_DEBUG_AI_EVENT"] = env["VISUELS_AI_DRAFT"] ?? "tips"
            app.launchEnvironment["PARTY_DEBUG_AI_SAID"] = env["VISUELS_AI_SAID"] ?? ""
            app.launch()
            let step = any("label == 'Étape 1 sur 3 : La soirée'")
            XCTAssertTrue(step.waitForExistence(timeout: 40), "Créer avec l'IA")
            shot("brut-ia", wait: 3)
            app.swipeUp(velocity: .slow)
            shot("brut-ia-2")
            app.terminate()
            launch()
        }

        if steps.contains("games") {
            tab("Jeux").tap()
            let create = app.buttons["Créer une salle"]
            XCTAssertTrue(create.waitForExistence(timeout: 30), "Créer une salle")
            create.tap()
            let code = app.staticTexts.matching(NSPredicate(format: "label MATCHES '^[0-9]{4}$'")).firstMatch
            XCTAssertTrue(code.waitForExistence(timeout: 20), "code de la salle")
            let room = code.label
            let players = [("Hugo", "quiz"), ("Inès", "quiz"), ("Tom", "president"), ("Zoé", "quiz"), ("Nathan", "heist"), ("Chloé", "neon")]
            for (i, (name, vote)) in players.enumerated() {
                let gid = "visuels-joueur-\(i + 1)"
                post("/api/games/\(room)", ["guest_id": gid, "name": name, "action": "join"])
                post("/api/games/\(room)", ["guest_id": gid, "name": name, "action": "rvote", "target": vote])
            }
            shot("brut-jeux", wait: 5)
            app.swipeUp(velocity: .slow)
            shot("brut-jeux-2")
        }

        if steps.contains("music") {
            // Le simulateur n'a pas d'enceinte de soirée : « Gérer la soirée » sur un état figé (PARTY_DEBUG_HOST_DEMO,
            // tools/appstore_visuels/host_demo.json : titres et artistes inventés).
            app.terminate()
            app = XCUIApplication()
            app.launchEnvironment["PARTY_DEBUG_JS"] = "localStorage.setItem('vp_install_dismissed','1');"
                + "localStorage.removeItem('vp_game');localStorage.removeItem('vp_room');" + (env["VISUELS_JS"] ?? "")
            app.launchEnvironment["PARTY_DEBUG_HOST_DEMO"] = env["VISUELS_HOST_DEMO"] ?? ""
            app.launch()
            XCTAssertTrue(app.staticTexts["Gérer la soirée"].waitForExistence(timeout: 30), "Gérer la soirée")
            XCTAssertTrue(any("label CONTAINS 'Paillettes'").waitForExistence(timeout: 10), "file de la soirée")
            shot("brut-musique", wait: 3)
        }
    }

    /// Aperçu vidéo (App Preview) : un tour de l'app, filmé par `simctl io recordVideo` (tools/appstore_visuels/apercu.sh).
    /// Le début et la fin du tour sont notés dans VISUELS_DIR/apercu-temps.txt (secondes depuis 1970) pour couper la vidéo.
    func testApercu() {
        launch()
        signIn()
        tab("Événements").tap()
        XCTAssertTrue(any("label BEGINSWITH 'Raclette chez Inès'").waitForExistence(timeout: 90), "liste des événements")
        sleep(6)
        var marks = [String(Date().timeIntervalSince1970)]
        sleep(3)
        app.swipeUp(velocity: .slow)
        sleep(1)
        app.swipeDown(velocity: .slow)
        sleep(1)
        any("label BEGINSWITH 'Anniversaire de Zoé'").tap()
        _ = any("label CONTAINS 'Rue de la Fabrique'").waitForExistence(timeout: 30)
        sleep(3)
        app.swipeUp(velocity: .slow)
        sleep(2)
        app.swipeUp(velocity: .slow)
        sleep(2)
        tab("Discussions").tap()
        sleep(3)
        any("label CONTAINS 'Les Lucioles'").tap()
        _ = any("label CONTAINS 'On répète la choré'").waitForExistence(timeout: 20)
        sleep(4)
        app.navigationBars.buttons.firstMatch.tap()
        sleep(2)
        tab("Jeux").tap()
        sleep(4)
        marks.append(String(Date().timeIntervalSince1970))
        try? marks.joined(separator: "\n").write(to: dir.appendingPathComponent("apercu-temps.txt"), atomically: true, encoding: .utf8)
    }
}

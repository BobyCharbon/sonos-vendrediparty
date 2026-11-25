import XCTest

/// Recette du refus Apple 1.4.3 (25.11.2026), configuration Release (= app App Store, « PartyStore »), serveur Party local
/// de la branche, base de TEST, drapeaux de la prod (bar allumé sur le serveur, Zicou éteint). Chaque écran est photographié
/// (avec son arbre d'accessibilité) dans REFUS_DIR ; tout mot de boisson, jeu caché ou mode Hot fait échouer le test.
///   TEST_RUNNER_REFUS_DIR=… [TEST_RUNNER_REFUS_PHONE=0790000001] [TEST_RUNNER_REFUS_EVENT=<titre>] xcodebuild test-without-building
///   … -only-testing:PartyUITests/RecetteRefus143UITests (build Release, ENABLE_TESTABILITY=YES PARTY_SWIFT_CONDITIONS=E2E_HOOKS
///   PARTY_BASE_URL=http://127.0.0.1:<port>). L'événement (avec un bar : Bière + Coca) est préparé à part sur la base de TEST.
final class RecetteRefus143UITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment
    private var dir: URL!
    private var app: XCUIApplication!
    private var step = 0

    static let forbidden = ["gorgée", "Gorgée", "boire", " boit", "alcool", "Alcool", "bière", "Bière", "vodka", "Vodka",
                            "tequila", "Tequila", "tournée", "ivre", "🍻", "🍺", "🥃", "🍸", "🍹", "🍷", "Bar de la soirée",
                            "Bar : ", "Beer pong", "Purify", "Biskit", "Casino", "Blackjack", "🔥 Hot", "🎲 Mix",
                            "Undercover", "Mr. White", "🍬", "bonbon"]

    override func setUpWithError() throws {
        guard let path = env["REFUS_DIR"] else { throw XCTSkip("Recette à la demande (REFUS_DIR)") }
        dir = URL(fileURLWithPath: path)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        continueAfterFailure = true
        addUIInterruptionMonitor(withDescription: "Alertes d'iOS") { alert in
            for label in ["Autoriser", "Allow", "OK", "Ne pas autoriser"] where alert.buttons[label].exists {
                alert.buttons[label].tap()
                return true
            }
            return false
        }
    }

    private func record(_ name: String) {
        step += 1
        let base = String(format: "ios-%02d-%@", step, name)
        sleep(1)
        try? app.screenshot().pngRepresentation.write(to: dir.appendingPathComponent("\(base).png"))
        let tree = app.debugDescription
        try? tree.write(to: dir.appendingPathComponent("\(base).txt"), atomically: true, encoding: .utf8)
        for word in Self.forbidden {
            for line in tree.split(separator: "\n") where line.contains(word) {
                let shown = line.replacingOccurrences(of: #"identifier: '[^']*'"#, with: "", options: .regularExpression)
                guard shown.contains(word) else { continue }
                let note = "\(base) : « \(word) » dans \(shown.trimmingCharacters(in: .whitespaces))\n"
                append(note)
                XCTFail(note)
            }
        }
    }

    private func append(_ text: String) {
        let file = dir.appendingPathComponent("anomalies.txt")
        if let handle = try? FileHandle(forWritingTo: file) {
            handle.seekToEndOfFile()
            handle.write(text.data(using: .utf8)!)
            try? handle.close()
        } else {
            try? text.data(using: .utf8)!.write(to: file)
        }
    }

    private func tab(_ label: String) -> XCUIElement {
        app.tabBars.buttons[label].exists ? app.tabBars.buttons[label]
            : app.buttons.matching(NSPredicate(format: "label == %@", label)).firstMatch
    }

    private func web(_ prefix: String) -> XCUIElement {
        app.webViews.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", prefix)).firstMatch
    }

    private func scrollAndRecord(_ name: String, pages: Int) {
        for i in 1...pages {
            app.swipeUp(velocity: .slow)
            record("\(name)-\(i)")
        }
        for _ in 0..<pages { app.swipeDown(velocity: .fast) }
    }

    /// Pyramide en points (décision du 25.11) : la partie est préparée et menée par refus_143_pyramide.py (même identité
    /// d'invité, REFUS_PYR_GID / REFUS_PYR_CODE) ; ici, une capture toutes les 4 s : distribution, mémorisation, sommet, tableau des points.
    func testPyramidPoints() throws {
        guard let gid = env["REFUS_PYR_GID"], let code = env["REFUS_PYR_CODE"] else { throw XCTSkip("REFUS_PYR_GID / CODE") }
        app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_JS"] = "localStorage.setItem('vp_install_dismissed','1');localStorage.setItem('vp_name','Léa');"
            + "localStorage.setItem('vp_guest','\(gid)');localStorage.setItem('vp_game','\(code)');localStorage.removeItem('vp_room');"
        app.launch()
        sleep(5)
        // Partie en cours : l'app s'ouvre dessus, en plein écran (sans barre d'onglets) ; sinon, l'onglet Jeux.
        if tab("Jeux").exists && tab("Jeux").isHittable { tab("Jeux").tap() }
        sleep(3)
        step = 60
        try? "ready".write(to: dir.appendingPathComponent("pyramide-prete.txt"), atomically: true, encoding: .utf8)
        let frames = Int(env["REFUS_PYR_FRAMES"] ?? "40") ?? 40
        for i in 0..<frames {
            record(String(format: "pyramide-%02d", i))
            sleep(3)
        }
    }

    func testGamesHaveNoDrinking() {
        app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_JS"] = "localStorage.setItem('vp_install_dismissed','1');localStorage.setItem('vp_name','Léa');localStorage.removeItem('vp_room');localStorage.removeItem('vp_game');"
        app.launch()
        sleep(6)

        // Jeux : accueil, puis la salle de jeux et toutes ses catégories.
        XCTAssertTrue(tab("Jeux").waitForExistence(timeout: 30))
        tab("Jeux").tap()
        sleep(4)
        record("jeux-accueil")
        let create = web("Créer une salle")
        XCTAssertTrue(create.waitForExistence(timeout: 20), "« Créer une salle »")
        create.tap()
        sleep(5)
        record("salle")
        scrollAndRecord("salle-categories", pages: 5)

        // Réglages de chaque jeu gardé (la feuille de la salle) : aucune option de gorgées, aucun mode Hot / Mix.
        for game in ["Je n'ai jamais", "Qui de nous", "Qui est le plus", "Quiz", "L'Intrus", "Roulette", "Pour ou contre"] {
            let tile = web(game)
            for _ in 0..<8 where !(tile.exists && tile.isHittable) { app.swipeUp(velocity: .slow) }
            guard tile.exists else { record("absent-\(game)"); XCTFail("tuile \(game) absente"); continue }
            tile.tap()
            sleep(2)
            record("reglages-\(game)")
            app.swipeUp(velocity: .slow)
            record("reglages-\(game)-bas")
            // La feuille se ferme en touchant le fond assombri, au-dessus d'elle.
            app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.12)).tap()
            sleep(2)
            for _ in 0..<6 { app.swipeDown(velocity: .fast) }
        }

        // Je n'ai jamais lancé pour la salle (mode Malaisant) : la partie, sans gorgée.
        let never = web("Je n'ai jamais")
        for _ in 0..<8 where !(never.exists && never.isHittable) { app.swipeUp(velocity: .slow) }
        if never.exists {
            never.tap()
            sleep(2)
            let launch = web("Lancer")
            for _ in 0..<4 where !(launch.exists && launch.isHittable) { app.swipeUp(velocity: .slow) }
            if launch.exists { launch.tap(); sleep(4); record("never-lance") }
        }

    }

    /// Événements (connecté) : la fiche d'un événement qui a un bar sur le web, sans bar ici ; réglages des notifications.
    func testEventWithoutBarAndNotifications() {
        app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_JS"] = "localStorage.setItem('vp_install_dismissed','1');localStorage.removeItem('vp_room');localStorage.removeItem('vp_game');"
        app.launch()
        sleep(6)
        step = 40
        let phone = env["REFUS_PHONE"] ?? "0790000001"
        let settings = app.buttons.matching(NSPredicate(format: "label IN {'Réglages', 'Se connecter'}")).firstMatch
        settings.tap()
        sleep(2)
        let row = app.staticTexts["Se connecter"].firstMatch
        if row.exists, row.isHittable, !app.textFields["login-phone"].exists { row.tap() }
        let field = app.textFields["login-phone"]
        if field.waitForExistence(timeout: 15) {
            field.tap()
            app.typeText(phone)
            app.sendLoginCode()
            let code = app.textFields["login-code"]
            if code.waitForExistence(timeout: 30) { code.tap(); app.typeText("123456"); sleep(8) }
        }
        tab("Événements").tap()
        sleep(6)
        // Le module Événements a sa propre session : connexion SMS dans la page si elle la demande.
        let webPhone = app.webViews.textFields.firstMatch
        if app.webViews.staticTexts["Ton compte Party"].exists, webPhone.exists {
            webPhone.tap()
            // Un autre numéro de test que l'écran natif (un code par minute et par numéro sur la base de TEST).
            app.typeText((env["REFUS_WEB_PHONE"] ?? "0790000003") + "\n")  // « Entrée » ferme le clavier qui cachait le bouton
            sleep(1)
            let send = web("Recevoir un code")
            if send.exists && send.isHittable { send.tap() }
            sleep(4)
            let webCode = app.webViews.textFields.matching(NSPredicate(format: "placeholderValue == '123456'")).firstMatch
            // Base de TEST : un code par minute et par numéro (l'écran natif vient d'en demander un).
            let later = app.webViews.staticTexts.matching(NSPredicate(format: "label CONTAINS 'Réessaie dans une minute'")).firstMatch
            if !webCode.waitForExistence(timeout: 8), later.exists { sleep(62); send.tap(); sleep(4) }
            if webCode.waitForExistence(timeout: 30) { webCode.tap(); app.typeText("123456") }
            let go = web("Se connecter")
            if go.waitForExistence(timeout: 5) { go.tap() }
            sleep(8)
        }
        record("evenements")
        let title = env["REFUS_EVENT"] ?? "Soirée recette 1.4.3 iPhone"
        let card = app.webViews.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", title)).firstMatch
        for _ in 0..<6 where !(card.exists && card.isHittable) { app.swipeUp(velocity: .slow) }
        if card.exists {
            card.tap()
            sleep(6)
            record("fiche")
            scrollAndRecord("fiche-bas", pages: 4)
        } else {
            record("fiche-introuvable")
            XCTFail("événement « \(title) » introuvable")
        }
        tab("Réglages").tap()
        sleep(2)
        let notifications = app.staticTexts["Notifications"].firstMatch
        for _ in 0..<6 where !(notifications.exists && notifications.isHittable) { app.swipeUp(velocity: .slow) }
        if notifications.exists {
            notifications.tap()
            sleep(4)
            record("notifications")
            scrollAndRecord("notifications-bas", pages: 3)
        }
    }
}

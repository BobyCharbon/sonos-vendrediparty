import XCTest

/// Recette RÉELLE des avis traités le 13.11.2026, dans le simulateur (configuration Release, comme l'App Store) :
/// serveur Party local branché sur la base de TEST, réglages de prod (Invitations v2, CGU exigées, Zicou éteint),
/// compte de test « Admin test » (code fixe, aucun SMS). Chaque étape est photographiée dans RECETTE_DIR.
/// Données préparées avant (recette.json) : RECETTE_CARPOOL, RECETTE_POLL, RECETTE_DRAFT (événements), RECETTE_GAME
/// (Purify Test d'Admin test). Lancé à la demande :
///   TEST_RUNNER_RECETTE_DIR=… TEST_RUNNER_RECETTE_…=… xcodebuild test -configuration Release ENABLE_TESTABILITY=YES
///   PARTY_SWIFT_CONDITIONS=E2E_HOOKS PARTY_BASE_URL=http://127.0.0.1:<port> -only-testing:PartyUITests/RecetteAvisUITests
final class RecetteAvisUITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment
    private var dir: URL!
    private var app: XCUIApplication!
    private var step = 0

    override func setUpWithError() throws {
        guard let path = env["RECETTE_DIR"] else { throw XCTSkip("Recette à la demande (RECETTE_DIR)") }
        dir = URL(fileURLWithPath: path)
        continueAfterFailure = true
        addUIInterruptionMonitor(withDescription: "Notifications d'iOS") { alert in
            for label in ["Autoriser", "Allow"] where alert.buttons[label].exists {
                alert.buttons[label].tap()
                return true
            }
            return false
        }
    }

    // MARK: Outils

    private func shot(_ name: String) {
        step += 1
        let base = String(format: "%@-%02d-%@", name.components(separatedBy: "/").first ?? "x", step, name.replacingOccurrences(of: "/", with: "_"))
        try? app.screenshot().pngRepresentation.write(to: dir.appendingPathComponent("\(base).png"))
    }

    /// Lancement de l'app ; js : code injecté dans la page au chargement (PARTY_DEBUG_JS, E2E_HOOKS).
    private func launch(_ js: String = "") {
        app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_JS"] = "localStorage.setItem('vp_install_dismissed','1');" + js
        app.launch()
    }

    /// Ouvre une page du module Événements (comme une notification) une fois Party chargée.
    private func openEvents(_ path: String) -> String {
        "addEventListener('load',()=>setTimeout(()=>PartyEvents.open('/events\(path)'),1500));"
    }

    private func web(_ text: String) -> XCUIElement {
        app.webViews.descendants(matching: .any).matching(NSPredicate(format: "label CONTAINS %@", text)).firstMatch
    }

    private func webButton(_ label: String) -> XCUIElement {
        app.webViews.buttons.matching(NSPredicate(format: "label == %@ OR label BEGINSWITH %@", label, label)).firstMatch
    }

    private func visible(_ element: XCUIElement) -> Bool {
        guard element.exists, element.isHittable else { return false }
        let view = app.webViews.firstMatch.frame
        let bar = app.tabBars.firstMatch.exists ? app.tabBars.firstMatch.frame.minY : app.frame.maxY
        return element.frame.minY >= view.minY && element.frame.maxY <= min(view.maxY, bar)
    }

    /// Fait défiler la page jusqu'à l'élément (vers le bas, puis vers le haut).
    @discardableResult
    private func reveal(_ element: XCUIElement, timeout: TimeInterval = 20) -> Bool {
        _ = element.waitForExistence(timeout: timeout)
        for _ in 0..<10 where !visible(element) { app.webViews.firstMatch.swipeUp(velocity: .slow) }
        for _ in 0..<10 where !visible(element) { app.webViews.firstMatch.swipeDown(velocity: .slow) }
        return visible(element)
    }

    private func tapWeb(_ element: XCUIElement, _ what: String) {
        XCTAssertTrue(reveal(element), "\(what) introuvable")
        if element.exists { element.tap() }
        sleep(1)
    }

    private func settingsTab() {
        let tab = app.tabBars.buttons.matching(NSPredicate(format: "label IN {'Réglages', 'Se connecter'}")).firstMatch
        XCTAssertTrue(tab.waitForExistence(timeout: 20), "onglet Réglages")
        tab.tap()
        // Écran précédent resté ouvert : son bouton retour « Réglages » (jamais la lune, qui met en pause).
        for _ in 0..<4 where app.navigationBars.buttons["Réglages"].exists { app.navigationBars.buttons["Réglages"].tap() }
        for _ in 0..<3 { app.swipeDown(velocity: .fast) }
        sleep(1)
    }

    @discardableResult
    private func openRow(_ title: String) -> Bool {
        let cell = app.staticTexts[title].firstMatch
        let barTop = app.tabBars.firstMatch.exists ? app.tabBars.firstMatch.frame.minY : app.frame.maxY
        for _ in 0..<8 where !(cell.exists && cell.isHittable && cell.frame.maxY < barTop - 8) {
            app.swipeUp(velocity: .slow)
            sleep(1)
        }
        guard cell.exists else {
            XCTFail("Ligne absente : \(title)")
            return false
        }
        cell.tap()
        sleep(2)
        return true
    }

    // MARK: 1. Purify Test : « Se connecter » sans compte (avis 8d5ec90f63da)

    func test1PurityGuestSignInKeepsTheTabBar() {
        let game = env["RECETTE_GAME"]!
        launch("if(!sessionStorage.recette){sessionStorage.recette='1';localStorage.clear();localStorage.setItem('vp_name','Recette');"
               + "localStorage.setItem('vp_install_dismissed','1');location.replace('/?game=\(game)');}")
        let login = webButton("Se connecter")
        XCTAssertTrue(web("Réservé aux comptes connectés").waitForExistence(timeout: 40), "carte « Réservé aux comptes connectés »")
        shot("purete/carte-cadenas")
        XCTAssertFalse(app.tabBars.firstMatch.isHittable, "partie en plein écran : barre cachée")
        tapWeb(login, "bouton « Se connecter » de la partie")
        sleep(2)
        shot("purete/apres-se-connecter")
        // Avant le correctif : écran vide, barre d'onglets native cachée, il fallait relancer l'app.
        XCTAssertTrue(app.tabBars.firstMatch.waitForExistence(timeout: 10) && app.tabBars.firstMatch.isHittable, "barre d'onglets visible")
        XCTAssertTrue(app.staticTexts["Se connecter"].waitForExistence(timeout: 10), "page de connexion à l'écran")
    }

    // MARK: 2. L'app s'ouvre sur Événements (avis fb95d317cb64)

    func test2AppOpensOnEvents() {
        launch("localStorage.setItem('vp_tab','music');")
        let events = app.tabBars.buttons["Événements"]
        XCTAssertTrue(events.waitForExistence(timeout: 30), "onglet Événements")
        sleep(3)
        shot("ouverture/evenements")
        XCTAssertTrue(events.isSelected, "l'app s'ouvre sur Événements (dernier onglet : Musique)")
    }

    // MARK: 3. Admin : connexion, connexions récentes, « Nouveau compte », groupes

    func test3AdminSettingsAndGroups() {
        launch()
        settingsTab()
        if app.staticTexts["Se connecter"].exists {
            XCTAssertTrue(openRow("Se connecter"))
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
        shot("admin/reglages")

        // Connexions récentes (avis 0abef7ffe7ba)
        settingsTab()
        if openRow("Connexions récentes") {
            let today = app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH \"AUJOURD'HUI\"")).firstMatch
            XCTAssertTrue(today.waitForExistence(timeout: 20), "« AUJOURD'HUI · n » (Admin test vient de se connecter)")
            XCTAssertTrue(app.descendants(matching: .any)["recent-sign-in"].firstMatch.exists, "au moins une connexion récente")
            shot("admin/connexions-recentes")
            app.navigationBars.buttons.firstMatch.tap()
        }

        // « Nouveau compte » (avis 662065a54b22)
        settingsTab()
        if openRow("Notifications") {
            let toggle = app.switches.matching(NSPredicate(format: "label BEGINSWITH 'Nouveau compte'")).firstMatch
            for _ in 0..<12 where !(toggle.exists && toggle.isHittable) { app.swipeUp(velocity: .slow) }
            XCTAssertTrue(toggle.exists, "interrupteur « Nouveau compte »")
            shot("admin/notif-nouveau-compte")
            if toggle.exists {
                let before = toggle.value as? String
                (toggle.switches.firstMatch.exists ? toggle.switches.firstMatch : toggle).tap()
                sleep(2)
                XCTAssertNotEqual(toggle.value as? String, before, "« Nouveau compte » se coupe")
                shot("admin/notif-nouveau-compte-coupe")
                (toggle.switches.firstMatch.exists ? toggle.switches.firstMatch : toggle).tap()
                sleep(2)
                XCTAssertEqual(toggle.value as? String, before, "« Nouveau compte » se rallume")
            }
            app.navigationBars.buttons.firstMatch.tap()
        }

        // Groupes : créer, la page s'ouvre avec « Inviter avec un lien » (avis e39b166040ea)
        settingsTab()
        if openRow("Groupes") {
            let name = app.textFields["new-group-name"]
            XCTAssertTrue(name.waitForExistence(timeout: 15), "champ « Nom du nouveau groupe »")
            name.tap()
            app.typeText("Recette 13.11")
            app.buttons["new-group-create"].tap()
            let invite = app.buttons["group-quick-invite"]
            XCTAssertTrue(invite.waitForExistence(timeout: 25), "le groupe s'ouvre avec « Inviter avec un lien » en haut")
            XCTAssertTrue(app.navigationBars["Recette 13.11"].exists, "page du nouveau groupe")
            shot("groupe/cree-inviter-avec-un-lien")
            invite.tap()
            sleep(3)
            shot("groupe/feuille-de-partage")
            let close = app.buttons.matching(NSPredicate(format: "label IN {'Fermer', 'Close'}")).firstMatch
            if close.exists { close.tap() } else { app.swipeDown() }
            sleep(2)
            let delete = app.buttons["Supprimer le groupe"]
            for _ in 0..<8 where !(delete.exists && delete.isHittable) { app.swipeUp(velocity: .slow) }
            if delete.exists {
                delete.tap()
                let confirm = app.buttons.matching(NSPredicate(format: "label == 'Supprimer'")).firstMatch
                if confirm.waitForExistence(timeout: 5) { confirm.tap() }
                sleep(2)
            }
        }
    }

    // MARK: 4. Fiche : bandeau des notifications, carte Invités repliée, covoiturage

    func test4EventBannerGuestsAndCarpool() {
        launch(openEvents("/event/\(env["RECETTE_CARPOOL"]!)"))
        XCTAssertTrue(web("Recette covoiturage").waitForExistence(timeout: 60), "fiche « Recette covoiturage »")
        sleep(2)
        // Bandeau en haut (avis c77d117ab172) : notifications pas encore autorisées sur ce simulateur.
        let banner = web("Ne rate rien de cet événement")
        if banner.waitForExistence(timeout: 15) {
            shot("fiche/bandeau-notifications")
            tapWeb(webButton("Activer les notifications"), "« Activer les notifications »")
            // L'alerte d'iOS (« Party » souhaite vous envoyer des notifications) : « Autoriser ».
            let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")
            let allow = springboard.buttons.matching(NSPredicate(format: "label IN {'Autoriser', 'Allow'}")).firstMatch
            if allow.waitForExistence(timeout: 8) {
                shot("fiche/alerte-ios")
                allow.tap()
            }
            app.activate()
            sleep(4)
            shot("fiche/apres-activer")
            XCTAssertFalse(web("Ne rate rien de cet événement").exists, "le bandeau disparaît une fois activées")
        } else {
            shot("fiche/sans-bandeau")
        }

        // Ordre : description, « Tu viens ? », puis Invités repliée (12.11)
        XCTAssertTrue(reveal(app.webViews.buttons["Présent"].firstMatch), "réponse « Présent / Peut-être / Absent »")
        let detail = webButton("Voir le détail des invités")
        XCTAssertTrue(reveal(detail), "carte Invités repliée : « Voir le détail »")
        shot("fiche/invites-repliee")
        detail.tap()
        sleep(1)
        XCTAssertTrue(webButton("Réduire la liste des invités").waitForExistence(timeout: 5), "carte dépliée")
        shot("fiche/invites-depliee")
        webButton("Réduire la liste des invités").tap()

        // Covoiturage (avis 34d5c07f2e56)
        XCTAssertTrue(reveal(web("Covoiturage")), "carte « 🚗 Covoiturage »")
        shot("covoiturage/carte")
        tapWeb(webButton("🚗 Je conduis"), "« Je conduis »")
        tapWeb(webButton("Une place de moins"), "« − »")
        let city = app.webViews.textFields.matching(NSPredicate(format: "label CONTAINS 'Ville de départ'")).firstMatch
        XCTAssertTrue(reveal(city), "champ « Ville de départ »")
        city.tap()
        app.typeText("Sion")
        shot("covoiturage/formulaire")
        tapWeb(webButton("Proposer mes places"), "« Proposer mes places »")
        XCTAssertTrue(web("Tu conduis depuis Sion · 2 places libres").waitForExistence(timeout: 20), "« Tu conduis depuis Sion · 2 places libres »")
        shot("covoiturage/je-conduis")
        tapWeb(webButton("Je ne conduis plus"), "« Je ne conduis plus »")
        XCTAssertTrue(webButton("🚗 Je conduis").waitForExistence(timeout: 15), "retour au choix")
        shot("covoiturage/plus-conducteur")
    }

    // MARK: 5. Sondage de dates : créé le / modifié le (avis d432d548d649)

    func test5PollDates() {
        launch(openEvents("/event/\(env["RECETTE_POLL"]!)"))
        let line = web("Sondage créé le")
        XCTAssertTrue(line.waitForExistence(timeout: 60), "« Sondage créé le … »")
        reveal(line)
        shot("sondage/cree-le")
    }

    // MARK: 6. Étape 2 « Des groupes » : Membres + un autre groupe, puis publier (avis 8eb031acd60f)

    func test6StepTwoSeveralGroups() {
        launch(openEvents("/event/\(env["RECETTE_DRAFT"]!)/invite"))
        let groups = webButton("👥 Des groupes")
        XCTAssertTrue(groups.waitForExistence(timeout: 60), "carte « 👥 Des groupes »")
        shot("etape2/choix")
        tapWeb(groups, "« Des groupes »")
        let vip = webButton("✓ 👥 Membres Vendredi Party")
        XCTAssertTrue(reveal(vip), "Membres Vendredi Party coché d'office")
        let bots = app.webViews.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Bots ·'")).firstMatch
        tapWeb(bots, "puce « Bots »")
        let publish = app.webViews.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Publier pour « Membres Vendredi Party », « Bots »'")).firstMatch
        XCTAssertTrue(reveal(publish), "« Publier pour « Membres Vendredi Party », « Bots » »")
        shot("etape2/membres-et-bots")
        publish.tap()
        XCTAssertTrue(web("C’est en ligne").waitForExistence(timeout: 30), "publié : « C’est en ligne ! »")
        shot("etape2/en-ligne")
    }

    // MARK: 7. Salle de jeux : « ? » des règles en haut à droite (avis 1745531cf33c)

    func test7RoomRules() {
        launch("localStorage.removeItem('vp_game');localStorage.removeItem('vp_room');")
        let games = app.tabBars.buttons["Jeux"]
        XCTAssertTrue(games.waitForExistence(timeout: 30), "onglet Jeux")
        games.tap()
        sleep(2)
        tapWeb(webButton("Ouvrir une salle"), "« Ouvrir une salle »")
        let help = app.webViews.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Règles : '")).firstMatch
        XCTAssertTrue(reveal(help, timeout: 30), "« ? » sur les jeux de la salle")
        shot("salle/tuiles")
        let name = help.label.replacingOccurrences(of: "Règles : ", with: "")
        help.tap()
        sleep(2)
        XCTAssertTrue(web("Règles du jeu").waitForExistence(timeout: 10), "fiche des règles de \(name)")
        shot("salle/regles")
        let ok = webButton("J'ai compris")
        if ok.exists { ok.tap() }
    }
}

import XCTest

/// Recette RÉELLE des nouveautés du 15.11.2026 dans le simulateur (configuration Release, comme l'App Store) : serveur
/// Party local branché sur la base de TEST, réglages de prod (Invitations v2, Zicou éteint, CGU exigées).
/// - Jeux : accueil « Salle de jeux » (Créer une salle / ou rejoindre + code), « 🧠 Jeux solo », rejoindre la salle d'un
///   2e téléphone (navigateur WebKit piloté par fichiers dans R15_DIR : r1.txt, go_likely, change, r2.txt, lea_in, stop),
///   puis « 🎮 Changer de jeu » de l'animateur (alerte d'iOS).
/// - Paiement (invité Guest A) : « Paiement en ligne » et « Payer avec Revolut » ouvrent Safari (jamais une page coincée
///   dans l'app), retour dans Party, fenêtre de paiement (✕, glisser vers le bas, sous la barre d'état), « J'ai payé ».
/// - Organisateur (Admin test) : « Reçu ✓ » ; sondage de dates : fixer la date, modifier, repasser en « Date à définir »
///   retrouve les dates et leurs votes.
/// Lancé à la demande (données préparées avant, comptes de test à code fixe, aucun SMS) :
///   TEST_RUNNER_R15_DIR=… TEST_RUNNER_R15_ONLINE=… TEST_RUNNER_R15_REVOLUT=… TEST_RUNNER_R15_ONSITE=… TEST_RUNNER_R15_POLL=…
///   xcodebuild test -configuration Release ENABLE_TESTABILITY=YES PARTY_SWIFT_CONDITIONS=E2E_HOOKS
///   PARTY_BASE_URL=http://127.0.0.1:<port> -only-testing:PartyUITests/Recette1511UITests
final class Recette1511UITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment
    private var dir: URL!
    private var app: XCUIApplication!
    private var step = 0

    override func setUpWithError() throws {
        guard let path = env["R15_DIR"] else { throw XCTSkip("Recette à la demande (R15_DIR)") }
        dir = URL(fileURLWithPath: path)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        continueAfterFailure = true
    }

    // MARK: Outils

    private func shot(_ name: String, screen: Bool = false) {
        step += 1
        let png = screen ? XCUIScreen.main.screenshot().pngRepresentation : app.screenshot().pngRepresentation
        try? png.write(to: dir.appendingPathComponent(String(format: "%@-%02d.png", name, step)))
    }

    private func launch(_ js: String = "") {
        app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_JS"] = "localStorage.setItem('vp_install_dismissed','1');" + js
        app.launch()
    }

    /// Ouvre une fiche ; sous forte charge, la vue web d'un relancement reste parfois vide : un second lancement.
    private func launchEvent(_ id: String, _ title: String) {
        for attempt in 0..<2 {
            if attempt > 0 { shot("relance-vide"); app.terminate() }
            launch(openEvents("/event/\(id)"))
            if web(title).waitForExistence(timeout: 90) { return }
        }
        XCTFail("fiche « \(title) »")
    }

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
        let bar = app.tabBars.firstMatch.exists && app.tabBars.firstMatch.isHittable ? app.tabBars.firstMatch.frame.minY : app.frame.maxY
        return element.frame.minY >= view.minY && element.frame.maxY <= min(view.maxY, bar)
    }

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

    private func waitFile(_ name: String, timeout: TimeInterval = 90) -> String? {
        let url = dir.appendingPathComponent(name)
        let end = Date().addingTimeInterval(timeout)
        while Date() < end {
            if let text = try? String(contentsOf: url, encoding: .utf8) { return text.trimmingCharacters(in: .whitespacesAndNewlines) }
            sleep(1)
        }
        return nil
    }

    private func signal(_ name: String, _ text: String = "1") {
        try? text.write(to: dir.appendingPathComponent(name), atomically: true, encoding: .utf8)
    }

    /// Réglages › « Se connecter » avec un numéro de test (code fixe 123456, aucun SMS).
    private func signIn(_ phone: String, as name: String) {
        let tab = app.tabBars.buttons.matching(NSPredicate(format: "label IN {'Réglages', 'Se connecter'}")).firstMatch
        XCTAssertTrue(tab.waitForExistence(timeout: 30), "onglet Réglages")
        tab.tap()
        sleep(2)
        if app.staticTexts[name].exists { return }
        // Autre compte resté connecté (le trousseau survit à la désinstallation) : « Se déconnecter » d'abord.
        let out = app.staticTexts["Se déconnecter"].firstMatch
        if !app.staticTexts["Se connecter"].exists {
            for _ in 0..<8 where !(out.exists && out.isHittable) { app.swipeUp(velocity: .slow) }
            if out.exists {
                out.tap()
                let sheet = app.sheets.buttons["Se déconnecter"].firstMatch
                let confirm = sheet.exists ? sheet : app.buttons.matching(identifier: "Se déconnecter").element(boundBy: 1)
                if confirm.waitForExistence(timeout: 5) { confirm.tap() }
                sleep(4)
                for _ in 0..<3 { app.swipeDown(velocity: .fast) }
            }
        }
        let row = app.staticTexts["Se connecter"].firstMatch
        for _ in 0..<6 where !(row.exists && row.isHittable) { app.swipeUp(velocity: .slow) }
        guard row.exists else { return XCTFail("Ligne « Se connecter » absente") }
        row.tap()
        let field = app.textFields["login-phone"]
        XCTAssertTrue(field.waitForExistence(timeout: 10), "champ du numéro")
        field.tap()
        app.typeText(phone)
        app.buttons["login-send"].tap()
        let code = app.textFields["login-code"]
        XCTAssertTrue(code.waitForExistence(timeout: 20), "champ du code")
        code.tap()
        app.typeText("123456")
        XCTAssertTrue(app.staticTexts[name].waitForExistence(timeout: 30), "connecté en \(name)")
    }

    /// Safari (ou l'app du lien) passe au premier plan ; on revient dans Party, comme avec « ◀ Party ».
    private func expectSafariThenBack(_ what: String) {
        let safari = XCUIApplication(bundleIdentifier: "com.apple.mobilesafari")
        let left = safari.wait(for: .runningForeground, timeout: 15)
        XCTAssertTrue(left, "\(what) : le lien s'ouvre dans Safari, hors de Party")
        sleep(3)
        shot("safari-\(what)", screen: true)
        app.activate()
        XCTAssertTrue(app.wait(for: .runningForeground, timeout: 10), "retour dans Party")
        sleep(2)
    }

    /// Onglet Jeux de la barre native, une fois la page chargée (l'app s'ouvre sur Événements, 13.11). Un toucher pendant
    /// le chargement de la page est perdu : on retouche jusqu'à voir l'accueil des Jeux.
    private func openGames(_ mark: XCUIElement) {
        _ = app.webViews.firstMatch.staticTexts.firstMatch.waitForExistence(timeout: 40)
        for attempt in 0..<4 where !mark.exists {
            if attempt > 0 { shot("jeux-onglet-pas-ouvert") }
            app.tabBars.buttons["Jeux"].tap()
            _ = mark.waitForExistence(timeout: 10)
        }
    }

    // MARK: 1. Jeux : accueil, rejoindre la salle d'un autre, changer de jeu

    func test1GamesHomeJoinAndChangeGame() throws {
        launch("localStorage.removeItem('vp_game');localStorage.removeItem('vp_room');localStorage.setItem('vp_name','iPhone');"
               + "localStorage.setItem('vp_tab','games');")
        let games = app.tabBars.buttons["Jeux"]
        XCTAssertTrue(games.waitForExistence(timeout: 90), "onglet Jeux (barre native)")
        let create = webButton("Créer une salle")
        openGames(create)
        XCTAssertTrue(create.waitForExistence(timeout: 30), "« Créer une salle »")
        sleep(2)
        shot("jeux-accueil")
        XCTAssertTrue(web("Salle de jeux").exists, "carte « Salle de jeux »")
        XCTAssertFalse(web("Braquage en miniature").exists, "les jeux à plusieurs ne sont plus sur l'accueil")
        let solo = web("Jeux solo")
        XCTAssertTrue(reveal(solo), "« 🧠 Jeux solo » sous la salle")
        shot("jeux-solo")

        // Code de la salle, clavier ouvert : le champ reste au-dessus du clavier.
        let code = app.webViews.textFields.matching(NSPredicate(format: "label CONTAINS 'Code de la salle'")).firstMatch
        XCTAssertTrue(reveal(code), "champ « Code de la salle »")
        code.tap()
        XCTAssertTrue(app.keyboards.firstMatch.waitForExistence(timeout: 5), "clavier numérique")
        sleep(1)
        shot("jeux-clavier")
        XCTAssertLessThanOrEqual(code.frame.maxY, app.keyboards.firstMatch.frame.minY, "le champ du code n'est pas sous le clavier")

        // Rejoindre la salle de Boby (2e téléphone) avec son code.
        guard let room = waitFile("r1.txt") else { return XCTFail("le 2e téléphone n'a pas créé de salle (r1.txt)") }
        app.typeText(room)
        XCTAssertTrue(web("Boby").waitForExistence(timeout: 20), "dans la salle de Boby")
        let join = webButton("Rejoindre")
        if join.waitForExistence(timeout: 3) { tapWeb(join, "« Rejoindre »") }
        sleep(2)
        shot("jeux-salle-de-boby")
        XCTAssertFalse(app.keyboards.firstMatch.exists, "clavier refermé après le 4e chiffre")

        // Boby lance un jeu : l'iPhone bascule ; pas de « Changer de jeu » pour un participant.
        signal("go_likely")
        XCTAssertTrue(web("Qui est le plus").waitForExistence(timeout: 30), "l'iPhone bascule dans le jeu lancé")
        sleep(3)
        shot("jeux-likely-participant")
        XCTAssertFalse(webButton("🎮 Changer de jeu").exists, "« Changer de jeu » réservé à l'animateur")
        signal("change")
        // Participant : les tuiles sont des boutons de vote (aria-pressed), des « toggles » pour XCUITest.
        let tile = app.webViews.descendants(matching: .any).matching(NSPredicate(format: "label BEGINSWITH 'Qui est le plus'")).firstMatch
        XCTAssertTrue(tile.waitForExistence(timeout: 30), "retour à la salle (tuiles des jeux)")
        sleep(2)
        shot("jeux-retour-salle-participant")
        app.terminate()

        // L'iPhone crée sa salle ; Léa (2e téléphone) la rejoint ; l'iPhone lance un jeu puis « Changer de jeu ».
        launch("localStorage.removeItem('vp_game');localStorage.removeItem('vp_room');localStorage.setItem('vp_tab','games');")
        XCTAssertTrue(app.tabBars.buttons["Jeux"].waitForExistence(timeout: 30))
        openGames(webButton("Créer une salle"))
        tapWeb(webButton("Créer une salle"), "« Créer une salle »")
        let codeText = app.webViews.staticTexts.matching(NSPredicate(format: "label MATCHES '^[0-9]{4}$'")).firstMatch
        XCTAssertTrue(codeText.waitForExistence(timeout: 20), "code de la salle affiché")
        signal("r2.txt", codeText.label)
        XCTAssertNotNil(waitFile("lea_in", timeout: 60), "Léa a rejoint")
        XCTAssertTrue(web("Lea").waitForExistence(timeout: 20), "Léa dans la salle de l'iPhone")
        shot("jeux-ma-salle")
        let mine = app.webViews.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Qui est le plus'")).firstMatch
        tapWeb(mine, "tuile « Qui est le plus… ? »")
        let launchIt = webButton("▶ Lancer pour toute la salle")
        XCTAssertTrue(launchIt.waitForExistence(timeout: 10), "feuille « Lancer pour toute la salle »")
        shot("jeux-feuille-lancer")
        launchIt.tap()
        let change = webButton("🎮 Changer de jeu")
        XCTAssertTrue(reveal(change, timeout: 30), "« 🎮 Changer de jeu » visible pour l'animateur")
        shot("jeux-changer-de-jeu")
        change.tap()
        let alert = app.alerts.firstMatch
        XCTAssertTrue(alert.waitForExistence(timeout: 8), "alerte d'iOS « Changer de jeu ? »")
        shot("jeux-alerte")
        alert.buttons["OK"].tap()
        XCTAssertTrue(app.webViews.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Qui est le plus'")).firstMatch
            .waitForExistence(timeout: 20), "retour à la salle pour l'animateur")
        XCTAssertFalse(webButton("🎮 Changer de jeu").exists, "plus de « Changer de jeu » dans la salle")
        sleep(1)
        shot("jeux-retour-salle-animateur")
        signal("stop")
    }

    // MARK: 2. Paiement, côté invité (Guest A)

    func test2GuestPays() throws {
        let online = try XCTUnwrap(env["R15_ONLINE"]), revolut = try XCTUnwrap(env["R15_REVOLUT"]), onsite = try XCTUnwrap(env["R15_ONSITE"])
        launch("localStorage.setItem('vp_tab','events');")
        signIn("0790000001", as: "Guest A")
        app.terminate()

        // « Paiement en ligne » : le bouton ouvre la billetterie dans Safari.
        launchEvent(online, "Recette paiement en ligne")
        XCTAssertTrue(reveal(web("Paiement en ligne")), "« Paiement en ligne » sous le prix")
        let payOnline = webButton("Payer en ligne · 20 CHF")
        XCTAssertTrue(reveal(payOnline), "« Payer en ligne · 20 CHF ↗ »")
        shot("paiement-en-ligne")
        payOnline.tap()
        expectSafariThenBack("billetterie")
        XCTAssertTrue(web("Recette paiement en ligne").exists, "Party garde la fiche au retour")
        shot("paiement-retour")
        tapWeb(webButton("J’ai payé"), "« J’ai payé »")
        XCTAssertTrue(web("Payé · en attente de confirmation").waitForExistence(timeout: 15), "en attente de confirmation")
        shot("paiement-en-ligne-note")
        app.terminate()

        // « On me paie » avec un lien Revolut : la fenêtre de paiement (✕, glisser, barre d'état) puis Revolut dans Safari.
        launchEvent(revolut, "Recette paiement Revolut")
        let open = app.webViews.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Payer ' AND label CONTAINS '12 CHF'")).firstMatch
        tapWeb(open, "« Payer … · 12 CHF »")
        let close = webButton("Fermer la fenêtre")
        XCTAssertTrue(close.waitForExistence(timeout: 15), "fenêtre de paiement ouverte (✕)")
        sleep(1)
        shot("paiement-fenetre")
        let statusBar = app.windows.firstMatch.frame.minY + 44
        XCTAssertGreaterThanOrEqual(close.frame.minY, statusBar, "le ✕ n'est pas sous la barre d'état")
        XCTAssertTrue(close.isHittable, "✕ touchable")
        close.tap()
        sleep(1)
        XCTAssertFalse(webButton("Fermer la fenêtre").exists, "✕ ferme la fenêtre")
        // Glisser vers le bas depuis la poignée ferme.
        tapWeb(open, "« Payer … · 12 CHF »")
        XCTAssertTrue(close.waitForExistence(timeout: 15))
        let grab = close.coordinate(withNormalizedOffset: CGVector(dx: -3, dy: 0.5))
        grab.press(forDuration: 0.1, thenDragTo: grab.withOffset(CGVector(dx: 0, dy: 450)))
        sleep(2)
        shot("paiement-glisse")
        XCTAssertFalse(webButton("Fermer la fenêtre").exists, "glisser vers le bas ferme la fenêtre")
        tapWeb(open, "« Payer … · 12 CHF »")
        let revolutButton = webButton("Payer avec Revolut")
        XCTAssertTrue(revolutButton.waitForExistence(timeout: 15), "« Payer avec Revolut » en tête")
        // Lien Revolut de l'événement + autre Revolut dans le profil de l'organisateur : un seul bouton (16.11).
        XCTAssertEqual(app.webViews.buttons.matching(NSPredicate(format: "label == 'Payer avec Revolut'")).count, 1,
                       "un seul « Payer avec Revolut » (celui de l'événement)")
        revolutButton.tap()
        expectSafariThenBack("revolut")
        shot("paiement-revolut-retour")
        tapWeb(webButton("J’ai payé"), "« J’ai payé » (fenêtre)")
        XCTAssertTrue(web("Payé · en attente de confirmation").waitForExistence(timeout: 15), "en attente de confirmation")
        shot("paiement-revolut-note")
        app.terminate()

        // Sur place : rien à payer ni à noter.
        launchEvent(onsite, "Recette paiement sur place")
        let line = web("à payer sur place")
        XCTAssertTrue(line.waitForExistence(timeout: 60), "« 📍 10 CHF · à payer sur place »")
        reveal(line)
        shot("paiement-sur-place")
        XCTAssertFalse(webButton("J’ai payé").exists, "pas de « J’ai payé » sur place")
    }

    // MARK: 3. Organisateur (Admin test) : « Reçu ✓ », puis le sondage de dates garde ses votes

    func test3OrganizerConfirmsAndPollKeepsVotes() throws {
        let online = try XCTUnwrap(env["R15_ONLINE"]), poll = try XCTUnwrap(env["R15_POLL"])
        launch("localStorage.setItem('vp_tab','events');")
        signIn("0790000004", as: "Admin test")
        app.terminate()

        launchEvent(online, "Recette paiement en ligne")
        let received = webButton("Reçu ✓")
        // Relancé après un premier passage : déjà confirmé (« ✓ … payé »).
        if reveal(received, timeout: 30) {
            shot("organisateur-a-confirmer")
            received.tap()
            sleep(3)
            XCTAssertFalse(webButton("Reçu ✓").exists, "paiement confirmé")
        }
        XCTAssertTrue(reveal(web("1 / 1 payé")), "« 1 / 1 payé »")
        shot("organisateur-recu")
        app.terminate()

        // Sondage : 3 dates votées ; fixer la 1re, modifier l'événement, repasser en « Date à définir ».
        launchEvent(poll, "Recette sondage votes")
        let fix = webButton("Fixer cette date")
        if reveal(fix, timeout: 30) {   // relancé après un premier passage : date déjà fixée
            shot("sondage-votes")
            fix.tap()
            sleep(4)
        }
        shot("sondage-date-fixee")
        // « Modifier » tout court (le ✨ juste à côté s'appelle « Modifier avec l'IA »).
        let modify = app.webViews.buttons.matching(NSPredicate(format: "label == 'Modifier'")).firstMatch
        tapWeb(modify, "« Modifier »")
        // « Enregistrer » tout court (« Enregistrer comme modèle » est juste au-dessus).
        let save = app.webViews.buttons.matching(NSPredicate(format: "label == 'Enregistrer'")).firstMatch
        XCTAssertTrue(reveal(save, timeout: 20), "formulaire « Enregistrer »")
        shot("sondage-formulaire-fixe")
        save.tap()
        sleep(4)
        shot("sondage-enregistre-fixe")
        tapWeb(modify, "« Modifier » (2e fois)")
        let advanced = app.webViews.descendants(matching: .any).matching(NSPredicate(format: "label == 'Avancé'")).firstMatch
        if advanced.waitForExistence(timeout: 5) { tapWeb(advanced, "onglet « Avancé »") }
        let toPoll = app.webViews.descendants(matching: .any)
            .matching(NSPredicate(format: "label == 'Date à définir' AND elementType != %d", XCUIElement.ElementType.staticText.rawValue)).firstMatch
        tapWeb(toPoll, "« Date à définir »")
        let slot = app.webViews.descendants(matching: .any).matching(NSPredicate(format: "label BEGINSWITH 'Créneau 3'")).firstMatch
        XCTAssertTrue(reveal(slot), "les 3 créneaux reviennent dans le formulaire")
        shot("sondage-formulaire-retour")
        tapWeb(save, "« Enregistrer » (sondage)")
        sleep(4)
        let fixAgain = webButton("Fixer cette date")
        XCTAssertTrue(reveal(fixAgain, timeout: 30), "le sondage est de retour")
        shot("sondage-votes-retrouves")
    }
}

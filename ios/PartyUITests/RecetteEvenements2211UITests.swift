import XCTest

/// Recette RÉELLE des décisions du 22.11.2026 (événements publics, validation, rôle Modérateur), dans le simulateur en
/// configuration Release : serveur Party local branché sur la base de TEST, réglages de la prod (validation obligatoire).
/// Comptes à code fixe : QA Cinq (0790000005), QA Six (0790000006, futur Modérateur), Admin test (0790000004).
/// Préparé avant (script de recette) : profils complets, CGU acceptées, « [QA] Sondage 22.11 » (RECETTE_POLL) et
/// « [QA] Payant covoit 22.11 » (RECETTE_PAY, QA Cinq Présent), une proposition de QA Cinq en attente (RECETTE_PENDING2).
/// Chaque test se lance seul, dans l'ordre (l'état passe par la base) :
///   TEST_RUNNER_RECETTE_DIR=… TEST_RUNNER_RECETTE_TITLE=… [TEST_RUNNER_RECETTE_EVENT=…] … xcodebuild test-without-building
///   -configuration Release -only-testing:PartyUITests/RecetteEvenements2211UITests/<test>
final class RecetteEvenements2211UITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment
    private var dir: URL!
    private var app: XCUIApplication!
    /// Créateur de l'événement : QA Cinq par défaut ; RECETTE_CREATOR=0790000006:QA Six si le code fixe de 0790000005 manque.
    private var creatorPhone: String { String((env["RECETTE_CREATOR"] ?? "0790000005:QA Cinq").split(separator: ":")[0]) }
    private var creatorName: String { String((env["RECETTE_CREATOR"] ?? "0790000005:QA Cinq").split(separator: ":")[1]) }

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

    // MARK: Outils

    private func shot(_ name: String) {
        try? app.screenshot().pngRepresentation.write(to: dir.appendingPathComponent("ev2211-\(name).png"))
    }

    private func launch(_ js: String = "") {
        app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_JS"] = "localStorage.setItem('vp_install_dismissed','1');" + js
        app.launch()
    }

    /// Ouvre une page du module Événements (dans la page Party), une fois la page chargée.
    private func launchEvents(_ path: String) {
        launch("addEventListener('load',()=>setTimeout(()=>PartyEvents.open('/events\(path)'),1500));")
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
        for _ in 0..<12 where !visible(element) { app.webViews.firstMatch.swipeUp(velocity: .slow) }
        for _ in 0..<12 where !visible(element) { app.webViews.firstMatch.swipeDown(velocity: .slow) }
        sleep(1)
        return visible(element)
    }

    private func tapWeb(_ element: XCUIElement, _ what: String) {
        XCTAssertTrue(reveal(element), "\(what) introuvable")
        if element.exists { element.tap() }
        sleep(2)
    }

    /// Réglages › « Se connecter » avec un numéro de test (code fixe 123456) ; déconnecte d'abord un autre compte.
    private func signIn(_ phone: String, as name: String) {
        let tab = app.tabBars.buttons.matching(NSPredicate(format: "label IN {'Réglages', 'Se connecter'}")).firstMatch
        XCTAssertTrue(tab.waitForExistence(timeout: 40), "onglet Réglages")
        tab.tap()
        sleep(3)
        shot("connexion-\(phone)-reglages")
        if app.staticTexts[name].exists { return }
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
        for _ in 0..<3 { app.swipeDown(velocity: .fast) }
        _ = row.waitForExistence(timeout: 20)
        for _ in 0..<6 where !(row.exists && row.isHittable) { app.swipeUp(velocity: .slow) }
        if !row.exists { shot("connexion-\(phone)-sans-ligne") }
        guard row.exists else { return XCTFail("Ligne « Se connecter » absente") }
        row.tap()
        let field = app.textFields["login-phone"]
        XCTAssertTrue(field.waitForExistence(timeout: 10), "champ du numéro")
        field.tap()
        app.typeText(phone)
        app.sendLoginCode()
        let code = app.textFields["login-code"]
        XCTAssertTrue(code.waitForExistence(timeout: 20), "champ du code")
        code.tap()
        app.typeText("123456")
        if !app.staticTexts[name].waitForExistence(timeout: 40) { shot("connexion-\(phone)-echec") }
        XCTAssertTrue(app.staticTexts[name].waitForExistence(timeout: 40), "connecté en \(name)")
    }

    /// Réglages › Administration du groupe (natif).
    private func openGroupAdmin() {
        app.tabBars.buttons["Réglages"].tap()
        let row = app.staticTexts["Administration du groupe"].firstMatch
        for _ in 0..<8 where !(row.exists && row.isHittable) { app.swipeUp(velocity: .slow) }
        XCTAssertTrue(row.waitForExistence(timeout: 10), "ligne « Administration du groupe »")
        row.tap()
        XCTAssertTrue(app.navigationBars["Administration"].waitForExistence(timeout: 20), "écran Administration")
        sleep(3)
    }

    private func encoded(_ s: String) -> String {
        s.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? s
    }

    // MARK: 0. Guest : peut-il proposer ?

    func test0GuestProposes() {
        launch()
        signIn(creatorPhone, as: creatorName)
        app.terminate()
        launchEvents("/event/new")
        sleep(8)
        shot("00-guest-nouvel-evenement")
        let refused = web("Tu ne peux pas proposer")
        try? "refuse=\(refused.exists)".write(to: dir.appendingPathComponent("test0.txt"), atomically: true, encoding: .utf8)
    }

    // MARK: 1–2. Proposer un événement public (avertissement, tag, en attente)

    func test1ProposePublicEvent() throws {
        let title = try XCTUnwrap(env["RECETTE_TITLE"])
        launch()
        signIn(creatorPhone, as: creatorName)
        app.terminate()
        launchEvents("/event/new?title=\(encoded(title))&start=\(encoded("2026-12-19T19:00:00+01:00"))")
        let send = webButton("Envoyer pour validation")
        XCTAssertTrue(send.waitForExistence(timeout: 60), "formulaire : « Envoyer pour validation »")
        sleep(2)
        shot("01-formulaire-public")
        // « Public » choisi par défaut ; la carte de validation le dit avant d'envoyer (PUBLIC_REVIEW).
        let review = web("Ils peuvent le refuser")
        XCTAssertTrue(reveal(review), "avertissement PUBLIC_REVIEW visible")
        XCTAssertTrue(web("modifier ses informations ou le retirer").exists, "modifier / retirer dit")
        shot("02-avertissement-validation")
        let publicChoice = web("Public + lien public")
        if reveal(publicChoice, timeout: 5) { shot("03-choix-public") }

        // Tag : mode Avancé, puis la puce « #bar ».
        let advanced = app.webViews.descendants(matching: .any).matching(NSPredicate(format: "label == 'Avancé'")).firstMatch
        tapWeb(advanced, "segment « Avancé »")
        let tag = web("#bar")
        XCTAssertTrue(reveal(tag), "puce de tag « #bar »")
        shot("04-tags-proposes")
        if tag.exists { tag.tap(); sleep(1) }
        shot("05-tag-choisi")

        tapWeb(send, "« Envoyer pour validation »")
        sleep(4)
        let sent = web("Envoyé pour validation")
        let badge = web("En attente de validation")
        XCTAssertTrue(sent.waitForExistence(timeout: 30) || badge.exists, "en attente après envoi")
        shot("06-envoye-en-attente")
        let shownTag = web("#bar")
        if reveal(shownTag, timeout: 10) { shot("07-fiche-tag") }
        XCTAssertTrue(shownTag.exists, "tag « #bar » sur la fiche")
    }

    // MARK: 3. Admin valide ; le créateur modifie

    func test2AdminApproves() throws {
        let title = try XCTUnwrap(env["RECETTE_TITLE"])
        launch()
        signIn("0790000004", as: "Admin test")
        openGroupAdmin()
        let item = app.staticTexts[title]
        for _ in 0..<8 where !(item.exists && item.isHittable) { app.swipeUp(velocity: .slow) }
        XCTAssertTrue(item.waitForExistence(timeout: 20), "la proposition dans « Propositions à valider »")
        shot("10-admin-propositions")
        let cell = app.cells.containing(NSPredicate(format: "label == %@", title)).firstMatch
        let approve = cell.exists ? cell.buttons["Approuver"] : app.buttons["Approuver"].firstMatch
        XCTAssertTrue(approve.exists, "Approuver")
        approve.tap()
        sleep(4)
        XCTAssertFalse(app.staticTexts[title].exists, "la proposition a quitté la liste")
        shot("11-admin-approuve")
    }

    func test3CreatorEdits() throws {
        let event = try XCTUnwrap(env["RECETTE_EVENT"])
        launch()
        signIn(creatorPhone, as: creatorName)
        app.terminate()
        launchEvents("/event/\(event)/edit")
        let save = app.webViews.buttons.matching(NSPredicate(format: "label == 'Enregistrer'")).firstMatch
        XCTAssertTrue(save.waitForExistence(timeout: 60), "formulaire de modification")
        sleep(2)
        shot("20-modifier-formulaire")
        let warn = web("ta modification repasse en validation")
        let warned = reveal(warn, timeout: 5)
        shot("21-modifier-avertissement-\(warned ? "oui" : "non")")
        // Change la description.
        let desc = app.webViews.textViews.firstMatch.exists ? app.webViews.textViews.firstMatch
            : app.webViews.descendants(matching: .any).matching(NSPredicate(format: "label == 'Description'")).firstMatch
        if reveal(desc, timeout: 5) {
            desc.tap()
            app.typeText(" Modifiée par la recette.")
        }
        tapWeb(save, "« Enregistrer »")
        sleep(5)
        shot("22-apres-modification")
        try? "warned=\(warned)\npending_badge=\(web("En attente de validation").exists)".write(
            to: dir.appendingPathComponent("test3.txt"), atomically: true, encoding: .utf8)
    }

    // MARK: 4. Rôle Modérateur

    func test4AdminMakesModerator() {
        launch()
        signIn("0790000004", as: "Admin test")
        openGroupAdmin()
        if env["RECETTE_SKIP_ROLE"] == nil {
        let members = app.staticTexts["Membres"].firstMatch
        for _ in 0..<6 where !(members.exists && members.isHittable) { app.swipeUp(velocity: .slow) }
        members.tap()
        XCTAssertTrue(app.navigationBars["Membres"].waitForExistence(timeout: 20), "Membres")
        sleep(3)
        let search = app.searchFields.firstMatch
        if !search.exists { app.swipeDown(velocity: .slow) }
        XCTAssertTrue(search.waitForExistence(timeout: 5), "recherche")
        search.tap()
        app.typeText("QA Six\n")
        sleep(3)
        // Résultats sous « D'où viennent les inscrits » : on descend jusqu'à la ligne.
        let person = app.buttons.matching(NSPredicate(format: "label CONTAINS 'QA Six'")).firstMatch
        for _ in 0..<8 where !(person.exists && person.isHittable) { app.swipeUp(velocity: .slow) }
        XCTAssertTrue(person.waitForExistence(timeout: 10), "QA Six trouvé")
        shot("30-membres-qa-six")
        person.tap()
        sleep(3)
        let moderator = app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Modérateur'")).firstMatch
        for _ in 0..<4 where !(moderator.exists && moderator.isHittable) { app.swipeUp(velocity: .slow) }
        XCTAssertTrue(moderator.exists, "choix « Modérateur » dans Rôle")
        shot("31-fiche-roles")
        moderator.tap()
        sleep(4)
        XCTAssertTrue(moderator.isSelected, "Modérateur coché")
        shot("32-qa-six-moderateur")
        }

        // Rôles et droits : ordre et nouveaux droits.
        app.terminate()
        launch()
        signIn("0790000004", as: "Admin test")
        openGroupAdmin()
        let roles = app.staticTexts["Rôles et droits"].firstMatch
        for _ in 0..<6 where !(roles.exists && roles.isHittable) { app.swipeUp(velocity: .slow) }
        roles.tap()
        XCTAssertTrue(app.navigationBars["Rôles et droits"].waitForExistence(timeout: 20), "Rôles et droits")
        sleep(3)
        shot("33-roles-ordre")
        func row(_ name: String) -> XCUIElement {
            app.descendants(matching: .any).matching(NSPredicate(format: "label BEGINSWITH %@", name + ",")).firstMatch
        }
        let org = row("Organisateur"), mod = row("Modérateur"), co = row("Co-admin")
        XCTAssertTrue(org.exists && mod.exists && co.exists, "les trois rôles")
        if org.exists && mod.exists && co.exists {
            XCTAssertLessThan(co.frame.minY, mod.frame.minY, "Co-admin au-dessus de Modérateur")
            XCTAssertLessThan(mod.frame.minY, org.frame.minY, "Modérateur au-dessus d'Organisateur")
        }
        try? "org=\(org.frame.minY) mod=\(mod.frame.minY) co=\(co.frame.minY)".write(
            to: dir.appendingPathComponent("test4.txt"), atomically: true, encoding: .utf8)
        // Co-admin : les deux nouveaux droits, cochés.
        co.tap()
        sleep(3)
        for name in ["Modifier les événements des autres", "Retirer / annuler les événements des autres"] {
            let sw = app.switches.matching(NSPredicate(format: "label CONTAINS %@", name)).firstMatch
            for _ in 0..<15 where !(sw.exists && sw.isHittable) { app.swipeUp(velocity: .slow) }
            XCTAssertTrue(sw.exists, "droit « \(name) »")
            XCTAssertEqual(sw.value as? String, "1", "« \(name) » coché pour Co-admin")
            shot("34-coadmin-\(name.prefix(8).replacingOccurrences(of: " ", with: "-").replacingOccurrences(of: "/", with: ""))")
        }
        app.navigationBars.buttons.firstMatch.tap(); sleep(2)
        // Modérateur : ces deux droits décochés.
        mod.tap()
        sleep(3)
        shot("35-moderateur-droits-haut")
        let edit = app.switches.matching(NSPredicate(format: "label CONTAINS 'Modifier les événements des autres'")).firstMatch
        for _ in 0..<15 where !(edit.exists && edit.isHittable) { app.swipeUp(velocity: .slow) }
        if edit.exists { XCTAssertEqual(edit.value as? String, "0", "Modérateur sans « Modifier les événements des autres »") }
        shot("36-moderateur-droits-evenements")
    }

    // MARK: 5. Le Modérateur valide

    func test5ModeratorApproves() throws {
        let title = try XCTUnwrap(env["RECETTE_TITLE2"])
        launch()
        signIn("0790000006", as: "QA Six")
        sleep(2)
        shot("40-moderateur-reglages")
        openGroupAdmin()
        shot("41-moderateur-administration")
        let item = app.staticTexts[title]
        for _ in 0..<8 where !(item.exists && item.isHittable) { app.swipeUp(velocity: .slow) }
        XCTAssertTrue(item.waitForExistence(timeout: 20), "proposition de QA Cinq visible du Modérateur")
        shot("42-moderateur-proposition")
        let cell = app.cells.containing(NSPredicate(format: "label == %@", title)).firstMatch
        let approve = cell.exists ? cell.buttons["Approuver"] : app.buttons["Approuver"].firstMatch
        if approve.exists { approve.tap() }
        sleep(4)
        XCTAssertFalse(app.staticTexts[title].exists, "validée par le Modérateur")
        shot("43-moderateur-approuve")
        let reports = app.descendants(matching: .any)["admin-reports"]
        for _ in 0..<8 where !(reports.exists && reports.isHittable) { app.swipeUp(velocity: .slow) }
        XCTAssertTrue(reports.exists, "ligne Signalements")
        shot("44-moderateur-gerer")
        XCTAssertTrue(app.staticTexts["Demandes d'adhésion"].exists || app.staticTexts["Demandes d’adhésion"].exists
                      || app.staticTexts["DEMANDES D'ADHÉSION"].exists, "Demandes d'adhésion (nouveaux comptes)")
        if reports.exists {
            reports.tap()
            sleep(4)
            shot("45-moderateur-signalements")
        }
    }

    // MARK: 6. Organisateur : Fixer cette date, covoiturage, A payé

    func test6OrganizerTools() throws {
        let poll = try XCTUnwrap(env["RECETTE_POLL"]), pay = try XCTUnwrap(env["RECETTE_PAY"])
        launch()
        signIn("0790000004", as: "Admin test")
        app.terminate()
        launchEvents("/event/\(poll)")
        let fix = webButton("Fixer cette date")
        XCTAssertTrue(reveal(fix, timeout: 60), "« Fixer cette date »")
        shot("50-sondage")
        fix.tap()
        let ask = web("Fixer la soirée au")
        XCTAssertTrue(ask.waitForExistence(timeout: 10), "confirmation demandée")
        sleep(1)
        shot("51-fixer-confirmation")
        let cancel = app.webViews.buttons.matching(NSPredicate(format: "label == 'Annuler'")).firstMatch
        if cancel.exists { cancel.tap() }
        sleep(2)
        XCTAssertFalse(web("Fixer la soirée au").exists, "Annuler ferme sans fixer")
        XCTAssertTrue(webButton("Fixer cette date").exists, "date toujours à définir")
        shot("52-fixer-annule")
        webButton("Fixer cette date").tap()
        XCTAssertTrue(web("Fixer la soirée au").waitForExistence(timeout: 10), "confirmation (2e fois)")
        app.webViews.buttons.matching(NSPredicate(format: "label == 'Confirmer'")).firstMatch.tap()
        sleep(5)
        XCTAssertFalse(webButton("Fixer cette date").exists, "date fixée après Confirmer")
        shot("53-date-fixee")
        app.terminate()

        launchEvents("/event/\(pay)")
        let drive = webButton("🚗 Je conduis")
        XCTAssertTrue(reveal(drive, timeout: 60), "« Je conduis »")
        drive.tap()
        sleep(2)
        let seats = web("Places libres dans ta voiture")
        XCTAssertTrue(reveal(seats), "formulaire du conducteur")
        XCTAssertTrue(app.webViews.staticTexts["4"].exists, "4 places par défaut")
        shot("54-covoiturage-4-places")
        let cancelDrive = app.webViews.buttons.matching(NSPredicate(format: "label == 'Annuler'")).firstMatch
        if cancelDrive.exists { cancelDrive.tap(); sleep(1) }

        let paid = webButton("A payé ✓")
        XCTAssertTrue(reveal(paid, timeout: 20), "« A payé ✓ »")
        shot("55-paiements-avant")
        paid.tap()
        sleep(4)
        let undo = app.webViews.buttons.matching(NSPredicate(format: "label == 'Annuler'")).firstMatch
        XCTAssertTrue(reveal(undo, timeout: 15), "« Annuler » sur la ligne payée")
        XCTAssertTrue(web("1 / 1 payé").exists, "1 / 1 payé")
        shot("56-a-paye")
        undo.tap()
        sleep(4)
        XCTAssertTrue(reveal(webButton("A payé ✓"), timeout: 15), "retour à « A payé ✓ » après Annuler")
        shot("57-paiement-annule")
    }
}

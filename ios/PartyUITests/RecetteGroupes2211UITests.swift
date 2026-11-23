import XCTest

/// Recette RÉELLE des groupes du 22.11 (groupes simples f0e9bf158133, groupes libres, droits des admins), dans le
/// simulateur en configuration Release : serveur Party local branché sur la base de TEST (code SMS fixe), comptes
/// « Guest A » (0790000001), « Guest B » (0790000002) et « Admin test » (0790000004). Une méthode par étape, lancée
/// à part (app réinstallée entre deux) ; les identifiants passent par l'environnement :
///   TEST_RUNNER_RECETTE_DIR=…  TEST_RUNNER_RECETTE_GROUP=<nom du groupe>  TEST_RUNNER_RECETTE_EVENT=<id>
///   TEST_RUNNER_RECETTE_TITLE=<titre de l'événement>
///   xcodebuild test-without-building -configuration Release … -only-testing:PartyUITests/RecetteGroupes2211UITests/test1…
final class RecetteGroupes2211UITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment
    private var dir: URL!
    private var app: XCUIApplication!
    private var group: String { env["RECETTE_GROUP"] ?? "[QA] Bande 2211" }
    private var title: String { env["RECETTE_TITLE"] ?? "[QA] Soirée de la bande 2211" }

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
        sleep(1)
        try? app.screenshot().pngRepresentation.write(to: dir.appendingPathComponent("g2211-\(name).png"))
    }

    private func any(_ predicate: String, _ args: CVarArg...) -> XCUIElement {
        app.descendants(matching: .any).matching(NSPredicate(format: predicate, argumentArray: args)).firstMatch
    }

    private func launch(_ js: String = "") {
        app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_JS"] = "localStorage.setItem('vp_install_dismissed','1');" + js
        app.launch()
    }

    private func signIn(_ phone: String, _ name: String) {
        let tab = app.tabBars.buttons.matching(NSPredicate(format: "label IN {'Réglages', 'Se connecter'}")).firstMatch
        XCTAssertTrue(tab.waitForExistence(timeout: 40), "onglet Réglages")
        tab.tap()
        sleep(2)
        guard app.staticTexts["Se connecter"].exists else { return }
        app.staticTexts["Se connecter"].firstMatch.tap()
        let field = app.textFields["login-phone"]
        XCTAssertTrue(field.waitForExistence(timeout: 10), "champ du numéro")
        field.tap()
        app.typeText(phone)
        app.sendLoginCode()
        let code = app.textFields["login-code"]
        XCTAssertTrue(code.waitForExistence(timeout: 20), "champ du code")
        code.tap()
        app.typeText("123456")
        XCTAssertTrue(app.staticTexts[name].waitForExistence(timeout: 30), "connecté en \(name)")
        sleep(2)
    }

    private func openGroupsList() {
        app.tabBars.buttons["Réglages"].tap()
        let groups = app.buttons["settings-groups"]
        XCTAssertTrue(groups.waitForExistence(timeout: 20), "ligne Réglages › Groupes")
        groups.tap()
        XCTAssertTrue(app.navigationBars["Groupes"].waitForExistence(timeout: 30), "liste native des groupes")
        sleep(3)
    }

    private func scrollTo(_ element: XCUIElement, max: Int = 6) {
        for _ in 0..<max where !(element.exists && element.isHittable && element.frame.maxY < app.frame.height - 110) {
            app.swipeUp(velocity: .slow)
            sleep(1)
        }
    }

    // MARK: 1–3. Guest A : crée le groupe, ajoute Guest B par son numéro, règle « Événements à valider »

    func test1GuestACreatesTheGroupAddsGuestBAndSetsTheRule() {
        launch()
        signIn("0790000001", "Guest A")
        openGroupsList()
        shot("01-A-liste-groupes")

        // 1. Nouveau groupe : nom, emoji, couleur (CGU si demandées).
        app.buttons["groups-new"].tap()
        let name = app.textFields["group-new-name"]
        XCTAssertTrue(name.waitForExistence(timeout: 10), "champ du nom")
        name.tap()
        app.typeText(group)
        if app.buttons["🎸"].exists { app.buttons["🎸"].tap() }
        if app.buttons["Bleu"].exists { app.buttons["Bleu"].tap() }
        shot("02-A-nouveau-groupe")
        app.buttons["group-new-continue"].tap()
        let accept = app.buttons["terms-accept"]
        if accept.waitForExistence(timeout: 6) {
            shot("03-A-cgu")
            accept.tap()
        }
        let search = app.textFields["group-invite-search"]
        XCTAssertTrue(search.waitForExistence(timeout: 30), "étape 2 Inviter : champ « numéro exact ou nom »")
        sleep(2)
        shot("04-A-inviter")
        XCTAssertFalse(app.staticTexts["group-new-error"].exists, "aucune erreur à la création")

        // 2. Ajouter quelqu'un : le numéro de Guest B, tapé « +41 (0)79… » (formats suisses, avis du 23.11) → proposé,
        // sans son numéro affiché.
        scrollTo(search)
        search.tap()
        app.typeText("+41 (0)79 000 00 02")
        let add = any("label BEGINSWITH 'Ajouter '")
        XCTAssertTrue(add.waitForExistence(timeout: 20), "Guest B proposé pour le numéro tapé")
        sleep(1)
        shot("05-A-guestB-propose")
        // Jamais le numéro d'une personne affiché dans un résultat (le champ seul le contient).
        let numbers = app.staticTexts.matching(NSPredicate(format: "label CONTAINS '790000002' OR label CONTAINS '79 000 00 02'"))
        XCTAssertEqual(numbers.count, 0, "aucun numéro affiché dans les résultats")
        // Jamais de liste de tout le site : 5 résultats au plus, ici un seul.
        XCTAssertLessThanOrEqual(app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Ajouter '")).count, 1, "un seul résultat")
        add.tap()
        let send = app.buttons["group-invite-send"]
        XCTAssertTrue(send.waitForExistence(timeout: 5), "bouton « Inviter Guest B »")
        scrollTo(send)
        shot("06-A-guestB-choisi")
        send.tap()
        // Confirmation visible sous la recherche, clavier fermé (avis du 23.11 : rien ne confirmait l'envoi).
        XCTAssertTrue(any("label BEGINSWITH 'Invitation envoyée à '").waitForExistence(timeout: 20), "« Invitation envoyée à Guest B ✓ »")
        XCTAssertFalse(app.keyboards.firstMatch.exists, "clavier fermé après l'envoi")
        shot("07-A-invitation-envoyee")

        // Recherche par nom (3 lettres) : 5 résultats au plus, jamais d'annuaire.
        search.tap()
        if let current = search.value as? String, !current.isEmpty, current != "Numéro, nom, prénom ou surnom" {
            app.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: current.count))
        }
        app.typeText("Gue")
        sleep(3)
        shot("08-A-recherche-par-nom")
        XCTAssertLessThanOrEqual(app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Ajouter ' OR label BEGINSWITH 'Déjà invité'")).count, 5, "5 résultats au plus")

        // Ouvrir le groupe : le créateur en est l'admin (réglages, inviter, créer un événement).
        let open = app.buttons["new-group-open"]
        scrollTo(open, max: 8)
        if open.exists { open.tap() } else { app.buttons["new-group-later"].tap() }
        XCTAssertTrue(app.staticTexts["group-page-name"].waitForExistence(timeout: 20), "page du groupe")
        sleep(2)
        shot("09-A-page-du-groupe")
        XCTAssertTrue(app.buttons["group-settings"].exists, "réglages du groupe (créateur = admin)")
        XCTAssertTrue(app.buttons["group-create-event"].exists, "« Créer un événement pour le groupe »")

        // 3. Réglages du groupe : « Événements à valider » (le groupe décide), allumé.
        app.buttons["group-settings"].tap()
        XCTAssertTrue(app.textFields["group-settings-name"].waitForExistence(timeout: 20), "réglages du groupe")
        let rule = app.switches["group-events-approval"]
        scrollTo(rule, max: 8)
        XCTAssertTrue(rule.exists, "règle « Événements à valider »")
        shot("10-A-regle-eteinte")
        XCTAssertEqual(rule.value as? String, "0", "éteinte par défaut")
        if rule.switches.firstMatch.exists { rule.switches.firstMatch.tap() } else { rule.coordinate(withNormalizedOffset: CGVector(dx: 0.93, dy: 0.5)).tap() }
        sleep(3)
        shot("11-A-regle-allumee")
        XCTAssertEqual(rule.value as? String, "1", "allumée")
        let invite = app.switches["group-members-invite"]
        if invite.exists { XCTAssertEqual(invite.value as? String, "1", "« Tous les membres peuvent inviter » allumé par défaut") }
    }

    // MARK: 4. Guest A crée l'événement réservé à son groupe (page du groupe › formulaire web)

    func test2GuestACreatesAGroupEvent() { createGroupEvent("0790000001", "Guest A", title, "A") }

    /// Bonus : Guest B, simple membre d'un groupe « Événements à valider », crée aussi un événement pour le groupe.
    func test6GuestBCreatesAGroupEvent() { createGroupEvent("0790000002", "Guest B", "[QA] Proposition de B 2211", "B") }

    private func createGroupEvent(_ phone: String, _ who: String, _ title: String, _ tag: String) {
        launch()
        signIn(phone, who)
        openGroupsList()
        let row = any("label CONTAINS %@", group)
        XCTAssertTrue(row.waitForExistence(timeout: 20), "le groupe dans la liste")
        row.tap()
        XCTAssertTrue(app.staticTexts["group-page-name"].waitForExistence(timeout: 20), "page du groupe")
        app.buttons["group-create-event"].tap()

        let titleField = app.webViews.textFields["Titre"]
        XCTAssertTrue(titleField.waitForExistence(timeout: 40), "formulaire web « Nouvel événement »")
        sleep(3)
        shot("20-\(tag)-formulaire")
        titleField.tap()
        app.typeText(title)

        // Date : le jour du champ « Début » (sélecteur d'iOS).
        let day = app.webViews.descendants(matching: .any).matching(NSPredicate(format: "label BEGINSWITH 'Début : jour'")).firstMatch
        scrollTo(day)
        shot("21-\(tag)-avant-date")
        day.tap()
        sleep(2)
        shot("22-\(tag)-selecteur-date")
        // Un jour de la semaine prochaine dans le calendrier d'iOS (boutons des jours).
        let days = app.buttons.matching(NSPredicate(format: "label MATCHES '.*[0-9]+ .*' AND isEnabled == true"))
            .allElementsBoundByIndex.filter { $0.isHittable }
        if days.count > 8 { days[days.count - 3].tap() } else if let d = days.last { d.tap() }
        sleep(1)
        shot("23-\(tag)-jour-choisi")
        // Ferme le sélecteur.
        if app.buttons["Terminé"].exists { app.buttons["Terminé"].tap() } else if app.buttons["Done"].exists { app.buttons["Done"].tap() }
        else { app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.12)).tap() }
        sleep(2)

        // « Qui » : le groupe coché d'office.
        let chip = app.webViews.descendants(matching: .any).matching(NSPredicate(format: "label CONTAINS %@", group)).firstMatch
        scrollTo(chip)
        shot("24-\(tag)-qui-groupe")

        // Bouton : « Publier » (jamais « Envoyer pour validation » pour un groupe ordinaire).
        let publish = app.webViews.buttons["Publier"]
        let review = app.webViews.buttons["Envoyer pour validation"]
        scrollTo(publish.exists ? publish : review, max: 10)
        shot("25-\(tag)-bouton-publier")
        XCTAssertFalse(review.exists, "jamais « Envoyer pour validation » pour son groupe")
        XCTAssertFalse(app.webViews.otherElements["site-review"].exists, "pas de bandeau de validation du site")
        XCTAssertTrue(publish.exists, "bouton Publier")
        publish.tap()
        sleep(6)
        shot("26-\(tag)-apres-publier")
        // Jamais la validation du SITE (badge « En attente de validation » seul) ; celle du groupe peut s'afficher.
        XCTAssertFalse(any("label ==[c] 'En attente de validation'").exists, "jamais « En attente de validation » du site")
    }

    // MARK: 4 (suite). Guest A modifie le titre : reste publié

    func test3GuestAEditsTheEvent() {
        guard let event = env["RECETTE_EVENT"] else { return XCTFail("RECETTE_EVENT") }
        launch()
        signIn("0790000001", "Guest A")
        app.terminate()
        launch("if(!sessionStorage.recette){sessionStorage.recette='1';location.replace('/?tab=events&event=\(event)');}")
        let edit = app.webViews.buttons["Modifier"]
        XCTAssertTrue(edit.waitForExistence(timeout: 40), "« Modifier » sur la fiche")
        sleep(2)
        shot("30-A-fiche")
        XCTAssertFalse(any("label CONTAINS 'attente de validation'").exists, "fiche : pas en attente de validation")
        edit.tap()
        let titleField = app.webViews.textFields["Titre"]
        XCTAssertTrue(titleField.waitForExistence(timeout: 30), "formulaire de modification")
        sleep(2)
        titleField.tap()
        app.typeText(" (modifié)")
        let save = app.webViews.buttons["Enregistrer"]
        scrollTo(save, max: 12)
        shot("31-A-modification")
        XCTAssertFalse(app.webViews.otherElements["site-review"].exists, "pas de « repasse en validation » du site")
        save.tap()
        sleep(6)
        shot("32-A-apres-modification")
        XCTAssertTrue(any("label CONTAINS '(modifié)'").waitForExistence(timeout: 20), "titre modifié sur la fiche")
        XCTAssertFalse(any("label CONTAINS 'attente de validation'").exists, "toujours publié")
    }

    // MARK: 5. Guest B : rejoint le groupe, voit l'événement

    func test4GuestBSeesTheGroupAndTheEvent() {
        launch()
        signIn("0790000002", "Guest B")
        openGroupsList()
        shot("40-B-liste-invitation")
        let join = app.buttons["Rejoindre"]
        if join.waitForExistence(timeout: 10) {
            join.tap()
            sleep(4)
            shot("41-B-rejoint")
        }
        let row = any("label CONTAINS %@", group)
        XCTAssertTrue(row.waitForExistence(timeout: 20), "le groupe dans les groupes de Guest B")
        row.tap()
        XCTAssertTrue(app.staticTexts["group-page-name"].waitForExistence(timeout: 20), "page du groupe")
        sleep(2)
        let ev = any("label CONTAINS %@", title)
        if !ev.exists { app.swipeUp(); sleep(1) }
        shot("42-B-page-du-groupe")
        XCTAssertTrue(ev.exists, "l'événement dans « Prochains événements » du groupe")

        // Onglet Événements : la carte de l'événement (l'écran des groupes couvre la barre d'onglets : on le ferme).
        if app.buttons["groups-close"].exists { app.buttons["groups-close"].tap(); sleep(1) }
        if app.buttons["groups-close"].exists { app.navigationBars.buttons.firstMatch.tap(); sleep(1); app.buttons["groups-close"].tap(); sleep(1) }
        app.tabBars.buttons["Événements"].tap()
        let card = app.webViews.descendants(matching: .any).matching(NSPredicate(format: "label CONTAINS %@", title)).firstMatch
        XCTAssertTrue(card.waitForExistence(timeout: 40), "l'événement dans Événements")
        sleep(2)
        shot("43-B-evenements")
    }

    // MARK: 6. Admin test : voit le groupe (membres) sans en être membre, jamais la discussion

    func test5AdminSeesTheGroupButNotItsChat() {
        launch()
        signIn("0790000004", "Admin test")
        openGroupsList()
        let more = app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Voir les '")).firstMatch
        for _ in 0..<10 where !more.exists { app.swipeUp(); sleep(1) }
        XCTAssertTrue(more.exists, "« Voir les N autres groupes » (admin)")
        more.tap()
        sleep(2)
        let row = any("label BEGINSWITH %@", "Groupe \(group)")
        // Petits pas : la barre « Chercher un groupe » flotte en bas et prendrait le toucher.
        for _ in 0..<15 where !(row.exists && row.frame.minY > 150 && row.frame.maxY < app.frame.height - 300) {
            app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.6))
                .press(forDuration: 0.05, thenDragTo: app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.45)))
            sleep(1)
        }
        shot("50-admin-autres-groupes")
        XCTAssertTrue(row.exists, "le groupe de Guest A parmi les autres groupes")
        row.coordinate(withNormalizedOffset: CGVector(dx: 0.4, dy: 0.3)).tap()
        XCTAssertTrue(app.staticTexts["group-page-name"].waitForExistence(timeout: 20), "page du groupe (admin)")
        sleep(2)
        shot("51-admin-page-du-groupe")
        XCTAssertFalse(app.buttons["group-chat"].exists, "jamais « Discussion » pour un admin non membre")
        XCTAssertFalse(app.buttons["group-settings"].exists, "jamais « Réglages » pour un admin non membre")
        for _ in 0..<2 { app.swipeUp(); sleep(1) }
        shot("52-admin-membres")
        XCTAssertTrue(any("label CONTAINS 'Guest A'").exists, "membre Guest A visible")
        XCTAssertTrue(any("label CONTAINS 'Guest B'").exists, "membre Guest B visible")

        // Discussions : le groupe n'y est pas (pas membre).
        app.tabBars.buttons["Discussions"].tap()
        sleep(4)
        if app.buttons["Plus tard"].exists { app.buttons["Plus tard"].tap(); sleep(1) }
        shot("53-admin-discussions")
        XCTAssertFalse(any("label CONTAINS %@", group).exists, "le groupe absent des Discussions de l'admin")
    }
}

import XCTest

/// Recette RÉELLE des réglages du groupe pour son admin (23.11) dans le simulateur, configuration Release : serveur Party
/// local branché sur la base de TEST (code SMS fixe). Groupe préparé sur la base de TEST (TEST_RUNNER_RECETTE_GROUP) :
/// créé par « Guest A » (0790000001, simple Guest du site), membres « QA Six » et « VIP test », demande d'entrée de
/// « Guest B ». Une méthode par étape, lancée à part (app réinstallée entre deux) :
///   TEST_RUNNER_RECETTE_DIR=…  TEST_RUNNER_RECETTE_GROUP=<nom du groupe>
///   xcodebuild test -configuration Release ENABLE_TESTABILITY=YES PARTY_SWIFT_CONDITIONS=E2E_HOOKS
///   PARTY_BASE_URL=http://127.0.0.1:<port> -only-testing:PartyUITests/RecetteReglagesGroupeUITests/test1…
final class RecetteReglagesGroupeUITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment
    private var dir: URL!
    private var app: XCUIApplication!
    private var group: String { env["RECETTE_GROUP"] ?? "[QA] Réglages 2311" }

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
        try? app.screenshot().pngRepresentation.write(to: dir.appendingPathComponent("ga-\(name).png"))
    }

    private func any(_ predicate: String, _ args: CVarArg...) -> XCUIElement {
        app.descendants(matching: .any).matching(NSPredicate(format: predicate, argumentArray: args)).firstMatch
    }

    private func launchAndSignIn(_ phone: String, _ name: String) {
        app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_JS"] = "localStorage.setItem('vp_install_dismissed','1');"
        app.launch()
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

    private func openGroup() {
        app.tabBars.buttons["Réglages"].tap()
        let groups = app.buttons["settings-groups"]
        XCTAssertTrue(groups.waitForExistence(timeout: 20), "ligne Réglages › Groupes")
        groups.tap()
        XCTAssertTrue(app.navigationBars["Groupes"].waitForExistence(timeout: 30), "liste native des groupes")
        sleep(2)
        let row = any("label CONTAINS %@", group)
        XCTAssertTrue(row.waitForExistence(timeout: 20), "le groupe de la recette dans la liste")
        row.tap()
        XCTAssertTrue(app.staticTexts["group-page-name"].waitForExistence(timeout: 20), "page du groupe")
        sleep(2)
    }

    /// Fait venir l'élément à l'écran : petits coups vers le bas de la liste, puis vers le haut s'il était déjà passé.
    private func scrollTo(_ element: XCUIElement, max: Int = 10) {
        func visible() -> Bool {
            element.exists && element.isHittable && element.frame.maxY < app.frame.height - 110 && element.frame.minY > 140
        }
        for _ in 0..<max where !visible() {
            app.swipeUp(velocity: .slow)
            sleep(1)
        }
        for _ in 0..<(max * 2) where !visible() {
            app.swipeDown(velocity: .slow)
            sleep(1)
        }
    }

    // MARK: 1. Guest A, admin de son groupe : rôles, « Qui peut… », un droit, rôle d'un membre, entrée, transmettre

    func test1TheGroupAdminSetsRightsRolesAndEntry() {
        launchAndSignIn("0790000001", "Guest A")
        openGroup()
        shot("01-page-du-groupe")
        app.buttons["group-settings"].tap()
        XCTAssertTrue(any("label CONTAINS 'tu es l’admin du groupe'").waitForExistence(timeout: 20), "en-tête : tu es l’admin du groupe")
        shot("02-reglages-haut")
        let roles = any("label CONTAINS 'Toi (créateur)'")
        scrollTo(roles)
        XCTAssertTrue(roles.exists, "rôles dans le groupe : Toi (créateur)")
        shot("03-roles")

        // « Qui peut… » : les 7 droits, avec qui les a.
        let write = app.buttons["group-right-write"]
        scrollTo(write)
        XCTAssertTrue(write.exists, "ligne « Écrire dans la discussion »")
        XCTAssertTrue(any("label == 'Retirer un membre : Admins seulement'").exists, "Retirer un membre : Admins seulement")
        shot("04-qui-peut")

        // Un droit : « Écrire dans la discussion » → Admins seulement.
        write.tap()
        XCTAssertTrue(app.staticTexts["Les autres lisent la discussion, réagissent et signalent."].waitForExistence(timeout: 15), "écran du droit")
        shot("05-droit-ecrire")
        any("label BEGINSWITH 'Admins seulement'").tap()
        shot("06-droit-ecrire-admins")
        app.buttons["group-right-save"].tap()
        let saved = any("label == 'Écrire dans la discussion : Admins seulement'")
        XCTAssertTrue(saved.waitForExistence(timeout: 20), "de retour : Écrire = Admins seulement")
        shot("07-qui-peut-apres")

        // « Créer un événement pour le groupe » : À valider par un admin, rappel de l'événement public.
        app.buttons["group-right-events"].tap()
        XCTAssertTrue(any("label BEGINSWITH 'Un événement PUBLIC passe toujours'").waitForExistence(timeout: 15), "rappel événement public")
        shot("08-droit-evenement")
        app.navigationBars.buttons.firstMatch.tap()
        sleep(2)

        // Rôle d'un membre : QA Six → Organisateur.
        let qa = app.buttons["group-member-9e2ebb12-aa57-4bf2-b7e7-4ba0f2076828"]  // QA Six sur la base de TEST
        // Tout en haut, puis par petits pas jusqu'à la ligne, bien sous la barre de navigation.
        for _ in 0..<6 { app.swipeDown(velocity: .fast) }
        let mid = app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.6))
        for _ in 0..<20 where !(qa.exists && qa.frame.minY > 160 && qa.frame.maxY < app.frame.height - 120) {
            mid.press(forDuration: 0.05, thenDragTo: mid.withOffset(CGVector(dx: 0, dy: -250)))
            sleep(1)
        }
        shot("09a-membres")
        qa.tap()
        if !app.buttons["group-role-organizer"].waitForExistence(timeout: 10) {
            try? app.debugDescription.write(to: dir.appendingPathComponent("ga-09-arbre.txt"), atomically: true, encoding: .utf8)
        }
        XCTAssertTrue(app.buttons["group-role-organizer"].exists, "feuille du rôle")
        shot("09-role-du-membre")
        app.buttons["group-role-organizer"].tap()
        XCTAssertTrue(any("label == 'QA Six, Organisateur'").waitForExistence(timeout: 20), "QA Six est organisateur")
        shot("10-qa-organisateur")

        // Entrée : accepter chaque nouveau membre, puis la demande de Guest B.
        let approval = app.switches["group-join-approval"]
        scrollTo(approval)
        approval.switches.firstMatch.exists ? approval.switches.firstMatch.tap() : approval.tap()
        sleep(3)
        shot("11-entree-accord")
        let accept = any("identifier BEGINSWITH 'group-join-accept-'")
        scrollTo(accept)
        XCTAssertTrue(accept.exists, "demande de Guest B")
        accept.tap()
        sleep(3)
        shot("12-demande-acceptee")
        XCTAssertFalse(any("identifier BEGINSWITH 'group-join-accept-'").exists, "plus de demande en attente")

        // Transmettre : la feuille (sans transmettre).
        let handover = app.buttons["group-settings-handover"]
        scrollTo(handover)
        handover.tap()
        XCTAssertTrue(app.staticTexts["Transmettre le groupe"].waitForExistence(timeout: 10), "feuille Transmettre")
        shot("13-transmettre")
        app.swipeDown(velocity: .fast)
        sleep(1)
        shot("14-reglages-bas")
    }

    // MARK: 2. QA Six (organisateur, pas admin) : lit la discussion sans écrire, ne règle pas le groupe

    func test2AnOrganizerReadsButDoesNotWriteAndCannotChangeRights() {
        launchAndSignIn("0790000006", "QA Six")
        openGroup()
        app.buttons["group-chat"].tap()
        let later = app.buttons["Plus tard"]  // « Reconnais tes amis » (contacts) : plus tard
        if later.waitForExistence(timeout: 6) { later.tap() }
        let readOnly = any("identifier == 'chat-read-only'")
        XCTAssertTrue(readOnly.waitForExistence(timeout: 30), "« Dans ce groupe, l'admin a réservé l'écriture »")
        shot("20-discussion-lecture-seule")
        // La discussion s'ouvre dans l'onglet Discussions : retour aux réglages par Réglages › Groupes.
        openGroup()
        app.buttons["group-settings"].tap()
        XCTAssertTrue(any("label CONTAINS 'tu es organisateur'").waitForExistence(timeout: 20), "en-tête : tu es organisateur")
        XCTAssertFalse(app.buttons["group-right-write"].exists, "pas de « Qui peut… » pour un organisateur")
        XCTAssertTrue(any("label BEGINSWITH 'Seuls l’admin et les co-admins du groupe changent son nom'").exists, "qui change le nom")
        shot("21-reglages-organisateur")
    }
}

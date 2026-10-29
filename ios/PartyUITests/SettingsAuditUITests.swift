import XCTest

/// Audit des Réglages en vrai, sur le site de test (base Supabase de TEST, numéros de test à code fixe, aucun SMS) :
/// connexion native en membre puis en admin, chaque écran ouvert, ses commandes touchées, déconnexion.
/// Chaque étape est enregistrée (capture + arbre d'accessibilité) ; un échec n'arrête pas l'audit.
/// Lancé seulement à la demande : TEST_RUNNER_PARTY_AUDIT=<dossier> xcodebuild test -only-testing:PartyUITests/SettingsAuditUITests
final class SettingsAuditUITests: XCTestCase {
    static let memberPhone = "0790000003"   // « VIP test », Membre VIP sur la base de test
    static let adminPhone = "0790000004"    // « Admin test », Admin sur la base de test
    static let code = "123456"

    private var dir: URL!
    private var app: XCUIApplication!
    private var step = 0
    private var prefix = ""

    override func setUpWithError() throws {
        guard let path = ProcessInfo.processInfo.environment["PARTY_AUDIT"] else { throw XCTSkip("Audit à la demande (PARTY_AUDIT)") }
        dir = URL(fileURLWithPath: path)
        continueAfterFailure = true
    }

    // MARK: Outils

    private func record(_ name: String) {
        step += 1
        let base = String(format: "%@-%02d-%@", prefix, step, name.replacingOccurrences(of: "/", with: "_"))
        try? app.screenshot().pngRepresentation.write(to: dir.appendingPathComponent("\(base).png"))
        try? app.debugDescription.write(to: dir.appendingPathComponent("\(base).txt"), atomically: true, encoding: .utf8)
    }

    private func settingsTab() {
        let tab = app.tabBars.buttons.matching(NSPredicate(format: "label IN {'Réglages', 'Se connecter'}")).firstMatch
        XCTAssertTrue(tab.waitForExistence(timeout: 20), "onglet Réglages")
        tab.tap()
        // Retour à la racine des Réglages (écran précédent resté ouvert).
        for _ in 0..<4 where app.navigationBars.buttons.firstMatch.exists && !app.staticTexts["Notifications"].isHittable {
            app.navigationBars.buttons.firstMatch.tap()
        }
        sleep(1)
    }

    private func back() {
        if app.navigationBars.buttons.firstMatch.exists { app.navigationBars.buttons.firstMatch.tap() }
        sleep(1)
    }

    private func type(_ text: String, into field: XCUIElement) {
        for _ in 0..<3 {
            field.tap()
            if app.keyboards.firstMatch.waitForExistence(timeout: 3) { break }
        }
        app.typeText(text)
    }

    /// Ligne (texte) rendue visible puis touchée ; false si elle n'existe pas.
    @discardableResult
    private func open(_ title: String) -> Bool {
        let cell = app.staticTexts[title].firstMatch
        // Visible et au-dessus de la barre d'onglets flottante (qui recouvre le bas de la liste).
        let barTop = app.tabBars.firstMatch.exists ? app.tabBars.firstMatch.frame.minY : app.frame.maxY
        for _ in 0..<6 where !(cell.exists && cell.isHittable && cell.frame.maxY < barTop - 8) {
            app.swipeUp(velocity: .slow)
            sleep(1)  // la liste finit de défiler avant le toucher
        }
        guard cell.exists else {
            XCTFail("Ligne absente : \(title)")
            record("ABSENT-\(title)")
            return false
        }
        cell.tap()
        sleep(2)
        return true
    }

    /// Un écran qui charge ne doit finir ni sur une roue, ni sur une erreur.
    private func expectLoaded(_ screen: String, timeout: TimeInterval = 15) {
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline && app.activityIndicators.firstMatch.exists { usleep(300_000) }
        let errors = ["Réessayer", "a expiré", "introuvable", "Internal Server Error", "n'a pas pu"]
        for word in errors where app.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", word)).firstMatch.exists
            || app.buttons[word].exists {
            XCTFail("\(screen) : « \(word) » affiché")
        }
        record(screen)
    }

    private func flip(_ toggle: XCUIElement) {
        let inner = toggle.switches.firstMatch
        (inner.exists ? inner : toggle).tap()
        sleep(2)
    }

    private func toggleTwice(_ label: String) {
        let toggle = app.switches.matching(NSPredicate(format: "label == %@ OR label BEGINSWITH %@", label, label + ",")).firstMatch
        for _ in 0..<5 where !(toggle.exists && toggle.isHittable) { app.swipeUp() }
        guard toggle.exists else { return XCTFail("Interrupteur absent : \(label)") }
        let before = toggle.value as? String
        flip(toggle)
        XCTAssertNotEqual(toggle.value as? String, before, "\(label) n'a pas changé")
        record("bascule-\(label)")
        flip(toggle)
        XCTAssertEqual(toggle.value as? String, before, "\(label) n'est pas revenu")
    }

    // MARK: Parcours

    private func signIn(_ phone: String, name: String) {
        settingsTab()
        if !app.staticTexts["Se connecter"].exists { signOut() }  // compte resté connecté d'un essai précédent
        record("avant-connexion")
        XCTAssertTrue(open("Se connecter"))
        let field = app.textFields["login-phone"]
        XCTAssertTrue(field.waitForExistence(timeout: 10), "champ du numéro natif")
        record("connexion")
        type(phone, into: field)
        app.buttons["login-send"].tap()
        let code = app.textFields["login-code"]
        XCTAssertTrue(code.waitForExistence(timeout: 15), "champ du code")
        record("code")
        type(Self.code, into: code)   // 6 chiffres : la connexion part toute seule
        XCTAssertTrue(app.staticTexts[name].waitForExistence(timeout: 20), "carte du compte « \(name) »")
        record("connecte")
    }

    private func signOut() {
        settingsTab()
        XCTAssertTrue(open("Se déconnecter"))
        let sheet = app.sheets.buttons["Se déconnecter"].firstMatch
        let confirm = sheet.exists ? sheet : app.buttons.matching(identifier: "Se déconnecter").element(boundBy: 1)
        XCTAssertTrue(confirm.waitForExistence(timeout: 5), "confirmation de déconnexion")
        confirm.tap()
        sleep(4)
        settingsTab()
        XCTAssertTrue(app.staticTexts["Se connecter"].waitForExistence(timeout: 15), "déconnecté : « Se connecter » revient")
        record("deconnecte")
    }

    private func auditMemberScreens() {
        settingsTab()
        record("reglages")
        app.swipeUp()
        record("reglages-bas")

        settingsTab()
        app.swipeDown()
        app.swipeDown()
        let profile = app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Mon profil'")).firstMatch
        XCTAssertTrue(profile.waitForExistence(timeout: 5), "carte Mon profil")
        profile.tap()
        sleep(3)
        expectLoaded("profil")
        XCTAssertFalse((app.textFields["Prénom"].value as? String ?? "").isEmpty, "prénom chargé")
        back()

        settingsTab()
        if open("Notifications") {
            expectLoaded("notifications")
            toggleTwice("Nouveau sondage")
            toggleTwice("La veille")
            if open("Annonces des admins · toujours reçues") {
                expectLoaded("annonces")
                back()
            }
            back()
        }

        settingsTab()
        if open("Groupes") { auditGroups() }

        settingsTab()
        if open("Mes stats de jeu") { expectLoaded("stats"); back() }
        settingsTab()
        if open("Ton avis") {
            sleep(2)
            record("ton-avis")
        }
        settingsTab()
        if open("Confidentialité") {
            XCTAssertTrue(app.staticTexts["Qui peut voir quoi ?"].waitForExistence(timeout: 5) || app.staticTexts["QUI PEUT VOIR QUOI ?"].exists)
            record("confidentialite")
            back()
        }
        settingsTab()
        if open("Gérer mon compte") {
            record("gerer-compte-ouvert")
            let button = app.buttons["delete-account"]
            guard button.waitForExistence(timeout: 5) else { return XCTFail("Gérer mon compte : écran pas ouvert") }
            XCTAssertFalse(button.isEnabled, "suppression bloquée sans SUPPRIMER")
            type("NON", into: app.textFields["delete-confirm"])
            app.swipeDown()  // ferme le clavier, qui recouvre le bouton
            record("gerer-compte-saisi")
            XCTAssertTrue(app.navigationBars["Gérer mon compte"].exists, "Gérer mon compte : l'écran s'est refermé pendant la saisie")
            XCTAssertFalse(button.exists && button.isEnabled, "suppression bloquée avec un autre mot")
            record("gerer-compte")
            back()
        }
    }

    private func auditGroups() {
        expectLoaded("groupes")
        let name = "Audit \(Int(Date().timeIntervalSince1970) % 100_000)"
        type(name, into: app.textFields["Nom du nouveau groupe"])
        app.buttons["Créer"].tap()
        XCTAssertTrue(app.staticTexts[name].waitForExistence(timeout: 10), "groupe créé")
        record("groupe-cree")
        guard app.staticTexts[name].exists else { return back() }
        app.staticTexts[name].tap()
        sleep(2)
        let first = app.collectionViews.buttons.element(boundBy: 0)
        if first.exists {
            first.tap()
            sleep(2)
            XCTAssertTrue(app.staticTexts["Membres · 1"].exists || app.staticTexts["MEMBRES · 1"].exists, "personne ajoutée au groupe")
        }
        record("groupe-compose")
        let delete = app.buttons["Supprimer le groupe"]
        for _ in 0..<5 where !delete.isHittable { app.swipeUp() }
        delete.tap()
        app.sheets.buttons["Supprimer"].firstMatch.tap()
        sleep(3)
        XCTAssertFalse(app.staticTexts[name].exists, "groupe supprimé")
        record("groupe-supprime")
        back()
    }

    private func auditAdminScreens() {
        settingsTab()
        if open("Invités et messages") {
            expectLoaded("invites-messages")
            if open("Journal de la soirée") { expectLoaded("journal-soiree"); back() }
            back()
        }
        settingsTab()
        if open("Admin de la soirée") {
            expectLoaded("admin-soiree")
            app.swipeUp()
            record("admin-soiree-bas")
            back()
        }
        settingsTab()
        guard open("Administration du groupe") else { return }
        expectLoaded("admin-groupe")
        if open("Membres") {
            expectLoaded("membres")
            if open("VIP test") {
                expectLoaded("fiche-membre")
                let beta = app.switches.firstMatch
                if beta.exists { toggleTwice(beta.label) }
                back()
            }
            back()
        }
        if app.staticTexts["Rôles et droits"].exists, open("Rôles et droits") {
            expectLoaded("roles")
            let first = app.switches.element(boundBy: 0)
            if first.exists && first.isEnabled { toggleTwice(first.label) }
            back()
        }
        if open("Journal des membres") { expectLoaded("journal-membres"); back() }
        if open("Utilisateurs") {
            expectLoaded("utilisateurs")
            app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Trier par'")).firstMatch.tap()
            sleep(1)
            app.buttons["Nom"].firstMatch.tap()
            sleep(1)
            record("utilisateurs-par-nom")
            back()
        }
        if open("Annonces admin") {
            expectLoaded("annonces-admin")
            let publish = app.buttons["Publier pour tout le groupe"]
            XCTAssertTrue(publish.exists && !publish.isEnabled, "publier bloqué sans titre ni message")
            back()
        }
        if open("Catégories et tags") { auditTaxonomy() }
    }

    /// Onglet « Retours » de l'hôte : retours reçus (liste, fiche d'un retour) et « Mon avis » à côté.
    private func auditFeedback() {
        let tab = app.tabBars.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Retours'")).firstMatch  // « Retours, 6 nouveaux »
        guard tab.waitForExistence(timeout: 10) else { return XCTFail("Onglet Retours absent pour l'admin") }
        tab.tap()
        sleep(3)
        XCTAssertTrue(app.buttons["Retours reçus"].exists && app.buttons["Mon avis"].exists, "deux parties : reçus et mon avis")
        expectLoaded("retours-recus")
        let filter = app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Filtrer'")).firstMatch
        if filter.exists {
            filter.tap()
            sleep(1)
            app.buttons.matching(NSPredicate(format: "label == 'Tout'")).firstMatch.tap()
            sleep(1)
            record("retours-tout")
        }
        let edit = app.buttons["Modifier"].firstMatch
        if edit.exists {
            edit.tap()
            XCTAssertTrue(app.navigationBars["Retour"].waitForExistence(timeout: 5), "fiche d'un retour")
            XCTAssertTrue(app.buttons["Copier le prompt"].exists, "copier le prompt")
            record("retour-fiche")
            app.buttons["Fermer"].tap()
            sleep(1)
        }
        app.buttons["Mon avis"].tap()
        sleep(1)
        XCTAssertTrue(app.buttons["Envoyer"].exists, "formulaire « Mon avis » gardé")
        record("retours-mon-avis")
    }

    private func auditTaxonomy() {
        expectLoaded("taxonomie")
        app.buttons["Tags"].tap()
        let tag = "audit\(Int(Date().timeIntervalSince1970) % 100_000)"
        type(tag, into: app.textFields["Nouveau tag"])
        app.buttons["Créer"].tap()
        XCTAssertTrue(app.staticTexts["#\(tag)"].waitForExistence(timeout: 10), "tag créé")
        let created = app.staticTexts["#\(tag)"]
        app.swipeDown()  // ferme le clavier
        for _ in 0..<8 where created.exists && !created.isHittable { app.swipeUp(velocity: .slow); sleep(1) }
        if created.exists && created.isHittable {
            created.swipeLeft()
            app.buttons["Archiver"].firstMatch.tap()
            sleep(2)
            XCTAssertTrue(app.staticTexts["Archivé"].exists, "tag archivé")
        }
        record("tag-archive")
        back()
    }

    func testMember() {
        app = XCUIApplication()
        app.launch()
        prefix = "membre"
        signIn(Self.memberPhone, name: "VIP test")
        auditMemberScreens()
        settingsTab()
        XCTAssertFalse(app.staticTexts["Administration du groupe"].exists, "pas d'administration pour un membre")
        signOut()
    }

    func testAdmin() {
        app = XCUIApplication()
        app.launch()
        prefix = "admin"
        signIn(Self.adminPhone, name: "Admin test")
        auditMemberScreens()
        auditAdminScreens()
        auditFeedback()
        auditChats()
        signOut()
    }

    /// Onglet Discussions natif (avis n°10) : liste, conversation, envoi, réaction, infos du groupe.
    func testChats() {
        app = XCUIApplication()
        app.launch()
        prefix = "discussions"
        signIn(Self.adminPhone, name: "Admin test")
        auditChats()
        signOut()
    }

    private func auditChats() {
        let tab = app.tabBars.buttons["Discussions"].firstMatch
        XCTAssertTrue(tab.waitForExistence(timeout: 20), "onglet Discussions")
        tab.tap()
        XCTAssertTrue(app.navigationBars["Discussions"].waitForExistence(timeout: 15), "liste des discussions")
        record("liste")
        let row = app.cells.firstMatch.exists ? app.cells.firstMatch : app.buttons.matching(NSPredicate(format: "label CONTAINS 'Vendredi'")).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 15), "au moins une discussion")
        row.tap()
        let field = app.textFields["chat-message"].exists ? app.textFields["chat-message"] : app.textViews["chat-message"]
        XCTAssertTrue(field.waitForExistence(timeout: 15), "champ du message")
        record("conversation")
        let text = "Audit natif \(Int(Date().timeIntervalSince1970) % 100000)"
        type(text, into: field)
        app.buttons["chat-send"].tap()
        let sent = app.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", text)).firstMatch
        XCTAssertTrue(sent.waitForExistence(timeout: 15), "message envoyé affiché")
        record("envoye")
        sent.press(forDuration: 1.2)
        let like = app.buttons["👍"].firstMatch
        if like.waitForExistence(timeout: 5) {
            like.tap()
            XCTAssertTrue(app.buttons.matching(NSPredicate(format: "label BEGINSWITH '👍 1'")).firstMatch.waitForExistence(timeout: 15), "réaction 👍")
        } else {
            XCTFail("menu des réactions")
        }
        record("reaction")
        app.buttons["Infos du groupe"].tap()
        XCTAssertTrue(app.staticTexts["Notifications"].waitForExistence(timeout: 10), "infos : notifications")
        record("infos")
        app.buttons["OK"].tap()
        back()
    }
}

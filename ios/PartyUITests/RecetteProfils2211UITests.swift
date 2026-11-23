import XCTest

/// Recette RÉELLE des avis du 22.11.2026 (profils, discussions, administration des membres), dans le simulateur
/// (configuration Release, comme l'App Store) : serveur Party local branché sur la base de TEST, codes fixes (aucun SMS).
/// Préparé avant (SQL sur la base de TEST) : RECETTE_EVENT = « [QA] P2211 Ensemble Présent » (Admin test organisateur
/// Présent, VIP test Présent, une photo d'Admin test et un message de VIP test dans la discussion, date et lieu modifiés),
/// « [QA] P2211 VIP Pas présent » (VIP test : Pas présent) et « [QA] P2211 VIP Peut-être » (VIP test : Peut-être).
/// Chaque test part d'une app neuve (désinstallée avant) : un seul compte par test.
///   TEST_RUNNER_RECETTE_DIR=… TEST_RUNNER_RECETTE_EVENT=<id> xcodebuild test-without-building -configuration Release …
///   -only-testing:PartyUITests/RecetteProfils2211UITests/<test>
final class RecetteProfils2211UITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment
    private var dir: URL!
    private var app: XCUIApplication!
    private var step = 0
    private var prefix = "p2211"
    static let note = "[QA] Rencontré à la recette du 22.11"

    override func setUpWithError() throws {
        guard let path = env["RECETTE_DIR"], env["RECETTE_EVENT"] != nil else { throw XCTSkip("Recette à la demande (RECETTE_DIR, RECETTE_EVENT)") }
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
        step += 1
        let base = String(format: "%@-%02d-%@", prefix, step, name)
        try? app.screenshot().pngRepresentation.write(to: dir.appendingPathComponent(base + ".png"))
    }

    /// Arbre d'accessibilité (pour comprendre un geste raté).
    private func tree(_ name: String) {
        try? app.debugDescription.write(to: dir.appendingPathComponent("\(prefix)-tree-\(name).txt"), atomically: true, encoding: .utf8)
    }

    private func launch(_ js: String = "") {
        app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_JS"] = "localStorage.setItem('vp_install_dismissed','1');" + js
        app.launch()
    }

    private func signIn(_ phone: String, expect name: String?) {
        let tab = app.tabBars.buttons.matching(NSPredicate(format: "label IN {'Réglages', 'Se connecter'}")).firstMatch
        XCTAssertTrue(tab.waitForExistence(timeout: 30), "onglet Réglages")
        tab.tap()
        // Attend l'écran (connecté ou non) : sans ce délai, une page lente faisait sauter la connexion.
        _ = app.staticTexts["Se connecter"].waitForExistence(timeout: 10)
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
        if let name { XCTAssertTrue(app.staticTexts[name].waitForExistence(timeout: 30), "connecté en \(name)") } else { sleep(6) }
    }

    /// La discussion native de l'événement, ouverte comme par la notification d'un message.
    private func openEventChat() -> XCUIElement {
        let event = env["RECETTE_EVENT"]!
        app.terminate()
        launch("if(!sessionStorage.recette){sessionStorage.recette='1';location.replace('/?tab=events&event=\(event)&chat=1');}")
        let field = app.descendants(matching: .any).matching(identifier: "chat-message").firstMatch
        XCTAssertTrue(field.waitForExistence(timeout: 45), "discussion native ouverte (champ Message)")
        sleep(3)
        return field
    }

    /// Le bouton visible (le fil natif), pas celui de la fiche web cachée derrière la discussion.
    private func hittableButton(_ label: String) -> XCUIElement {
        let all = app.buttons.matching(NSPredicate(format: "label == %@", label))
        for _ in 0..<10 {
            if let b = all.allElementsBoundByIndex.first(where: { $0.exists && $0.isHittable }) { return b }
            sleep(1)
        }
        return all.firstMatch
    }

    private func any(_ id: String) -> XCUIElement { app.descendants(matching: .any).matching(identifier: id).firstMatch }

    private func text(containing s: String) -> XCUIElement {
        app.descendants(matching: .any).matching(NSPredicate(format: "label CONTAINS %@", s)).firstMatch
    }

    /// Fait défiler la feuille jusqu'à l'élément (au plus n gestes).
    private func scrollTo(_ el: XCUIElement, in container: XCUIElement, _ n: Int = 6) {
        var i = 0
        while (!el.exists || !el.isHittable) && i < n { container.swipeUp(velocity: .slow); i += 1 }
    }

    /// Points 1, 2, 3 (Admin test) : photo de la discussion en grand, mini-profil de VIP test, note privée, « À venir
    /// ensemble », photo de profil en grand.
    func test1AdminNoteUpcomingAndPhotos() {
        prefix = "p2211-admin"
        launch()
        signIn("0790000004", expect: "Admin test")
        _ = openEventChat()
        shot("discussion")

        // Toucher la photo d'un message : plein écran (« Enregistrer », partage), ✕ ferme.
        let photo = any("chat-photo")
        XCTAssertTrue(photo.waitForExistence(timeout: 15), "photo dans la discussion")
        if photo.exists {
            photo.tap()
            let close = app.buttons["photo-viewer-close"]
            XCTAssertTrue(close.waitForExistence(timeout: 10), "photo ouverte en grand")
            sleep(2)
            shot("photo-message-grand")
            XCTAssertTrue(app.buttons["photo-viewer-save"].exists || app.buttons["photo-viewer-share"].exists, "Enregistrer / partager")
            if close.exists { close.tap() }
            sleep(1)
        }

        // Mini-profil de VIP test (toucher son nom / sa photo dans le fil).
        // Toucher VIP test dans le fil : ce qui s'ouvre (constat).
        let inChat = hittableButton("Profil de VIP test")
        XCTAssertTrue(inChat.waitForExistence(timeout: 10), "VIP test dans le fil")
        inChat.tap()
        sleep(4)
        shot("profil-depuis-discussion")
        tree("profil-depuis-discussion")
        // Mini-profil (corrigé le 23.11 : avant, l'ancienne fiche) : « À venir ensemble » visible, la note plus bas.
        XCTAssertTrue(app.buttons["Fiche"].exists, "toucher une personne dans la discussion ouvre le mini-profil")
        for _ in 0..<3 where !app.staticTexts["📝 Ma note privée"].exists { app.swipeUp(velocity: .slow); sleep(1) }
        shot("mini-profil-depuis-discussion-note")
        XCTAssertTrue(app.staticTexts["📝 Ma note privée"].exists, "la note privée dans le mini-profil ouvert depuis la discussion")
        if app.buttons["Fermer"].exists { app.buttons["Fermer"].tap() } else if any("mini-profile-close").exists { any("mini-profile-close").tap() }
        sleep(2)
        // Mini-profil natif depuis la fiche de l'événement (Présents : … VIP test).
        if app.buttons["event-chat-close"].exists { app.buttons["event-chat-close"].tap() }
        sleep(3)
        let author = app.webViews.descendants(matching: .any).matching(NSPredicate(format: "label BEGINSWITH 'Profil de VIP test'")).firstMatch
        var tries = 0
        while !(author.exists && author.isHittable) && tries < 10 { app.webViews.firstMatch.swipeUp(velocity: .slow); tries += 1 }
        XCTAssertTrue(author.exists, "VIP test dans les Présents de la fiche")
        author.tap()
        let sheet = app.otherElements.matching(NSPredicate(format: "label == '📝 Ma note privée'")).firstMatch
        XCTAssertTrue(sheet.waitForExistence(timeout: 20), "mini-profil de VIP test (bloc de la note)")
        sleep(3)
        shot("mini-profil")
        tree("mini-profil")

        // Note privée.
        XCTAssertTrue(app.staticTexts["📝 Ma note privée"].waitForExistence(timeout: 10), "bloc « 📝 Ma note privée »")
        XCTAssertTrue(text(containing: "Visible par toi seul").exists, "« Visible par toi seul »")
        let input = app.textViews.matching(NSPredicate(format: "label BEGINSWITH 'Ma note privée sur'")).firstMatch
        XCTAssertTrue(input.exists, "champ de la note")
        let previous = (input.value as? String) ?? ""
        if !previous.isEmpty && previous != input.placeholderValue, app.buttons["Effacer ma note"].exists {
            app.buttons["Effacer ma note"].tap()  // une note d'un essai précédent : on repart de zéro
            sleep(2)
        }
        input.tap()
        app.typeText(Self.note)
        shot("note-en-cours")
        let save = app.buttons.matching(NSPredicate(format: "identifier == 'private-note-save' OR label == 'Enregistrer'")).firstMatch
        XCTAssertTrue(save.waitForExistence(timeout: 5), "Enregistrer")
        save.tap()
        XCTAssertTrue(text(containing: "Enregistrée ✓").waitForExistence(timeout: 10), "« Enregistrée ✓ »")
        shot("note-enregistree")

        // « À venir ensemble » : Présent et Peut-être, jamais Pas présent.
        let together = app.staticTexts.matching(NSPredicate(format: "label ==[c] 'À venir ensemble'")).firstMatch
        app.swipeUp(velocity: .slow)
        sleep(1)
        shot("a-venir-ensemble")
        tree("a-venir")
        XCTAssertTrue(text(containing: "[QA] P2211 Ensemble Présent").exists, "À venir ensemble : les deux Présent")
        XCTAssertTrue(text(containing: "[QA] P2211 VIP Peut-être").exists, "À venir ensemble : VIP test Peut-être")
        XCTAssertFalse(text(containing: "[QA] P2211 VIP Pas présent").exists, "jamais un événement où VIP test est Pas présent")

        // Fermer, rouvrir : la note est retrouvée.
        app.swipeDown(velocity: .fast)
        if app.buttons["mini-profile-close"].exists { app.buttons["mini-profile-close"].tap() } else if app.buttons["Fermer"].exists { app.buttons["Fermer"].tap() }
        sleep(2)
        if sheet.exists { app.swipeDown(velocity: .fast); sleep(2) }
        XCTAssertFalse(sheet.exists, "mini-profil fermé")
        shot("profil-ferme")
        author.tap()
        XCTAssertTrue(sheet.waitForExistence(timeout: 20), "mini-profil rouvert")
        sleep(3)
        let again = app.textViews.matching(NSPredicate(format: "label BEGINSWITH 'Ma note privée sur'")).firstMatch
        XCTAssertTrue(again.waitForExistence(timeout: 10), "champ de la note (rouvert)")
        XCTAssertEqual(again.value as? String, Self.note, "note retrouvée après fermeture")
        shot("note-retrouvee")

        // Photo de profil en grand.
        let open = app.buttons.matching(NSPredicate(format: "identifier == 'profile-photo-open' OR label BEGINSWITH 'Voir la photo de'")).firstMatch
        XCTAssertTrue(open.waitForExistence(timeout: 10), "photo du mini-profil touchable")
        if open.exists {
            open.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.85)).tap()
            let full = app.descendants(matching: .any).matching(NSPredicate(format: "identifier == 'profile-photo-full' OR label BEGINSWITH 'Photo de profil de'")).firstMatch
            XCTAssertTrue(full.waitForExistence(timeout: 10), "photo de profil en plein écran")
            sleep(2)
            shot("photo-profil-grand")
            app.buttons.matching(NSPredicate(format: "label == 'Fermer'")).allElementsBoundByIndex.first(where: { $0.isHittable })?.tap()
        }
    }

    /// Points 3 et 5 (VIP test) : @surnom proposé à un simple participant, la note d'Admin test invisible, notification
    /// de modification (lieu, date) en phrases claires.
    func test2VipMentionsNoteAndNotification() {
        prefix = "p2211-vip"
        launch()
        signIn("0790000003", expect: "VIP test")
        let field = openEventChat()
        shot("discussion")
        XCTAssertFalse(app.buttons["chat-announce"].exists, "VIP test n'est pas de l'organisation (pas de 📣)")

        field.tap()
        app.typeText("@Adm")
        let bar = any("chat-mentions")
        let suggestion = app.buttons.matching(NSPredicate(format: "identifier == 'chat-mentions' AND label == 'Citer Admin test'")).firstMatch
        XCTAssertTrue(suggestion.waitForExistence(timeout: 8), "« @Admin test » proposé à la frappe de @ (simple participant)")
        _ = bar
        shot("suggestion-arobase")
        tree("suggestion")
        if suggestion.exists {
            suggestion.tap()
            app.typeText("[QA] à quelle heure on arrive ?")
            app.buttons["chat-send"].tap()
            sleep(3)
            shot("citation-envoyee")
        }

        // Mini-profil d'Admin test vu par VIP test : son propre bloc de note est vide (la note d'Admin test sur VIP test
        // n'existe que pour Admin test).
        let author = hittableButton("Profil de Admin test")
        if author.waitForExistence(timeout: 10) {
            author.tap()
            sleep(4)
            XCTAssertFalse(text(containing: Self.note).exists, "VIP test ne voit jamais la note d'Admin test")
            shot("profil-admin-vu-par-vip")
            if app.buttons["Fermer"].exists { app.buttons["Fermer"].tap() } else if app.buttons["mini-profile-close"].exists { app.buttons["mini-profile-close"].tap() }
            sleep(1)
        }

        // Notifications : la cloche (Activité) de l'onglet Événements.
        if app.buttons["event-chat-close"].exists { app.buttons["event-chat-close"].tap(); sleep(2) }
        let events = app.tabBars.buttons["Événements"]
        XCTAssertTrue(events.waitForExistence(timeout: 20), "onglet Événements")
        events.tap()
        sleep(2)
        let bell = app.webViews.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Activité'")).firstMatch
        XCTAssertTrue(bell.waitForExistence(timeout: 40), "cloche")
        bell.tap()
        let tout = app.webViews.buttons["Tout"]
        if tout.waitForExistence(timeout: 15) { tout.tap() }
        let changed = app.webViews.descendants(matching: .any)
            .matching(NSPredicate(format: "label CONTAINS 'La date a été modifiée au 05.12 à 20:30'")).firstMatch
        XCTAssertTrue(changed.waitForExistence(timeout: 20), "notification « La date a été modifiée au … »")
        sleep(1)
        shot("activite-modification")
        tree("activite")
        XCTAssertTrue(app.webViews.descendants(matching: .any)
            .matching(NSPredicate(format: "label CONTAINS 'Le nouveau lieu de l’événement est Salle QA Bis' OR label CONTAINS \"Le nouveau lieu de l'événement est Salle QA Bis\"")).firstMatch.exists,
                      "phrase du nouveau lieu")
    }

    /// Point 4 (inscription) : 0790000007, profil vide, complète « Faisons connaissance » dans l'app.
    func test3NewAccountCompletesProfile() {
        prefix = "p2211-inscription"
        launch()
        signIn("0790000007", expect: nil)
        shot("apres-code")
        tree("apres-code")
        let events = app.tabBars.buttons["Événements"]
        if events.waitForExistence(timeout: 15) { events.tap() }
        let title = app.webViews.textFields["Prénom"]
        XCTAssertTrue(title.waitForExistence(timeout: 40), "formulaire du profil (Prénom, Nom, Surnom)")
        sleep(2)
        shot("faisons-connaissance")
        tree("faisons-connaissance")
        let fields = app.webViews.textFields
        XCTAssertGreaterThanOrEqual(fields.count, 3, "Prénom, Nom, Surnom")
        guard fields.count >= 3 else { return }
        let values = ["Qa", "Origine", "QA Origine"]
        for (i, v) in values.enumerated() {
            let f = fields.element(boundBy: i)
            f.tap()
            if let old = f.value as? String, !old.isEmpty, i == 2 {
                f.press(forDuration: 1.0)
                if app.menuItems["Tout sélectionner"].waitForExistence(timeout: 2) { app.menuItems["Tout sélectionner"].tap() }
                else if app.menuItems["Select All"].exists { app.menuItems["Select All"].tap() }
                app.typeText(XCUIKeyboardKey.delete.rawValue)
            }
            app.typeText(v)
        }
        shot("rempli")
        // Fermer le clavier (✓), puis le bouton du formulaire, plus bas.
        if app.buttons["Terminé"].exists { app.buttons["Terminé"].tap() } else if app.buttons["Done"].exists { app.buttons["Done"].tap() }
        else { app.toolbars.buttons.allElementsBoundByIndex.last?.tap() }
        sleep(1)
        let next = app.webViews.buttons.matching(NSPredicate(format: "label IN {'Continuer', 'Enregistrer'}")).firstMatch
        var k = 0
        while !(next.exists && next.isHittable) && k < 6 { app.webViews.firstMatch.swipeUp(velocity: .slow); k += 1 }
        XCTAssertTrue(next.exists, "Continuer / Enregistrer")
        next.tap()
        sleep(3)
        shot("apres-continuer")
        // CGU au premier surnom.
        let accept = app.webViews.buttons.matching(NSPredicate(format: "label BEGINSWITH 'J’accepte' OR label BEGINSWITH \"J'accepte\" OR label BEGINSWITH 'Accepter'")).firstMatch
        if accept.waitForExistence(timeout: 8) {
            shot("cgu")
            accept.tap()
            sleep(4)
        }
        tree("apres-cgu")
        shot("profil-complet")
        sleep(2)
        shot("profil-complet-2")
        XCTAssertTrue(app.webViews.staticTexts.matching(NSPredicate(format: "label CONTAINS 'QA Origine'")).firstMatch.exists, "profil complété (QA Origine)")
    }

    /// Point 4 (administration) : Admin test voit l'origine de l'inscription et le nom actuel (jamais « compte supprimé »).
    func test4AdminSeesSignupOrigin() {
        prefix = "p2211-origine"
        launch()
        signIn("0790000004", expect: "Admin test")
        let adminRow = app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Administration du groupe'")).firstMatch
        let anyRow = adminRow.exists ? adminRow : app.staticTexts["Administration du groupe"]
        var i = 0
        while !anyRow.isHittable && i < 8 { app.swipeUp(velocity: .slow); i += 1 }
        XCTAssertTrue(anyRow.exists, "Administration du groupe")
        anyRow.tap()
        let members = app.staticTexts["Membres"].firstMatch
        XCTAssertTrue(members.waitForExistence(timeout: 20), "Membres")
        i = 0
        while !members.isHittable && i < 6 { app.swipeUp(velocity: .slow); i += 1 }
        members.tap()
        let stats = app.staticTexts.matching(NSPredicate(format: "label ==[c] \"D'où viennent les inscrits\"")).firstMatch
        XCTAssertTrue(stats.waitForExistence(timeout: 30), "« D'où viennent les inscrits »")
        sleep(2)
        shot("membres-sources")
        tree("membres")
        let search = app.searchFields.firstMatch
        if search.waitForExistence(timeout: 5) {
            search.tap()
            app.typeText("QA Origine\n")
            sleep(2)
        }
        let text = app.staticTexts.matching(NSPredicate(format: "label CONTAINS 'QA Origine'")).firstMatch
        var j = 0
        while !(text.exists && text.isHittable) && j < 6 { app.swipeUp(velocity: .slow); j += 1 }
        shot("recherche")
        tree("recherche")
        XCTAssertTrue(text.exists, "QA Origine dans Membres (nom actuel)")
        text.tap()
        let line = app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH 'Inscrit directement' OR label BEGINSWITH 'Inscrit via' OR label BEGINSWITH 'Origine inconnue'")).firstMatch
        XCTAssertTrue(line.waitForExistence(timeout: 20), "ligne « Inscrit … » sur la fiche")
        sleep(1)
        shot("fiche-origine")
        tree("fiche")
        XCTAssertTrue(line.label.contains("Inscrit directement") && line.label.contains("app iPhone"), "origine : directe, app iPhone (\(line.label))")

        // Journal de la personne (fiche) : le nom actuel, jamais « compte supprimé ».
        let link = app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Journal de'")).firstMatch
        var k = 0
        while !(link.exists && link.isHittable) && k < 8 { app.swipeUp(velocity: .slow); k += 1 }
        XCTAssertTrue(link.exists, "Journal de QA Origine")
        XCTAssertEqual(link.label, "Journal de QA Origine", "nom actuel sur le lien du journal")
        link.tap()
        let entry = app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH 'QA Origine'")).firstMatch
        XCTAssertTrue(entry.waitForExistence(timeout: 30), "journal : « QA Origine s'est connecté… » (nom actuel)")
        sleep(2)
        shot("journal-personne")
        tree("journal-personne")
        XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label CONTAINS 'compte supprimé'")).firstMatch.exists, "jamais « compte supprimé »")
    }
}

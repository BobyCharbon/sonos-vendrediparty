import XCTest

/// Recette RÉELLE de TOUS les parcours de l'Agenda dans l'app iPhone (24.11, avant la mise en prod), configuration Release,
/// serveur Party local sur la base de TEST, compte Testeur 1 (0790000001), membre de « [QA] Qui est libre 2311 ».
///   TEST_RUNNER_RECETTE_DIR=<captures> xcodebuild test-without-building … -only-testing:PartyUITests/RecetteAgendaParcoursUITests
/// Chaque écran est capturé (agenda-parcours-NN-<nom>.png) pour être relu à l'œil : rien sous la barre d'état ni sous la
/// barre d'onglets, aucun texte coupé, aucun mot technique ou anglais.
/// Préparer avant (base de TEST) : prefs de l'agenda de Testeur 1 sans `tutorial_off` ni `setup_off` ; groupe et partages de
/// « Qui est libre ? » par ios/PartyUITests/recette-agenda-qui-est-libre.sql ; accès au calendrier déjà donné
/// (`xcrun simctl privacy <appareil> grant calendar ch.bobycharbon.party`, après l'installation) : la demande d'iOS
/// juste après l'installation se fermait parfois seule (« Pas d'accès à ton iPhone ? »).
final class RecetteAgendaParcoursUITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment
    private var dir: URL!
    private var app: XCUIApplication!
    private var step = 0
    private let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")

    override func setUpWithError() throws {
        guard let path = env["RECETTE_DIR"] else { throw XCTSkip("Recette à la demande (RECETTE_DIR)") }
        dir = URL(fileURLWithPath: path)
        continueAfterFailure = true
    }

    private func shot(_ name: String) {
        step += 1
        try? app.screenshot().pngRepresentation.write(to: dir.appendingPathComponent(String(format: "agenda-parcours-%02d-%@.png", step, name)))
    }

    private func launch() {
        app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_JS"] = "localStorage.setItem('vp_install_dismissed','1');"
        app.launch()
    }

    private func any(_ predicate: String, _ args: CVarArg...) -> XCUIElement {
        app.descendants(matching: .any).matching(NSPredicate(format: predicate, argumentArray: args)).firstMatch
    }

    /// Fait défiler jusqu'à l'élément (vers le bas, puis vers le haut) et le touche.
    @discardableResult
    private func reach(_ el: XCUIElement, timeout: TimeInterval = 15, _ what: String) -> Bool {
        _ = el.waitForExistence(timeout: timeout)
        for _ in 0..<8 where !(el.exists && el.isHittable) { app.swipeUp(velocity: .slow); usleep(600_000) }
        for _ in 0..<8 where !(el.exists && el.isHittable) { app.swipeDown(velocity: .slow); usleep(600_000) }
        guard el.exists && el.isHittable else {
            XCTFail("introuvable : \(what)")
            try? app.debugDescription.write(to: dir.appendingPathComponent("arbre-\(step)-\(what.prefix(30)).txt"), atomically: true, encoding: .utf8)
            return false
        }
        el.tap()
        return true
    }

    private func button(_ label: String) -> XCUIElement { any("label == %@ AND elementType IN {9, 75, 48}", label) }

    private func allowCalendar() {
        let allow = springboard.alerts.buttons.matching(NSPredicate(
            format: "label IN {'Autoriser l’accès complet', 'Autoriser l\\'accès complet', 'Allow Full Access', 'OK', 'Autoriser'}")).firstMatch
        for _ in 0..<3 where allow.waitForExistence(timeout: 6) { sleep(1); if allow.exists { allow.tap() }; sleep(1) }
    }

    private func signIn() {
        launch()
        let tab = app.tabBars.buttons.matching(NSPredicate(format: "label IN {'Réglages', 'Se connecter'}")).firstMatch
        XCTAssertTrue(tab.waitForExistence(timeout: 40), "onglet Réglages")
        // Onglet « Se connecter » = pas encore connecté (app réinstallée) : on attend la page, qui peut tarder plus de 2 s.
        let needsLogin = tab.label == "Se connecter"
        tab.tap()
        sleep(2)
        guard needsLogin || app.staticTexts["Se connecter"].exists else { return }
        XCTAssertTrue(app.staticTexts["Se connecter"].firstMatch.waitForExistence(timeout: 20), "page de connexion")
        app.staticTexts["Se connecter"].firstMatch.tap()
        let field = app.textFields["login-phone"]
        XCTAssertTrue(field.waitForExistence(timeout: 10), "champ du numéro")
        field.tap()
        app.typeText("0790000001")
        app.sendLoginCode()
        let code = app.textFields["login-code"]
        XCTAssertTrue(code.waitForExistence(timeout: 20), "champ du code")
        code.tap()
        app.typeText("123456")
        // Le prénom du compte de recette change sur la base de TEST (« Agenda Léa ») : on attend la ligne « Mon profil ».
        XCTAssertTrue(app.descendants(matching: .any).matching(NSPredicate(format: "label CONTAINS 'Mon profil'")).firstMatch.waitForExistence(timeout: 30), "connecté (Testeur 1)")
        sleep(3)
        app.terminate()
        launch()
    }

    private func openFromSettings(shotName: String? = nil) {
        XCTAssertTrue(app.tabBars.buttons["Réglages"].waitForExistence(timeout: 40), "onglet Réglages")
        app.tabBars.buttons["Réglages"].tap()
        sleep(3)
        let row = app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", "Agenda, ")).firstMatch
        for _ in 0..<10 where !(row.exists && row.isHittable) { app.swipeUp(velocity: .slow); sleep(1) }
        XCTAssertTrue(row.waitForExistence(timeout: 20), "Réglages › Autres apps › Agenda")
        if let shotName { shot(shotName) }
        row.tap()
        XCTAssertTrue(any("label CONTAINS 'Qui est libre' OR label CONTAINS 'Ton agenda Party'").waitForExistence(timeout: 30), "Agenda ouvert")
        XCTAssertFalse(any("label CONTAINS 'Page introuvable'").exists)
        sleep(2)
    }

    private func back() {
        let b = any("label BEGINSWITH '‹' OR label BEGINSWITH 'Retour' OR identifier == 'top-back'")
        if b.exists && b.isHittable { b.tap() } else { app.swipeRight() }
        sleep(2)
    }

    func testEveryAgendaJourney() {
        signIn()
        // 1. Réglages › Autres apps › Agenda ; le tutoriel s'ouvre (5 cartes), « Passer » le ferme pour cette fois.
        openFromSettings(shotName: "reglages-ligne-agenda")
        XCTAssertTrue(any("label CONTAINS 'Ton agenda Party'").waitForExistence(timeout: 20), "tutoriel à l'arrivée")
        shot("tuto-carte-1")
        for n in 2...5 { reach(button("Suivant"), "Suivant \(n)"); sleep(1); shot("tuto-carte-\(n)") }
        reach(button("Plus tard"), "Plus tard (fin du tutoriel)")
        sleep(2)
        XCTAssertFalse(any("label CONTAINS 'Ton agenda Party'").exists, "tutoriel fermé")
        shot("accueil-semaine")

        // 2. Vues : semaine (par défaut), jour, mois.
        for v in ["Jour", "Mois", "Semaine"] {
            reach(any("label == %@", v), v)
            sleep(2)
            shot("vue-\(v.lowercased())")
        }

        // 3. Ajouter un rendez-vous, l'ouvrir, le supprimer.
        reach(any("label == 'Nouveau rendez-vous'"), "+ Ajouter")
        let title = any("label == 'Titre du rendez-vous' AND elementType IN {49, 50}")
        XCTAssertTrue(title.waitForExistence(timeout: 15), "titre du rendez-vous")
        shot("nouveau-rendez-vous")
        title.tap()
        app.typeText("Recette dentiste")
        let done = app.buttons.matching(NSPredicate(format: "label IN {'Terminé', 'Done', 'OK'}")).firstMatch
        if done.exists { done.tap() } else { any("label == 'JOUR'").tap() }
        sleep(1)
        reach(any("label BEGINSWITH 'Plus d’options'"), "Plus d'options")
        sleep(1)
        shot("nouveau-rendez-vous-options")
        reach(any("label == 'Ajouter le rendez-vous'"), "Ajouter le rendez-vous")
        sleep(3)
        let item = any("label CONTAINS 'Recette dentiste'")
        XCTAssertTrue(item.waitForExistence(timeout: 15), "rendez-vous dans la semaine")
        shot("rendez-vous-ajoute")
        reach(item, "ouvrir le rendez-vous")
        sleep(2)
        shot("rendez-vous-ouvert")
        reach(any("label == 'Supprimer le rendez-vous'"), "Supprimer le rendez-vous")
        sleep(1)
        shot("supprimer-confirmer")
        reach(button("Supprimer"), "Supprimer (confirmer)")
        sleep(3)
        XCTAssertFalse(any("label CONTAINS 'Recette dentiste'").exists, "rendez-vous supprimé")
        shot("rendez-vous-supprime")

        // 4. Calendriers : relier l'iPhone (demande d'iOS), calendriers de l'iPhone visibles.
        reach(any("label BEGINSWITH 'Calendriers'"), "Calendriers")
        sleep(2)
        shot("calendriers")
        let iphone = any("label == 'Relier' OR label == 'Pas relié Relier'")
        if iphone.waitForExistence(timeout: 5) {
            reach(iphone, "Relier l'iPhone")
            sleep(2)
            shot("calendriers-explication-iphone")
            let go = button("Continuer")
            if go.waitForExistence(timeout: 5) { go.tap() }
            allowCalendar()
            sleep(3)
        }
        app.swipeUp(velocity: .slow); sleep(1)
        shot("calendriers-iphone")
        XCTAssertTrue(any("label CONTAINS[c] 'iphone · ' OR label CONTAINS[c] 'iphone · relié'").waitForExistence(timeout: 10), "calendriers de l'iPhone")

        // 5. Partager mes dispos, groupe par groupe.
        app.swipeDown(velocity: .fast); app.swipeDown(velocity: .fast); sleep(1)
        reach(any("label == '📤 Partager'"), "onglet Partager")
        sleep(2)
        shot("partage-onglet")
        let shareBtn = any("label CONTAINS 'Partager mes dispos' OR label == 'Modifier'")
        reach(shareBtn, "Partager mes dispos")
        sleep(2)
        shot("partage")
        let group = any("label BEGINSWITH '[QA] Qui est libre 2311'")
        if group.waitForExistence(timeout: 10) && !(group.value as? String ?? "").contains("1") {
            shot("partage-groupe")
        }
        let save = any("label BEGINSWITH 'Partager avec' OR label BEGINSWITH 'Enregistrer'")
        if save.waitForExistence(timeout: 5) { reach(save, "Partager avec …"); sleep(3) }
        shot("partage-enregistre")
        back()

        // 6. Qui est libre ? : mois, feuille d'un jour, Organiser, Faire voter.
        openFromSettings()
        let skip = button("Passer")
        if skip.waitForExistence(timeout: 5) { skip.tap(); sleep(1) }
        reach(any("label CONTAINS 'Qui est libre'"), "Qui est libre ?")
        let qa = any("label == '[QA] Qui est libre 2311'")
        reach(qa, timeout: 30, "bulle du groupe de recette")
        XCTAssertTrue(any("label BEGINSWITH 'Le mieux'").waitForExistence(timeout: 30), "le meilleur jour")
        sleep(2)
        shot("qui-est-libre-mois")
        reach(any("label BEGINSWITH 'Le mieux : '"), "case du meilleur jour")
        let organise = any("label BEGINSWITH 'Organiser le'")
        XCTAssertTrue(organise.waitForExistence(timeout: 15), "feuille du jour")
        sleep(1)
        shot("qui-est-libre-feuille-jour")
        organise.tap()
        sleep(4)
        shot("organiser-nouvel-evenement")
        app.terminate()
        launch()
        openFromSettings()
        if skip.waitForExistence(timeout: 5) { skip.tap(); sleep(1) }
        reach(any("label CONTAINS 'Qui est libre'"), "Qui est libre ? (2)")
        reach(qa, timeout: 30, "bulle du groupe (2)")
        sleep(2)
        reach(any("label == '🗳️ Faire voter le groupe'"), "Faire voter")
        sleep(1)
        shot("faire-voter-3-dates")
        reach(any("label BEGINSWITH '🗳️ Faire voter le groupe ('"), "Faire voter (n dates)")
        sleep(4)
        shot("faire-voter-sondage")

        // 7. Lien de dispo : explication, réglages (durées, délai, calendriers, adresse lisible), copier, partager.
        app.terminate()
        launch()
        openFromSettings()
        if skip.waitForExistence(timeout: 5) { skip.tap(); sleep(1) }
        reach(any("label BEGINSWITH 'Calendriers'"), "Calendriers (liens)")
        sleep(2)
        reach(any("label == '📤 Partager'"), "onglet Partager (liens)")
        sleep(2)
        reach(any("label BEGINSWITH 'Mes liens de dispo'"), "Mes liens de dispo")
        sleep(2)
        shot("liens")
        let newLink = any("label == 'Créer un lien' OR label == '+ Nouveau lien'")
        reach(newLink, "Créer un lien")
        sleep(2)
        shot("lien-explication")
        reach(button("J’ai compris, continuer"), "J'ai compris, continuer")
        sleep(2)
        shot("lien-reglages-haut")
        // Un nom (et donc une adresse) neuf à chaque passage : « jours-de-semaine » existe déjà après le premier.
        let linkName = any("label == 'Nom du lien (pour toi)' AND elementType IN {49, 50}")
        if reach(linkName, "Nom du lien") {
            linkName.coordinate(withNormalizedOffset: CGVector(dx: 0.97, dy: 0.5)).tap()  // curseur après le texte
            let stamp = DateFormatter()
            stamp.dateFormat = "HHmmss"
            app.typeText(" \(stamp.string(from: Date()))")
            let done = app.buttons.matching(NSPredicate(format: "label IN {'Terminé', 'Done', 'OK'}")).firstMatch
            if done.exists { done.tap() }
            sleep(1)
        }
        reach(any("label BEGINSWITH 'Demandes de rendez-vous'"), "Demandes de rendez-vous")
        sleep(1)
        shot("lien-demandes")
        let d1h = any("label == '1 h'")
        if d1h.exists && d1h.isHittable { d1h.tap() }
        shot("lien-durees-delai")
        app.swipeUp(velocity: .slow); sleep(1)
        shot("lien-champs")
        app.swipeUp(velocity: .slow); sleep(1)
        shot("lien-adresse")
        app.swipeUp(velocity: .slow); sleep(1)
        shot("lien-calendriers")
        app.swipeUp(velocity: .slow); sleep(1)
        shot("lien-marges-apercu")
        reach(button("Créer le lien"), "Créer le lien")
        sleep(4)
        shot("lien-cree")
        let copy = any("label == 'Copier'")
        if reach(copy, "Copier") { sleep(1); shot("lien-copie") }
        let share = any("label == 'Partager'")
        if reach(share, "Partager") {
            sleep(3)
            shot("lien-feuille-partage")
            let close = app.buttons.matching(NSPredicate(format: "label IN {'Fermer', 'Close', 'Annuler', 'Cancel'}")).firstMatch
            if close.waitForExistence(timeout: 5) { close.tap() } else { app.swipeDown(velocity: .fast) }
            sleep(1)
        }
        back()
        sleep(1)
        shot("liens-apres")

        // 8. Demandes reçues.
        let req = any("label BEGINSWITH 'Demandes de rendez-vous'")
        if req.waitForExistence(timeout: 5) { reach(req, "Demandes de rendez-vous"); sleep(2); shot("demandes") }

        // 9. Revoir le tutoriel, depuis l'accueil de l'Agenda.
        app.terminate()
        launch()
        openFromSettings()
        if skip.waitForExistence(timeout: 5) { skip.tap(); sleep(1) }
        let again = any("label CONTAINS 'Revoir le tutoriel'")
        if reach(again, "Revoir le tutoriel") {
            XCTAssertTrue(any("label CONTAINS 'Ton agenda Party'").waitForExistence(timeout: 10), "tutoriel revu")
            sleep(1)
            shot("tuto-revu")
        }
    }
}

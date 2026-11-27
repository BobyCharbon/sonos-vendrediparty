import XCTest

/// Parcours « comme un examinateur Apple » (revue du 19.11.2026), en configuration Release, serveur Party local branché sur
/// la base de TEST avec les drapeaux de la prod (Agenda, Pronos et Zicou éteints). Chaque écran est photographié avec son
/// arbre d'accessibilité dans EXAM_DIR ; tout texte suspect (« undefined », « NaN », « Bientôt », Agenda / Pronos / Zicou,
/// message d'erreur brut en anglais) fait échouer le test et s'écrit dans anomalies.txt.
///   TEST_RUNNER_EXAM_DIR=… [TEST_RUNNER_EXAM_PHONE=0790000008] xcodebuild test -configuration Release ENABLE_TESTABILITY=YES
///   PARTY_SWIFT_CONDITIONS=E2E_HOOKS PARTY_BASE_URL=http://127.0.0.1:<port> -only-testing:PartyUITests/ParcoursExaminateurUITests
/// testNewAccount crée un compte (numéro de test à code fixe), le complète, puis le SUPPRIME (Réglages › Gérer mon compte).
final class ParcoursExaminateurUITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment
    private var dir: URL!
    private var app: XCUIApplication!
    private var step = 0

    /// Textes qu'un examinateur ne doit jamais voir (fonctions éteintes en prod, valeurs JS, erreurs brutes).
    static let suspicious = ["undefined", "NaN", "[object Object]", "Bientôt", "Pronos", "Zicou", "Compagnon",
                             "Invalid Date", "The operation couldn", "The Internet connection", "Error Domain",
                             "Could not connect", "TypeError"]

    override func setUpWithError() throws {
        guard let path = env["EXAM_DIR"] else { throw XCTSkip("Parcours à la demande (EXAM_DIR)") }
        dir = URL(fileURLWithPath: path)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        continueAfterFailure = true
        addUIInterruptionMonitor(withDescription: "Alertes d'iOS") { alert in
            for label in ["Autoriser", "Allow", "OK", "Autoriser l’accès complet"] where alert.buttons[label].exists {
                alert.buttons[label].tap()
                return true
            }
            return false
        }
    }

    // MARK: Outils

    private func record(_ name: String) {
        step += 1
        let base = String(format: "%02d-%@", step, name)
        sleep(1)
        try? app.screenshot().pngRepresentation.write(to: dir.appendingPathComponent("\(base).png"))
        let tree = app.debugDescription
        try? tree.write(to: dir.appendingPathComponent("\(base).txt"), atomically: true, encoding: .utf8)
        for word in Self.suspicious {
            // Les identifiants de code (accessibilityIdentifier) ne sont pas lus : seulement les libellés et valeurs.
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

    private func launch(fresh: Bool = false) {
        app = XCUIApplication()
        var js = "localStorage.setItem('vp_install_dismissed','1');"
        if fresh { js = "if(!sessionStorage.exam){sessionStorage.exam='1';localStorage.clear();}" }
        app.launchEnvironment["PARTY_DEBUG_JS"] = js
        app.launchEnvironment["PARTY_CLEAR_CHATS_CACHE"] = "1"
        app.launch()
    }

    private func tab(_ label: String) -> XCUIElement {
        app.tabBars.buttons[label].exists ? app.tabBars.buttons[label]
            : app.buttons.matching(NSPredicate(format: "label == %@", label)).firstMatch
    }

    private func visitTab(_ label: String, _ name: String, wait: UInt32 = 4) {
        let button = tab(label)
        guard button.waitForExistence(timeout: 20) else { return XCTFail("onglet \(label) absent") }
        button.tap()
        sleep(wait)
        record(name)
    }

    private func signIn(_ phone: String) {
        let settings = app.buttons.matching(NSPredicate(format: "label IN {'Réglages', 'Se connecter'}")).firstMatch
        XCTAssertTrue(settings.waitForExistence(timeout: 30), "onglet Réglages / Se connecter")
        settings.tap()
        sleep(2)
        let row = app.staticTexts["Se connecter"].firstMatch
        if row.exists, row.isHittable, !app.textFields["login-phone"].exists { row.tap() }
        let field = app.textFields["login-phone"]
        XCTAssertTrue(field.waitForExistence(timeout: 15), "champ du numéro")
        field.tap()
        app.typeText(phone)
        record("connexion-numero")
        app.sendLoginCode()
        let code = app.textFields["login-code"]
        XCTAssertTrue(code.waitForExistence(timeout: 30), "champ du code")
        code.tap()
        app.typeText("123456")
        sleep(6)
        record("connexion-apres-code")
    }

    private func scrollAndRecord(_ name: String, pages: Int = 3) {
        for i in 1...pages {
            app.swipeUp(velocity: .slow)
            sleep(1)
            record("\(name)-bas-\(i)")
        }
        for _ in 0..<pages { app.swipeDown(velocity: .fast) }
    }

    /// Réglages › une ligne : ouverte, photographiée (3 s), puis retour aux Réglages.
    private func openSettingsRow(_ title: String) {
        tab("Réglages").tap()
        for _ in 0..<4 where app.navigationBars.buttons["Réglages"].exists { app.navigationBars.buttons["Réglages"].tap() }
        for _ in 0..<4 where app.navigationBars.buttons["BackButton"].exists { app.navigationBars.buttons["BackButton"].tap() }
        for _ in 0..<3 { app.swipeDown(velocity: .fast) }
        let cell = app.staticTexts[title].firstMatch
        let barTop = app.tabBars.firstMatch.exists ? app.tabBars.firstMatch.frame.minY : app.frame.maxY
        for _ in 0..<8 where !(cell.exists && cell.isHittable && cell.frame.maxY < barTop - 8) { app.swipeUp(velocity: .slow) }
        guard cell.exists else { return record("absent-\(title)") }
        cell.tap()
        sleep(4)
        record("page-\(title)")
        if app.alerts.firstMatch.exists { app.alerts.buttons.firstMatch.tap() }
        let close = app.buttons.matching(NSPredicate(format: "label IN {'Fermer', 'OK', 'Terminé'}")).firstMatch
        if !app.navigationBars.buttons["Réglages"].exists, close.exists, close.isHittable { close.tap(); sleep(1) }
    }

    // MARK: 1. Compte neuf : premier lancement, connexion SMS, profil, CGU, onglets, suppression du compte

    func testNewAccount() {
        let phone = env["EXAM_PHONE"] ?? "0790000008"
        launch(fresh: true)
        sleep(8)
        record("premier-lancement")
        // App App Store : pas d'onglet Musique (refus 1.4.3, on la rejoint par Jeux › Code).
        for (label, name) in [("Jeux", "visiteur-jeux"), ("Événements", "visiteur-evenements")] {
            visitTab(label, name)
        }
        signIn(phone)
        // Compte neuf : Réglages › « Profil à compléter » (prénom, nom, surnom ; CGU au premier surnom).
        let row = app.staticTexts["Profil à compléter"].firstMatch
        if row.waitForExistence(timeout: 20) {
            row.tap()
            let first = app.collectionViews.textFields["profile-first"].firstMatch
            XCTAssertTrue(first.waitForExistence(timeout: 15), "fiche du profil")
            record("profil-a-remplir")
            first.tap(); app.typeText("Examen")
            app.collectionViews.textFields["profile-last"].firstMatch.tap(); app.typeText("Apple")
            app.collectionViews.textFields["profile-nickname"].firstMatch.tap(); app.typeText("Examen QA")
            // Simulateur neuf : la bulle d'iOS sur la saisie glissée (« Continue ») couvre le clavier ; on la ferme.
            let tip = app.buttons.matching(NSPredicate(format: "label IN {'Continue', 'Continuer'}")).firstMatch
            if tip.exists { tip.tap() }
            record("profil-rempli")
            app.buttons["Enregistrer"].firstMatch.tap()
            let accept = app.buttons["terms-accept"]
            if accept.waitForExistence(timeout: 10) { record("cgu"); accept.tap() }
            sleep(4)
            record("profil-enregistre")
            if tip.exists { tip.tap() }
            if app.navigationBars.buttons["BackButton"].exists { app.navigationBars.buttons["BackButton"].tap() }
            sleep(1)
        } else {
            record("profil-introuvable")
            XCTFail("« Profil à compléter » absent après la connexion d'un compte neuf")
        }
        for (label, name) in [("Jeux", "membre-jeux"), ("Événements", "membre-evenements"),
                              ("Discussions", "membre-discussions"), ("Réglages", "membre-reglages")] {
            visitTab(label, name)
        }
        scrollAndRecord("membre-reglages")

        // Suppression du compte (Apple 5.1.1(v)) : Réglages › Gérer mon compte.
        tab("Réglages").tap()
        let manage = app.staticTexts["Gérer mon compte"].firstMatch
        for _ in 0..<8 where !(manage.exists && manage.isHittable) { app.swipeUp(velocity: .slow) }
        XCTAssertTrue(manage.exists, "« Gérer mon compte » dans les Réglages")
        manage.tap()
        sleep(2)
        record("gerer-mon-compte")
        let delete = app.buttons["delete-account"]
        for _ in 0..<6 where !(delete.exists && delete.isHittable) { app.swipeUp(velocity: .slow) }
        XCTAssertTrue(delete.exists, "« Supprimer mon compte »")
        let confirm = app.textFields["delete-confirm"]
        if confirm.exists {
            confirm.tap()
            app.typeText("SUPPRIMER")
        }
        record("suppression-prete")
        delete.tap()
        sleep(6)
        record("compte-supprime")
        XCTAssertTrue(tab("Se connecter").waitForExistence(timeout: 20), "déconnecté après la suppression")
    }

    // MARK: 1b. Code faux : l'erreur se voit au-dessus du pavé numérique (avant : cachée dessous, le code s'effaçait seul)

    func testAWrongCodeSaysSoAboveTheKeypad() {
        launch(fresh: true)
        let settings = app.buttons.matching(NSPredicate(format: "label IN {'Réglages', 'Se connecter'}")).firstMatch
        XCTAssertTrue(settings.waitForExistence(timeout: 30), "onglet Se connecter")
        settings.tap()
        sleep(2)
        let row = app.staticTexts["Se connecter"].firstMatch
        if row.exists, row.isHittable, !app.textFields["login-phone"].exists { row.tap() }
        let field = app.textFields["login-phone"]
        guard field.waitForExistence(timeout: 15) else { return XCTFail("champ du numéro (déjà connecté ?)") }
        field.tap()
        app.typeText("0790000003")  // VIP de test : jamais le compte Admin des recettes (un code par minute et par numéro)
        app.sendLoginCode()
        let code = app.textFields["login-code"]
        XCTAssertTrue(code.waitForExistence(timeout: 30), "champ du code")
        code.tap()
        app.typeText("000000")
        let error = app.descendants(matching: .any)["login-error"].firstMatch
        XCTAssertTrue(error.waitForExistence(timeout: 30), "message d'erreur du code")
        sleep(1)
        record("code-faux")
        let keyboard = app.keyboards.firstMatch
        if keyboard.exists {
            XCTAssertLessThanOrEqual(error.frame.maxY, keyboard.frame.minY, "l'erreur est sous le pavé numérique : \(error.frame)")
        }
        XCTAssertTrue(error.isHittable, "l'erreur est visible")
    }

    // MARK: 2. Compte de démo (Admin test) : chaque onglet, Discussions, Réglages en entier

    func testDemoAccountTabs() {
        launch()
        if !tab("Discussions").waitForExistence(timeout: 15) { signIn("0790000004") }
        for (label, name) in [("Jeux", "admin-jeux"), ("Événements", "admin-evenements"),
                              ("Discussions", "admin-discussions"), ("Réglages", "admin-reglages")] {
            visitTab(label, name, wait: 5)
            if app.buttons["Plus tard"].exists { app.buttons["Plus tard"].tap(); sleep(1) }
        }
        scrollAndRecord("admin-reglages", pages: 4)
        // Chaque page des Réglages, ouverte puis refermée (écran vide, texte suspect, bouton retour).
        for title in ["Notifications", "Groupes", "Mes amis dans Party", "Assistant IA", "Mes stats de jeu", "Pot commun",
                      "Confidentialité", "Connexions récentes", "Invités et messages", "Administration du groupe", "Gérer mon compte"] {
            openSettingsRow(title)
        }
        tab("Événements").tap()
        sleep(3)
        scrollAndRecord("admin-evenements", pages: 2)
        tab("Jeux").tap()
        sleep(3)
        scrollAndRecord("admin-jeux", pages: 2)
    }
}

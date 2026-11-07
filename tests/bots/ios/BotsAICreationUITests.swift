import XCTest

/// Campagne 2, agent 02 : « Créer avec l'IA » dans l'app iPhone (Release + E2E_HOOKS), contre le serveur du banc (base
/// de TEST). Le brouillon de l'IA est injecté (PARTY_DEBUG_AI_EVENT, pas de clé Anthropic) ; « Oui, continuer », l'étape
/// 2 et la publication passent par le vrai serveur. Lancé par tests/bots/ios_run_ia.sh, jamais sans BOTS_IOS_OUT.
/// BOTS_IOS_CASE : variantes (corriger, fermer, double, ouvrir, quitter-attente, valid) ; BOTS_IOS_CHOICE : invite,
/// group, public. Constats « BOTS: » dans le journal, captures dans BOTS_IOS_OUT.
final class BotsAICreationUITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment
    private var out: URL { URL(fileURLWithPath: env["BOTS_IOS_OUT"] ?? NSTemporaryDirectory()) }
    private var notes: [String] = []
    private var step = 0
    private var kase: String { env["BOTS_IOS_CASE"] ?? "" }

    override func setUpWithError() throws {
        continueAfterFailure = true
        try XCTSkipUnless(env["BOTS_IOS_OUT"] != nil, "Banc des bots : serveur local et base de TEST nécessaires")
        try? FileManager.default.createDirectory(at: out, withIntermediateDirectories: true)
    }

    override func tearDown() {
        try? notes.joined(separator: "\n").write(to: out.appendingPathComponent("constats.txt"), atomically: true, encoding: .utf8)
    }

    private func note(_ text: String) {
        notes.append("\(Date()) \(text)")
        print("BOTS: \(text)")
    }

    private func shot(_ app: XCUIApplication, _ name: String) {
        step += 1
        try? app.screenshot().pngRepresentation.write(to: out.appendingPathComponent(String(format: "%02d-%@.png", step, name)))
    }

    private func label(_ app: XCUIApplication, _ text: String) -> XCUIElement {
        app.descendants(matching: .any).matching(NSPredicate(format: "label == %@", text)).firstMatch
    }

    private func containing(_ app: XCUIApplication, _ text: String) -> XCUIElement {
        app.descendants(matching: .any).matching(NSPredicate(format: "label CONTAINS %@", text)).firstMatch
    }

    private func webButton(_ app: XCUIApplication, _ text: String) -> XCUIElement {
        app.webViews.buttons.matching(NSPredicate(format: "label == %@", text)).firstMatch
    }

    private func swipeWebUp(_ app: XCUIApplication) {
        let web = app.webViews.firstMatch
        web.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.8))
            .press(forDuration: 0.05, thenDragTo: web.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.35)),
                   withVelocity: .default, thenHoldForDuration: 0.1)
        Thread.sleep(forTimeInterval: 0.8)
    }

    private func reach(_ app: XCUIApplication, _ element: XCUIElement, web: Bool = true) -> Bool {
        for _ in 0..<8 where !(element.exists && element.isHittable) {
            if web { swipeWebUp(app) } else { app.swipeUp() }
        }
        return element.exists && element.isHittable
    }

    /// Textes visibles (lecture tolérante : un élément qui disparaît entre-temps est ignoré).
    private func texts(_ query: XCUIElementQuery, _ keep: (String) -> Bool = { $0.count > 12 }, most: Int = 10) -> [String] {
        var out: [String] = []
        let n = min(query.count, 150)
        for i in 0..<n where out.count < most {
            let e = query.element(boundBy: i)
            guard e.exists else { continue }
            let l = e.label
            if keep(l) { out.append(l) }
        }
        return out
    }

    private func check(_ ok: Bool, _ what: String) {
        note(ok ? "✅ \(what)" : "❌ \(what)")
    }

    /// Onglet natif « Événements » (barre d'onglets système, ou bouton du même nom).
    private func eventsTab(_ app: XCUIApplication) {
        let bar = app.tabBars.buttons["Événements"].firstMatch
        let any = app.buttons.matching(NSPredicate(format: "label == 'Événements'")).firstMatch
        if bar.waitForExistence(timeout: 40) { bar.tap() }
        else if any.waitForExistence(timeout: 5) { any.tap() }
        else { note("❌ onglet « Événements » introuvable") }
        Thread.sleep(forTimeInterval: 4)
    }

    private func launch(draft: String?) -> XCUIApplication {
        let app = XCUIApplication()
        if let draft, !draft.isEmpty {
            app.launchEnvironment["PARTY_DEBUG_AI_EVENT"] = draft
            app.launchEnvironment["PARTY_DEBUG_AI_SAID"] = "Soirée des bots chez moi, rue du Lac 12 à Vevey. J'invite Bot Max."
            app.launchEnvironment["PARTY_DEBUG_AI_PICK"] = "1"
        }
        app.launch()
        return app
    }

    /// Connexion par le vrai écran de l'onglet Événements (numéro de test, code fixe 123456) ; la session reste ensuite.
    func testLogin() {
        let app = launch(draft: nil)
        eventsTab(app)
        let phoneField = app.webViews.textFields["Ton numéro de téléphone"].firstMatch
        if phoneField.waitForExistence(timeout: 40) {
            phoneField.tap()
            phoneField.typeText(env["BOTS_IOS_PHONE"] ?? "0790000104")
            let code = app.webViews.textFields.matching(NSPredicate(format: "placeholderValue == '123456' OR label CONTAINS 'Code'")).firstMatch
            for _ in 0..<5 {
                webButton(app, "Recevoir un code par SMS").tap()
                if code.waitForExistence(timeout: 12) { break }
                note("pas de code (limite d'envoi), nouvel essai dans 45 s")
                Thread.sleep(forTimeInterval: 45)
            }
            code.tap()
            code.typeText("123456")
            webButton(app, "Se connecter").tap()
            Thread.sleep(forTimeInterval: 6)
        } else {
            note("déjà connecté")
        }
        let ai = app.webViews.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Créer un événement avec l'"))
            .firstMatch
        check(ai.waitForExistence(timeout: 20), "bouton « ✨ Avec l'IA » dans la liste des événements")
        shot(app, "liste-connecte")
    }

    /// Ouvre l'assistant depuis la liste (bouton « ✨ Avec l'IA »), sans brouillon injecté : accord IA, puis une phrase
    /// envoyée → l'IA est indisponible (pas de clé) ou le plafond est atteint : le message doit le dire.
    func testAssistantFromListUnavailable() {
        let app = launch(draft: nil)
        eventsTab(app)
        let ai = app.webViews.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Créer un événement avec l'")).firstMatch
        guard ai.waitForExistence(timeout: 25) else { return note("❌ bouton « ✨ Avec l'IA » introuvable") }
        ai.tap()
        check(label(app, "Étape 1 sur 3 : La soirée").waitForExistence(timeout: 10), "assistant ouvert, étape 1")
        shot(app, "assistant-conseils")
        let input = app.textViews["ai-text"].exists ? app.textViews["ai-text"] : app.textFields["ai-text"]
        guard input.waitForExistence(timeout: 5) else { shot(app, "pas-de-champ"); return note("❌ champ de saisie introuvable") }
        input.tap()
        input.typeText("Raclette des bots samedi à 19 h rue du Lac 12 à Vevey")
        app.buttons["Envoyer"].firstMatch.tap()
        // Accord IA (première fois pour ce compte) : « Pas maintenant » d'abord, puis « J'accepte » au 2e envoi.
        let accept = app.buttons["event-ai-accept"]
        if accept.waitForExistence(timeout: 8) {
            shot(app, "accord-ia")
            app.buttons["Pas maintenant"].tap()
            Thread.sleep(forTimeInterval: 1.5)
            shot(app, "accord-refuse")
            note("après « Pas maintenant » : \(texts(app.staticTexts, { $0.count > 20 }, most: 4))")
            app.buttons["Envoyer"].firstMatch.tap()
            if accept.waitForExistence(timeout: 8) { accept.tap() } else { note("❌ feuille d'accord pas reproposée au 2e envoi") }
        } else {
            note("pas de feuille d'accord (déjà donné)")
        }
        let message = containing(app, env["BOTS_IOS_EXPECT"] ?? "pas encore configuré")
        check(message.waitForExistence(timeout: 40), "message « \(env["BOTS_IOS_EXPECT"] ?? "pas encore configuré") » affiché")
        shot(app, "ia-indisponible")
        check(app.buttons["Recommencer"].exists, "« Recommencer » présent après l'erreur")
        note("textes : \(texts(app.staticTexts, most: 8))")
    }

    /// Étape 1 (récapitulatif, « C'est juste ? », Corriger…), « Oui, continuer », étape 2 (choix BOTS_IOS_CHOICE), étape 3.
    func testStepOneToThree() {
        let app = launch(draft: env["BOTS_IOS_DRAFT"])
        eventsTab(app)
        check(label(app, "Étape 1 sur 3 : La soirée").waitForExistence(timeout: 25), "étape 1 « La soirée »")
        shot(app, "etape1-haut")
        let proceed = app.buttons["ai-continue"]
        let correct = app.buttons["ai-correct"]
        _ = reach(app, correct, web: false)
        app.swipeUp()
        check(proceed.waitForExistence(timeout: 10), "« Oui, continuer »")
        check(app.staticTexts["C'est juste ?"].exists, "« C'est juste ? »")
        let deadline = Date().addingTimeInterval(20)
        while !proceed.isEnabled && Date() < deadline { RunLoop.current.run(until: Date().addingTimeInterval(0.3)) }
        check(proceed.isEnabled, "« Oui, continuer » actif (lieu confirmé)")
        note("textes de l'étape 1 : \(texts(app.staticTexts, { $0.contains("coché") || $0.contains("étape suivante") || $0.contains("Ensuite") }))")
        shot(app, "etape1-c-est-juste")

        if kase.contains("corriger") {
            correct.tap()
            let field = app.textViews["ai-text"].exists ? app.textViews["ai-text"] : app.textFields["ai-text"]
            check(field.waitForExistence(timeout: 5), "Corriger : le champ s'ouvre")
            field.typeText("Mets 20 places")
            app.buttons["Envoyer"].firstMatch.tap()
            check(containing(app, "pas encore configuré").waitForExistence(timeout: 40), "Corriger sans IA : « pas encore configuré » affiché")
            shot(app, "corriger-ia-indisponible")
            _ = reach(app, proceed, web: false)
            check(proceed.exists, "après l'échec de la correction, « Oui, continuer » reste là (brouillon gardé)")
            note("après correction : \(texts(app.staticTexts))")
            shot(app, "apres-correction")
        }
        if kase.contains("fermer") {  // quitter au milieu de l'étape 1, puis revenir par « ✨ Avec l'IA »
            app.buttons["Fermer"].firstMatch.tap()
            Thread.sleep(forTimeInterval: 2)
            shot(app, "ferme-etape1")
            let ai = app.webViews.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Créer un événement avec l'")).firstMatch
            if ai.waitForExistence(timeout: 15) { ai.tap() } else { note("❌ « ✨ Avec l'IA » introuvable après Fermer") }
            check(proceed.waitForExistence(timeout: 10) || reach(app, proceed, web: false), "rouvert : le brouillon de l'étape 1 est toujours là")
            shot(app, "rouvert-etape1")
        }

        _ = reach(app, proceed, web: false)
        if kase.contains("double") {  // deux touchers rapides au même endroit (le 2e arrive pendant l'enregistrement)
            let f = proceed.frame
            let point = app.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(dx: f.midX, dy: f.midY))
            point.tap()
            point.tap()
            note("double toucher envoyé sur « Oui, continuer »")
        } else {
            proceed.tap()
        }
        let accept = app.buttons["terms-accept"]
        if accept.waitForExistence(timeout: 4) {
            shot(app, "cgu")
            accept.tap()
            note("CGU acceptées")
        }
        if kase.contains("quitter-attente") {  // « Fermer » pendant « Brouillon enregistré » (avant l'ouverture de l'étape 2)
            let saved = containing(app, "Brouillon enregistré")
            check(saved.waitForExistence(timeout: 30), "« Brouillon enregistré »")
            app.buttons["Fermer"].firstMatch.tap()
            Thread.sleep(forTimeInterval: 4)
            shot(app, "ferme-pendant-attente")
            check(!label(app, "Étape 2 sur 3 : Qui est invité").exists, "Fermer : l'étape 2 ne s'ouvre pas d'elle-même")
            note("écran après Fermer : \(texts(app.webViews.staticTexts, { !$0.isEmpty }, most: 12))")
            return
        }
        if kase.contains("ouvrir") {  // « Ouvrir l'événement » (finir à la main) puis « Inviter et publier »
            let open = app.buttons["ai-open-event"]
            check(open.waitForExistence(timeout: 30), "« Ouvrir l'événement » sous « Brouillon enregistré »")
            shot(app, "brouillon-enregistre")
            open.tap()
            let publish = webButton(app, "Inviter et publier")
            check(publish.waitForExistence(timeout: 25), "fiche du brouillon : « Inviter et publier »")
            shot(app, "fiche-brouillon")
            _ = reach(app, publish)
            publish.tap()
        }
        let step2 = label(app, "Étape 2 sur 3 : Qui est invité")
        check(step2.waitForExistence(timeout: 60), "étape 2 « Qui est invité » ouverte")
        Thread.sleep(forTimeInterval: 5)
        check(step2.exists, "étape 2 toujours ouverte après 5 s")
        shot(app, "etape2")
        publish(app)
    }

    private func publish(_ app: XCUIApplication) {
        let valid = kase.contains("valid")
        let choice = env["BOTS_IOS_CHOICE"] ?? "invite"
        switch choice {
        case "group":
            let group = webButton(app, "👥 Un groupe")
            _ = reach(app, group)
            group.tap()
            Thread.sleep(forTimeInterval: 1)
            shot(app, "un-groupe")
            let toggle = app.webViews.switches["Prévenir le groupe"].firstMatch
            if reach(app, toggle) { toggle.tap(); note("« Prévenir le groupe » allumé") } else { note("❌ interrupteur « Prévenir le groupe » introuvable") }
            Thread.sleep(forTimeInterval: 1)
            note("phrase : \(texts(app.webViews.staticTexts, { $0.contains("groupe") }, most: 4))")
            shot(app, "prevenir-le-groupe")
            let go = webButton(app, valid ? "Envoyer pour validation" : "Publier pour « Bots »")
            let all = app.webViews.buttons.matching(NSPredicate(format: "label == %@", valid ? "Envoyer pour validation" : "Publier pour « Bots »"))
            let target = all.count > 1 ? all.element(boundBy: all.count - 1) : go
            if reach(app, target) { target.tap() } else { note("❌ bouton de publication du groupe introuvable") }
        default:
            let titles = ["invite": "✉️ Sur invitation seulement", "public": "🌍 Public + lien public"]
            let actions = ["invite": "Publier et envoyer le lien", "public": "Publier"]
            let name = "\(titles[choice] ?? titles["invite"]!) : \(valid ? "Envoyer pour validation" : actions[choice] ?? "Publier")"
            let option = webButton(app, name)
            if reach(app, option) { option.tap() } else { note("❌ « \(name) » introuvable") }
        }
        Thread.sleep(forTimeInterval: 4)
        shot(app, "apres-choix")
        if valid {
            check(label(app, "Envoyé pour validation").waitForExistence(timeout: 30), "« Envoyé pour validation »")
        } else if choice == "invite" {
            check(label(app, "C’est en ligne : envoie le lien à tes invités").waitForExistence(timeout: 30), "« C'est en ligne : envoie le lien »")
            check(webButton(app, "Partager le lien…").waitForExistence(timeout: 10), "« Partager le lien… »")
            check(webButton(app, "Retirer Bot Max").exists, "Bot Max coché d'avance (cité à l'IA)")
            shot(app, "feuille-inviter")
            let qr = webButton(app, "QR code")
            if qr.exists { qr.tap() }
            check(app.webViews.images["QR code du lien d’invitation"].waitForExistence(timeout: 20), "QR du lien")
            shot(app, "qr")
        } else {
            check(label(app, "C’est en ligne !").waitForExistence(timeout: 30), "« C'est en ligne ! »")
        }
        shot(app, "etape3")
        note("textes étape 3 : \(texts(app.webViews.staticTexts))")
    }
}

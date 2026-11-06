import XCTest

/// Banc des bots (tests/bots) : parcours organisateur dans l'app iPhone (configuration Release) contre le serveur
/// local branché sur la base de TEST. Copié dans PartyUITests par tests/bots/ios_run.sh, jamais dans le dépôt de l'app.
/// Session de Bot Olga passée par BOTS_IOS_SESSION ; captures et constats dans BOTS_IOS_OUT.
/// Gestes : vrais glissements du doigt (press + drag), pas de défilement programmé.
final class BotsOrganizerUITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment
    private var out: URL { URL(fileURLWithPath: env["BOTS_IOS_OUT"] ?? NSTemporaryDirectory()) }
    private var notes: [String] = []
    private var step = 0

    override func setUpWithError() throws {
        continueAfterFailure = true
        try XCTSkipUnless(env["BOTS_IOS_SESSION"] != nil, "Banc des bots : session et serveur local nécessaires")
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
        let file = out.appendingPathComponent(String(format: "%02d-%@.png", step, name))
        try? app.screenshot().pngRepresentation.write(to: file)
    }

    private func any(_ app: XCUIApplication, _ predicate: String) -> XCUIElement {
        app.webViews.descendants(matching: .any).matching(NSPredicate(format: predicate)).firstMatch
    }

    /// Glisse le doigt de bas en haut dans la vue web (zone donnée en fractions de l'écran).
    private func swipeUp(_ app: XCUIApplication, from: CGFloat = 0.8, to: CGFloat = 0.35) {
        let web = app.webViews.firstMatch
        let a = web.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: from))
        let b = web.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: to))
        a.press(forDuration: 0.05, thenDragTo: b, withVelocity: .default, thenHoldForDuration: 0.1)
        Thread.sleep(forTimeInterval: 0.8)
    }

    private func onScreen(_ app: XCUIApplication, _ element: XCUIElement) -> Bool {
        guard element.exists else { return false }
        let f = element.frame, screen = app.windows.firstMatch.frame
        return f.minY >= screen.minY && f.maxY <= screen.maxY - 40 && f.height > 0
    }

    func testOrganizerInviteSheetAndFormScrollWithTheFinger() throws {
        let app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_JS"] =
            "localStorage.setItem('sb-ewromqfsmcqsthftyhzm-auth-token', \(env["BOTS_IOS_SESSION"]!));"
            + "localStorage.setItem('vp_tab','events');localStorage.setItem('vp_install_dismissed','1');localStorage.setItem('vp_name','Bot Olga')"
        app.launch()
        let title = env["BOTS_IOS_EVENT_TITLE"] ?? "Bot Soirée complète"
        // Barre d'onglets native (UITabBar) : onglet « Événements » (la vue web y charge le module).
        let tab = app.tabBars.buttons["Événements"].firstMatch
        if tab.waitForExistence(timeout: 20) { tab.tap() } else { note("onglet natif « Événements » introuvable") }
        Thread.sleep(forTimeInterval: 4)
        shot(app, "onglet-evenements")
        // Pas de session reprise : connexion comme un vrai utilisateur (numéro de test, code fixe 123456).
        let phoneField = app.webViews.textFields["Ton numéro de téléphone"].firstMatch
        if phoneField.waitForExistence(timeout: 10) {
            phoneField.tap()
            phoneField.typeText(env["BOTS_IOS_PHONE"] ?? "0790000103")
            app.webViews.buttons["Recevoir un code par SMS"].firstMatch.tap()
            let code = app.webViews.textFields.matching(NSPredicate(format: "placeholderValue == '123456' OR label CONTAINS 'Code'")).firstMatch
            if code.waitForExistence(timeout: 60) {
                code.tap()
                code.typeText("123456")
                shot(app, "code")
                app.webViews.buttons["Se connecter"].firstMatch.tap()
                Thread.sleep(forTimeInterval: 5)
            } else {
                note("❌ champ du code SMS introuvable")
            }
            shot(app, "connecte")
        }

        // 1. Liste des événements → la fiche de l'événement complet
        let card = any(app, "label BEGINSWITH '\(title)'")
        for _ in 0..<8 where !(card.exists && card.isHittable) { swipeUp(app) }
        shot(app, "liste")
        guard card.waitForExistence(timeout: 40) else {
            note("❌ fiche « \(title) » introuvable dans la liste"); shot(app, "liste-sans-fiche"); return
        }
        card.tap()
        let invite = app.webViews.buttons["Inviter"]
        guard invite.waitForExistence(timeout: 30) else { note("❌ bouton « Inviter » absent de la fiche"); shot(app, "fiche"); return }
        shot(app, "fiche")

        // 2. Feuille « Inviter » : le bas (« Ajouter des gens de Party », groupes) doit venir au doigt.
        for _ in 0..<4 where !invite.isHittable { swipeUp(app) }
        invite.tap()
        Thread.sleep(forTimeInterval: 1.5)
        shot(app, "feuille-inviter")
        let bottom = any(app, "label CONTAINS 'reçoivent une notification Party' OR label CONTAINS 'Ajouter Bots 2' OR label == 'GROUPES'")
        let search = any(app, "label == 'Chercher une personne ou un groupe'")
        let startY = search.exists ? search.frame.minY : -1
        note("feuille Inviter : champ de recherche à y=\(startY), bas visible=\(onScreen(app, bottom))")
        var moved = false
        for i in 0..<5 {
            swipeUp(app, from: 0.85, to: 0.4)
            shot(app, "feuille-inviter-doigt-\(i + 1)")
            let y = search.exists ? search.frame.minY : -1
            if y >= 0 && startY >= 0 && y < startY - 20 { moved = true }
            if onScreen(app, bottom) { break }
        }
        note(moved ? "✅ feuille Inviter : défile au doigt" : "❌ feuille Inviter : NE DÉFILE PAS au doigt (champ toujours à y=\(startY))")
        note(onScreen(app, bottom) ? "✅ feuille Inviter : bas de la feuille atteint" : "❌ feuille Inviter : bas de la feuille jamais atteint")
        // Même feuille, clavier ouvert (recherche « Bot ») : la liste de résultats doit encore défiler au doigt.
        if search.exists {
            search.tap()
            search.typeText("Bot")
            Thread.sleep(forTimeInterval: 1.5)
            shot(app, "feuille-inviter-clavier")
            let lastHit = any(app, "label BEGINSWITH 'Ajouter Bot'")
            let before = lastHit.exists ? lastHit.frame.minY : -1
            swipeUp(app, from: 0.45, to: 0.2)
            shot(app, "feuille-inviter-clavier-doigt")
            let after = lastHit.exists ? lastHit.frame.minY : -1
            note(before != after ? "✅ feuille Inviter, clavier ouvert : la liste défile (\(before) → \(after))"
                                 : "❌ feuille Inviter, clavier ouvert : rien ne bouge au doigt (\(before))")
        }
        let close = app.webViews.buttons["Fermer"].firstMatch
        if close.exists { close.tap() }
        Thread.sleep(forTimeInterval: 1)

        // 3. Fiche : jusqu'en bas (zone organisateur)
        let zone = any(app, "label == 'Annuler l’événement'")
        for _ in 0..<15 where !onScreen(app, zone) { swipeUp(app) }
        shot(app, "fiche-bas")
        note(onScreen(app, zone) ? "✅ fiche : zone organisateur atteinte au doigt" : "❌ fiche : zone organisateur jamais atteinte")

        // 4. Formulaire « Proposer » : jusqu'au bouton Publier
        let back = app.webViews.buttons["Retour : Événements"]
        if back.exists { back.tap() }
        let propose = app.webViews.buttons["Proposer un événement"]
        // Liste défilée : « + Proposer » effacé doit être SORTI de l'arbre d'accessibilité (bug 3 : VoiceOver l'activait
        // et touchait ce qu'il y avait derrière). Puis on remonte la liste : il revient, on le touche.
        Thread.sleep(forTimeInterval: 2)
        for _ in 0..<4 { swipeUp(app) }
        Thread.sleep(forTimeInterval: 1)
        note(propose.exists ? "❌ « + Proposer » effacé mais encore dans l'arbre d'accessibilité" : "✅ « + Proposer » effacé : hors de l'arbre d'accessibilité")
        for _ in 0..<4 where !propose.exists { swipeUp(app, from: 0.35, to: 0.8) }
        if propose.waitForExistence(timeout: 15) {
            Thread.sleep(forTimeInterval: 2)
            propose.tap()
            Thread.sleep(forTimeInterval: 2)
            if !app.webViews.textFields["Titre"].exists {
                note("❌ « + Proposer » touché mais le formulaire ne s'ouvre pas (1er essai)")
                shot(app, "proposer-sans-effet")
                propose.tap()
            }
            Thread.sleep(forTimeInterval: 2)
            shot(app, "formulaire")
            let publish = app.webViews.buttons["Publier"]
            for _ in 0..<15 where !onScreen(app, publish) { swipeUp(app) }
            shot(app, "formulaire-bas")
            note(onScreen(app, publish) ? "✅ formulaire : « Publier » atteint au doigt" : "❌ formulaire : « Publier » jamais atteint")
        } else {
            note("❌ bouton « Proposer un événement » absent")
        }
    }
}

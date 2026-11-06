import XCTest

/// VRAI essai de la feuille « Inviter » (bug de l'admin du 06.11 : la feuille ne défilait pas au doigt dans l'app iPhone,
/// impossible d'atteindre « Ajouter des gens de Party », les groupes ni le bas). Lancé à la main contre un serveur Party
/// local branché sur la base de TEST, invitations v2 allumées : app construite avec PARTY_BASE_URL=http://127.0.0.1:<port>,
/// session du compte de test et événement publié passés par l'environnement (TEST_RUNNER_SHEET_SESSION,
/// TEST_RUNNER_SHEET_EVENT ; SHEET_AUTO=1 : ouverte d'elle-même comme après « Publier » ; SHEET_NOWAIT=1 : glisser dès
/// l'ouverture). Ignoré sinon. Vrais glissers du doigt dans la feuille, doigt posé sur les boutons. Captures : $SHEET_SHOTS.
final class InviteSheetScrollUITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment

    override func setUpWithError() throws {
        continueAfterFailure = false
        try XCTSkipUnless(env["SHEET_SESSION"] != nil && env["SHEET_EVENT"] != nil, "Essai réel : serveur local et base de TEST")
    }

    private func shot(_ app: XCUIApplication, _ name: String) {
        guard let dir = env["SHEET_SHOTS"] else { return }
        try? FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
        let file = URL(fileURLWithPath: dir).appendingPathComponent("\(env["SHEET_CASE"] ?? "ios")-\(name).png")
        try? app.screenshot().pngRepresentation.write(to: file)
    }

    private func web(_ app: XCUIApplication, contains text: String) -> XCUIElement {
        app.webViews.descendants(matching: .any).matching(NSPredicate(format: "label CONTAINS %@", text)).firstMatch
    }

    /// Visible à l'écran (dans la vue web, au-dessus de la barre d'onglets).
    private func onScreen(_ app: XCUIApplication, _ element: XCUIElement) -> Bool {
        guard element.exists else { return false }
        let view = app.webViews.firstMatch.frame
        let frame = element.frame
        return frame.minY >= view.minY && frame.maxY <= view.maxY && frame.height > 0
    }

    /// La fiche de l'événement (base de TEST), puis « Inviter » (carte « Invités ») ; vrais glissers sur la fiche.
    private func openSheet() -> (XCUIApplication, XCUIElement) {
        let app = XCUIApplication()
        let event = env["SHEET_EVENT"]!
        // SHEET_AUTO=1 : comme juste après « Publier » (assistant IA, sur invitation) : la feuille s'ouvre d'elle-même.
        let auto = env["SHEET_AUTO"] == "1"
        app.launchEnvironment["PARTY_DEBUG_JS"] =
            "localStorage.setItem('sb-ewromqfsmcqsthftyhzm-auth-token', \(env["SHEET_SESSION"]!));localStorage.setItem('vp_tab','events');"
            + "localStorage.setItem('vp_install_dismissed','1');localStorage.setItem('vp_name','Admin test');"
            + "addEventListener('load',()=>setTimeout(()=>PartyEvents.open('/events/event/\(event)\(auto ? "?step=online&invite=link" : "")'),1500));"
        app.launch()
        let title = web(app, contains: "et seulement à cet événement")
        if !auto {
            let invite = app.webViews.buttons.matching(NSPredicate(format: "label == 'Inviter'")).firstMatch
            XCTAssertTrue(invite.waitForExistence(timeout: 60), "La fiche de l'événement ne s'est pas ouverte")
            for _ in 0..<8 where !(invite.isHittable && onScreen(app, invite)) { app.webViews.firstMatch.swipeUp(velocity: .slow) }
            invite.tap()
        }
        let opened = title.waitForExistence(timeout: auto ? 60 : 15)
        if !opened { shot(app, "00-feuille-pas-ouverte") }
        XCTAssertTrue(opened, "La feuille « Inviter » ne s'est pas ouverte")
        if env["SHEET_NOWAIT"] != "1" { Thread.sleep(forTimeInterval: 1) }  // la feuille finit de monter (NOWAIT : glisser aussitôt)
        return (app, title)
    }

    private func dragUp(_ app: XCUIApplication, from: CGFloat = 0.72, to: CGFloat = 0.3) {
        app.webViews.firstMatch.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: from))
            .press(forDuration: 0.05, thenDragTo: app.webViews.firstMatch.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: to)),
                   withVelocity: .slow, thenHoldForDuration: 0.1)
    }

    /// Recherche au clavier (le clavier couvre le bas de l'écran) : la liste trouvée et le bas de la feuille s'atteignent
    /// toujours au doigt, au-dessus du clavier.
    func testWithTheKeyboardOpenTheFingerReachesTheResultsAndTheBottom() throws {
        let (app, _) = openSheet()
        let search = app.webViews.textFields.matching(NSPredicate(format: "label CONTAINS 'Chercher une personne'")).firstMatch
        for _ in 0..<6 where !onScreen(app, search) { dragUp(app, from: 0.6, to: 0.35) }
        search.tap()
        search.typeText("t")
        let keyboard = app.keyboards.firstMatch
        XCTAssertTrue(keyboard.waitForExistence(timeout: 10), "Le clavier ne s'est pas ouvert")
        Thread.sleep(forTimeInterval: 1)
        shot(app, "k1-clavier-ouvert")
        let bottom = web(app, contains: "sans entrer dans le groupe")
        let visible = { () -> Bool in
            let f = bottom.frame
            return bottom.exists && f.height > 0 && f.minY >= app.webViews.firstMatch.frame.minY && f.maxY <= keyboard.frame.minY
        }
        for _ in 0..<10 where !visible() { dragUp(app, from: 0.45, to: 0.15) }
        shot(app, "k2-clavier-bas-de-la-feuille")
        XCTAssertTrue(visible(), "Clavier ouvert : le bas de la feuille reste caché sous le clavier (\(bottom.frame) / clavier \(keyboard.frame))")
    }

    /// Les gestes réels avant de chercher plus bas : taper dans la recherche, fermer le clavier, fermer puis rouvrir la
    /// feuille ; ensuite le doigt doit toujours la faire défiler jusqu'en bas.
    func testAfterKeyboardAndReopenTheFingerStillScrolls() throws {
        let (app, title) = openSheet()
        let search = app.webViews.textFields.matching(NSPredicate(format: "label CONTAINS 'Chercher une personne'")).firstMatch
        for _ in 0..<6 where !onScreen(app, search) { dragUp(app, from: 0.6, to: 0.35) }
        search.tap()
        search.typeText("b")
        XCTAssertTrue(app.keyboards.firstMatch.waitForExistence(timeout: 10))
        // « ✓ » de la barre au-dessus du clavier (le dernier bouton ; les premiers sont « précédent / suivant »).
        let bar = app.toolbars.buttons
        bar.element(boundBy: bar.count - 1).tap()
        XCTAssertTrue(app.keyboards.firstMatch.waitForNonExistence(timeout: 10), "Le clavier ne se ferme pas")
        Thread.sleep(forTimeInterval: 1)
        let bottom = web(app, contains: "sans entrer dans le groupe")
        for _ in 0..<10 where !onScreen(app, bottom) { dragUp(app) }
        shot(app, "r1-apres-clavier")
        XCTAssertTrue(onScreen(app, bottom), "Après le clavier, le doigt ne fait plus défiler la feuille")

        app.webViews.buttons.matching(NSPredicate(format: "label == 'Fermer'")).firstMatch.tap()
        XCTAssertTrue(title.waitForNonExistence(timeout: 10))
        let invite = app.webViews.buttons.matching(NSPredicate(format: "label == 'Inviter'")).firstMatch
        invite.tap()
        XCTAssertTrue(title.waitForExistence(timeout: 15))
        Thread.sleep(forTimeInterval: 1)
        for _ in 0..<10 where !onScreen(app, bottom) { dragUp(app) }
        shot(app, "r2-feuille-rouverte")
        XCTAssertTrue(onScreen(app, bottom), "Feuille rouverte : le doigt ne la fait plus défiler")
    }

    /// Vidéo de l'admin (06.11, iPhone réel) : tirée vers le bas depuis la poignée ou le titre, la feuille revenait en place
    /// et ne se fermait jamais ; le ✕ était caché sous la pastille de Zicou. Tirée franchement, elle doit disparaître.
    func testPullingTheHandleOrTheTitleDownClosesTheSheet() throws {
        let (app, title) = openSheet()
        let web = app.webViews.firstMatch
        // Repère sûr : le ✕ en haut à droite, sur la ligne du titre ; la poignée est juste au-dessus, au milieu.
        let close = app.webViews.buttons.matching(NSPredicate(format: "label == 'Fermer'")).firstMatch
        XCTAssertTrue(close.waitForExistence(timeout: 5))
        let row = close.frame, view = web.frame
        let point = { (x: CGFloat, y: CGFloat) in web.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(dx: x - view.minX, dy: y - view.minY)) }
        // 1. La poignée.
        let handle = point(view.midX, row.minY - 22)
        shot(app, "f1-avant-poignee")
        handle.press(forDuration: 0.05, thenDragTo: web.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.85)),
                     withVelocity: .default, thenHoldForDuration: 0)
        XCTAssertTrue(title.waitForNonExistence(timeout: 5), "Tirée vers le bas par la poignée, la feuille ne se ferme pas")
        shot(app, "f2-apres-poignee")

        // 2. Rouverte, tirée par le titre.
        let invite = app.webViews.buttons.matching(NSPredicate(format: "label == 'Inviter'")).firstMatch
        invite.tap()
        XCTAssertTrue(title.waitForExistence(timeout: 15))
        Thread.sleep(forTimeInterval: 1)
        point(view.minX + 70, close.frame.midY)   // le mot « Inviter »
            .press(forDuration: 0.05, thenDragTo: web.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.9)),
                   withVelocity: .default, thenHoldForDuration: 0)
        XCTAssertTrue(title.waitForNonExistence(timeout: 5), "Tirée vers le bas par le titre, la feuille ne se ferme pas")

        // 3. Rouverte : le ✕ en haut à droite se touche (rien ne flotte dessus) et ferme.
        invite.tap()
        XCTAssertTrue(title.waitForExistence(timeout: 15))
        Thread.sleep(forTimeInterval: 1)
        XCTAssertTrue(close.waitForExistence(timeout: 5))
        shot(app, "f3-croix-visible")
        close.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
        XCTAssertTrue(title.waitForNonExistence(timeout: 5), "Le ✕ ne ferme pas la feuille (couvert ?)")
    }

    func testFingerScrollsTheInviteSheetToItsBottom() throws {
        let (app, title) = openSheet()

        // Le bas de la feuille : la phrase de la règle (« … sans entrer dans le groupe »), sous « Ajouter des gens de Party ».
        let bottom = web(app, contains: "sans entrer dans le groupe")
        XCTAssertTrue(bottom.waitForExistence(timeout: 5))
        XCTAssertFalse(onScreen(app, bottom), "Le bas de la feuille est déjà visible : la feuille est trop courte pour l'essai")
        shot(app, "01-feuille-ouverte")
        let link = web(app, contains: "Envoyer le lien")
        let marker = web(app, contains: "Ajouter des gens de Party")
        // Le doigt se pose là où l'on pose vraiment le pouce : sur un bouton, le choix Une personne / Plusieurs,
        // l'aperçu du message, le champ de recherche… (pas seulement dans un vide entre deux éléments).
        let starts = ["Plusieurs", "Nombre de places", "Hello", "Partager le lien", "WhatsApp", "Copier"]
        for name in starts where !onScreen(app, bottom) {
            let from = web(app, contains: name)
            guard from.exists, onScreen(app, from), from.frame.midY > app.webViews.firstMatch.frame.midY - 200 else { continue }
            let before = marker.frame.minY
            from.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5))
                .press(forDuration: 0.05, thenDragTo: from.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).withOffset(CGVector(dx: 0, dy: -260)),
                       withVelocity: .slow, thenHoldForDuration: 0.1)
            XCTContext.runActivity(named: "doigt sur « \(name) » : \(before) → \(marker.frame.minY)") { _ in }
            XCTAssertLessThan(marker.frame.minY, before - 100, "Le doigt posé sur « \(name) » ne fait pas défiler la feuille")
        }
        for _ in 0..<8 where !onScreen(app, bottom) {
            app.webViews.firstMatch.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.72))
                .press(forDuration: 0.05, thenDragTo: app.webViews.firstMatch.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.3)),
                       withVelocity: .slow, thenHoldForDuration: 0.1)
        }
        shot(app, "03-bas-de-la-feuille")
        XCTAssertTrue(onScreen(app, bottom), "Le doigt ne fait pas défiler la feuille « Inviter » jusqu'en bas")

        // Retour en haut au doigt, puis la feuille se ferme toujours (✕).
        for _ in 0..<8 where !onScreen(app, link) {
            app.webViews.firstMatch.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.35))
                .press(forDuration: 0.05, thenDragTo: app.webViews.firstMatch.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.8)),
                       withVelocity: .slow, thenHoldForDuration: 0.1)
        }
        XCTAssertTrue(onScreen(app, link), "La feuille ne remonte pas au doigt")
        app.webViews.buttons.matching(NSPredicate(format: "label == 'Fermer'")).firstMatch.tap()
        XCTAssertTrue(title.waitForNonExistence(timeout: 10), "La feuille ne se ferme plus")
        shot(app, "04-feuille-fermee")
    }
}

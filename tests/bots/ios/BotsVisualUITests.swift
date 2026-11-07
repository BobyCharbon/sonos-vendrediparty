import XCTest

/// Banc des bots, campagne 2, agent 09 (visuel, gestes, accessibilité) : app iPhone en Release sur le simulateur
/// « C2-09 iPhone », serveur local branché sur la base de TEST. Copié dans PartyUITests par tests/bots/ios_visuel.sh.
/// BOTS_IOS_SESSION : session de Bot Oscar (littéral JS) ; BOTS_IOS_EVENT / BOTS_IOS_TOKEN : événement [C2-09] et lien.
/// Constats dans BOTS_IOS_OUT/constats-<test>.txt, captures et arbres d'accessibilité à côté.
final class BotsVisualUITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment
    private var out: URL { URL(fileURLWithPath: env["BOTS_IOS_OUT"] ?? NSTemporaryDirectory()) }
    private var notes: [String] = []
    private var step = 0
    private var scene = "visuel"

    override func setUpWithError() throws {
        continueAfterFailure = true
        try XCTSkipUnless(env["BOTS_IOS_EVENT"] != nil, "Banc des bots : événement et serveur local nécessaires")
        try? FileManager.default.createDirectory(at: out, withIntermediateDirectories: true)
    }

    override func tearDown() {
        try? notes.joined(separator: "\n").write(to: out.appendingPathComponent("constats-\(scene).txt"), atomically: true, encoding: .utf8)
    }

    private func note(_ text: String) {
        notes.append("\(Date()) \(text)")
        print("BOTS: [\(scene)] \(text)")
    }

    private func shot(_ app: XCUIApplication, _ label: String) {
        step += 1
        let file = out.appendingPathComponent(String(format: "%@-%02d-%@.png", scene, step, label))
        try? app.screenshot().pngRepresentation.write(to: file)
    }

    /// Arbre d'accessibilité (ce que VoiceOver lit) : libellés, cadres, état.
    private func tree(_ app: XCUIApplication, _ label: String) {
        try? app.debugDescription.write(to: out.appendingPathComponent("\(scene)-\(label).ax.txt"), atomically: true, encoding: .utf8)
    }

    private func any(_ app: XCUIApplication, _ predicate: String) -> XCUIElement {
        app.webViews.descendants(matching: .any).matching(NSPredicate(format: predicate)).firstMatch
    }

    private func swipeUp(_ app: XCUIApplication, from: CGFloat = 0.75, to: CGFloat = 0.3) {
        let web = app.webViews.firstMatch
        web.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: from))
            .press(forDuration: 0.05, thenDragTo: web.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: to)),
                   withVelocity: .default, thenHoldForDuration: 0.1)
        Thread.sleep(forTimeInterval: 0.8)
    }

    private func launch(session: Bool, extraJS: String = "", args: [String] = []) -> XCUIApplication {
        let app = XCUIApplication()
        var js = "localStorage.setItem('vp_tab','events');localStorage.setItem('vp_install_dismissed','1');"
        if !session { js += "localStorage.removeItem('sb-ewromqfsmcqsthftyhzm-auth-token');" }
        if session, let s = env["BOTS_IOS_SESSION"] {
            js += "localStorage.setItem('sb-ewromqfsmcqsthftyhzm-auth-token', \(s));localStorage.setItem('vp_name','Bot Oscar');"
        }
        app.launchEnvironment["PARTY_DEBUG_JS"] = js + extraJS
        app.launchArguments += args
        app.launch()
        return app
    }


    /// En Release, PARTY_DEBUG_JS est ignoré : connexion comme un vrai utilisateur (numéro de test, code fixe).
    private func signInIfNeeded(_ app: XCUIApplication) {
        let tab = app.tabBars.buttons["Événements"].firstMatch
        if tab.waitForExistence(timeout: 25) { tab.tap() }
        Thread.sleep(forTimeInterval: 4)
        let phoneField = app.webViews.textFields["Ton numéro de téléphone"].firstMatch
        guard phoneField.waitForExistence(timeout: 8) else { return }
        phoneField.tap()
        phoneField.typeText("0790000104")
        app.webViews.buttons["Recevoir un code par SMS"].firstMatch.tap()
        let code = app.webViews.textFields.matching(NSPredicate(format: "placeholderValue == '123456' OR label CONTAINS 'Code'")).firstMatch
        if code.waitForExistence(timeout: 90) {
            code.tap()
            code.typeText("123456")
            app.webViews.buttons["Se connecter"].firstMatch.tap()
            Thread.sleep(forTimeInterval: 8)
        } else {
            note("❌ champ du code SMS introuvable")
        }
    }

    private var statusBarBottom: CGFloat { 54 }   // iPhone 17 : barre d'état + Dynamic Island ≈ 54 pt

    /// Éléments touchables de la vue web qui passent sous la barre d'état ou sous la barre d'onglets native.
    private func checkBars(_ app: XCUIApplication, _ screen: String) {
        let tabTop = app.tabBars.firstMatch.exists ? app.tabBars.firstMatch.frame.minY : app.windows.firstMatch.frame.maxY
        let hits = app.webViews.descendants(matching: .any).matching(NSPredicate(format: "elementType IN %@",
            [XCUIElement.ElementType.button.rawValue, XCUIElement.ElementType.link.rawValue,
             XCUIElement.ElementType.textField.rawValue])).allElementsBoundByIndex.prefix(80)
        var under: [String] = []
        var small: [String] = []
        for e in hits where e.exists {
            let f = e.frame
            guard f.height > 0, f.width > 0 else { continue }
            if (f.minY < statusBarBottom && f.maxY > 4) || (f.minY < tabTop && f.maxY > tabTop + 4) { under.append("\(e.label) \(Int(f.minY))…\(Int(f.maxY))") }
            if f.minY >= 0 && f.maxY <= tabTop && (f.height < 44 || f.width < 44) && !e.label.isEmpty { small.append("\(e.label) \(Int(f.width))×\(Int(f.height))") }
        }
        note("\(screen) : barre d'onglets à y=\(Int(tabTop)) ; sous une barre : \(under.prefix(8)) ; cibles < 44 pt : \(small.prefix(12))")
    }

    /// 1. Onglet Événements : liste, fiche jusqu'en bas, feuille Inviter (glisser vers le bas), retour (bouton et bord).
    func testEventsTabLayoutGesturesAndBack() throws {
        scene = "onglet"
        let app = launch(session: true)
        signInIfNeeded(app)
        Thread.sleep(forTimeInterval: 5)
        shot(app, "liste")
        tree(app, "liste")
        checkBars(app, "liste")
        for _ in 0..<6 { swipeUp(app) }
        shot(app, "liste-bas")
        checkBars(app, "liste (bas)")

        let card = any(app, "label CONTAINS 'Très longue soirée'")
        for _ in 0..<10 where !(card.exists && card.isHittable) { swipeUp(app, from: 0.3, to: 0.75) }
        guard card.waitForExistence(timeout: 20) else { note("❌ carte de l'événement [C2-09] introuvable"); shot(app, "sans-carte"); return }
        card.tap()
        Thread.sleep(forTimeInterval: 4)
        shot(app, "fiche")
        tree(app, "fiche")
        checkBars(app, "fiche (haut)")
        let report = any(app, "label == 'Annuler l’événement' OR label BEGINSWITH 'Supprimer' OR label == 'Signaler cet événement'")
        for _ in 0..<18 where !(report.exists && report.isHittable) { swipeUp(app) }
        shot(app, "fiche-bas")
        let tabTop = app.tabBars.firstMatch.exists ? app.tabBars.firstMatch.frame.minY : 9999
        note(report.exists ? "fiche bas : dernier bouton « \(report.label) » y=\(Int(report.frame.minY))…\(Int(report.frame.maxY)), barre d'onglets y=\(Int(tabTop)) \(report.frame.maxY <= tabTop ? "✅" : "❌ sous la barre")"
                           : "❌ fiche : bas jamais atteint")
        checkBars(app, "fiche (bas)")

        // Feuille Inviter : sous la barre d'état ? se ferme en glissant vers le bas ?
        let invite = app.webViews.buttons["Inviter"].firstMatch
        for _ in 0..<12 where !(invite.exists && invite.isHittable) { swipeUp(app, from: 0.3, to: 0.8) }
        if invite.exists && invite.isHittable {
            invite.tap()
            Thread.sleep(forTimeInterval: 1.5)
            shot(app, "inviter")
            tree(app, "inviter")
            let close = app.webViews.buttons["Fermer"].firstMatch
            note(close.exists ? "Inviter : ✕ à y=\(Int(close.frame.minY)) taille \(Int(close.frame.width))×\(Int(close.frame.height)) \(close.frame.minY >= statusBarBottom ? "✅" : "❌ sous la barre d'état")" : "❌ Inviter : pas de ✕")
            let sheet = any(app, "label BEGINSWITH 'Inviter à '")
            let top = sheet.exists ? sheet.frame.minY : 120
            let web = app.webViews.firstMatch
            let a = web.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(dx: web.frame.width / 2, dy: top + 12 - web.frame.minY))
            a.press(forDuration: 0.05, thenDragTo: a.withOffset(CGVector(dx: 0, dy: 420)), withVelocity: .fast, thenHoldForDuration: 0)
            Thread.sleep(forTimeInterval: 1.2)
            shot(app, "inviter-apres-glisser")
            note(close.exists && close.isHittable ? "❌ Inviter : la feuille ne se ferme pas en glissant vers le bas" : "✅ Inviter : fermée en glissant vers le bas")
            if close.exists && close.isHittable { close.tap() }
        } else {
            note("❌ bouton « Inviter » introuvable sur la fiche")
        }

        // Retour : bouton ‹ puis glissement depuis le bord gauche.
        let back = app.webViews.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Retour'")).firstMatch
        note(back.exists ? "bouton retour « \(back.label) » \(Int(back.frame.width))×\(Int(back.frame.height)) y=\(Int(back.frame.minY))" : "❌ pas de bouton retour sur la fiche")
        if back.exists && back.isHittable { back.tap(); Thread.sleep(forTimeInterval: 2) }
        shot(app, "apres-retour")
        note(card.exists && card.isHittable ? "✅ retour : liste revenue" : "⚠️ retour : liste pas revenue (ou carte hors écran)")
        if card.exists && card.isHittable {
            card.tap()
            Thread.sleep(forTimeInterval: 3)
            let web = app.webViews.firstMatch
            let edge = web.coordinate(withNormalizedOffset: CGVector(dx: 0.005, dy: 0.5))
            edge.press(forDuration: 0.05, thenDragTo: web.coordinate(withNormalizedOffset: CGVector(dx: 0.8, dy: 0.5)), withVelocity: .default, thenHoldForDuration: 0)
            Thread.sleep(forTimeInterval: 2)
            shot(app, "apres-bord-gauche")
            note(invite.exists && invite.isHittable ? "❌ glissement depuis le bord gauche : la fiche reste" : "✅ glissement depuis le bord gauche : retour à la liste")
        }
    }

    /// 2. Lien profond /events/event/<id> : la vue web charge le module seul (WebModel.open), comme un lien universel.
    func testDeepLinkEvent() throws {
        scene = "lien-fiche"
        let id = env["BOTS_IOS_EVENT"]!
        let app = launch(session: true, extraJS: "if (location.pathname === '/' && !sessionStorage.getItem('c209')) { sessionStorage.setItem('c209','1'); location.href = '/events/event/\(id)'; }")
        Thread.sleep(forTimeInterval: 20)
        shot(app, "ouvert")
        tree(app, "ouvert")
        let tabs = app.tabBars.firstMatch
        note("lien fiche : barre d'onglets native \(tabs.exists ? "présente (\(tabs.buttons.count) onglets, choisi : \(tabs.buttons.allElementsBoundByIndex.first { $0.isSelected }?.label ?? "aucun"))" : "absente")")
        let title = any(app, "label CONTAINS 'Très longue soirée'")
        note(title.exists ? "✅ lien fiche : la fiche s'affiche" : "❌ lien fiche : fiche absente")
        checkBars(app, "lien fiche")
        let back = app.webViews.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Retour'")).firstMatch
        note(back.exists ? "lien fiche : bouton retour « \(back.label) »" : "lien fiche : pas de bouton retour")
        if back.exists && back.isHittable { back.tap(); Thread.sleep(forTimeInterval: 3); shot(app, "apres-retour") }
        if tabs.exists {
            tabs.buttons["Musique"].firstMatch.tap()
            Thread.sleep(forTimeInterval: 3)
            shot(app, "onglet-musique")
            note("lien fiche puis onglet Musique : \(any(app, "label CONTAINS 'Très longue soirée'").exists ? "❌ la fiche reste affichée" : "écran changé")")
        }
    }

    /// 3. Lien d'invitation /events/invite/<jeton>, sans compte puis avec.
    func testDeepLinkInvite() throws {
        let token = env["BOTS_IOS_TOKEN"]!
        for logged in [false, true] {
            scene = logged ? "lien-invitation-connecte" : "lien-invitation-deconnecte"
            notes = []
            step = 0
            let app = launch(session: logged, extraJS: "if (location.pathname === '/' && !sessionStorage.getItem('c209')) { sessionStorage.setItem('c209','1'); location.href = '/events/invite/\(token)'; }")
            Thread.sleep(forTimeInterval: 20)
            shot(app, "ouvert")
            tree(app, "ouvert")
            checkBars(app, scene)
            for _ in 0..<5 { swipeUp(app) }
            shot(app, "bas")
            checkBars(app, "\(scene) (bas)")
            tearDown()
            app.terminate()
        }
    }

    /// 4. Texte agrandi (Dynamic Type le plus grand) : le module suit-il la taille du texte du téléphone ?
    func testLargeDynamicType() throws {
        scene = "texte-agrandi"
        for (label, size) in [("normal", "UICTContentSizeCategoryL"), ("xxxl", "UICTContentSizeCategoryAccessibilityXXXL")] {
            let app = launch(session: true, args: ["-UIPreferredContentSizeCategoryName", size])
            signInIfNeeded(app)
            Thread.sleep(forTimeInterval: 8)
            shot(app, "liste-\(label)")
            let title = any(app, "label BEGINSWITH 'Salut'")
            note("\(label) : « Salut… » \(title.exists ? "\(Int(title.frame.width))×\(Int(title.frame.height))" : "absent") ; onglets natifs \(app.tabBars.firstMatch.exists ? "hauteur \(Int(app.tabBars.firstMatch.frame.height))" : "absents")")
            app.terminate()
        }
    }
}

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

    /// Relance R-09 : la liste du banc a ~80 cartes ; parcourir son arbre d'accessibilité bloquait l'app (« main thread
    /// busy for 30 s » sous la charge). On filtre la liste par le champ de recherche, puis on touche la carte.
    private func openEventByName(_ app: XCUIApplication, _ text: String = "Très longue") -> XCUIElement {
        // Accueil compact (08.11) : le champ s'ouvre par la loupe.
        let loupe = app.webViews.buttons["Rechercher"].firstMatch
        if loupe.waitForExistence(timeout: 60) { loupe.tap() }
        let search = app.webViews.textFields["Rechercher un événement"].firstMatch
        if search.waitForExistence(timeout: 10) {
            search.tap()
            search.typeText(text)
            Thread.sleep(forTimeInterval: 3)
            shot(app, "recherche-clavier")
            search.typeText("\n")   // touche « Rechercher » du clavier
            Thread.sleep(forTimeInterval: 2)
            if app.keyboards.firstMatch.exists {
                note("constat : la touche « Rechercher » du clavier ne ferme pas le clavier")
                let done = app.toolbars.buttons.allElementsBoundByIndex.last
                if let done, done.exists { done.tap() } else { any(app, "label == 'Les événements du groupe'").tap() }
                Thread.sleep(forTimeInterval: 2)
                note(app.keyboards.firstMatch.exists ? "⚠️ clavier toujours ouvert" : "clavier fermé par ✓")
            }
        } else {
            note("⚠️ champ de recherche introuvable")
        }
        return any(app, "label CONTAINS 'Très longue soirée'")
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
        let card = openEventByName(app)
        shot(app, "liste-filtree")
        guard card.waitForExistence(timeout: 30) else { note("❌ carte de l'événement [C2-09] introuvable"); shot(app, "sans-carte"); return }
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

        // Feuille Inviter : sous la barre d'état ? se ferme en glissant vers le bas ? (relance R-09 : contrôles stricts,
        // la feuille est cherchée par son nom « Inviter à … » et la liste par son champ de recherche)
        let invite = app.webViews.buttons["Inviter"].firstMatch
        let sheet = any(app, "label BEGINSWITH 'Inviter à '")
        let close = app.webViews.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Fermer'")).firstMatch
        // Le bouton doit être à l'écran, sous l'en-tête collant (sinon le toucher tombe sur l'en-tête) : haut de fiche,
        // puis petits défilements jusqu'à ce qu'il soit entre y=140 et y=700, et toucher à son centre.
        for _ in 0..<8 { swipeUp(app, from: 0.3, to: 0.9) }
        for _ in 0..<12 where invite.exists && invite.frame.minY > 700 { swipeUp(app, from: 0.7, to: 0.45) }
        if invite.exists && invite.frame.minY > 140 && invite.frame.maxY < 760 {
            invite.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
            let opened = sheet.waitForExistence(timeout: 15)
            Thread.sleep(forTimeInterval: 2)
            shot(app, "inviter")
            tree(app, "inviter")
            note(opened ? "✅ Inviter : feuille ouverte, cadre y=\(Int(sheet.frame.minY))…\(Int(sheet.frame.maxY))" : "❌ Inviter : la feuille ne s'ouvre pas (15 s)")
            note(close.exists ? "Inviter : ✕ à y=\(Int(close.frame.minY)) taille \(Int(close.frame.width))×\(Int(close.frame.height)) \(close.frame.minY >= statusBarBottom ? "✅" : "❌ sous la barre d'état")" : "❌ Inviter : pas de ✕")
            if opened {
                // La fenêtre « Inviter à … » couvre tout l'écran (fond compris) : on part de la poignée, juste au-dessus du ✕.
                let top = close.exists ? close.frame.minY - 6 : sheet.frame.minY + 90
                let web = app.webViews.firstMatch
                let a = web.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(dx: web.frame.width / 2, dy: top - web.frame.minY))
                a.press(forDuration: 0.05, thenDragTo: a.withOffset(CGVector(dx: 0, dy: 420)), withVelocity: .fast, thenHoldForDuration: 0)
                Thread.sleep(forTimeInterval: 3)
                shot(app, "inviter-apres-glisser")
                let stillOpen = close.exists && close.frame.minY < 300
                note(stillOpen ? "❌ Inviter : la feuille ne se ferme pas en glissant vers le bas (départ y=\(Int(top)), ✕ y=\(Int(close.frame.minY)))" : "✅ Inviter : fermée en glissant vers le bas (départ y=\(Int(top)))")
                if stillOpen && close.exists { close.tap(); Thread.sleep(forTimeInterval: 2) }
                // Seconde ouverture : fermeture par le ✕.
                if invite.exists && invite.frame.minY > 140 && invite.frame.maxY < 760 {
                    invite.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
                    if sheet.waitForExistence(timeout: 15), close.waitForExistence(timeout: 5) {
                        close.tap()
                        Thread.sleep(forTimeInterval: 3)
                        shot(app, "inviter-apres-croix")
                        note(sheet.exists ? "❌ Inviter : le ✕ ne ferme pas" : "✅ Inviter : fermée par le ✕")
                    }
                }
            }
        } else {
            note("❌ bouton « Inviter » introuvable sur la fiche (ou hors de la zone touchable : y=\(invite.exists ? Int(invite.frame.minY) : -1))")
        }

        // Retour : bouton ‹ puis glissement depuis le bord gauche. La liste est reconnue à sa loupe.
        let list = app.webViews.buttons["Rechercher"].firstMatch
        let back = app.webViews.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Retour'")).firstMatch
        for _ in 0..<8 where !(back.exists && back.isHittable) { swipeUp(app, from: 0.3, to: 0.8) }
        note(back.exists ? "bouton retour « \(back.label) » \(Int(back.frame.width))×\(Int(back.frame.height)) y=\(Int(back.frame.minY))" : "❌ pas de bouton retour sur la fiche")
        if back.exists && back.isHittable { back.tap() }
        let backOk = list.waitForExistence(timeout: 20)
        Thread.sleep(forTimeInterval: 2)
        shot(app, "apres-retour")
        note(backOk ? "✅ retour (bouton ‹) : liste revenue" : "❌ retour (bouton ‹) : toujours sur la fiche après 20 s")
        let card2 = any(app, "label CONTAINS 'Très longue soirée'")
        if backOk && card2.waitForExistence(timeout: 20) && card2.isHittable {
            card2.tap()
            _ = back.waitForExistence(timeout: 20)
            Thread.sleep(forTimeInterval: 3)
            shot(app, "fiche-2")
            let web = app.webViews.firstMatch
            let edge = web.coordinate(withNormalizedOffset: CGVector(dx: 0.005, dy: 0.5))
            edge.press(forDuration: 0.05, thenDragTo: web.coordinate(withNormalizedOffset: CGVector(dx: 0.8, dy: 0.5)), withVelocity: .default, thenHoldForDuration: 0)
            let edgeOk = list.waitForExistence(timeout: 20)
            Thread.sleep(forTimeInterval: 2)
            shot(app, "apres-bord-gauche")
            note(edgeOk ? "✅ glissement depuis le bord gauche : retour à la liste" : "❌ glissement depuis le bord gauche : la fiche reste (20 s)")
        } else {
            note("⚠️ bord gauche non essayé : carte introuvable après le retour")
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

    /// 5. Relance (R-09) : texte agrandi au maximum, fiche ouverte depuis la liste — l'en-tête (retour, Sourdine,
    /// Modifier) se chevauche-t-il ? Le texte de la fiche déborde-t-il ? (fix-E : -webkit-text-size-adjust)
    func testLargeTextEventHeader() throws {
        for (label, size) in [("normal", "UICTContentSizeCategoryL"), ("xl", "UICTContentSizeCategoryXL"),
                              ("xxxl", "UICTContentSizeCategoryXXXL"), ("ax-xxxl", "UICTContentSizeCategoryAccessibilityXXXL")] {
            scene = "entete-\(label)"
            notes = []
            step = 0
            let app = launch(session: true, args: ["-UIPreferredContentSizeCategoryName", size])
            signInIfNeeded(app)
            Thread.sleep(forTimeInterval: 6)
            shot(app, "liste")
            let salut = any(app, "label BEGINSWITH 'Salut'")
            note("\(label) : « Salut… » \(salut.exists ? "\(Int(salut.frame.width))×\(Int(salut.frame.height))" : "absent")")
            let card = openEventByName(app)
            _ = card.waitForExistence(timeout: 30)
            guard card.exists && card.isHittable else { note("❌ \(label) : carte introuvable"); shot(app, "sans-carte"); tearDown(); app.terminate(); continue }
            card.tap()
            Thread.sleep(forTimeInterval: 5)
            shot(app, "fiche")
            tree(app, "fiche")
            let web = app.webViews.firstMatch
            let buttons = web.descendants(matching: .button).allElementsBoundByIndex.prefix(40)
                .filter { $0.exists && $0.frame.height > 0 && $0.frame.minY < 140 && $0.frame.minY > 40 }
            note("\(label) : en-tête : " + buttons.map { "« \($0.label) » x=\(Int($0.frame.minX))…\(Int($0.frame.maxX)) y=\(Int($0.frame.minY))…\(Int($0.frame.maxY))" }.joined(separator: " ; "))
            var overlaps: [String] = []
            for i in 0..<buttons.count { for j in (i + 1)..<buttons.count {
                let a = buttons[i].frame, b = buttons[j].frame
                let w = min(a.maxX, b.maxX) - max(a.minX, b.minX), h = min(a.maxY, b.maxY) - max(a.minY, b.minY)
                if w > 4 && h > 4 && !a.contains(b) && !b.contains(a) { overlaps.append("« \(buttons[i].label) » ⟷ « \(buttons[j].label) »") }
            } }
            note(overlaps.isEmpty ? "✅ \(label) : en-tête sans chevauchement" : "❌ \(label) : chevauchement dans l'en-tête : \(overlaps)")
            let wide = web.descendants(matching: .staticText).allElementsBoundByIndex.prefix(60)
                .filter { $0.exists && ($0.frame.maxX > web.frame.maxX + 2 || $0.frame.minX < web.frame.minX - 2) }
            note(wide.isEmpty ? "✅ \(label) : aucun texte hors de l'écran" : "❌ \(label) : texte hors de l'écran : \(wide.prefix(5).map { "\($0.label.prefix(30)) x=\(Int($0.frame.minX))…\(Int($0.frame.maxX))" })")
            for _ in 0..<4 { swipeUp(app) }
            shot(app, "fiche-milieu")
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

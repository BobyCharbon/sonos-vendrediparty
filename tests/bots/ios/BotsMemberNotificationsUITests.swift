import XCTest

/// Relance de la campagne 2 (agent 02, vérifications de fix E restées en suspens) : Réglages › Notifications natifs d'un
/// Membre (Bot Marc), interrupteurs refusés aux non-VIP cachés, puis heures de silence (éteindre, rallumer, changer « De »).
/// Connexion par le vrai écran (numéro de test, code 123456), serveur du banc, base de TEST. La base est vérifiée par le
/// script appelant entre deux tests (BOTS_IOS_STEP). Lancé seulement par le banc (BOTS_IOS_OUT).
final class BotsMemberNotificationsUITests: XCTestCase {
    private var env: [String: String] { ProcessInfo.processInfo.environment }
    private var step = 0

    override func setUpWithError() throws {
        continueAfterFailure = true
        try XCTSkipUnless(env["BOTS_IOS_OUT"] != nil, "Banc des bots : serveur local et base de TEST nécessaires")
    }

    private func shot(_ app: XCUIApplication, _ name: String) {
        guard let dir = env["BOTS_IOS_OUT"] else { return }
        try? FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
        step += 1
        let file = URL(fileURLWithPath: dir).appendingPathComponent(String(format: "%02d-%@.png", step, name))
        try? app.screenshot().pngRepresentation.write(to: file)
    }

    private func note(_ text: String) { print("BOTS: \(text)") }

    private func check(_ ok: Bool, _ what: String) { note(ok ? "✅ \(what)" : "❌ \(what)") }

    /// Lance l'app, se connecte si besoin (onglet Événements), ouvre Réglages › Notifications.
    private func openNotifications() -> XCUIApplication {
        let app = XCUIApplication()
        app.launch()
        let events = app.tabBars.buttons["Événements"].firstMatch
        XCTAssertTrue(events.waitForExistence(timeout: 40))
        events.tap()
        let phone = app.webViews.textFields["Ton numéro de téléphone"].firstMatch
        if phone.waitForExistence(timeout: 75) {  // machine chargée : la page met du temps
            phone.tap()
            phone.typeText(env["BOTS_IOS_PHONE"] ?? "0790000109")
            let code = app.webViews.textFields.matching(NSPredicate(format: "placeholderValue == '123456' OR label CONTAINS 'Code'")).firstMatch
            for _ in 0..<5 {
                app.webViews.buttons["Recevoir un code par SMS"].firstMatch.tap()
                if code.waitForExistence(timeout: 12) { break }
                note("pas de code (limite d'envoi), nouvel essai dans 45 s")
                Thread.sleep(forTimeInterval: 45)
            }
            code.tap()
            code.typeText("123456")
            app.webViews.buttons["Se connecter"].firstMatch.tap()
            Thread.sleep(forTimeInterval: 8)
        }
        let settings = app.tabBars.buttons["Réglages"].firstMatch
        XCTAssertTrue(settings.waitForExistence(timeout: 30), "onglet Réglages")
        settings.tap()
        let notif = app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Notifications'")).firstMatch
        XCTAssertTrue(notif.waitForExistence(timeout: 20), "ligne Notifications")
        notif.tap()
        check(app.staticTexts["Modifié ou annulé"].waitForExistence(timeout: 40), "réglages des événements chargés")
        return app
    }

    func testMemberSeesOnlyUsefulSwitches() {
        let app = openNotifications()
        var seen = Set<String>()
        for i in 0..<10 {
            shot(app, String(format: "notif-%02d", i))
            for e in app.staticTexts.allElementsBoundByIndex where e.exists { seen.insert(e.label) }
            app.swipeUp()
        }
        let hidden = ["Nouveau sondage", "Rappel pour voter", "Un organisateur répond pour moi", "Paiement de ma place confirmé",
                      "Billet prêt", "Réponses à mes événements", "Quelqu'un dit avoir payé", "Ma proposition validée ou refusée",
                      "Nouvel événement publié", "Discussions des événements"]
        let shown = ["Modifié ou annulé", "Date choisie", "Place libérée", "Invitation à un événement privé",
                     "Quelqu'un rejoint ou demande à venir", "Heures de silence"]
        for t in hidden { check(!seen.contains(t) && !seen.contains(t.uppercased()), "caché : \(t)") }
        for t in shown { check(seen.contains(t), "affiché : \(t)") }
    }

    private func quietSwitch(_ app: XCUIApplication) -> XCUIElement {
        app.switches.matching(NSPredicate(format: "label BEGINSWITH 'Heures de silence'")).firstMatch
    }

    private func isOn(_ s: XCUIElement) -> Bool { (s.value as? String) == "1" }

    /// BOTS_IOS_STEP = off : éteint les heures de silence ; on : les rallume ; de : met « De » à 22 h 30.
    func testQuietHours() {
        let app = openNotifications()
        let sw = quietSwitch(app)
        check(sw.waitForExistence(timeout: 20), "interrupteur « Heures de silence »")
        shot(app, "silence-avant")
        let want = env["BOTS_IOS_STEP"] ?? "off"
        note("heures de silence avant : \(isOn(sw) ? "allumées" : "éteintes") ; étape \(want)")
        switch want {
        case "off", "on":
            let target = want == "on"
            if isOn(sw) != target { sw.switches.firstMatch.exists ? sw.switches.firstMatch.tap() : sw.tap() }
            Thread.sleep(forTimeInterval: 4)
            check(isOn(sw) == target, "interrupteur \(target ? "allumé" : "éteint") après le toucher")
            let from = app.datePickers.matching(NSPredicate(format: "label == 'De'")).firstMatch
            check(from.exists == target, "« De » / « À » \(target ? "affichés" : "cachés")")
        default:
            let from = app.datePickers.matching(NSPredicate(format: "label == 'De'")).firstMatch
            guard from.waitForExistence(timeout: 10) else { return note("❌ sélecteur « De » introuvable") }
            note("« De » : \(from.value as? String ?? "?")")
            from.buttons.firstMatch.exists ? from.buttons.firstMatch.tap() : from.tap()
            Thread.sleep(forTimeInterval: 1.5)
            shot(app, "de-ouvert")
            let wheels = app.pickerWheels
            if wheels.count >= 2 {
                wheels.element(boundBy: 0).adjust(toPickerWheelValue: "22")
                wheels.element(boundBy: 1).adjust(toPickerWheelValue: "30")
                note("roues : \(wheels.element(boundBy: 0).value as? String ?? "?") \(wheels.element(boundBy: 1).value as? String ?? "?")")
            } else {
                note("❌ roues de l'heure introuvables (\(wheels.count))")
            }
            shot(app, "de-change")
            app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.08)).tap()  // fermer la bulle
            Thread.sleep(forTimeInterval: 4)
            note("« De » après : \(from.value as? String ?? "?")")
        }
        shot(app, "silence-apres")
        note("textes : \(app.staticTexts.allElementsBoundByIndex.prefix(40).filter { $0.exists }.map(\.label).filter { $0.contains("enregistr") || $0.contains("Réessaie") || $0.contains("erreur") })")
    }
}

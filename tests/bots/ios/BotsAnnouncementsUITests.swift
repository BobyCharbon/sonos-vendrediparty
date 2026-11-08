import XCTest

/// Banc des bots (tests/bots, phase « annonces ») : annonces d'événement aux groupes dans l'app iPhone (Release), contre
/// le serveur local branché sur la base de TEST. Copié dans PartyUITests par tests/bots/ios_run.sh (jamais dans l'app).
/// - testOrganizerAsksToTellTheGroup : Bot Olga (simple membre du groupe « Bots ») ouvre sa fiche « BOTS_IOS_EVENT_TITLE »,
///   allume « Prévenir le groupe », lit la phrase (demande à l'admin, 48 h) et voit « Annonce en attente ».
/// - testValidatorAcceptsInActivity : Bot Ada (créatrice du groupe) ouvre Activité › À valider et accepte.
/// Numéro du bot : BOTS_IOS_PHONE (code fixe 123456) ; captures et constats dans BOTS_IOS_OUT.
final class BotsAnnouncementsUITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment
    private var out: URL { URL(fileURLWithPath: env["BOTS_IOS_OUT"] ?? NSTemporaryDirectory()) }
    private var notes: [String] = []
    private var step = 0
    private var title: String { env["BOTS_IOS_EVENT_TITLE"] ?? "Bot Annonce iPhone" }

    override func setUpWithError() throws {
        continueAfterFailure = true
        try XCTSkipUnless(env["BOTS_IOS_PHONE"] != nil, "Banc des bots : numéro du bot et serveur local nécessaires")
        try? FileManager.default.createDirectory(at: out, withIntermediateDirectories: true)
    }

    override func tearDown() {
        let file = out.appendingPathComponent("constats-annonces.txt")
        let previous = (try? String(contentsOf: file, encoding: .utf8)) ?? ""
        try? (previous + notes.joined(separator: "\n") + "\n").write(to: file, atomically: true, encoding: .utf8)
    }

    private func note(_ text: String) {
        notes.append("\(Date()) \(text)")
        print("BOTS: \(text)")
    }

    private func shot(_ app: XCUIApplication, _ name: String) {
        step += 1
        let file = out.appendingPathComponent(String(format: "annonces-%@-%02d-%@.png", env["BOTS_IOS_WHO"] ?? "bot", step, name))
        try? app.screenshot().pngRepresentation.write(to: file)
    }

    private func any(_ app: XCUIApplication, _ predicate: String) -> XCUIElement {
        app.webViews.descendants(matching: .any).matching(NSPredicate(format: predicate)).firstMatch
    }

    private func swipeUp(_ app: XCUIApplication, from: CGFloat = 0.8, to: CGFloat = 0.35) {
        let web = app.webViews.firstMatch
        let a = web.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: from))
        let b = web.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: to))
        a.press(forDuration: 0.05, thenDragTo: b, withVelocity: .default, thenHoldForDuration: 0.1)
        Thread.sleep(forTimeInterval: 0.8)
    }

    /// Lance l'app, onglet Événements, connexion par le vrai écran (numéro de test, code fixe).
    private func launchSignedIn() -> XCUIApplication {
        let app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_JS"] = "localStorage.setItem('vp_tab','events');localStorage.setItem('vp_install_dismissed','1')"
        app.launch()
        let tab = app.tabBars.buttons["Événements"].firstMatch
        if tab.waitForExistence(timeout: 20) { tab.tap() } else { note("onglet natif « Événements » introuvable") }
        Thread.sleep(forTimeInterval: 4)
        let phoneField = app.webViews.textFields["Ton numéro de téléphone"].firstMatch
        if phoneField.waitForExistence(timeout: 10) {
            phoneField.tap()
            phoneField.typeText(env["BOTS_IOS_PHONE"]!)
            app.webViews.buttons["Recevoir un code par SMS"].firstMatch.tap()
            let code = app.webViews.textFields.matching(NSPredicate(format: "placeholderValue == '123456' OR label CONTAINS 'Code'")).firstMatch
            if code.waitForExistence(timeout: 60) {
                code.tap()
                code.typeText("123456")
                app.webViews.buttons["Se connecter"].firstMatch.tap()
                Thread.sleep(forTimeInterval: 5)
            } else {
                note("❌ champ du code SMS introuvable")
            }
        }
        shot(app, "connecte")
        return app
    }

    func testOrganizerAsksToTellTheGroup() throws {
        let app = launchSignedIn()
        let card = any(app, "label BEGINSWITH '\(title)'")
        for _ in 0..<8 where !(card.exists && card.isHittable) { swipeUp(app) }
        guard card.waitForExistence(timeout: 40) else { note("❌ fiche « \(title) » introuvable dans la liste"); shot(app, "liste"); return }
        card.tap()
        Thread.sleep(forTimeInterval: 3)
        let status = any(app, "label == 'Annonce au groupe'")
        for _ in 0..<10 where !(status.exists && status.isHittable) { swipeUp(app) }
        shot(app, "fiche-annonce")
        let toggle = app.webViews.switches["Prévenir le groupe"].firstMatch
        guard toggle.waitForExistence(timeout: 15) else { note("❌ interrupteur « Prévenir le groupe » absent de la fiche"); return }
        note("interrupteur « Prévenir le groupe » : valeur \(String(describing: toggle.value)) (attendu : éteint)")
        toggle.tap()
        Thread.sleep(forTimeInterval: 3)
        shot(app, "demande-envoyee")
        let pending = any(app, "label CONTAINS 'Annonce en attente'")
        note(pending.waitForExistence(timeout: 15) ? "✅ organisatrice : « Annonce en attente » affichée après « Prévenir le groupe »"
                                                    : "❌ organisatrice : pas de « Annonce en attente » après « Prévenir le groupe »")
    }

    func testValidatorAcceptsInActivity() throws {
        let app = launchSignedIn()
        // Accueil compact (08.11) : l'Activité s'ouvre par la cloche (« Activité » ou « Activité, N nouveauté(s)… »).
        let activity = app.webViews.buttons.matching(NSPredicate(format: "label == 'Activité' OR label BEGINSWITH 'Activité,'")).firstMatch
        guard activity.waitForExistence(timeout: 20) else { note("❌ cloche « Activité » de l'accueil introuvable"); shot(app, "sans-activite"); return }
        activity.tap()
        Thread.sleep(forTimeInterval: 3)
        let card = any(app, "label BEGINSWITH 'Annonce à valider : \(title)'")
        for _ in 0..<6 where !(card.exists && card.isHittable) { swipeUp(app) }
        shot(app, "a-valider")
        guard card.waitForExistence(timeout: 20) else { note("❌ valideuse : carte « Annonce à valider : \(title) » absente d'Activité"); return }
        let message = any(app, "label CONTAINS 'avec le groupe Bots'")
        note(message.exists ? "✅ valideuse : aperçu du message reçu par le groupe" : "❌ valideuse : aperçu du message absent")
        let accept = card.buttons["Accepter"].firstMatch.exists ? card.buttons["Accepter"].firstMatch : app.webViews.buttons["Accepter"].firstMatch
        for _ in 0..<4 where !accept.isHittable { swipeUp(app, from: 0.7, to: 0.5) }
        accept.tap()
        Thread.sleep(forTimeInterval: 3)
        shot(app, "acceptee")
        let done = any(app, "label CONTAINS 'C’est parti : Bots est prévenu.'")
        note(done.waitForExistence(timeout: 15) ? "✅ valideuse : « Accepter » → « C’est parti : Bots est prévenu. »"
                                                 : "❌ valideuse : pas de confirmation après « Accepter »")
    }
}

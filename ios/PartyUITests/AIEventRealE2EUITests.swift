import XCTest

/// VRAI bout en bout de « Créer avec l'IA » (bugs de prod du 06.11), lancé à la main contre un serveur Party local
/// branché sur la base de TEST : app construite avec PARTY_BASE_URL=http://127.0.0.1:<port>, session du compte de test
/// et brouillon passés par l'environnement (TEST_RUNNER_AI_E2E_SESSION, TEST_RUNNER_AI_E2E_DRAFT). Ignoré sinon.
/// « Oui, continuer » → (CGU exigées : feuille « Avant de publier », « J'accepte », nouvel essai) → brouillon enregistré
/// → l'étape 2 « Qui est invité » s'ouvre dans Événements ET y reste → un toucher sur « qui voit » publie : sur invitation,
/// la feuille « Inviter » avec le lien prêt (QR) ; Membres : la fiche et « ＋ Inviter d'autres personnes » ; public : la
/// fiche ; sans le droit de publier : « Envoyé pour validation ». Captures dans $AI_E2E_SHOTS.
final class AIEventRealE2EUITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment

    override func setUpWithError() throws {
        continueAfterFailure = false
        try XCTSkipUnless(env["AI_E2E_SESSION"] != nil && env["AI_E2E_DRAFT"] != nil, "Essai réel : serveur local et base de TEST")
    }

    private func shot(_ app: XCUIApplication, _ name: String) {
        guard let dir = env["AI_E2E_SHOTS"] else { return }
        try? FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
        let file = URL(fileURLWithPath: dir).appendingPathComponent("\(env["AI_E2E_CASE"] ?? "ios")-\(name).png")
        try? app.screenshot().pngRepresentation.write(to: file)
    }

    private func label(_ app: XCUIApplication, _ text: String) -> XCUIElement {
        app.descendants(matching: .any).matching(NSPredicate(format: "label == %@", text)).firstMatch
    }

    func testOuiContinuerThenStepTwoStaysOpenThenPublish() throws {
        let app = XCUIApplication()
        let session = env["AI_E2E_SESSION"]!
        app.launchEnvironment["PARTY_DEBUG_JS"] =
            "localStorage.setItem('sb-ewromqfsmcqsthftyhzm-auth-token', \(session));localStorage.setItem('vp_tab','events');"
            + "localStorage.setItem('vp_install_dismissed','1');localStorage.setItem('vp_name','Admin test')"
        app.launchEnvironment["PARTY_DEBUG_AI_EVENT"] = env["AI_E2E_DRAFT"]
        app.launchEnvironment["PARTY_DEBUG_AI_SAID"] = "Samedi party chez Boby, rue du Lac 12 à Vevey."
        app.launchEnvironment["PARTY_DEBUG_AI_PICK"] = "1"
        app.launch()

        let proceed = app.buttons["ai-continue"]
        for _ in 0..<10 where !(proceed.exists && proceed.isHittable) { app.swipeUp() }
        XCTAssertTrue(proceed.waitForExistence(timeout: 40))
        let deadline = Date().addingTimeInterval(30)
        while !proceed.isEnabled && Date() < deadline { RunLoop.current.run(until: Date().addingTimeInterval(0.3)) }
        shot(app, "01-etape-1-c-est-juste")
        proceed.tap()

        // CGU exigées et pas encore acceptées : la feuille, puis l'enregistrement repart tout seul.
        let accept = app.buttons["terms-accept"]
        if env["AI_E2E_TERMS"] == "1" {
            XCTAssertTrue(accept.waitForExistence(timeout: 30), "La feuille des CGU devait s'ouvrir")
            shot(app, "02-feuille-cgu")
            accept.tap()
        }
        XCTAssertFalse(app.staticTexts["L'événement n'a pas pu être créé. Réessaie, ou crée-le à la main."].exists)

        // « Brouillon enregistré » reste affiché ; « Choisir qui est invité » ouvre l'étape 2 dans Événements.
        let invite = app.buttons["ai-invite"]
        XCTAssertTrue(invite.waitForExistence(timeout: 60), "« Brouillon enregistré » ne s'est pas affiché")
        Thread.sleep(forTimeInterval: 3)
        XCTAssertTrue(invite.isHittable, "« Choisir qui est invité » doit rester touchable")
        shot(app, "02b-brouillon-enregistre")
        invite.tap()
        let step = label(app, "Étape 2 sur 3 : Qui est invité")
        XCTAssertTrue(step.waitForExistence(timeout: 60), "L'étape 2 « Qui est invité » ne s'est pas ouverte")
        XCTAssertTrue(app.buttons["ai-continue"].waitForNonExistence(timeout: 20))
        shot(app, "03-etape-2-ouverte")
        Thread.sleep(forTimeInterval: 6)  // le bug : la page revenait aussitôt à la liste
        XCTAssertTrue(step.exists, "L'étape 2 s'est refermée")
        shot(app, "04-etape-2-toujours-ouverte")

        // Un toucher sur « qui voit » publie (AI_E2E_CHOICE : invite, vip, public) ; AI_E2E_PROPOSING=1 : compte sans le
        // droit de publier directement, l'événement part en validation.
        let choice = env["AI_E2E_CHOICE"] ?? "invite"
        let proposing = env["AI_E2E_PROPOSING"] == "1"
        let titles = ["invite": "✉️ Sur invitation seulement", "vip": "👥 Membres Vendredi Party", "public": "🌍 Public + lien public"]
        let actions = ["invite": "Publier et envoyer le lien", "vip": "Publier pour les Membres Vendredi Party", "public": "Publier"]
        let name = "\(titles[choice]!) : \(proposing ? "Envoyer pour validation" : actions[choice]!)"
        let option = app.webViews.buttons[name]
        for _ in 0..<6 where !(option.exists && option.isHittable) { app.webViews.firstMatch.swipeUp() }
        XCTAssertTrue(option.waitForExistence(timeout: 10), "Bouton « \(name) » introuvable")
        XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label CONTAINS 'dès la publication'")).firstMatch.exists)
        shot(app, "05-qui-voit-un-toucher")
        option.tap()

        if proposing {
            XCTAssertTrue(label(app, "Envoyé pour validation").waitForExistence(timeout: 30), "« Envoyé pour validation » attendu")
            if choice == "invite" {
                XCTAssertTrue(app.staticTexts.matching(NSPredicate(format: "label CONTAINS 'sera disponible dès la validation'")).firstMatch.exists)
            }
            XCTAssertFalse(app.webViews.buttons["Partager le lien…"].exists)
            shot(app, "06-envoye-pour-validation")
        } else if choice == "invite" && env["AI_E2E_V2"] == "0" {
            // Invitations v2 éteintes : la fiche, la carte « Lien d'invitation » en tête.
            XCTAssertTrue(label(app, "C’est en ligne !").waitForExistence(timeout: 30), "La fiche publiée ne s'est pas ouverte")
            let create = app.webViews.buttons["Créer un lien unique"]
            XCTAssertTrue(create.waitForExistence(timeout: 20), "Carte du lien attendue")
            shot(app, "06-fiche-carte-du-lien")
            create.tap()
            XCTAssertTrue(app.webViews.buttons["Créer un autre lien unique"].waitForExistence(timeout: 20), "Lien créé attendu")
            shot(app, "07-lien-cree")
        } else if choice == "invite" {
            // La feuille « Inviter » s'ouvre aussitôt, lien prêt à partager.
            XCTAssertTrue(label(app, "C’est en ligne : envoie le lien à tes invités").waitForExistence(timeout: 30))
            let share = app.webViews.buttons["Partager le lien…"]
            XCTAssertTrue(share.waitForExistence(timeout: 10))
            for how in ["WhatsApp", "Messages", "QR code", "Copier"] { XCTAssertTrue(app.webViews.buttons[how].exists, how) }
            shot(app, "06-lien-pret-a-partager")
            app.webViews.buttons["QR code"].tap()  // crée le vrai lien (base de TEST) et le montre en QR
            XCTAssertTrue(app.webViews.images["QR code du lien d’invitation"].waitForExistence(timeout: 20), "QR du lien attendu")
            shot(app, "07-qr-du-lien")
        } else {
            XCTAssertTrue(label(app, "C’est en ligne !").waitForExistence(timeout: 30), "La fiche publiée ne s'est pas ouverte")
            if choice == "vip" && env["AI_E2E_V2"] != "0" {  // carte « Invités » : invitations v2 seulement
                XCTAssertTrue(app.webViews.buttons["＋ Inviter d’autres personnes"].waitForExistence(timeout: 20))
            }
            shot(app, "06-publie-fiche")
        }
    }
}

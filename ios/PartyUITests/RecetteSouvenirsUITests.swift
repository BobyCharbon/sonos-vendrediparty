import XCTest

/// Recette RÉELLE des Souvenirs (24.11) dans le simulateur en configuration Release : serveur Party local branché sur la
/// base de TEST, compte « Admin test » (code fixe). La page de cette branche n'a pas encore ses boutons : les écrans natifs
/// s'ouvrent par le vrai pont (`PartyNative.souvenirs.*`, appelé par PARTY_DEBUG_JS) ou par le toucher de notification.
/// Le simulateur n'a pas de caméra : PARTY_E2E_SOUVENIR_CAMERA=1 (crochet DEBUG / E2E_HOOKS) donne une image de test.
/// Préparé avant (scratchpad souvenirs-recette/prep.py) : RECETTE_EVENT ouvert (2 photos d'un autre membre, Admin test
/// Présent), RECETTE_EVENT2 au labo. test1 : l'appareil photo ; puis prep.py story ; test2 : bulles, story, Réglages.
///   TEST_RUNNER_RECETTE_DIR=… TEST_RUNNER_RECETTE_EVENT=<id> TEST_RUNNER_RECETTE_EVENT2=<id> [TEST_RUNNER_RECETTE_SAVE=<lien>]
///   xcodebuild test -configuration Release ENABLE_TESTABILITY=YES PARTY_SWIFT_CONDITIONS=E2E_HOOKS
///   PARTY_BASE_URL=http://127.0.0.1:<port> -only-testing:PartyUITests/RecetteSouvenirsUITests/test1Camera
final class RecetteSouvenirsUITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment
    private var dir: URL!
    private var app: XCUIApplication!
    private var step = 0
    private var event = ""
    private var event2 = ""

    override func setUpWithError() throws {
        guard let path = env["RECETTE_DIR"], let e = env["RECETTE_EVENT"], let e2 = env["RECETTE_EVENT2"] else {
            throw XCTSkip("Recette à la demande (RECETTE_DIR, RECETTE_EVENT, RECETTE_EVENT2)")
        }
        dir = URL(fileURLWithPath: path)
        event = e
        event2 = e2
        continueAfterFailure = true
        addUIInterruptionMonitor(withDescription: "Alertes d'iOS") { [unowned self] alert in
            // test0 : l'appareil photo REFUSÉ (comme un invité qui dit non) ; sinon on autorise.
            if self.denyAlerts, alert.buttons["Ne pas autoriser"].firstMatch.exists {
                alert.buttons["Ne pas autoriser"].firstMatch.tap()
                return true
            }
            for label in ["Autoriser l'accès complet", "Autoriser", "Allow", "OK"] where alert.buttons[label].firstMatch.exists {
                alert.buttons[label].firstMatch.tap()
                return true
            }
            return false
        }
    }

    private var denyAlerts = false

    private func shot(_ name: String) {
        step += 1
        let prefix = name.hasPrefix("story") || name.hasPrefix("bulles") || name.hasPrefix("reglages") || name.hasPrefix("notif") ? "b"
            : name.hasPrefix("discussion") ? "c" : name.hasPrefix("refus") ? "0" : "a"
        try? app.screenshot().pngRepresentation.write(to: dir.appendingPathComponent(String(format: "souvenirs-%@%02d-%@.png", prefix, step, name)))
    }

    private func launch(_ js: String = "", fakeCamera: Bool = true) {
        app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_JS"] = "localStorage.setItem('vp_install_dismissed','1');" + js
        if fakeCamera { app.launchEnvironment["PARTY_E2E_SOUVENIR_CAMERA"] = "1" }
        app.launch()
    }

    /// Une seule fois par lancement (sessionStorage) : la page rechargée ne rouvre pas l'écran.
    private func once(_ code: String, after ms: Int = 5000) -> String {
        "if(!sessionStorage.recette){sessionStorage.recette='1';setTimeout(function(){\(code)},\(ms));}"
    }

    private func any(_ predicate: String, _ args: CVarArg...) -> XCUIElement {
        app.descendants(matching: .any).matching(NSPredicate(format: predicate, argumentArray: args)).firstMatch
    }

    private func signInAdminIfNeeded() {
        let tab = app.tabBars.buttons.matching(NSPredicate(format: "label IN {'Réglages', 'Se connecter'}")).firstMatch
        XCTAssertTrue(tab.waitForExistence(timeout: 30), "onglet Réglages")
        tab.tap()
        sleep(2)
        guard app.staticTexts["Se connecter"].exists else { return }
        app.staticTexts["Se connecter"].firstMatch.tap()
        let field = app.textFields["login-phone"]
        XCTAssertTrue(field.waitForExistence(timeout: 10), "champ du numéro")
        field.tap()
        app.typeText("0790000004")
        app.sendLoginCode()
        let code = app.textFields["login-code"]
        XCTAssertTrue(code.waitForExistence(timeout: 20), "champ du code")
        code.tap()
        app.typeText("123456")
        XCTAssertTrue(app.staticTexts["Admin test"].waitForExistence(timeout: 30), "connecté en Admin test")
    }

    /// Une photo : le déclencheur, puis la carte « Partie au labo » (jamais d'aperçu).
    private func shoot(_ name: String) {
        let shutter = app.buttons["souvenir-shutter"]
        XCTAssertTrue(shutter.waitForExistence(timeout: 15), "déclencheur")
        let enabled = NSPredicate(format: "isEnabled == true")
        expectation(for: enabled, evaluatedWith: shutter)
        waitForExpectations(timeout: 45)  // compteur relu par la base de TEST (parfois lente)
        shutter.tap()
        XCTAssertTrue(any("identifier == 'souvenir-labo'").waitForExistence(timeout: 30), "partie au labo")
        shot(name)
    }

    /// Appareil photo refusé (run.sh : `simctl privacy reset camera`, vrai capteur, « Ne pas autoriser ») : message et « Ouvrir Réglages ».
    func test0CameraDenied() {
        denyAlerts = true
        launch()
        signInAdminIfNeeded()
        app.terminate()
        launch(once("PartyNative.souvenirs.camera('\(event)')"), fakeCamera: false)
        // Première demande d'iOS : « Ne pas autoriser » (comme un invité qui refuse), puis le message de Party.
        let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        let deny = springboard.buttons["Ne pas autoriser"].firstMatch
        if deny.waitForExistence(timeout: 45) {
            shot("refus-demande-ios")
            deny.tap()
        } else {
            app.tap()  // déclenche le moniteur d'alertes (« Ne pas autoriser »)
        }
        let open = app.buttons["souvenir-open-settings"]
        XCTAssertTrue(open.waitForExistence(timeout: 20), "« Ouvrir Réglages »")
        XCTAssertTrue(any("label CONTAINS %@", "Autorise l'appareil photo pour Party").exists, "message du refus")
        shot("refus-appareil-ouvrir-reglages")
        open.tap()
        let settings = XCUIApplication(bundleIdentifier: "com.apple.Preferences")
        XCTAssertTrue(settings.wait(for: .runningForeground, timeout: 15), "Réglages d'iOS ouverts")
        sleep(5)
        try? XCUIScreen.main.screenshot().pngRepresentation.write(to: dir.appendingPathComponent("souvenirs-002-refus-reglages-ios.png"))
        settings.terminate()
    }

    func test1Camera() {
        launch()
        signInAdminIfNeeded()
        app.terminate()

        // PartyNative.souvenirs.camera(id), comme le bouton « 📸 Prendre une photo » de la fiche.
        launch(once("PartyNative.souvenirs.camera('\(event)')"))
        XCTAssertTrue(app.buttons["souvenir-shutter"].waitForExistence(timeout: 45), "appareil photo ouvert par le pont")
        XCTAssertTrue(any("identifier == 'souvenir-poses' AND label == '3 poses'").waitForExistence(timeout: 15), "3 poses")
        XCTAssertTrue(any("identifier == 'souvenir-camera-promise' AND label CONTAINS 'pendant 24 h'").waitForExistence(timeout: 45),
                      "ce que deviennent les photos")
        shot("appareil-3-poses")

        // 1re photo puis « Annuler » : la pose est rendue.
        shoot("labo-annuler-5s")
        app.buttons["souvenir-cancel"].tap()  // aussitôt : la capture d'écran prend déjà 1 à 3 s des 5 s
        XCTAssertTrue(any("identifier == 'souvenir-problem' AND label CONTAINS 'Photo annulée'").waitForExistence(timeout: 15), "annulée")
        XCTAssertTrue(any("identifier == 'souvenir-poses' AND label == '3 poses'").waitForExistence(timeout: 5), "pose rendue")
        shot("annulee-pose-rendue")

        // Trois photos : pellicule terminée.
        shoot("photo-1")
        shoot("photo-2")
        shoot("photo-3")
        XCTAssertTrue(any("identifier == 'souvenir-poses' AND label == '0 pose'").exists, "0 pose")
        XCTAssertTrue(any("identifier == 'souvenir-finished'").waitForExistence(timeout: 20), "pellicule terminée")
        shot("pellicule-terminee")
        app.buttons["souvenir-camera-done"].tap()
        XCTAssertTrue(app.tabBars.firstMatch.waitForExistence(timeout: 10), "retour à la page")

        // Rouvert : refus lisible (« Tes 3 photos sont au labo »), sans déclencheur actif.
        app.terminate()
        launch(once("PartyNative.souvenirs.camera('\(event)')"))
        XCTAssertTrue(any("identifier == 'souvenir-finished'").waitForExistence(timeout: 45), "plus de pose")
        XCTAssertTrue(any("label CONTAINS 'Tes 3 photos sont au labo'").exists)
        shot("rouvert-plus-de-pose")
        app.buttons["souvenir-camera-done"].tap()
    }

    func test2Story() {
        launch()
        signInAdminIfNeeded()

        // Bulles en haut des Discussions : la story (néon) et la soirée au labo (grise, cadenas, compte à rebours).
        app.tabBars.buttons["Discussions"].tap()
        let story = app.buttons["souvenir-bubble-\(event)"]
        let waiting = app.buttons["souvenir-bubble-\(event2)"]
        XCTAssertTrue(story.waitForExistence(timeout: 40), "bulle de la story")
        XCTAssertTrue(waiting.waitForExistence(timeout: 10), "bulle au labo")
        XCTAssertTrue(waiting.label.contains("au labo"), waiting.label)
        shot("bulles")
        // Dans la ligne qui défile de la liste, XCUITest juge la bulle « non touchable » : vrai toucher à l'écran.
        waiting.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.4)).tap()
        XCTAssertTrue(any("identifier == 'souvenir-waiting-info'").waitForExistence(timeout: 5), "dévoilement annoncé")
        shot("bulles-labo-touchee")

        // La story : 5 photos (2 d'Agenda Léa, 3 d'Admin test), barres, auteur, « Visible encore … h ».
        story.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.4)).tap()
        XCTAssertTrue(any("identifier == 'souvenir-story-close'").waitForExistence(timeout: 20), "story ouverte")
        XCTAssertTrue(any("identifier == 'souvenir-position' AND label CONTAINS '/ 5'").waitForExistence(timeout: 20), "5 photos")
        XCTAssertTrue(any("identifier == 'souvenir-visible' AND label CONTAINS 'Visible encore'").exists, "visible encore")
        sleep(1)
        shot("story-1")

        // ⭐ Garder une photo d'un autre, puis Gardée.
        let keep = app.buttons["souvenir-keep"]
        XCTAssertTrue(keep.waitForExistence(timeout: 10), "⭐ Garder")
        keep.tap()
        XCTAssertTrue(any("identifier == 'souvenir-keep' AND label == 'Gardée dans tes souvenirs'").waitForExistence(timeout: 10), "Gardée")
        shot("story-gardee")

        // Maintenir = pause (la position ne change pas) ; toucher à droite = suivante.
        let photo = any("identifier == 'souvenir-photo'")
        photo.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).press(forDuration: 6)
        XCTAssertTrue(any("identifier == 'souvenir-position' AND label BEGINSWITH '1 /'").exists, "pause : toujours la 1re")
        photo.coordinate(withNormalizedOffset: CGVector(dx: 0.85, dy: 0.5)).tap()
        XCTAssertTrue(any("identifier == 'souvenir-position' AND label BEGINSWITH '2 /'").waitForExistence(timeout: 5), "suivante")
        photo.coordinate(withNormalizedOffset: CGVector(dx: 0.1, dy: 0.5)).tap()
        XCTAssertTrue(any("identifier == 'souvenir-position' AND label BEGINSWITH '1 /'").waitForExistence(timeout: 5), "précédente")

        // ⋯ Signaler, motif « Je suis sur la photo… », puis le message de remerciement : la photo part de la story.
        app.buttons["souvenir-more"].tap()
        app.buttons["Signaler la photo"].tap()
        let mine = app.buttons["souvenir-report-my_image"]
        XCTAssertTrue(mine.waitForExistence(timeout: 10), "motifs")
        shot("story-signaler-motifs")
        mine.tap()
        XCTAssertTrue(any("identifier == 'souvenir-report-thanks'").waitForExistence(timeout: 15), "merci")
        shot("story-signalee-merci")
        app.buttons["souvenir-report-done"].tap()
        XCTAssertTrue(any("identifier == 'souvenir-position' AND label CONTAINS '/ 4'").waitForExistence(timeout: 10), "photo retirée")

        // ⋯ Bloquer l'auteur de l'autre photo : ses photos disparaissent ; restent les 3 miennes.
        XCTAssertTrue(app.buttons["souvenir-more"].waitForExistence(timeout: 5), "⋯ sur la photo d'un autre")
        app.buttons["souvenir-more"].tap()
        let blockItem = app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Bloquer'")).firstMatch
        XCTAssertTrue(blockItem.waitForExistence(timeout: 5))
        blockItem.tap()
        let confirm = app.buttons.matching(NSPredicate(format: "label == 'Bloquer'")).firstMatch
        XCTAssertTrue(confirm.waitForExistence(timeout: 5), "confirmer le blocage")
        shot("story-bloquer")
        confirm.tap()
        XCTAssertTrue(any("identifier == 'souvenir-position' AND label CONTAINS '/ 3'").waitForExistence(timeout: 15), "ses photos parties")
        XCTAssertTrue(any("label == 'Ta photo · dans tes souvenirs'").waitForExistence(timeout: 5), "mes photos restent")
        shot("story-mes-photos")

        // Glisser vers le bas : fermée ; la bulle est « vue ».
        if app.buttons["souvenir-replay"].exists { app.buttons["souvenir-replay"].tap() }  // story finie : on la reprend
        app.swipeDown(velocity: .slow)  // depuis le milieu de l'écran : la photo
        XCTAssertTrue(any("identifier == 'souvenir-story-close'").waitForNonExistence(timeout: 10), "fermée d'un glissé")
        XCTAssertTrue(app.buttons["souvenir-bubble-\(event)"].waitForExistence(timeout: 20))
        sleep(2)
        shot("bulles-story-vue")

        // Réglages › Notifications : la ligne « Souvenirs ».
        app.tabBars.buttons["Réglages"].tap()
        let notifications = any("label BEGINSWITH 'Notifications'")
        XCTAssertTrue(notifications.waitForExistence(timeout: 15))
        notifications.tap()
        let row = any("identifier == 'notif-souvenirs'")
        for _ in 0..<16 where !row.exists { app.swipeUp(velocity: .slow); sleep(1) }
        if row.exists && !row.isHittable { app.swipeUp(velocity: .slow); sleep(1) }
        XCTAssertTrue(row.waitForExistence(timeout: 10), "ligne Souvenirs")
        shot("reglages-notifications-souvenirs")

        // Adresse de la notification « Les souvenirs sont dévoilés » (?souvenirs=1) suivie dans la page déjà prête (comme un
        // toucher, app ouverte) : la fiche derrière, la story native par-dessus ; puis, si un lien
        // est fourni, PartyNative.souvenirs.save(url) enregistre une photo dans Photos.
        app.terminate()
        var js = "if(!sessionStorage.recette){sessionStorage.recette='1';setTimeout(function(){location.href='/?tab=events&event=\(event)&souvenirs=1';},7000);}"
        if let save = env["RECETTE_SAVE"] {
            js += "if(!sessionStorage.saved){sessionStorage.saved='1';setTimeout(function(){PartyNative.souvenirs.save('\(save)')"
                + ".then(function(){document.title='ok';document.body.insertAdjacentHTML('afterbegin','<h1 style=\"position:fixed;top:120px;z-index:99999;background:#000;color:#fff\">PHOTO ENREGISTREE</h1>');})"
                + ".catch(function(e){document.body.insertAdjacentHTML('afterbegin','<h1 style=\"position:fixed;top:120px;z-index:99999;background:#000;color:#fff\">REFUS '+e+'</h1>');});},9000);}"
        }
        launch(js)
        XCTAssertTrue(any("identifier == 'souvenir-story-close'").waitForExistence(timeout: 45), "story ouverte par la notification")
        XCTAssertTrue(any("identifier == 'souvenir-position' AND label CONTAINS '/ 3'").waitForExistence(timeout: 20))
        sleep(1)
        shot("notif-story")
        app.buttons["souvenir-story-close"].firstMatch.tap()
        XCTAssertTrue(any("identifier == 'souvenir-story-close'").waitForNonExistence(timeout: 10))
        if env["RECETTE_SAVE"] != nil {
            app.tap()  // déclenche le moniteur d'alertes (autorisation « ajouter à Photos »)
            let saved = any("label CONTAINS 'PHOTO ENREGISTREE' OR label BEGINSWITH 'REFUS'")
            for _ in 0..<20 where !saved.exists { sleep(1); app.tap() }
            XCTAssertTrue(saved.exists && saved.label.contains("PHOTO ENREGISTREE"), saved.exists ? saved.label : "rien")
            shot("notif-save-photos")
        }
    }

    /// La discussion de l'événement (écran natif) pendant la story : bandeau « Les souvenirs sont arrivés » → la story.
    func test3ChatBanner() {
        launch(once("PartyNative.chat.openEvent('\(event)')", after: 6000))
        let banner = app.buttons["souvenir-chat-banner"]
        XCTAssertTrue(any("identifier == 'souvenir-chat-banner'").waitForExistence(timeout: 45), "bandeau des souvenirs")
        XCTAssertTrue(any("identifier == 'souvenir-chat-banner' AND label BEGINSWITH 'Les souvenirs sont arrivés'").exists)
        sleep(1)
        shot("discussion-bandeau-souvenirs")
        (banner.exists ? banner : any("identifier == 'souvenir-chat-banner'")).tap()
        XCTAssertTrue(any("identifier == 'souvenir-story-close'").waitForExistence(timeout: 20), "story ouverte depuis le bandeau")
        sleep(1)
        shot("discussion-story-ouverte")
        app.buttons["souvenir-story-close"].firstMatch.tap()
        XCTAssertTrue(any("identifier == 'souvenir-chat-banner'").waitForExistence(timeout: 15), "retour à la discussion")
        sleep(1)
        shot("discussion-bandeau-revoir")
    }
}

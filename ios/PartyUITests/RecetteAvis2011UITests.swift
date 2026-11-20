import XCTest

/// Recette RÉELLE des avis du 20.11.2026, dans le simulateur (configuration Release, comme l'App Store) : serveur Party
/// local branché sur la base de TEST, compte « Admin test » (code fixe, aucun SMS), réglages de la prod.
/// Préparé avant (script de recette) : 3 discussions épinglées d'Admin test (RECETTE_PINS = id,id,id dans l'ordre
/// affiché), une notification non lue « [QA] Glisser pour lire », la discussion directe avec « VIP test » (photo).
///   TEST_RUNNER_RECETTE_DIR=… TEST_RUNNER_RECETTE_PINS=… xcodebuild test-without-building -configuration Release …
///   -only-testing:PartyUITests/RecetteAvis2011UITests
final class RecetteAvis2011UITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment
    private var dir: URL!
    private var app: XCUIApplication!
    private var step = 0

    override func setUpWithError() throws {
        guard let path = env["RECETTE_DIR"], env["RECETTE_PINS"] != nil else { throw XCTSkip("Recette à la demande (RECETTE_DIR, RECETTE_PINS)") }
        dir = URL(fileURLWithPath: path)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        continueAfterFailure = true
        addUIInterruptionMonitor(withDescription: "Alertes d'iOS") { alert in
            for label in ["Autoriser", "Allow", "Ne pas autoriser", "Don’t Allow"] where alert.buttons[label].exists {
                alert.buttons[label].tap()
                return true
            }
            return false
        }
    }

    private func shot(_ name: String) {
        step += 1
        try? app.screenshot().pngRepresentation.write(to: dir.appendingPathComponent(String(format: "avis2011-%02d-%@.png", step, name)))
    }

    private func launch() {
        app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_JS"] = "localStorage.setItem('vp_install_dismissed','1');"
        app.launch()
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

    private func openChats() {
        let tab = app.tabBars.buttons["Discussions"]
        XCTAssertTrue(tab.waitForExistence(timeout: 20), "onglet Discussions")
        tab.tap()
    }

    /// Ids des tuiles épinglées, de gauche à droite.
    private func pinOrder() -> [String] {
        let tiles = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'chat-pin-'")).allElementsBoundByIndex
        return tiles.filter { $0.exists && $0.frame.width > 0 }
            .sorted { $0.frame.minX < $1.frame.minX }
            .map { String($0.identifier.dropFirst("chat-pin-".count)) }
    }

    /// Chaque tuile épinglée ouvre SON menu (bug trouvé par cette recette : l'appui long ouvrait toujours le menu de la
    /// première tuile, « Désépingler » touchait la mauvaise discussion) ; un toucher ouvre toujours la discussion.
    func test0EachPinnedTileOpensItsOwnMenu() {
        let direct = env["RECETTE_PINS"]!.split(separator: ",").map(String.init)[0]
        launch()
        signInAdminIfNeeded()
        openChats()
        XCTAssertTrue(app.buttons["chat-pin-\(direct)"].waitForExistence(timeout: 30), "tuiles")
        sleep(3)
        let tiles = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'chat-pin-'")).allElementsBoundByIndex
            .sorted { $0.frame.minX < $1.frame.minX }
        XCTAssertEqual(tiles.count, 3, "les 3 épinglées (aucune désépinglée en route)")
        for tile in tiles {
            let isDirect = tile.identifier == "chat-pin-\(direct)"
            tile.press(forDuration: 1.2)
            XCTAssertTrue(app.buttons["Réorganiser les épinglées"].waitForExistence(timeout: 5), "menu de \(tile.label)")
            shot("menu-\(tile.identifier.suffix(6))")
            // « Voir le profil » seulement dans le menu de la discussion directe : le menu est bien celui de la tuile.
            XCTAssertEqual(app.buttons["Voir le profil"].exists, isDirect, "menu de la bonne tuile : \(tile.label)")
            // iOS 27 : bulle sans « Annuler » (iPhone plus ancien : feuille avec « Annuler ») ; toucher à côté la ferme.
            if app.buttons["Annuler"].exists { app.buttons["Annuler"].tap() } else {
                app.coordinate(withNormalizedOffset: CGVector(dx: 0.97, dy: 0.62)).tap()
            }
            sleep(1)
            XCTAssertFalse(app.buttons["Réorganiser les épinglées"].exists, "menu fermé sans rien choisir")
        }
        XCTAssertEqual(app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'chat-pin-'")).count, 3, "toujours 3 épinglées après les menus")
        // Un toucher ouvre la discussion de la tuile (ici la dernière).
        tiles.last!.tap()
        sleep(3)
        shot("tuile-ouverte")
        XCTAssertFalse(app.buttons["chats-more"].isHittable, "la discussion s'est ouverte")
    }

    /// Avis e75a1d5af3ee : réorganiser les discussions épinglées (appui long d'une tuile, puis les poignées ≡).
    func test1PinnedChatsCanBeReordered() {
        let pins = env["RECETTE_PINS"]!.split(separator: ",").map(String.init)
        launch()
        signInAdminIfNeeded()
        openChats()
        let first = app.buttons["chat-pin-\(pins[0])"]
        XCTAssertTrue(first.waitForExistence(timeout: 30), "tuiles épinglées")
        sleep(2)
        XCTAssertEqual(pinOrder(), pins, "ordre de départ")
        shot("epinglees-avant")

        // Appui long sur une tuile : « Réorganiser les épinglées ».
        first.press(forDuration: 1.2)
        let reorder = app.buttons["Réorganiser les épinglées"]
        XCTAssertTrue(reorder.waitForExistence(timeout: 5), "menu : Réorganiser les épinglées")
        shot("menu-tuile")
        reorder.tap()
        let sheetRow = app.descendants(matching: .any).matching(identifier: "pin-order-\(pins[0])").firstMatch
        XCTAssertTrue(sheetRow.waitForExistence(timeout: 5), "feuille Épinglées")
        sleep(1)
        shot("feuille")

        // La première descend tout en bas : glisser sa poignée ≡ (bord droit de la ligne) sous la dernière.
        let lastRow = app.descendants(matching: .any).matching(identifier: "pin-order-\(pins[pins.count - 1])").firstMatch
        let handle = app.cells.containing(.any, identifier: "pin-order-\(pins[0])").firstMatch
        let target = app.cells.containing(.any, identifier: "pin-order-\(pins[pins.count - 1])").firstMatch
        XCTAssertTrue(handle.exists && target.exists && lastRow.exists, "lignes de la feuille")
        handle.coordinate(withNormalizedOffset: CGVector(dx: 0.95, dy: 0.5))
            .press(forDuration: 0.8, thenDragTo: target.coordinate(withNormalizedOffset: CGVector(dx: 0.95, dy: 1.6)))
        sleep(1)
        shot("feuille-glisse")
        app.buttons["pin-order-done"].tap()
        sleep(3)
        // Le geste du test n'est pas précis à la ligne près : la première a quitté la tête, les trois sont là.
        let expected = pinOrder()
        XCTAssertNotEqual(expected.first, pins[0], "la première a changé de place")
        XCTAssertEqual(Set(expected), Set(pins), "toujours les mêmes épinglées")
        shot("epinglees-apres")

        // Relancée (liste relue de la base) : l'ordre reste.
        app.terminate()
        launch()
        openChats()
        XCTAssertTrue(app.buttons["chat-pin-\(pins[1])"].waitForExistence(timeout: 30), "tuiles après relance")
        sleep(3)
        XCTAssertEqual(pinOrder(), expected, "ordre gardé après relance")
        shot("epinglees-relance")

        // Aussi par « … » : « Réorganiser les épinglées » ; Annuler ne change rien.
        app.buttons["chats-more"].tap()
        XCTAssertTrue(app.buttons["Réorganiser les épinglées"].waitForExistence(timeout: 5), "« … » : Réorganiser les épinglées")
        app.buttons["Réorganiser les épinglées"].tap()
        XCTAssertTrue(app.buttons["Annuler"].waitForExistence(timeout: 5), "feuille ouverte depuis « … »")
        app.buttons["Annuler"].tap()
        sleep(2)
        XCTAssertEqual(pinOrder(), expected, "Annuler ne change rien")
    }

    /// Avis 163be6ce5df6 : la photo du mini-profil s'ouvre en grand (natif), se zoome et se ferme.
    func test2ProfilePhotoOpensFullScreen() {
        launch()
        signInAdminIfNeeded()
        openChats()
        // La discussion avec VIP test (épinglée par la préparation de la recette).
        let row = app.buttons["chat-pin-\(env["RECETTE_PINS"]!.split(separator: ",")[0])"]
        XCTAssertTrue(row.waitForExistence(timeout: 30), "discussion avec VIP test")
        sleep(2)
        row.press(forDuration: 1.2)
        sleep(1)
        shot("menu-vip")
        let profile = app.buttons["Voir le profil"]
        XCTAssertTrue(profile.waitForExistence(timeout: 5), "menu : Voir le profil")
        profile.tap()
        let open = app.buttons["profile-photo-open"]
        XCTAssertTrue(open.waitForExistence(timeout: 20), "photo du mini-profil touchable")
        sleep(2)
        shot("mini-profil")
        open.tap()
        let full = app.descendants(matching: .any).matching(identifier: "profile-photo-full").firstMatch
        XCTAssertTrue(full.waitForExistence(timeout: 10), "photo en plein écran")
        sleep(2)
        XCTAssertGreaterThan(full.frame.width, app.frame.width * 0.9, "toute la largeur de l'écran")
        shot("photo-grand")
        full.doubleTap()
        sleep(1)
        shot("photo-zoom")
        app.buttons["profile-photo-close"].tap()
        sleep(1)
        XCTAssertFalse(full.exists, "fermée")
        XCTAssertTrue(open.exists, "retour au mini-profil")
        // Glisser vers le bas ferme aussi.
        open.tap()
        XCTAssertTrue(full.waitForExistence(timeout: 10), "rouverte")
        sleep(1)
        full.swipeDown(velocity: .fast)
        sleep(2)
        XCTAssertFalse(full.exists, "fermée en glissant vers le bas")
        shot("retour-mini-profil")
    }

    /// Avis 85cd4af01e3e : dans l'Activité (la cloche, page web dans l'app), glisser de droite à gauche = lue.
    func test3SwipeANotificationToMarkItRead() {
        launch()
        signInAdminIfNeeded()
        let events = app.tabBars.buttons["Événements"]
        XCTAssertTrue(events.waitForExistence(timeout: 20), "onglet Événements")
        events.tap()
        let bell = app.webViews.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Activité'")).firstMatch
        XCTAssertTrue(bell.waitForExistence(timeout: 40), "cloche")
        bell.tap()
        let tout = app.webViews.buttons["Tout"]
        if tout.waitForExistence(timeout: 15) { tout.tap() }
        let row = app.webViews.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Non lu : [QA] Glisser pour lire'")).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 20), "notification non lue de la recette")
        sleep(1)
        shot("activite-avant")
        row.swipeLeft(velocity: .slow)
        let read = app.webViews.buttons.matching(NSPredicate(format: "label BEGINSWITH '[QA] Glisser pour lire'")).firstMatch
        XCTAssertTrue(read.waitForExistence(timeout: 10), "marquée lue par le glissé")
        XCTAssertTrue(app.webViews.staticTexts["Activité"].exists, "toujours dans l'Activité (rien ouvert)")
        sleep(1)
        shot("activite-apres")
    }
}

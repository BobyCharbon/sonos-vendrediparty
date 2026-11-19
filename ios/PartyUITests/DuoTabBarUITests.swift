import XCTest

/// iPhone Duo (simulateur « iPhone Duo », iOS 27.1+) : la barre d'onglets suit le système (verticale sur le côté de
/// l'écran extérieur) et un toucher passe toujours par la page (PartyTabs.select), qui allume l'onglet choisi.
/// Sur un autre iPhone, la même recette vérifie la barre du bas (rien n'a changé). Il faut le site chargé par l'app
/// (site de test en Debug, ou PARTY_BASE_URL) : ignoré sans TEST_RUNNER_PARTY_DUO_UI=1
/// (`xcodebuild test … -only-testing:PartyUITests/DuoTabBarUITests TEST_RUNNER_PARTY_DUO_UI=1`, plus
/// TEST_RUNNER_PARTY_DUO_VERTICAL=1 sur l'écran extérieur du Duo, où la barre doit être verticale).
final class DuoTabBarUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
        try XCTSkipUnless(ProcessInfo.processInfo.environment["PARTY_DUO_UI"] == "1", "Recette Duo : site requis")
    }

    private func snapshot(_ app: XCUIApplication, _ name: String) {
        let shot = XCTAttachment(screenshot: app.screenshot())
        shot.name = name
        shot.lifetime = .keepAlways
        add(shot)
    }

    func testTheTabBarFollowsTheSystemAndTouchesReachThePage() {
        let app = XCUIApplication()
        // Départ connu : l'onglet Musique (la page le retient dans vp_tab).
        app.launchEnvironment["PARTY_DEBUG_JS"] = "localStorage.setItem('vp_tab','music');"
        app.launch()
        // Barre du bas : élément « tab bar » ; barre verticale du système : rangée dans une « toolbar ».
        let games = app.buttons["Jeux"]
        let music = app.buttons["Musique"]
        XCTAssertTrue(games.waitForExistence(timeout: 40), app.debugDescription)
        let screen = app.windows.firstMatch.frame
        if ProcessInfo.processInfo.environment["PARTY_DUO_VERTICAL"] == "1" {
            // Écran extérieur du Duo : boutons empilés dans la colonne de droite (sous la barre d'état).
            XCTAssertEqual(games.frame.midX, music.frame.midX, accuracy: 2)
            XCTAssertGreaterThan(games.frame.midY, music.frame.midY)
            XCTAssertGreaterThan(games.frame.minX, screen.width * 0.75, "barre verticale à droite attendue : \(games.frame)")
        } else {
            // Autres iPhone (et Duo ouvert en portrait) : la barre du bas, comme avant.
            XCTAssertTrue(app.tabBars.buttons["Jeux"].exists)
            XCTAssertEqual(games.frame.midY, music.frame.midY, accuracy: 2)
            XCTAssertGreaterThan(games.frame.minY, screen.height * 0.8)
        }
        snapshot(app, "duo-1-depart")

        games.tap()
        let selected = NSPredicate(format: "isSelected == true")
        wait(for: [expectation(for: selected, evaluatedWith: games)], timeout: 10)
        snapshot(app, "duo-2-jeux")

        music.tap()
        wait(for: [expectation(for: selected, evaluatedWith: music)], timeout: 10)
        XCTAssertFalse(games.isSelected)
    }

    /// « Retour » en haut de la barre verticale (comme Safari) quand la page a un écran derrière ; il le referme.
    func testBackSitsAtTheTopOfTheVerticalBarAndClosesThePageLayer() throws {
        try XCTSkipUnless(ProcessInfo.processInfo.environment["PARTY_DUO_VERTICAL"] == "1", "iPhone Duo seulement")
        let app = XCUIApplication()
        // Onglet Jeux (page), puis une feuille de la page (pile Nav) s'ouvre : il y a un écran derrière.
        app.launchEnvironment["PARTY_DEBUG_JS"] = """
        localStorage.setItem('vp_tab','games');
        addEventListener('load', function () { setTimeout(function () {
          document.getElementById('installSheet').classList.remove('hidden'); }, 1500); });
        """
        app.launch()
        let back = app.buttons["duo-back"]
        XCTAssertTrue(back.waitForExistence(timeout: 40), app.debugDescription)
        let games = app.buttons["Jeux"]
        XCTAssertEqual(back.frame.midX, games.frame.midX, accuracy: 4, "Retour dans la barre verticale : \(back.frame)")
        XCTAssertLessThan(back.frame.midY, games.frame.midY, "Retour au-dessus des onglets")
        snapshot(app, "duo-4-retour")
        back.tap()
        wait(for: [expectation(for: NSPredicate(format: "exists == false"), evaluatedWith: back)], timeout: 10)
        snapshot(app, "duo-5-apres-retour")
    }

    /// Réglages natifs › Notifications : iOS pose le « ‹ » de la pile en haut de la colonne de la barre verticale, sous
    /// la barre d'onglets du système ; il doit ramener aux Réglages (retour de l'admin, 19.11 : il ne faisait rien).
    func testSettingsBackInTheVerticalBarClosesTheSubPage() throws {
        try XCTSkipUnless(ProcessInfo.processInfo.environment["PARTY_DUO_VERTICAL"] == "1", "iPhone Duo seulement")
        let app = XCUIApplication()
        app.launch()
        // Onglet Réglages, nommé « Se connecter » sans compte (barre verticale : rangée d'une « toolbar »).
        let settings = app.toolbars.buttons.matching(NSPredicate(format: "label IN {'Réglages', 'Se connecter'}")).firstMatch
        XCTAssertTrue(settings.waitForExistence(timeout: 40), app.debugDescription)
        settings.tap()
        let notifications = app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Notifications'")).firstMatch
        XCTAssertTrue(notifications.waitForExistence(timeout: 15), app.debugDescription)
        notifications.tap()
        // Dans la colonne, le « ‹ » de la pile n'est plus dans sa barre de navigation : bouton « BackButton ».
        let back = app.buttons["BackButton"]
        XCTAssertTrue(back.waitForExistence(timeout: 10), app.debugDescription)
        XCTAssertGreaterThan(back.frame.minX, app.windows.firstMatch.frame.width * 0.75, "« ‹ » dans la colonne : \(back.frame)")
        snapshot(app, "duo-6-notifications")
        back.tap()
        wait(for: [expectation(for: NSPredicate(format: "exists == false"), evaluatedWith: back)], timeout: 10)
        XCTAssertTrue(notifications.waitForExistence(timeout: 5), "Retour aux Réglages attendu")
        snapshot(app, "duo-7-retour-reglages")
    }

    /// Écrans natifs (Musique, Discussions, Réglages) sur l'écran extérieur du Duo : rien sous la colonne de la barre d'état
    /// ni sous la barre verticale (recette du 19.11 : « Entrer » et la fin de la consigne de Musique passaient dessous).
    func testNativeScreensStayLeftOfTheStatusColumn() throws {
        try XCTSkipUnless(ProcessInfo.processInfo.environment["PARTY_DUO_VERTICAL"] == "1", "iPhone Duo seulement")
        let app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_JS"] = "localStorage.setItem('vp_tab','music');"
        app.launch()
        let music = app.buttons["Musique"]
        XCTAssertTrue(music.waitForExistence(timeout: 40), app.debugDescription)
        music.tap()
        let scan = app.buttons.matching(NSPredicate(format: "label CONTAINS 'Scanner le QR'")).firstMatch
        XCTAssertTrue(scan.waitForExistence(timeout: 30), "Musique (écran natif) : « Scanner le QR de l'hôte »")
        sleep(2)
        snapshot(app, "duo-6-musique")
        // La colonne de droite (heure, réseau, barre d'onglets) commence au bord gauche des boutons d'onglets.
        let column = music.frame.minX
        XCTAssertLessThanOrEqual(scan.frame.maxX, column, "« Scanner le QR » sous la colonne de droite : \(scan.frame) / \(column)")
        let code = app.buttons.matching(NSPredicate(format: "label == 'Entrer'")).firstMatch
        if code.exists { XCTAssertLessThanOrEqual(code.frame.maxX, column, "« Entrer » sous la colonne de droite : \(code.frame)") }
    }

    /// Onglet Événements (module web dans le cadre de la page), compte connecté : l'accueil prend toute la largeur jusqu'à
    /// la colonne de droite (retour de l'admin du 19.11 sur son Duo plié : ~64 % de la largeur, « Événements » coupé en
    /// trois lignes, filtres coupés, « + Proposer » sur la liste). Session de test : TEST_RUNNER_PARTY_DUO_SESSION.
    func testTheEventsHomeUsesTheWholeWidthUpToTheColumn() throws {
        try XCTSkipUnless(ProcessInfo.processInfo.environment["PARTY_DUO_VERTICAL"] == "1", "iPhone Duo seulement")
        let session = try XCTUnwrap(ProcessInfo.processInfo.environment["PARTY_DUO_SESSION"], "session de test (TEST_RUNNER_PARTY_DUO_SESSION)")
        let app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_JS"] = "localStorage.setItem('sb-ewromqfsmcqsthftyhzm-auth-token', \(session));"
            + "localStorage.setItem('vp_tab','events');localStorage.setItem('vp_install_dismissed','1');"
        app.launch()
        let title = app.webViews.staticTexts["Événements"].firstMatch
        let bell = app.webViews.buttons["home-bell"].exists ? app.webViews.buttons["home-bell"]
            : app.webViews.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Activité' OR label BEGINSWITH 'Notifications'")).firstMatch
        XCTAssertTrue(title.waitForExistence(timeout: 60), app.debugDescription)
        let propose = app.webViews.buttons["Proposer un événement"]
        XCTAssertTrue(propose.waitForExistence(timeout: 30), "« + Proposer »")
        sleep(3)
        snapshot(app, "duo-7-evenements")
        let column = app.buttons["Musique"].frame.minX
        // Une seule ligne pour « Événements » (coupé en trois avant : ~90 pt de haut).
        XCTAssertLessThan(title.frame.height, 64, "titre « Événements » sur plusieurs lignes : \(title.frame)")
        // Le contenu va jusqu'à la colonne (marge de la page comprise), « + Proposer » reste dans le contenu.
        if bell.exists { XCTAssertGreaterThan(bell.frame.maxX, column - 60, "en-tête arrêté loin de la colonne : \(bell.frame) / \(column)") }
        XCTAssertLessThanOrEqual(propose.frame.maxX, column, "« + Proposer » sous la colonne : \(propose.frame)")
    }

    /// Pont du pli : la page reçoit la posture (événement « party-fold », `<html data-posture>`). Duo fermé : « closed ».
    func testThePageKnowsThePosture() throws {
        try XCTSkipUnless(ProcessInfo.processInfo.environment["PARTY_DUO_VERTICAL"] == "1", "iPhone Duo seulement")
        let app = XCUIApplication()
        // Sonde de test : un bouton lisible par XCUITest recopie ce que la page a reçu.
        app.launchEnvironment["PARTY_DEBUG_JS"] = """
        window.addEventListener('party-fold', function (e) {
          var b = document.getElementById('fold-probe') || document.createElement('button');
          b.id = 'fold-probe'; b.style.cssText = 'position:fixed;top:120px;left:20px;z-index:99999';
          b.textContent = 'posture ' + e.detail.posture + ' ' + document.documentElement.getAttribute('data-posture');
          (document.body || document.documentElement).appendChild(b);
        });
        """
        app.launch()
        XCTAssertTrue(app.buttons["posture closed closed"].waitForExistence(timeout: 40), app.debugDescription)
        snapshot(app, "duo-3-posture")
    }
}

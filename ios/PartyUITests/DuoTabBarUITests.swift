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

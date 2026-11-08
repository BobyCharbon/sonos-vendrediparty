import XCTest

/// Bulle de Zicou native (avis 3cd6d282745b, 08.11), dans l'app : glisser vers un autre coin (retenu au relancement),
/// puis Réglages › « Bulle de Zicou » la masque. Il faut l'app BETA (Zicou compilé) branchée sur un serveur Party local
/// (PARTY_BASE_URL) : la description de la page est imposée par PARTY_DEBUG_JS. Ignoré sans
/// TEST_RUNNER_PARTY_ZICOU_UI=1 (`xcodebuild test … TEST_RUNNER_PARTY_ZICOU_UI=1`).
final class ZicouBubbleUITests: XCTestCase {
    private static let fakeState = """
    localStorage.setItem('vp_tab','games'); setInterval(function () { window.webkit.messageHandlers.partyZicou.postMessage(\
    {visible:true,stage:'adult',emotion:'hungry',red:true,asleep:false,label:'Zicou : a faim',hint:null}); }, 1000);
    """

    override func setUpWithError() throws {
        continueAfterFailure = false
        try XCTSkipUnless(ProcessInfo.processInfo.environment["PARTY_ZICOU_UI"] == "1", "Recette de la bulle : serveur local requis")
    }

    private func launch(resetSpot: Bool) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_JS"] = Self.fakeState
        if resetSpot { app.launchArguments += ["-zicouBubbleSpot", "bottomTrailing", "-zicouBubbleShown", "YES"] }
        app.launch()
        return app
    }

    private func snapshot(_ app: XCUIApplication, _ name: String) {
        let shot = XCTAttachment(screenshot: app.screenshot())
        shot.name = name
        shot.lifetime = .keepAlways
        add(shot)
    }

    private func flip(_ toggle: XCUIElement) {
        let knob = toggle.switches.firstMatch
        (knob.exists ? knob : toggle).tap()
    }

    func testTheBubbleMovesToAnotherCornerAndTheSettingHidesIt() {
        var app = launch(resetSpot: true)
        let bubble = app.buttons["zicou-bubble"]
        XCTAssertTrue(bubble.waitForExistence(timeout: 30))
        let screen = app.windows.firstMatch.frame
        XCTAssertGreaterThan(bubble.frame.midX, screen.midX)              // en bas à droite au départ
        XCTAssertGreaterThan(bubble.frame.midY, screen.midY)
        snapshot(app, "bulle-1-bas-droite")

        // Glisser vers le haut à gauche : elle s'y pose.
        let start = bubble.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5))
        let target = app.windows.firstMatch.coordinate(withNormalizedOffset: CGVector(dx: 0.08, dy: 0.18))
        // Glisser lent, comme un doigt, puis tenu un instant : la bulle suit le doigt, les repères s'affichent.
        start.press(forDuration: 0.3, thenDragTo: target, withVelocity: XCUIGestureVelocity(220), thenHoldForDuration: 0.8)
        let movedLeft = NSPredicate { _, _ in bubble.frame.midX < screen.midX && bubble.frame.midY < screen.midY }
        wait(for: [expectation(for: movedLeft, evaluatedWith: nil)], timeout: 5)
        snapshot(app, "bulle-2-haut-gauche")

        // Retenu au prochain lancement.
        app.terminate()
        app = launch(resetSpot: false)
        let again = app.buttons["zicou-bubble"]
        XCTAssertTrue(again.waitForExistence(timeout: 30))
        XCTAssertLessThan(again.frame.midX, screen.midX)
        XCTAssertLessThan(again.frame.midY, screen.midY)

        // Réglages › Bulle de Zicou : éteinte, la bulle s'en va.
        app.tabBars.buttons.element(boundBy: app.tabBars.buttons.count - 1).tap()
        let toggle = app.switches["settings-zicou-bubble"]
        XCTAssertTrue(toggle.waitForExistence(timeout: 10))
        snapshot(app, "bulle-3-reglage")
        flip(toggle)
        wait(for: [expectation(for: NSPredicate(format: "exists == false"), evaluatedWith: again)], timeout: 5)
        snapshot(app, "bulle-4-masquee")
        flip(toggle)                                                       // remise comme avant
        XCTAssertTrue(again.waitForExistence(timeout: 5))
    }
}

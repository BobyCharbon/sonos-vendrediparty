import UIKit
import XCTest

/// « Créer avec l'IA » (retour du 03.11) : une image copiée se colle par le bouton « Coller » ou par appui long ›
/// Coller dans le champ, et arrive en vignette avec sa croix. Écran de conseils (PARTY_DEBUG_AI_EVENT=tips), sans serveur.
final class AIEventPasteUITests: XCTestCase {
    override func setUp() {
        continueAfterFailure = false
    }

    private func launch() -> XCUIApplication {
        let app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_AI_EVENT"] = "tips"
        app.launch()
        XCTAssertTrue(app.staticTexts["Décris ton événement"].waitForExistence(timeout: 15))
        return app
    }

    private func copyImages(_ count: Int) {
        let format = UIGraphicsImageRendererFormat.default()
        format.scale = 1
        let colors: [UIColor] = [.systemPink, .systemTeal, .systemOrange, .systemPurple]
        UIPasteboard.general.images = (0..<count).map { i in
            UIGraphicsImageRenderer(size: CGSize(width: 600, height: 400), format: format).image { context in
                colors[i % colors.count].setFill()
                context.fill(CGRect(x: 0, y: 0, width: 600, height: 400))
            }
        }
    }

    private func removeButtons(_ app: XCUIApplication) -> XCUIElementQuery {
        app.buttons.matching(identifier: "Retirer cette capture")
    }

    private func snapshot(_ app: XCUIApplication, _ name: String) {
        let shot = XCTAttachment(screenshot: app.screenshot())
        shot.name = name
        shot.lifetime = .keepAlways
        add(shot)
    }

    func testThePasteButtonAttachesTheCopiedImage() {
        let app = launch()
        copyImages(1)
        let paste = app.buttons["ai-paste"]
        XCTAssertTrue(paste.waitForExistence(timeout: 5))
        paste.tap()
        XCTAssertTrue(removeButtons(app).firstMatch.waitForExistence(timeout: 5))
        XCTAssertEqual(removeButtons(app).count, 1)
        snapshot(app, "coller-bouton")
        removeButtons(app).firstMatch.tap()
        XCTAssertFalse(removeButtons(app).firstMatch.waitForExistence(timeout: 2))
    }

    func testPastingInTheTextFieldAttachesImagesUpToThree() {
        let app = launch()
        copyImages(4)
        let field = app.textViews["ai-text"]
        XCTAssertTrue(field.waitForExistence(timeout: 5))
        field.tap()
        field.press(forDuration: 1.0)
        let menuPaste = app.menuItems.matching(NSPredicate(format: "label IN %@", ["Coller", "Paste"])).firstMatch
        XCTAssertTrue(menuPaste.waitForExistence(timeout: 5))
        menuPaste.tap()
        XCTAssertTrue(removeButtons(app).firstMatch.waitForExistence(timeout: 5))
        XCTAssertEqual(removeButtons(app).count, 3)
        XCTAssertTrue(app.staticTexts["3 images au plus : 1 image n'a pas été ajoutée."].waitForExistence(timeout: 3))
        snapshot(app, "coller-champ-limite")
    }
}

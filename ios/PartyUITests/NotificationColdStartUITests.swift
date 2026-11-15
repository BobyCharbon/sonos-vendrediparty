import XCTest

/// Toucher une notification, app FERMÉE, ouvre la bonne page (campagne de tests du 14.11.2026 : l'agent APNs soupçonnait
/// que `partyOpenURL` partait avant que la vue SwiftUI l'écoute). Essai réel dans le simulateur, piloté de l'extérieur :
///   1. ce test ferme l'app (notifications déjà autorisées) ;
///   2. pendant qu'il attend, `xcrun simctl push <appareil> <bundle> charge.apns` avec `"url": "/events/event/<id>"` ;
///   3. ce test touche la notification dans le Centre de notifications, puis attend le titre de l'événement dans l'app.
/// TEST_RUNNER_NOTIF_TITLE = titre de la notification, TEST_RUNNER_NOTIF_EXPECT = texte attendu sur la page ouverte.
final class NotificationColdStartUITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment

    func testTappingANotificationWhileClosedOpensItsPage() throws {
        guard let title = env["NOTIF_TITLE"], !title.isEmpty, let expected = env["NOTIF_EXPECT"] else {
            throw XCTSkip("Essai piloté de l'extérieur (NOTIF_TITLE, NOTIF_EXPECT)")
        }
        let app = XCUIApplication()
        app.terminate()  // app fermée : le toucher la lance à froid
        XCTAssertEqual(app.state, .notRunning, "l'app doit être fermée avant le toucher")

        // La notification est envoyée de l'extérieur (simctl push) une fois ce test lancé : bannière, sinon le Centre.
        let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        let note = springboard.descendants(matching: .any)
            .matching(NSPredicate(format: "label CONTAINS %@", title)).firstMatch
        if !note.waitForExistence(timeout: 60) {
            // Centre de notifications : glisser depuis le haut de l'écran.
            let top = springboard.coordinate(withNormalizedOffset: CGVector(dx: 0.3, dy: 0.01))
            top.press(forDuration: 0.1, thenDragTo: springboard.coordinate(withNormalizedOffset: CGVector(dx: 0.3, dy: 0.7)))
        }
        XCTAssertTrue(note.waitForExistence(timeout: 10), "notification « \(title) » introuvable")
        note.tap()

        XCTAssertTrue(app.wait(for: .runningForeground, timeout: 20), "l'app ne s'est pas ouverte")
        let page = app.webViews.descendants(matching: .any)
            .matching(NSPredicate(format: "label CONTAINS %@", expected)).firstMatch
        let opened = page.waitForExistence(timeout: 30)
        if let dir = env["NOTIF_SHOTS"] {
            try? app.screenshot().pngRepresentation.write(to: URL(fileURLWithPath: dir).appendingPathComponent("notif-froid.png"))
        }
        XCTAssertTrue(opened, "la page de la notification (« \(expected) ») ne s'est pas ouverte")
    }
}

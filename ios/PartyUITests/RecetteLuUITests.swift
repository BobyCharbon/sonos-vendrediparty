import XCTest

/// Recette RÉELLE du bug du 19.11 (« ça me garde un message en non lu alors que je suis allé sur la conversation »), dans
/// le simulateur, configuration Release : serveur Party local branché sur la base de TEST, compte « Admin test ». Un
/// message de Guest B attend dans un message direct, un groupe et une discussion d'événement (LU_CHATS = leurs ids,
/// préparés avant). Liste des Discussions (le direct et le groupe se préchargent), toucher chaque ligne, revenir :
/// la ligne ne dit plus « non lu ». La base est relue ensuite par le script de la recette (chat_list de l'Admin à 0).
///   TEST_RUNNER_LU_DIR=… TEST_RUNNER_LU_CHATS=<direct>,<groupe>,<événement> xcodebuild test -configuration Release
///   ENABLE_TESTABILITY=YES PARTY_SWIFT_CONDITIONS=E2E_HOOKS PARTY_BASE_URL=http://127.0.0.1:<port>
///   -only-testing:PartyUITests/RecetteLuUITests
final class RecetteLuUITests: XCTestCase {
    private let env = ProcessInfo.processInfo.environment
    private var dir: URL!
    private var app: XCUIApplication!

    override func setUpWithError() throws {
        guard let path = env["LU_DIR"], env["LU_CHATS"] != nil else { throw XCTSkip("Recette à la demande (LU_DIR, LU_CHATS)") }
        dir = URL(fileURLWithPath: path)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        continueAfterFailure = true
        addUIInterruptionMonitor(withDescription: "Alertes d'iOS") { alert in
            for label in ["Autoriser", "Allow", "Ne pas autoriser", "Don’t Allow", "Plus tard", "Not Now"] where alert.buttons[label].exists {
                alert.buttons[label].tap()
                return true
            }
            return false
        }
    }

    private func shot(_ name: String) {
        try? app.screenshot().pngRepresentation.write(to: dir.appendingPathComponent("lu-\(name).png"))
    }

    private func signInAdminIfNeeded() {
        let tab = app.tabBars.buttons.matching(NSPredicate(format: "label IN {'Réglages', 'Se connecter'}")).firstMatch
        XCTAssertTrue(tab.waitForExistence(timeout: 40), "onglet Réglages")
        if app.tabBars.buttons["Réglages"].waitForExistence(timeout: 8) { return }
        tab.tap()
        sleep(2)
        let entry = app.descendants(matching: .any).matching(NSPredicate(format: "label BEGINSWITH 'Se connecter, '")).firstMatch
        if entry.waitForExistence(timeout: 10) { entry.tap() } else { app.staticTexts["Se connecter"].firstMatch.tap() }
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

    func testOpeningAConversationReadsIt() {
        let chats = env["LU_CHATS"]!.split(separator: ",").map(String.init)
        app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_JS"] = "localStorage.setItem('vp_install_dismissed','1');"
        app.launch()
        signInAdminIfNeeded()
        sleep(3)
        let tab = app.tabBars.buttons["Discussions"]
        XCTAssertTrue(tab.waitForExistence(timeout: 20), "onglet Discussions")
        tab.tap()
        var badges = ["avant: \(tab.value as? String ?? "")"]
        for (i, chat) in chats.enumerated() {
            let row = app.buttons["chat-row-\(chat)"]
            XCTAssertTrue(row.waitForExistence(timeout: 20), "ligne \(chat)")
            sleep(4)  // la liste précharge ses premières conversations (ce qui cachait le bug)
            XCTAssertTrue(row.label.contains("non lu"), "avant : \(row.label)")
            shot("\(i)-1-liste")
            row.tap()
            XCTAssertTrue(app.descendants(matching: .any)["chat-message"].waitForExistence(timeout: 20), "conversation ouverte")
            sleep(2)
            shot("\(i)-2-conversation")
            let back = app.buttons["event-chat-close"].exists ? app.buttons["event-chat-close"] : app.navigationBars.buttons.firstMatch
            back.tap()
            XCTAssertTrue(row.waitForExistence(timeout: 20), "retour à la liste")
            sleep(2)
            XCTAssertFalse(row.label.contains("non lu"), "après : \(row.label)")
            badges.append("après \(i): \(tab.value as? String ?? "")")
            shot("\(i)-3-retour")
        }
        try? badges.joined(separator: "\n").data(using: .utf8)!.write(to: dir.appendingPathComponent("lu-pastilles.txt"))
    }
}

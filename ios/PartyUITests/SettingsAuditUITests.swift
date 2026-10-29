import XCTest

/// Audit des Réglages en vrai, sur le site de test (base Supabase de TEST, numéros de test à code fixe, aucun SMS) :
/// connexion en membre puis en admin, chaque ligne touchée, capture et arbre d'accessibilité enregistrés.
/// Lancé seulement à la demande : TEST_RUNNER_PARTY_AUDIT=<dossier> xcodebuild test -only-testing:PartyUITests/SettingsAuditUITests
final class SettingsAuditUITests: XCTestCase {
    static let memberPhone = "0790000003"   // « VIP test », Membre VIP sur la base de test
    static let adminPhone = "0790000004"    // « Admin test », Admin sur la base de test
    static let code = "123456"

    private var dir: URL!
    private var app: XCUIApplication!
    private var step = 0
    private var prefix = ""

    override func setUpWithError() throws {
        guard let path = ProcessInfo.processInfo.environment["PARTY_AUDIT"] else { throw XCTSkip("Audit à la demande (PARTY_AUDIT)") }
        dir = URL(fileURLWithPath: path)
        continueAfterFailure = true
    }

    private func record(_ name: String) {
        step += 1
        let base = String(format: "%@-%02d-%@", prefix, step, name.replacingOccurrences(of: "/", with: "_"))
        try? app.screenshot().pngRepresentation.write(to: dir.appendingPathComponent("\(base).png"))
        try? app.debugDescription.write(to: dir.appendingPathComponent("\(base).txt"), atomically: true, encoding: .utf8)
    }

    private func settingsTab() {
        let tab = app.tabBars.buttons.matching(NSPredicate(format: "label IN {'Réglages', 'Se connecter'}")).firstMatch
        XCTAssertTrue(tab.waitForExistence(timeout: 20), "onglet Réglages")
        tab.tap()
        sleep(2)
    }

    private func back() {
        let capsule = app.buttons["Réglages"]
        if app.navigationBars.buttons.count > 0, app.navigationBars.buttons.firstMatch.isHittable {
            app.navigationBars.buttons.firstMatch.tap()
        } else if capsule.exists {
            capsule.firstMatch.tap()
        } else {
            app.swipeRight()
        }
        sleep(2)
    }

    private func signIn(_ phone: String) {
        settingsTab()
        record("avant-connexion")
        app.collectionViews.cells.element(boundBy: 0).tap()   // ligne « Se connecter » en tête des Réglages
        sleep(3)
        let field = app.webViews.textFields["Ton numéro de téléphone"]
        XCTAssertTrue(field.waitForExistence(timeout: 20), "champ du numéro")
        record("connexion")
        type(phone, into: field)
        app.webViews.buttons["Recevoir un code par SMS"].tap()
        sleep(4)
        record("code")
        type(Self.code, into: app.webViews.textFields.firstMatch)
        app.webViews.buttons["Se connecter"].firstMatch.tap()
        sleep(8)
        record("connecte")
    }

    /// Champ de la page : le clavier logiciel met un instant à prendre le focus dans la vue web.
    private func type(_ text: String, into field: XCUIElement) {
        for _ in 0..<3 {
            field.tap()
            if app.keyboards.firstMatch.waitForExistence(timeout: 3) { break }
        }
        app.typeText(text)
    }

    /// Touche une ligne des Réglages (par son titre), enregistre ce qui s'affiche, puis revient.
    private func visit(_ title: String, inside: (() -> Void)? = nil) {
        settingsTab()
        let cell = app.staticTexts[title].firstMatch
        for _ in 0..<4 where !cell.isHittable { app.swipeUp() }
        guard cell.exists else {
            record("ABSENT-\(title)")
            return
        }
        cell.tap()
        sleep(4)
        record(title)
        inside?()
        back()
    }

    private func auditCommon() {
        settingsTab()
        record("reglages-haut")
        app.swipeUp()
        record("reglages-bas")
        app.swipeDown()
        visit("Notifications") {
            for _ in 0..<3 { self.app.swipeUp(); self.record("notifications-suite") }
        }
        visit("Groupes")
        visit("Mes stats de jeu")
        visit("Ton avis")
        visit("Confidentialité")
        visit("Gérer mon compte")
        settingsTab()
        app.swipeDown()
        let profile = app.buttons.containing(NSPredicate(format: "label BEGINSWITH 'Mon profil'")).firstMatch
        if profile.exists {
            profile.tap()
            sleep(3)
            record("profil")
            back()
        }
    }

    private func launch() {
        app = XCUIApplication()
        app.launch()
    }

    func testMember() {
        launch()
        prefix = "membre"
        signIn(Self.memberPhone)
        auditCommon()
        visit("Se déconnecter")
    }

    func testAdmin() {
        launch()
        prefix = "admin"
        signIn(Self.adminPhone)
        auditCommon()
        visit("Invités et messages")
        visit("Admin de la soirée")
        visit("Administration du groupe") {
            for title in ["Membres", "Rôles et droits", "Journal des membres", "Utilisateurs", "Annonces admin", "Catégories et tags"] {
                let row = self.app.staticTexts[title].firstMatch
                for _ in 0..<3 where !row.isHittable { self.app.swipeUp() }
                guard row.exists else { self.record("ABSENT-\(title)"); continue }
                row.tap()
                sleep(4)
                self.record("groupe-\(title)")
                self.back()
            }
        }
        visit("Se déconnecter")
    }
}

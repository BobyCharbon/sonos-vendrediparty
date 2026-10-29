import XCTest

/// Administration du groupe native, en vrai simulateur : accueil, membres, fiche d'un membre, rôles et droits.
/// État de démonstration (PARTY_DEBUG_GROUP_ADMIN) : aucun serveur nécessaire.
final class GroupAdminUITests: XCTestCase {
    static let demo = ##"""
    {"overview": {"me": "me", "perms": ["events.approve", "members.approve", "group.settings", "roles.manage", "taxonomy.manage", "announcements.publish"], "rank": 4, "require_approval": true,
      "events": [{"id": "e1", "title": "Raclette chez Tom", "author": "Tom", "at": "2026-10-29T10:00:00+00:00", "summary": "12 places", "starts_at": "2026-11-12T19:00:00+00:00"}],
      "requests": [{"id": "u2", "name": "Léa", "full_name": "Léa Martin", "phone": "41791234567", "photo": null, "message": "Salut, c'est Léa du foot !", "at": "2026-10-29T09:00:00+00:00", "complete": true},
                   {"id": "u3", "name": "", "full_name": "", "phone": "41790000000", "photo": null, "message": null, "at": null, "complete": false}]},
     "members": {"me": "me", "perms": [], "rank": 4, "full": true, "people": [
      {"id": "me", "name": "Boby", "full_name": "Ludo T", "role": "admin", "status": "active", "root": true, "complete": true},
      {"id": "a", "name": "Paul", "full_name": "Paul D", "role": "organizer", "status": "active", "complete": true},
      {"id": "b", "name": "Léa", "full_name": "Léa Martin", "phone": "41791234567", "role": "member", "status": "active", "beta": true, "complete": true, "created_at": "2026-10-01T10:00:00+00:00"},
      {"id": "c", "name": "Zoé", "full_name": "Zoé R", "role": "basic", "status": "active", "complete": false},
      {"id": "d", "name": "Max", "role": "guest", "status": "banned"}]},
     "roles": {"me": "me", "perms": ["events.approve"], "rank": 4, "editable": ["coadmin", "organizer", "member", "basic", "guest"],
      "catalog": [{"key": "events.approve", "grp": "Événements", "label": "Valider les propositions", "hint": "Publier ou refuser"},
                  {"key": "events.publish", "grp": "Événements", "label": "Publier sans validation", "hint": null},
                  {"key": "members.ban", "grp": "Membres", "label": "Retirer l'accès", "hint": null}],
      "grants": {"member": ["events.publish"]}}}
    """##

    private static let shots = ProcessInfo.processInfo.environment["PARTY_SHOTS"]

    private func shot(_ app: XCUIApplication, _ name: String) {
        let screenshot = app.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
        if let dir = Self.shots {
            try? screenshot.pngRepresentation.write(to: URL(fileURLWithPath: dir).appendingPathComponent("\(name).png"))
        }
    }

    private func launch() -> XCUIApplication {
        let app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_GROUP_ADMIN"] = Self.demo
        app.launch()
        XCTAssertTrue(app.staticTexts["Raclette chez Tom"].waitForExistence(timeout: 10))
        return app
    }

    override func setUp() {
        continueAfterFailure = false
    }

    func testHomeShowsProposalsRequestsAndRules() {
        let app = launch()
        XCTAssertTrue(app.buttons["Approuver"].exists && app.buttons["Modifier"].exists)
        XCTAssertTrue(app.staticTexts["« Salut, c'est Léa du foot ! »"].exists)
        // Profil incomplet : « Accepter » grisé pour cette demande.
        let accept = app.buttons.matching(identifier: "Accepter")
        XCTAssertEqual(accept.count, 2)
        XCTAssertTrue(accept.element(boundBy: 0).isEnabled)
        XCTAssertFalse(accept.element(boundBy: 1).isEnabled)
        shot(app, "1-accueil")
        app.swipeUp()
        XCTAssertTrue(app.switches.firstMatch.exists)
        shot(app, "2-accueil-bas")
    }

    func testRefusingAProposalAsksForAMessage() {
        let app = launch()
        app.buttons.matching(identifier: "Refuser").element(boundBy: 0).tap()
        XCTAssertTrue(app.alerts.firstMatch.waitForExistence(timeout: 3))
        XCTAssertTrue(app.alerts.firstMatch.textFields.firstMatch.exists)
        shot(app, "3-refus")
        app.alerts.firstMatch.buttons["Annuler"].tap()
    }

    func testMembersByRoleAndAMemberSheet() {
        let app = launch()
        app.swipeUp()
        app.staticTexts["Membres"].firstMatch.tap()
        XCTAssertTrue(app.staticTexts["Membre VIP (1)"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["Membre (1)"].exists && app.staticTexts["Accès retiré (1)"].exists)
        shot(app, "4-membres")
        app.staticTexts["Léa"].firstMatch.tap()
        XCTAssertTrue(app.buttons["Co-admin"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons["Admin"].exists)  // seulement en dessous de mon rang
        XCTAssertTrue(app.switches.firstMatch.exists)  // bêta-testeur
        shot(app, "5-fiche")
        app.swipeUp()
        XCTAssertTrue(app.buttons["Retirer l'accès"].exists && app.buttons["Supprimer le compte"].exists)
        shot(app, "6-fiche-bas")
        app.navigationBars.buttons.firstMatch.tap()
        app.staticTexts["Zoé"].firstMatch.tap()
        // Profil incomplet : Membre VIP et plus grisés, Membre et Guest possibles.
        XCTAssertTrue(app.buttons["Membre VIP"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons["Membre VIP"].isEnabled)
        XCTAssertTrue(app.buttons["Guest"].isEnabled)
    }

    func testRolesStartOnVipAndOnlyGiveOwnRights() {
        let app = launch()
        app.swipeUp()
        app.staticTexts["Rôles et droits"].firstMatch.tap()
        XCTAssertTrue(app.staticTexts["Valider les propositions"].waitForExistence(timeout: 5))
        let toggles = app.switches
        // Valider (je l'ai) : activable ; Publier (déjà donné) : retirable ; Retirer l'accès (je ne l'ai pas) : grisé.
        XCTAssertTrue(toggles.element(boundBy: 0).isEnabled && toggles.element(boundBy: 1).isEnabled)
        XCTAssertFalse(toggles.element(boundBy: 2).isEnabled)
        shot(app, "7-roles")
    }
}

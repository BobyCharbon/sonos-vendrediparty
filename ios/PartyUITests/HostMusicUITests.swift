import XCTest

/// « Gérer la soirée » natif, avec de vrais gestes : la poignée ≡ (appui long puis glisser) réorganise la file,
/// les sections se replient. État de démonstration (PARTY_DEBUG_HOST_DEMO) : aucun serveur nécessaire.
final class HostMusicUITests: XCTestCase {
    /// File de démonstration : Blinding Lights, Alors on danse, Tout oublier, Papaoutai (demandes) + titres de playlist.
    static let demo = ##"{"feedback_new": 0, "guest_pin": "0537", "guest_url": "https://party.bobycharbon.ch/", "active": true, "room_uid": "RINCON_X", "room_name": "Salon", "mode": "next", "started_at": 1793204286.588437, "spotify_configured": false, "requests": [{"id": "rq1", "track_id": "bbbbbbbbbbbbbbbbbbbbbb", "title": "Trois", "artist": "A", "image": "", "guest_id": "guest-1234567", "guest_name": "Léa", "added_at": 1800000000, "status": "queued", "ip": "", "duration_ms": 0}], "guests": [{"guest_id": "guest-léa0000", "name": "Léa", "joined_at": 1793200760.3173099, "total": 2, "queued": 1, "via": ["music", "games"], "active_at": 1793204360.3173099, "ban": null, "last_seen": 1793204360.3173099}, {"guest_id": "guest-tom0000", "name": "Tom", "joined_at": 1793200760.3173099, "total": 2, "queued": 1, "via": ["music", "games"], "active_at": 1793204360.3173099, "ban": null, "last_seen": 1793204360.3173099}, {"guest_id": "guest-zoé0000", "name": "Zoé", "joined_at": 1793200760.3173099, "total": 2, "queued": 1, "via": ["music", "games"], "active_at": 1793204360.3173099, "ban": null, "last_seen": 1793204360.3173099}], "bans": [], "messages": [], "top_playlists": [{"id": "spotify:playlist:37i9dQZF1DX05r4Oy3Ln97", "title": "Soirée"}], "source": "sonos", "spotify_transfer_issues": [], "spotify_legacy_pending": 0, "spotify_account": null, "admin_notify": {"messages": true, "games": false, "feedback": true}, "games": [], "event": {"id": "e1", "title": "Vendredi Party d'Halloween"}, "sonos": {"queue_editable": true, "device": "", "state": "PLAYING", "from_queue": true, "now": {"title": "Sapés comme jamais", "artist": "Maître Gims", "art": "", "position": "", "duration": "", "by": "Tom", "track_id": "cccccccccccccccccccccc"}, "upcoming": [{"title": "Un", "artist": "A", "art": "", "track_id": "aaaaaaaaaaaaaaaaaaaaaa", "by": null, "rid": null, "eta": null, "service": null}, {"title": "Deux", "artist": "A", "art": "", "track_id": null, "by": null, "rid": null, "eta": null, "service": null}, {"title": "Trois", "artist": "A", "art": "", "track_id": "bbbbbbbbbbbbbbbbbbbbbb", "by": "Léa", "rid": null, "eta": null, "service": null}], "upcoming_total": 3, "volume": 34}, "queue": [{"pos": 5, "key": "k0", "title": "Blinding Lights", "artist": "The Weeknd", "art": "", "by": "Léa", "eta": 120, "service": null}, {"pos": 6, "key": "k1", "title": "Dernière danse", "artist": "Indila", "art": "", "by": null, "eta": 320, "service": null}, {"pos": 7, "key": "k2", "title": "Alors on danse", "artist": "Stromae", "art": "", "by": "Tom", "eta": 520, "service": null}, {"pos": 8, "key": "k3", "title": "Levitating", "artist": "Dua Lipa", "art": "", "by": null, "eta": 720, "service": null}, {"pos": 9, "key": "k4", "title": "Tout oublier", "artist": "Angèle", "art": "", "by": "Zoé", "eta": 920, "service": null}, {"pos": 10, "key": "k5", "title": "Get Lucky", "artist": "Daft Punk", "art": "", "by": null, "eta": 1120, "service": null}, {"pos": 11, "key": "k6", "title": "Bad Habits", "artist": "Ed Sheeran", "art": "", "by": null, "eta": 1320, "service": null}, {"pos": 12, "key": "k7", "title": "Papaoutai", "artist": "Stromae", "art": "", "by": "Léa", "eta": 1520, "service": null}]}"##

    private func launch() -> XCUIApplication {
        let app = XCUIApplication()
        app.launchEnvironment["PARTY_DEBUG_HOST_DEMO"] = Self.demo
        app.launch()
        XCTAssertTrue(app.staticTexts["Gérer la soirée"].waitForExistence(timeout: 10))
        return app
    }

    private func y(_ app: XCUIApplication, _ title: String) -> CGFloat {
        app.staticTexts[title].firstMatch.frame.midY
    }

    override func setUp() {
        continueAfterFailure = false
    }

    func testDraggingTheHandleMovesTheTrackDown() {
        let app = launch()
        XCTAssertTrue(app.staticTexts["Blinding Lights"].waitForExistence(timeout: 5))
        XCTAssertLessThan(y(app, "Blinding Lights"), y(app, "Tout oublier"))
        let handles = app.buttons.matching(identifier: "Réorganiser")
        XCTAssertGreaterThanOrEqual(handles.count, 3)
        let first = handles.element(boundBy: 0), third = handles.element(boundBy: 2)
        first.press(forDuration: 0.6, thenDragTo: third)
        // Blinding Lights est maintenant après Tout oublier ; Alors on danse est remonté en tête.
        let moved = NSPredicate { _, _ in self.y(app, "Blinding Lights") > self.y(app, "Tout oublier") }
        wait(for: [expectation(for: moved, evaluatedWith: nil)], timeout: 5)
        XCTAssertLessThan(y(app, "Alors on danse"), y(app, "Tout oublier"))
    }

    func testDraggingUpMovesTheTrackToTheTop() {
        let app = launch()
        let handles = app.buttons.matching(identifier: "Réorganiser")
        XCTAssertTrue(handles.element(boundBy: 2).waitForExistence(timeout: 5))
        handles.element(boundBy: 2).press(forDuration: 0.6, thenDragTo: handles.element(boundBy: 0))
        let moved = NSPredicate { _, _ in self.y(app, "Tout oublier") < self.y(app, "Blinding Lights") }
        wait(for: [expectation(for: moved, evaluatedWith: nil)], timeout: 5)
    }

    func testAQuickSwipeOnTheHandleDoesNotReorder() {
        let app = launch()
        let handles = app.buttons.matching(identifier: "Réorganiser")
        XCTAssertTrue(handles.element(boundBy: 0).waitForExistence(timeout: 5))
        // Sans appui long : rien ne bouge (la page défile, la file reste dans le même ordre).
        handles.element(boundBy: 0).press(forDuration: 0.01, thenDragTo: handles.element(boundBy: 2))
        sleep(1)
        XCTAssertLessThan(y(app, "Blinding Lights"), y(app, "Alors on danse"))
    }

    func testSectionsFoldAndShowThePlaylist() {
        let app = launch()
        // En-tête de section : « File d'attente, 8 » (titre et nombre de titres).
        let header = app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", "File d'attente")).firstMatch
        XCTAssertTrue(header.waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["Blinding Lights"].exists)
        header.tap()
        XCTAssertTrue(app.staticTexts["Blinding Lights"].waitForNonExistence(timeout: 3))
        header.tap()
        XCTAssertTrue(app.staticTexts["Blinding Lights"].waitForExistence(timeout: 3))
        // Titres de la playlist : masqués par défaut, affichés à la demande.
        XCTAssertFalse(app.staticTexts["Dernière danse"].exists)
        app.buttons["Voir les 4 titres de la playlist"].tap()
        XCTAssertTrue(app.staticTexts["Dernière danse"].waitForExistence(timeout: 3))
        app.buttons["Masquer les titres de la playlist"].tap()
    }

    func testTrackActionsAreInTheMenu() {
        let app = launch()
        let menu = app.buttons["Actions pour Alors on danse"]
        XCTAssertTrue(menu.waitForExistence(timeout: 5))
        menu.tap()
        for action in ["Jouer ensuite", "Monter", "Descendre", "Jouer maintenant", "Retirer"] {
            XCTAssertTrue(app.buttons[action].waitForExistence(timeout: 3), action)
        }
    }
}

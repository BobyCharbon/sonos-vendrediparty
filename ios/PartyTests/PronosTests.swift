import XCTest
@testable import Party

/// Pronos (17.11) : messages du pont PartyNative.pronos, toucher d'une notification, lecture d'un prono tel que la base
/// le renvoie (prono_get), textes de l'écran.
final class PronosTests: XCTestCase {
    private let id = "11111111-2222-3333-4444-555555555555"

    func testTheBridgeAcceptsOnlyItsRoutes() {
        XCTAssertEqual(PronoRoute.parse("open:\(id.uppercased())"), .open(id))
        XCTAssertEqual(PronoRoute.parse("list"), .list(group: nil))
        XCTAssertEqual(PronoRoute.parse("list:\(id)"), .list(group: id))
        XCTAssertEqual(PronoRoute.parse("create"), .create(group: nil, event: nil))
        XCTAssertEqual(PronoRoute.parse("create:group:\(id)"), .create(group: id, event: nil))
        XCTAssertEqual(PronoRoute.parse("create:event:\(id)"), .create(group: nil, event: id))
        for bad in ["open:../admin", "open", "create:other:\(id)", "list:x", "board:\(id)", ""] {
            XCTAssertNil(PronoRoute.parse(bad), bad)
        }
    }

    func testANotificationOpensTheProno() {
        XCTAssertEqual(PronoRoute.requested(in: URL(string: "https://x.ch/?tab=events&prono=\(id)")!), id)
        XCTAssertNil(PronoRoute.requested(in: URL(string: "https://x.ch/?tab=events&prono=../admin")!))
        XCTAssertNil(PronoRoute.requested(in: URL(string: "https://x.ch/?tab=chats&prono=\(id)")!))
    }

    func testAPronoFromTheDatabaseIsRead() throws {
        let json = """
        {"id": "\(id)", "question": "Qui gagne ?", "kind": "choice", "points": 3, "closes_at": "2026-11-18T19:00:00+00:00",
         "reveal": "result", "state": "done", "revealed": true, "created_at": "2026-11-17T19:00:00.123+00:00", "mine": false,
         "locked": true, "creator": {"id": "a", "name": "Léa", "avatar_url": null, "me": false, "photo": null},
         "group": {"id": "g", "name": "Les footeux", "emoji": "⚽", "color": "mint", "photo": null}, "event": null,
         "options": [{"id": "o1", "label": "Max", "count": 1, "correct": false}, {"id": "o2", "label": "Jo", "count": 2, "correct": true}],
         "candidates": null, "my_answer": {"option_id": "o2", "number": null, "text": null, "person_id": null, "winner": true},
         "answered": [{"id": "b", "name": "Marc", "avatar_url": "b/p.png", "me": true, "photo": "https://s/p"}], "players": 3,
         "answers": [{"user": {"id": "b", "name": "Marc", "avatar_url": null, "me": true}, "option_id": "o2", "number": null,
                      "text": null, "hidden": false, "person": null, "winner": true}],
         "result": {"option_id": "o2", "number": null, "person": null, "at": "2026-11-18T19:05:00+00:00"},
         "winners": [{"id": "b", "name": "Marc", "avatar_url": null, "me": true}],
         "can_answer": false, "can_edit": false, "can_move_end": false, "can_result": false, "can_cancel": false, "link": null}
        """
        let p = try PronosStore.decoder.decode(Prono.self, from: Data(json.utf8))
        XCTAssertEqual(p.resultLabel, "Jo")
        XCTAssertEqual(p.myAnswer?.winner, true)
        XCTAssertEqual(p.winners?.first?.label, "Toi")
        XCTAssertEqual(p.answered.first?.photo, "https://s/p")
        XCTAssertEqual(p.label(option: "o1", number: nil, text: nil, person: nil), "Max")
        XCTAssertNotNil(p.closes)
        XCTAssertNotNil(PronoFormat.date(p.createdAt))
    }

    func testTexts() {
        XCTAssertEqual(PronoFormat.points(1), "1 point")
        XCTAssertEqual(PronoFormat.points(5), "5 points")
        XCTAssertEqual(PronoFormat.number(25), "25")
        XCTAssertEqual(PronoFormat.number(2.5), "2,5")
        XCTAssertEqual(PronoFormat.stateLine(state: "closed", closesAt: "", revealed: false), "Fermé · résultat attendu")
        XCTAssertEqual(PronoFormat.place(group: nil, event: PronoEventRef(id: "e", title: "Paintball"), creator: PronoFace(id: "a", name: "Léa")), "📅 Paintball")
    }
}

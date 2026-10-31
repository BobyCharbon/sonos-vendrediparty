import XCTest
@testable import Party

/// Tricount : montants en clair (à la suisse), saisie d'une dépense en mode simplifié et avancé, contrôles.
final class TricountTests: XCTestCase {
    private func group() -> TC.Group {
        let json = """
        {"id":"g","name":"Week-end","emoji":"⛷️","currency":"CHF","archived":false,"me":"a","link":"https://x/tricount/t",
         "members":[{"id":"a","name":"Léa","linked":true,"left":false,"me":true,"balance_cents":0,"payment":null},
                    {"id":"b","name":"Tom","linked":false,"left":false,"me":false,"balance_cents":0,"payment":null}],
         "expenses":[],"total_cents":0,"my_balance_cents":0,"my_spent_cents":0,"by_category":[],"settle":[]}
        """
        return try! JSONDecoder().decode(TC.Group.self, from: Data(json.utf8))
    }

    func testEventPotSaysWhichEvent() throws {
        XCTAssertNil(group().event)
        let json = """
        {"tricounts":[{"id":"g","name":"Raclette","emoji":"🎉","currency":"CHF","archived":false,"members":3,"total_cents":0,
          "my_balance_cents":0,"event":{"id":"e","title":"Raclette","starts_at":null}}],"categories":[],"currencies":["CHF"]}
        """
        let overview = try JSONDecoder().decode(TC.Overview.self, from: Data(json.utf8))
        XCTAssertEqual(overview.tricounts.first?.event?.title, "Raclette")
    }

    func testMoneyIsReadAndShownTheSwissWay() {
        XCTAssertEqual(Money.cents("12,5"), 1250)
        XCTAssertEqual(Money.cents("1'250.40"), 125040)
        XCTAssertNil(Money.cents("0"))
        XCTAssertNil(Money.cents("abc"))
        XCTAssertTrue(Money.text(-1250, "CHF").hasPrefix("−"))
        XCTAssertTrue(Money.text(1250, "CHF", sign: true).hasPrefix("+"))
    }

    func testSimpleExpenseIsPaidByMeForEveryone() throws {
        var d = TricountDraft(group: group())
        d.title = "Courses"
        d.amount = "30"
        guard case .success(let body) = d.payload(groupCurrency: "CHF", receiptPath: nil) else { return XCTFail("refusée") }
        XCTAssertEqual(body["paid_by"] as? String, "a")
        XCTAssertEqual(body["amount_cents"] as? Int, 3000)
        XCTAssertEqual((body["shares"] as? [[String: Any]])?.count, 2)
        XCTAssertEqual(body["split_mode"] as? String, "equal")
    }

    func testProblemsAreExplained() {
        var d = TricountDraft(group: group())
        d.amount = "10"
        if case .failure(let p) = d.payload(groupCurrency: "CHF", receiptPath: nil) { XCTAssertTrue(p.message.contains("titre")) } else { XCTFail() }
        d.title = "Resto"
        d.forWhom = []
        if case .failure(let p) = d.payload(groupCurrency: "CHF", receiptPath: nil) { XCTAssertTrue(p.message.contains("Pour qui")) } else { XCTFail() }
        d.forWhom = ["a", "b"]
        d.split = .amounts
        d.amounts = ["a": "3", "b": "4"]
        if case .failure(let p) = d.payload(groupCurrency: "CHF", receiptPath: nil) { XCTAssertTrue(p.message.contains("au lieu de")) } else { XCTFail() }
        d.amounts = ["a": "3", "b": "7"]
        if case .failure = d.payload(groupCurrency: "CHF", receiptPath: nil) { XCTFail("10 = 3 + 7") }
    }

    func testTricountLinkOpensJoin() {
        XCTAssertEqual(WebModel.tricountLink(in: URL(string: "https://partytest.bobycharbon.ch/tricount/0f5c2b9e-1111-4a2b-9c3d-123456789abc")!),
                       "0f5c2b9e-1111-4a2b-9c3d-123456789abc")
        XCTAssertEqual(WebModel.tricountLink(in: URL(string: "https://partytest.bobycharbon.ch/pot/0f5c2b9e-1111-4a2b-9c3d-123456789abc")!),
                       "0f5c2b9e-1111-4a2b-9c3d-123456789abc")
        XCTAssertNil(WebModel.tricountLink(in: URL(string: "https://partytest.bobycharbon.ch/tricount/pas-un-lien")!))
    }
}

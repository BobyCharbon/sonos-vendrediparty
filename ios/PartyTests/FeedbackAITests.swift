import Foundation
import Testing
import UIKit
@testable import Party

/// « Ton avis » avec l'IA : réponses du serveur (app/ai_feedback.py) et ce que l'app renvoie à l'envoi.
struct FeedbackAITests {
    private func decode<T: Decodable>(_ json: String) throws -> T {
        try JSONDecoder().decode(T.self, from: Data(json.utf8))
    }

    private let bug = """
    {"kind": "bug", "area": "games", "game": "quiz", "title": "Le Quiz se fige", "description": "Il se fige.",
     "steps": ["Lancer un Quiz", "Répondre à 3 questions"], "expected": "La 4e question", "actual": "Figé",
     "need": "", "proposal": "", "device": "iPhone · iOS 26.1"}
    """

    @Test("État : accord à demander, accepté, refusé ; IA éteinte ou limite du jour = écrire sans elle")
    func status() throws {
        let fresh: FeedbackAI.Status = try decode(#"{"configured": true, "consent": "", "remaining": 10, "max_turns": 4}"#)
        #expect(fresh.usable && !fresh.accepted && fresh.maxTurns == 4)
        let declined: FeedbackAI.Status = try decode(#"{"configured": true, "consent": "declined", "remaining": 10}"#)
        #expect(!declined.usable)
        let off: FeedbackAI.Status = try decode(#"{"configured": false, "consent": "accepted", "remaining": 10}"#)
        #expect(!off.usable && off.accepted)
        let tired: FeedbackAI.Status = try decode(#"{"configured": true, "consent": "accepted", "remaining": 0}"#)
        #expect(!tired.usable)
    }

    @Test("Reformulation : prête, question de précision, ou indisponible")
    func rewrite() throws {
        let ready: FeedbackAI.Rewrite = try decode(#"{"status": "ready", "question": "", "remaining": 9, "draft": \#(bug)}"#)
        #expect(!ready.unavailable && !ready.needsInfo && ready.draft?.title == "Le Quiz se fige")
        let ask: FeedbackAI.Rewrite = try decode(#"{"status": "needs_info", "question": "Dans quel jeu ?", "draft": \#(bug)}"#)
        #expect(ask.needsInfo && ask.question == "Dans quel jeu ?")
        let off: FeedbackAI.Rewrite = try decode(#"{"status": "unavailable", "message": "L'IA a atteint sa limite"}"#)
        #expect(off.unavailable && off.message.hasPrefix("L'IA"))
    }

    @Test("Version structurée : renvoyée telle quelle à l'envoi, lignes affichées dans l'ordre")
    func draft() throws {
        let d: FeedbackAI.Draft = try decode(bug)
        let json = d.json
        #expect(json["kind"] as? String == "bug" && json["area"] as? String == "games")
        #expect(json["steps"] as? [String] == ["Lancer un Quiz", "Répondre à 3 questions"])
        #expect(d.rows.map(\.label) == ["Étapes", "Attendu", "Ce qui se passe", "Appareil"])
        #expect(d.rows[0].text == "1. Lancer un Quiz\n2. Répondre à 3 questions")
    }

    @Test("Appareil rempli par l'app : iPhone, version d'iOS et de l'app")
    func device() {
        let ctx = FeedbackAI.deviceContext(info: ["CFBundleShortVersionString": "2.4", "CFBundleVersion": "51"],
                                           system: "26.1", idiom: .phone)
        #expect(ctx == ["platform": "iphone", "os": "iOS 26.1", "app": "2.4 (51)"])
        #expect(FeedbackAI.deviceContext(info: [:], system: "26.1", idiom: .pad)["platform"] == "ipad")
    }

    @Test("Mes retours : le titre de l'IA s'affiche quand il existe")
    func itemTitle() throws {
        let list: FeedbackList = try decode("""
        {"mine": [{"id": "a", "at": 1, "kind": "bug", "text": "euh le quiz", "status": "new", "reply": "", "unseen": false,
                   "title": "Le Quiz se fige"},
                  {"id": "b", "at": 2, "kind": "idea", "text": "Plus de chapeaux", "status": "new", "reply": "", "unseen": false}]}
        """)
        #expect(list.mine[0].title == "Le Quiz se fige" && list.mine[1].title == nil)
    }

    @Test("Feuille d'accord : le texte exact demandé par l'admin")
    func consentText() {
        #expect(FeedbackAI.consentText.contains("Anthropic (Claude)") && FeedbackAI.consentText.hasSuffix("pour un ticket du pot commun, sa photo."))
    }
}

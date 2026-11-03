import Foundation
import Testing
@testable import Party

/// 🧠 Méninges sur la fiche d'un membre : réponse de /api/brain/compare (agrégats des deux joueurs).
struct BrainCompareTests {
    private func decode(_ json: String) throws -> BrainCompareResponse {
        try JSONDecoder().decode(BrainCompareResponse.self, from: Data(json.utf8))
    }

    @Test("Comparaison : Température en tête, puis les domaines, et la phrase-bilan")
    func decodesComparison() throws {
        let r = try decode(#"""
        {"board": [], "rank": 1, "players": 2, "percentile": 100, "target": {"id": "b", "name": "Bob", "self": false,
         "played": true, "temperature": 1100, "me_played": true, "me_temperature": 1250,
         "rows": [{"domain": "vitesse", "label": "Vitesse", "icon": "⚡", "me": 1300, "them": 900},
                  {"domain": "memoire", "label": "Mémoire", "icon": "🧠", "me": null, "them": 1300}],
         "verdict": "Ton point fort : Vitesse (+400 °M)."}}
        """#)
        let t = try #require(r.target)
        #expect(t.bars.map(\.domain) == ["temperature", "vitesse", "memoire"])
        #expect(t.bars[0].me == 1250 && t.bars[0].them == 1100)
        #expect(t.bars[2].me == nil && t.bars[2].them == 1300)
        #expect(t.verdict.hasPrefix("Ton point fort"))
    }

    @Test("Membre qui n'a jamais joué, membre inconnu")
    func decodesNeverPlayedAndUnknown() throws {
        let t = try #require(try decode(#"{"target": {"id": "b", "name": "Bob", "self": false, "played": false, "temperature": 0, "me_played": false, "me_temperature": 0, "rows": [], "verdict": "Bob n'a pas encore joué à Méninges."}}"#).target)
        #expect(!t.played && t.bars.count == 1 && t.bars[0].them == nil && t.bars[0].me == nil)
        #expect(try decode(#"{"board": [], "target": null}"#).target == nil)
    }
}

import Foundation
import Testing
@testable import PartyTV

/// App Apple TV : lecture des vraies vues « spectateur » du serveur (samples.json, générées par /api/tv/game/<code>).
struct PartyTVTests {
    private func samples() throws -> JSON {
        let url = try #require(Bundle(for: Marker.self).url(forResource: "samples", withExtension: "json"))
        return try JSONDecoder().decode(JSON.self, from: Data(contentsOf: url))
    }

    @Test("Les vues spectateur se lisent pour chaque jeu prioritaire, sans aucun secret")
    func readsSpectatorViews() throws {
        let all = try samples()
        let words = all["undercover_words"]
        #expect(words["phase"].string == "words" && words["players"].array.count == 5)
        #expect(words["players"].array.allSatisfy { $0["word"].isNull && $0["role"].isNull })  // aucun mot ni rôle
        #expect(all["quiz_q"]["quiz"]["q"]["choices"].array.count == 4)
        #expect(!(all["likely_ask"]["likely"]["q"].string ?? "").isEmpty)
        #expect(all["whoof_votes"]["players"].array.filter { $0["voted"].bool }.count == 3)
    }

    @Test("Libellés de phase et gagnant d'Undercover en français")
    func labels() throws {
        let all = try samples()
        #expect(Phase.label(all["undercover_words"]) == "Chacun décrit son mot")
        #expect(Phase.label(all["quiz_q"]) == "Question en cours")
        #expect(Phase.label(all["undercover_lobby"]) == "En attente des joueurs")
        #expect(UndercoverTV.winner("civils") == "Les civils gagnent" && UndercoverTV.winner("white") == "Mr. White gagne")
    }

    @Test("JSON : nombres, textes, absents")
    func json() throws {
        let j = try JSONDecoder().decode(JSON.self, from: Data(#"{"a":1,"b":"x","c":[true],"d":null,"e":2.5}"#.utf8))
        #expect(j["a"].int == 1 && j["a"].string == "1" && j["b"].string == "x" && j["c"][0].bool)
        #expect(j["d"].isNull && j["zz"].isNull && j["e"].double == 2.5 && j["e"].string == "2.5")
    }
}

private final class Marker {}

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

    private func all() throws -> JSON {
        let url = try #require(Bundle(for: Marker.self).url(forResource: "samples-all", withExtension: "json"))
        return try JSONDecoder().decode(JSON.self, from: Data(contentsOf: url))
    }

    @Test("Salle de jeux : la télé montre le jeu lancé dedans (Je n'ai jamais), avec les prénoms ajoutés à la main")
    func roomShowsItsGame() throws {
        let s = try all()
        let lobby = s["room_lobby"], running = s["room_never"]
        #expect(GameView.shown(lobby)["type"].string == "room")
        #expect(lobby["players"].array.compactMap { $0["name"].string }.contains("Grand-mère"))
        let shown = GameView.shown(running)
        #expect(shown["type"].string == "never" && !(shown["question"].string ?? "").isEmpty)
        #expect(shown["players"].array.count == 4)
    }

    @Test("Classements de la colonne de droite : jetons (Blackjack, Casino), points (Président)")
    func sideBoards() throws {
        let s = try all()
        #expect(SideBoard.rows(s["blackjack_play"])?.0 == "Jetons" && SideBoard.rows(s["blackjack_play"])?.1.count == 4)
        #expect(SideBoard.rows(s["president"])?.0 == "Points")
        #expect(SideBoard.rows(s["casino"])?.1.first?.value == "100")
        #expect(SideBoard.rows(s["room_lobby"]) == nil)
    }

    @Test("Tous les jeux non 3D ont un échantillon lisible (phase et joueurs)")
    func everyGameReads() throws {
        let s = try all()
        for key in ["debate", "never", "roulette", "blackjack_play", "casino", "divan", "tmc", "pyramid", "biskit", "president"] {
            #expect(!s[key]["phase"].isNull, "\(key)")
            #expect(s[key]["players"].array.count >= 4, "\(key)")
        }
    }

    @Test("JSON : nombres, textes, absents")
    func json() throws {
        let j = try JSONDecoder().decode(JSON.self, from: Data(#"{"a":1,"b":"x","c":[true],"d":null,"e":2.5}"#.utf8))
        #expect(j["a"].int == 1 && j["a"].string == "1" && j["b"].string == "x" && j["c"][0].bool)
        #expect(j["d"].isNull && j["zz"].isNull && j["e"].double == 2.5 && j["e"].string == "2.5")
    }
}

private final class Marker {}

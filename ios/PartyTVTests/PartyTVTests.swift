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

/// Résultats annoncés en grand sur la télé (vraies parties jouées par tools/tv_samples.py).
struct OutcomeTests {
    private func samples() throws -> JSON {
        let url = try #require(Bundle(for: Marker.self).url(forResource: "samples-outcomes", withExtension: "json"))
        return try JSONDecoder().decode(JSON.self, from: Data(contentsOf: url))
    }

    @Test("Je n'ai jamais : ceux qui l'ont fait boivent les gorgées de la partie")
    func neverDrinkers() throws {
        let o = try #require(Outcome.of(try samples()["never_results"]))
        #expect(Set(o.lines(.drink).map(\.name)) == ["Tom", "Inès", "Nina"])
        #expect(o.lines(.drink).allSatisfy { $0.amount == 2 })
    }

    @Test("Blackjack aux gorgées : les perdants boivent, les gagnants distribuent")
    func blackjackSips() throws {
        let o = try #require(Outcome.of(try samples()["blackjack_results"]))
        #expect(Dictionary(uniqueKeysWithValues: o.lines(.drink).map { ($0.name, $0.amount ?? 0) }) == ["Boby": 1, "Tom": 4, "Nina": 2])
        #expect(Set(o.lines(.give).map(\.name)) == ["Léa", "Max"])
    }

    @Test("Qui de nous ? : le plus désigné boit")
    func whoofTop() throws {
        let o = try #require(Outcome.of(try samples()["whoof_results"]))
        #expect(o.lines(.drink).map(\.name) == ["Max"] && o.headline.contains("Max"))
    }

    @Test("Undercover : à la fin, le camp gagnant et les rôles cachés révélés")
    func undercoverEnd() throws {
        let o = try #require(Outcome.of(try samples()["undercover_end"]))
        #expect(o.headline.contains("imposteurs"))
        #expect(Set(o.lines.map(\.name)) == ["Tom", "Nina"])
    }

    @Test("Casino : annoncé une fois la bille arrêtée, avec qui boit et qui distribue")
    func casinoSpin() throws {
        let o = try #require(Outcome.of(try samples()["casino_results"]))
        #expect(o.headline == "Le 6 noir est sorti !")
        #expect(o.lines(.drink).map(\.name) == ["Max"] && o.lines(.give).map(\.name) == ["Nina"])
    }

    @Test("Phases sans résultat : rien n'est annoncé")
    func nothingWhileVoting() throws {
        #expect(Outcome.of(.object(["type": .string("never"), "phase": .string("question")])) == nil)
    }
}

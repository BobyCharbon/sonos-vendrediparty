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

    @Test("Le Masque : votes en clair (masques levés), en nombre sans votant (masques gardés)")
    func masqueVotes() throws {
        let open = try JSONDecoder().decode(JSON.self, from: Data(#"""
            {"text":"La mer","open":true,"author":"Alice","votes":[{"voter":"Bob","guess":"Alice","right":true},
             {"voter":"Chloé","guess":"Bob","right":false}]}
            """#.utf8))
        let line = String(MasqueTV.votesLine(open).characters)
        #expect(line == "✓ Bob   ✗ Chloé (pensait Bob)")
        let closed = try JSONDecoder().decode(JSON.self, from: Data(#"{"open":false,"votes":[{"guess":"Alice","n":2},{"guess":"Bob","n":1}]}"#.utf8))
        #expect(String(MasqueTV.votesLine(closed).characters) == "On a pensé à Alice ×2 · Bob")
        let none = try JSONDecoder().decode(JSON.self, from: Data(#"{"open":true,"votes":[]}"#.utf8))
        #expect(String(MasqueTV.votesLine(none).characters) == "Personne n'a voté pour cette réponse")
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
        #expect(Set(o.lines(.win).map(\.name)) == ["Tom", "Nina"])
        #expect(Set(o.lines(.lose).map(\.name)) == ["Léa", "Max", "Boby"])
    }

    @Test("Casino : annoncé une fois la bille arrêtée, avec qui boit et qui distribue")
    func casinoSpin() throws {
        let o = try #require(Outcome.of(try samples()["casino_results"]))
        #expect(o.headline == "Le 6 noir est sorti !")
        #expect(o.lines(.drink).map(\.name) == ["Max"] && o.lines(.give).map(\.name) == ["Nina"])
    }

    @Test("Annonce plein écran : même sort regroupé sur une ligne, dans l'ordre du tableau")
    func flashGroups() throws {
        let o = try #require(Outcome.of(try samples()["blackjack_results"]))
        let groups = o.groups
        #expect(groups.map(\.kind) == [.drink, .drink, .drink, .give])
        let give = try #require(groups.first { $0.kind == .give })
        #expect(Set(give.names) == ["Léa", "Max"] && give.verb == "distribuent 4 gorgées")
        #expect(groups.first?.verb == "boit 1 gorgée")
    }

    @Test("Casino : tant que la bille roule, le classement ne dévoile pas qui a bu ou gagné")
    func casinoBoardWaitsForTheBall() {
        func casino(age: Double) -> JSON {
            .object(["type": .string("casino"), "phase": .string("results"),
                     "casino": .object(["drinks": .number(1), "spin": .object(["number": .number(8), "age": .number(age)])]),
                     "players": .array([.object(["name": .string("Léa"), "drink": .number(2)]),
                                        .object(["name": .string("Tom"), "drink": .number(0)])])])
        }
        #expect(SideBoard.rows(casino(age: 2)) == nil && !SideBoard.shows(casino(age: 2)))
        #expect(SideBoard.rows(casino(age: 8))?.1.first?.name == "Léa")
    }

    @Test("Fin de partie : le classement de la colonne s'efface pendant le podium, qui le garde pour lui")
    func endHidesSideBoard() {
        let board: JSON = .array([.object(["name": .string("Boby"), "pts": .number(120)]),
                                  .object(["name": .string("Léa"), "pts": .number(95)])])
        func quiz(_ phase: String) -> JSON {
            .object(["type": .string("quiz"), "phase": .string(phase), "quiz": .object(["board": board])])
        }
        #expect(SideBoard.shows(quiz("q")))
        #expect(!SideBoard.shows(quiz("end")) && SideBoard.rows(quiz("end"))?.1.first?.name == "Boby")
    }

    @Test("Phases sans résultat : rien n'est annoncé")
    func nothingWhileVoting() throws {
        #expect(Outcome.of(.object(["type": .string("never"), "phase": .string("question")])) == nil)
    }
}

/// Beer pong : l'annonce ne montre que la sentence du gobelet, jamais les gorgées des précédents.
struct BeerPongOutcomeTests {
    private func game(_ last: [String: JSON], log: [JSON]) -> JSON {
        .object(["type": .string("beerpong"), "phase": .string("play"), "sips_log": .array(log),
                 "bp": .object(["last": .object(last), "players": .array([]), "team_names": .object([:])])])
    }

    @Test("Une sentence de sport n'annonce pas les gorgées d'avant")
    func sportOnly() throws {
        let old: JSON = .object(["n": .number(1), "name": .string("Boby"), "drink": .number(2), "give": .number(0), "age": .number(1)])
        let o = try #require(Outcome.of(game(["n": .number(4), "name": .string("Tom"), "kind": .string("sport"), "text": .string("15 abdos"), "team": .string("red")], log: [old])))
        #expect(o.lines.map(\.name) == ["Tom"] && o.lines(.drink).isEmpty)
    }
}

/// Quiz Drapeaux (avis 544a8fd8b5bd) : lisible à la télé.
struct QuizFlagTests {
    @Test("Quiz Drapeaux : le drapeau sort de la question pour s'afficher en grand, les réponses-drapeaux sont reconnues")
    func quizFlags() {
        let parts = QuizFlag.split("À quel pays appartient ce drapeau ? 🇨🇭")
        #expect(parts.text == "À quel pays appartient ce drapeau ?" && parts.flag == "🇨🇭")
        #expect(QuizFlag.split("Quelle est la capitale de la Suisse ?").flag == nil)
        #expect(QuizFlag.isFlag("🇹🇩") && !QuizFlag.isFlag("Tchad") && !QuizFlag.isFlag("🚩") && !QuizFlag.isFlag("🇹🇩🇷🇴"))
    }
}

/// Contrôle App Store du 05.11.2026 (O1, O6) : rien qui pousse à boire, pas de jeu d'argent simulé dans l'app du Store.
struct StoreComplianceTests {
    @Test("Beer pong : un shot reste facultatif (« ou un verre d'eau »), jamais « cul sec »")
    func shotIsOptional() throws {
        let g: JSON = .object(["type": .string("beerpong"), "phase": .string("play"), "sips_log": .array([]),
                               "bp": .object(["last": .object(["n": .number(2), "name": .string("Tom"), "kind": .string("shot"),
                                                               "text": .string("Shot")]),
                                              "players": .array([]), "team_names": .object([:])])])
        let o = try #require(Outcome.of(g))
        #expect(o.lines.first?.detail == "Un shot (ou un verre d'eau)")
    }

    @Test("Casino et Blackjack masqués dans l'app de l'App Store (Salle de jeux comprise), gardés en BETA ; Roulette montrée")
    func moneyGamesHiddenInStoreApp() {
        let casino: JSON = .object(["type": .string("casino"), "name": .string("Casino"), "phase": .string("bet")])
        let room: JSON = .object(["type": .string("room"), "current": .object(["type": .string("blackjack"), "name": .string("Blackjack")])])
        let roulette: JSON = .object(["type": .string("roulette"), "name": .string("Roulette")])
        #expect(StoreGames.hides(casino, storeApp: true) && StoreGames.hides(room, storeApp: true))
        #expect(!StoreGames.hides(casino, storeApp: false) && !StoreGames.hides(roulette, storeApp: true))
        #expect(StoreGames.name(casino, storeApp: true) == "Partie en cours" && StoreGames.name(casino, storeApp: false) == "Casino")
        #expect(StoreGames.name(roulette, storeApp: true) == "Roulette")
        #expect(!StoreGames.isStoreApp)  // les tests tournent en Debug (Party BETA)
    }
}

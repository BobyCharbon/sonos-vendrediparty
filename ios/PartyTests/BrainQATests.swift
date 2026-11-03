import Foundation
import Testing
@testable import Party

/// QA Méninges : réponses extrêmes ou abîmées de /api/brain/me, /compare et /catalog. L'écran ne doit jamais planter
/// (nombre hors des bornes d'Int) ni tout perdre pour une seule entrée illisible.
struct BrainQATests {
    private func stats(_ json: String) throws -> BrainStats {
        try JSONDecoder().decode(BrainStats.self, from: Data(json.utf8))
    }

    private func board(_ json: String) throws -> BrainBoard {
        try JSONDecoder().decode(BrainBoard.self, from: Data(json.utf8))
    }

    private func compare(_ json: String) throws -> BrainCompare? {
        try JSONDecoder().decode(BrainCompareResponse.self, from: Data(json.utf8)).target
    }

    // MARK: Profil (/api/brain/me)

    @Test("Jamais joué : réponse vide ou tout à null → écran « Pas encore de partie », sans erreur")
    func neverPlayed() throws {
        let nulls = #"{"name": null, "temperature": null, "domains": null, "games": null, "streak": null, "history": null, "#
            + #""strengths": null, "weaknesses": null, "insight": null, "percentile": null, "speed_vs_accuracy": null, "month_progress": null}"#
        for json in [#"{}"#, nulls] {
            let s = try stats(json)
            #expect(s.plays == 0 && s.temperature == 0 && s.curve.isEmpty && s.percentile == nil && s.monthProgress == nil)
            #expect(s.name == "Méninges")
        }
    }

    @Test("Une seule partie, historique d'un jour : pas de courbe, un jeu")
    func singleGame() throws {
        let s = try stats(#"""
        {"temperature": 1000, "games": {"pareil": {"index": 1000, "best": 420, "plays": 1, "last_level": 1, "max_tier": 1}},
         "history": [{"day": "2026-11-03", "temperature": 1000}]}
        """#)
        #expect(s.plays == 1 && s.playedGames.map(\.id) == ["pareil"] && s.curve.count == 1)
    }

    @Test("Nombres énormes (au-delà d'Int, négatifs, à virgule) : aucun plantage, valeurs bornées")
    func hugeNumbers() throws {
        let s = try stats(#"""
        {"temperature": 1e300, "percentile": -1e300, "month_progress": 9223372036854775808,
         "domains": {"vitesse": {"index": 1e40, "played": 3.7}},
         "games": {"pareil": {"index": 99999999999999999999, "best": 1.5e19, "plays": 2, "last_level": 1e10, "max_tier": 1e30}},
         "streak": {"current": 1e200, "best": -1e200},
         "speed_vs_accuracy": {"speed": 1e308, "accuracy": -5}}
        """#)
        #expect(s.temperature > 0 && s.temperature <= BrainStats.numberLimit)
        #expect(s.percentile! < 0 && s.percentile! >= -BrainStats.numberLimit)
        #expect(s.domains["vitesse"]?.index == BrainStats.numberLimit && s.domains["vitesse"]?.played == 4)
        #expect(s.games["pareil"]?.best == BrainStats.numberLimit && s.plays == 2)
        #expect(!BrainStats.degrees(s.temperature).isEmpty && !BrainStats.degrees(Int.min).isEmpty)
        #expect(BrainStats.degrees(-1234) == "−1\u{202F}234 °M")
    }

    @Test("Palier 20 et niveau 100 : lus pour chaque jeu")
    func maxTier() throws {
        let s = try stats(#"{"games": {"aiguillage": {"index": 2000, "best": 987654321, "plays": 50, "last_level": 100, "max_level": 100, "max_tier": 20}}}"#)
        let g = try #require(s.games["aiguillage"])
        #expect(g.maxTier == 20 && g.maxLevel == 100 && g.lastLevel == 100)
        // Ancien serveur, sans max_tier : palier déduit du dernier niveau (5 niveaux par palier).
        let old = try stats(#"{"games": {"pareil": {"index": 900, "best": 10, "plays": 1, "last_level": 12}}}"#)
        #expect(old.games["pareil"]?.maxTier == 3)
    }

    @Test("Une entrée illisible ne fait pas disparaître les autres (jeux, domaines, historique)")
    func lossyEntries() throws {
        let s = try stats(#"""
        {"games": {"pareil": {"index": 1000, "best": 10, "plays": 3, "last_level": 2}, "motif": null, "grille": "?"},
         "domains": {"vitesse": {"index": 1200, "played": 3}, "memoire": null},
         "history": [{"day": "2026-11-01", "temperature": 900}, null, 7, {"day": 20261102, "temperature": 1},
                     {"day": "2026-11-03", "temperature": 950}],
         "strengths": ["vitesse", null, 3], "weaknesses": "memoire"}
        """#)
        #expect(s.plays == 3, "un seul jeu abîmé effaçait toutes les parties (écran « jamais joué »)")
        #expect(s.domains["vitesse"]?.index == 1200)
        #expect(s.curve.map(\.day) == ["2026-11-01", "2026-11-03"])
        #expect(s.strengths == ["vitesse"])
    }

    @Test("Historique de 365 jours : tout est gardé, dans l'ordre")
    func longHistory() throws {
        let start = Calendar(identifier: .gregorian).date(from: DateComponents(year: 2025, month: 11, day: 4))!
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd"
        let days = (0..<365).map { #"{"day": "\#(f.string(from: start.addingTimeInterval(Double($0) * 86400 + 43200)))", "temperature": \#(800 + $0)}"# }
        let s = try stats(#"{"history": [\#(days.joined(separator: ","))]}"#)
        #expect(s.curve.count == 365 && s.curve.first?.temperature == 800 && s.curve.last?.temperature == 1164)
    }

    // MARK: Classement (/api/brain/compare)

    @Test("200 joueurs, noms très longs, emoji, HTML piégé, ex aequo ; une ligne abîmée n'efface pas les autres")
    func bigBoard() throws {
        let long = String(repeating: "Maximilienne-Antoinette 🧠🔥 ", count: 8)
        var players = (0..<200).map { #"{"id": "u-\#($0)", "name": "\#(long)\#($0)", "temperature": \#(2000 - $0 / 2), "me": \#($0 == 150)}"# }
        players.append(#"{"id": "u-trap", "name": "<img src=x onerror=alert(1)>", "temperature": 1e300}"#)
        players.append("null")
        let b = try board(#"{"board": [\#(players.joined(separator: ","))], "rank": 151, "players": 1e30, "percentile": 25}"#)
        #expect(b.board.count == 201, "une ligne null effaçait tout le classement")
        #expect(b.board.first { $0.me }?.id == "u-150")
        #expect(b.board.contains { $0.name == "<img src=x onerror=alert(1)>" })
        #expect(b.rank(of: b.board[0]) == 2 && b.rank(of: b.board[1]) == 2)  // 1e300 borné, devant ; 2000 ex aequo
        #expect(Set(b.board.map(\.id)).count == b.board.count)
    }

    @Test("Identifiants absents ou en double : chaque ligne garde un identifiant unique (ForEach)")
    func uniqueIDs() throws {
        let b = try board(#"{"board": [{"name": "Léa", "temperature": 1}, {"name": "Léa", "temperature": 2}, {"id": "x", "name": "A"}, {"id": "x", "name": "B"}]}"#)
        #expect(Set(b.board.map(\.id)).count == 4)
    }

    // MARK: Fiche d'un membre (/api/brain/compare, target)

    @Test("Comparaison abîmée : nombres à virgule ou énormes, id numérique, ligne sans icône → fiche lisible quand même")
    func tolerantCompare() throws {
        let t = try #require(try compare(#"""
        {"target": {"id": 42, "name": null, "self": null, "played": true, "temperature": 1240.6, "me_played": true,
         "me_temperature": 1e300, "rows": [{"domain": "vitesse", "label": "Vitesse", "me": 1e40, "them": 900.4},
                                            null, {"label": "sans domaine"}, {"domain": "memoire", "icon": "🧠", "me": "?", "them": 1300}],
         "verdict": null}}
        """#))
        #expect(t.id == "42" && t.name == "?" && t.temperature == 1241)
        #expect(t.meTemperature == BrainStats.numberLimit)
        #expect(t.rows.map(\.domain) == ["vitesse", "memoire"])
        #expect(t.rows[0].icon == "🧠" && t.rows[0].me == BrainStats.numberLimit && t.rows[0].them == 900)
        #expect(t.rows[1].label == "memoire" && t.rows[1].me == nil)
    }

    @Test("Comparaison avec un membre au nom piégé : texte brut, jamais interprété")
    func trappedName() throws {
        let t = try #require(try compare(#"{"target": {"id": "b", "name": "<b>Bob</b>‮🔥", "played": false, "rows": []}}"#))
        #expect(t.name == "<b>Bob</b>\u{202E}🔥" && t.bars.count == 1)
    }

    @Test("Barres de la fiche : valeur hors bornes ramenée entre 0 et 1")
    func compareRatio() {
        #expect(BrainCompareSection.ratio(nil) == 0 && BrainCompareSection.ratio(-5) == 0)
        #expect(BrainCompareSection.ratio(1000) == 0.5 && BrainCompareSection.ratio(Int.max) == 1)
    }
}

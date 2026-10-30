import SwiftUI

/// Aiguillage : vue riche pour Quiz, Purify, Qui est le plus, Undercover, Qui de nous (et Je n'ai jamais) ;
/// vue spectateur commune pour tous les autres jeux (phase, joueurs, question, résultats, gagnant).
struct GameView: View {
    let game: JSON

    var body: some View {
        if game.isNull {
            ProgressView("Chargement de la partie…").font(.title2)
        } else if game["phase"].string == "lobby" {
            LobbyView(game: game)
        } else {
            switch game["type"].string {
            case "quiz": QuizTV(game: game)
            case "likely": LikelyTV(game: game)
            case "purity": PurityTV(game: game)
            case "undercover": UndercoverTV(game: game)
            case "whoof", "never": QuestionVoteTV(game: game)
            case "room" where !game["current"].isNull: GameView(game: game["current"])
            default: GenericTV(game: game)
            }
        }
    }
}

enum Phase {
    static func label(_ game: JSON) -> String {
        switch game["phase"].string {
        case "lobby": return "En attente des joueurs"
        case "end": return "Partie terminée"
        case "words": return "Chacun décrit son mot"
        case "vote", "question": return "Vote en cours"
        case "results", "reveal", "rev": return "Résultats"
        case "white_guess": return "Mr. White tente sa chance"
        case "answering": return "Chacun répond au test"
        case "ask": return "Vote en cours"
        case "q": return "Question en cours"
        case "run": return "Chacun joue à son rythme"
        default: return game["round"].int.map { "Manche \($0)" } ?? "En cours"
        }
    }
}

struct PhaseTag: View {
    let text: String
    var color: Color = TV.accent
    var body: some View {
        Text(text.uppercased()).font(.callout.bold()).foregroundStyle(.black).lineLimit(1).fixedSize()
            .padding(.horizontal, 18).padding(.vertical, 8).background(color, in: Capsule())
    }
}

/// Classement de la partie, sous la musique (colonne de droite) : Quiz, Qui est le plus, et les scores en cours.
struct SideBoard: View {
    let game: JSON

    static func shows(_ game: JSON) -> Bool {
        let g = game["type"].string == "room" && !game["current"].isNull ? game["current"] : game
        return !g["quiz"]["board"].array.isEmpty || !g["likely"]["scores"].array.isEmpty
    }

    var body: some View {
        let g = game["type"].string == "room" && !game["current"].isNull ? game["current"] : game
        switch g["type"].string {
        case "quiz" where !g["quiz"]["board"].array.isEmpty:
            Leaderboard(title: "Classement", rows: g["quiz"]["board"].array.map { ($0["name"].string ?? "?", "\($0["pts"].int ?? 0) pts") })
        case "likely" where !g["likely"]["scores"].array.isEmpty:
            Leaderboard(title: "Les plus désignés", rows: g["likely"]["scores"].array.map { ($0["name"].string ?? "?", "\($0["pts"].int ?? 0)") })
        default:
            EmptyView()
        }
    }
}

struct PlayersRow: View {
    let players: [JSON]
    var highlight: Set<String> = []
    var size: CGFloat = 92
    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: size + 60), spacing: 20)], alignment: .leading, spacing: 24) {
            ForEach(Array(players.enumerated()), id: \.offset) { _, p in
                PlayerBadge(player: p, size: size, highlight: highlight.contains(p["pid"].string ?? ""))
            }
        }
    }
}

/// Salle d'attente : qui est là, et le code pour rejoindre.
struct LobbyView: View {
    let game: JSON
    var body: some View {
        VStack(alignment: .leading, spacing: 34) {
            PhaseTag(text: "En attente des joueurs", color: TV.lavender)
            Text("Rejoins avec le code \(game["code"].string ?? "")").font(.system(size: 54, weight: .bold))
            Text("\(game["players"].array.count) joueur\(game["players"].array.count > 1 ? "s" : "") dans la partie")
                .font(.title2).foregroundStyle(TV.muted)
            PlayersRow(players: game["players"].array, size: 110)
        }
    }
}

/// Classement commun (nom + valeur), du premier au dernier.
struct Leaderboard: View {
    let title: String
    let rows: [(name: String, value: String)]
    var limit = 5
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title).font(.title3.bold())
            ForEach(Array(rows.prefix(limit).enumerated()), id: \.offset) { i, row in
                HStack {
                    Text(i == 0 ? "🥇" : i == 1 ? "🥈" : i == 2 ? "🥉" : "\(i + 1)").font(.headline).frame(width: 48)
                    Text(row.name).font(.headline).lineLimit(1)
                    Spacer()
                    Text(row.value).font(.headline.monospacedDigit()).foregroundStyle(TV.lavender).lineLimit(1).fixedSize()
                }
                .padding(.horizontal, 20).padding(.vertical, 8).card(i == 0 ? TV.accent.opacity(0.35) : TV.surface, radius: 18)
            }
        }
    }
}

/// Tous les autres jeux : phase, question éventuelle, résultats, gagnant, et les joueurs (votes, éliminés, gorgées).
struct GenericTV: View {
    let game: JSON
    var body: some View {
        VStack(alignment: .leading, spacing: 30) {
            PhaseTag(text: Phase.label(game))
            if let q = game["question"].string, !q.isEmpty {
                Text(q).font(.system(size: 54, weight: .bold)).lineLimit(4)
            }
            if let winner = game["winner"].string, !winner.isEmpty {
                Text("🏆 \(game["type"].string == "undercover" ? UndercoverTV.winner(winner) : winner)").font(.system(size: 54, weight: .heavy)).foregroundStyle(TV.coral)
            }
            if !game["results"].array.isEmpty {
                Leaderboard(title: "Résultats", rows: game["results"].array.map { ($0["name"].string ?? "?", $0["count"].string ?? $0["answer"].string ?? "") })
            }
            PlayersRow(players: game["players"].array)
            let sips = game["players"].array.filter { ($0["drink"].int ?? 0) + ($0["give"].int ?? 0) > 0 }
            if !sips.isEmpty {
                Text("🍻 " + sips.map { "\($0["name"].string ?? "?") \($0["drink"].int ?? 0) bue(s), \($0["give"].int ?? 0) donnée(s)" }.joined(separator: " · "))
                    .font(.title3).foregroundStyle(TV.muted)
            }
        }
    }
}

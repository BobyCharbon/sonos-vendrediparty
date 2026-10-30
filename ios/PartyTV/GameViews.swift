import SwiftUI

/// Aiguillage de la télé. La Salle de jeux affiche le jeu lancé dedans (quelle que soit sa phase) ; une salle d'attente
/// montre le QR code et les joueurs (ceux ajoutés à la main compris). Île, Néon et Braquage (3D/2D) se suivent sur les
/// téléphones. Tous les autres jeux ont leur vue.
struct GameView: View {
    let game: JSON
    /// Adresse pour rejoindre (QR) : la partie regardée par la télé.
    let join: URL?

    /// Jeu réellement affiché : dans une Salle de jeux, le jeu lancé dedans (s'il y en a un).
    static func shown(_ game: JSON) -> JSON {
        game["type"].string == "room" && !game["current"].isNull ? game["current"] : game
    }

    var body: some View {
        if game.isNull {
            ProgressView("Chargement de la partie…").font(.title2)
        } else if game["type"].string == "room" {
            if game["current"].isNull { RoomTV(room: game, join: join) } else { GameView(game: game["current"], join: join) }
        } else if game["phase"].string == "lobby" {
            LobbyView(game: game, join: join)
        } else if game["phase"].string == "end" && !["undercover", "president"].contains(game["type"].string ?? "") {
            EndTV(game: game)
        } else {
            VStack(alignment: .leading, spacing: 30) {
                // Le résultat de la manche d'abord, en très grand ; le jeu dessous.
                if let outcome = Outcome.of(game), game["type"].string != "roulette" {
                    OutcomeBoard(outcome: outcome).transition(.move(edge: .top).combined(with: .opacity))
                }
                board
            }
        }
    }

    @ViewBuilder private var board: some View {
            switch game["type"].string {
            case "quiz": QuizTV(game: game)
            case "likely": LikelyTV(game: game)
            case "purity": PurityTV(game: game)
            case "undercover": UndercoverTV(game: game)
            case "whoof", "never": QuestionVoteTV(game: game)
            case "debate": DebateTV(game: game)
            case "roulette": RouletteTV(game: game)
            case "divan": DivanTV(game: game)
            case "tmc": TmcTV(game: game)
            case "blackjack": BlackjackTV(game: game)
            case "casino": CasinoTV(game: game)
            case "pyramid": PyramidTV(game: game)
            case "biskit": BiskitTV(game: game)
            case "president": PresidentTV(game: game)
            case "island", "neon", "heist": ActionGameTV(game: game)
            default: GenericTV(game: game)
            }
    }
}

enum Phase {
    static func label(_ game: JSON) -> String {
        switch game["phase"].string {
        case "lobby": return "En attente des joueurs"
        case "end": return "Partie terminée"
        case "words": return "Chacun décrit son mot"
        case "vote", "question", "ask": return "Vote en cours"
        case "results", "reveal", "rev", "scored": return "Résultats"
        case "white_guess": return "Mr. White tente sa chance"
        case "answering": return "Chacun répond au test"
        case "q": return "Question en cours"
        case "run": return "Chacun joue à son rythme"
        case "bet": return "Les mises"
        case "play": return "En jeu"
        case "spun": return "La roue a tourné"
        case "card": return "Carte tirée"
        case "answer": return "Réponse en cours"
        case "deal", "memory", "memres", "pyramid": return "Pyramide"
        default: return game["round"].int.map { "Manche \($0)" } ?? "En cours"
        }
    }
}

extension Phase {
    /// Avancée de la partie, dans la barre du haut (« Question 3/10 », « Manche 2 »…).
    static func progress(_ game: JSON) -> String? {
        switch game["type"].string {
        case "quiz": return game["quiz"]["n"].int.map { "Question \($0)" }
        case "likely": return game["likely"]["n"].int.map { "Question \($0)/\(game["likely"]["count"].int ?? 0)" }
        case "debate": return game["debate"]["n"].int.map { "Dilemme \($0)/\(game["debate"]["count"].int ?? 0)" }
        case "whoof", "never": return game["round"].int.flatMap { $0 > 0 ? "Question \($0)" : nil }
        case "undercover": return game["round"].int.flatMap { $0 > 0 ? "Manche \($0)" : nil }
        case "blackjack": return game["round"].int.flatMap { $0 > 0 ? "Main \($0)" : nil }
        case "casino": return game["round"].int.flatMap { $0 > 0 ? "Tour \($0)" : nil }
        case "divan": return game["divan"]["current"]["name"].string.map { "Au tour de \($0)" }
        case "president": return turnName(game["president"]["seats"].array, game["president"]["turn"].string)
        case "pyramid": return turnName(game["pyr"]["seats"].array, game["pyr"]["turn"].string)
        case "biskit": return turnName(game["bk"]["seats"].array, game["bk"]["turn"].string)
        default: return nil
        }
    }

    private static func turnName(_ seats: [JSON], _ pid: String?) -> String? {
        guard let pid, let name = seats.first(where: { $0["pid"].string == pid })?["name"].string else { return nil }
        return "Au tour de \(name)"
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

/// En-tête commun d'une vue de jeu : la phase et une info (manche, question n°…).
struct GameTop: View {
    let game: JSON
    var info: String?
    var body: some View {
        // La phase est dans la barre du haut ; ici seulement une précision du jeu, s'il y en a une.
        if let info, !info.isEmpty { Text(info).font(.system(size: 34, weight: .bold)).foregroundStyle(TV.lavender).lineLimit(1) }
    }
}

/// Classement de la partie, sous la musique (colonne de droite).
struct SideBoard: View {
    let game: JSON

    private static func shown(_ game: JSON) -> JSON {
        game["type"].string == "room" && !game["current"].isNull ? game["current"] : game
    }

    static func rows(_ game: JSON) -> (String, [(name: String, value: String)])? {
        let g = shown(game)
        func list(_ a: [JSON], _ value: (JSON) -> String) -> [(name: String, value: String)] { a.map { ($0["name"].string ?? "?", value($0)) } }
        switch g["type"].string {
        case "quiz": return ("Classement", list(g["quiz"]["board"].array) { "\($0["pts"].int ?? 0) pts" })
        case "likely": return ("Les plus désignés", list(g["likely"]["scores"].array) { "\($0["pts"].int ?? 0)" })
        case "tmc": return ("Classement", list(g["tmc"]["ranking"].array) { "\($0["pts"].string ?? "0") pts" })
        case "blackjack" where (g["bj"]["drinks"].int ?? 0) == 0: return ("Jetons", list(g["bj"]["seats"].array.sorted { ($0["chips"].int ?? 0) > ($1["chips"].int ?? 0) }) { "\($0["chips"].int ?? 0)" })
        case "casino" where (g["casino"]["drinks"].int ?? 0) == 0: return ("Jetons", list(g["casino"]["table"].array.sorted { ($0["chips"].int ?? 0) > ($1["chips"].int ?? 0) }) { "\($0["chips"].int ?? 0)" })
        case "president": return ("Points", list(g["president"]["seats"].array.sorted { ($0["points"].int ?? 0) > ($1["points"].int ?? 0) }) { "\($0["points"].int ?? 0)" })
        case "room" where game["current"].isNull: return nil
        default:
            let sips = g["players"].array.filter { ($0["drink"].int ?? 0) > 0 }.sorted { ($0["drink"].int ?? 0) > ($1["drink"].int ?? 0) }
            return sips.isEmpty ? nil : ("🍻 Gorgées bues", list(sips) { "\($0["drink"].int ?? 0)" })
        }
    }

    static func shows(_ game: JSON) -> Bool { !(rows(game)?.1.isEmpty ?? true) }

    let gameRows: (String, [(name: String, value: String)])?
    init(game: JSON) {
        self.game = game
        gameRows = Self.rows(game)
    }

    var body: some View {
        if let gameRows, !gameRows.1.isEmpty { Leaderboard(title: gameRows.0, rows: gameRows.1) }
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

/// Salle d'attente : le QR code pour rejoindre, et qui est là (les prénoms ajoutés à la main compris).
struct LobbyView: View {
    let game: JSON
    let join: URL?
    var body: some View {
        HStack(alignment: .top, spacing: 50) {
            if let join { QRCodeView(url: join, size: 300) }
            VStack(alignment: .leading, spacing: 26) {
                PhaseTag(text: "En attente des joueurs", color: TV.lavender)
                Text("Scanne le QR code pour jouer").font(.system(size: 50, weight: .heavy)).lineLimit(2).minimumScaleFactor(0.7)
                Text("\(game["players"].array.count) joueur\(game["players"].array.count > 1 ? "s" : "") dans la partie")
                    .font(.title2).foregroundStyle(TV.muted)
                PlayersRow(players: game["players"].array, size: 100)
            }
        }
    }
}

/// Salle de jeux sans jeu lancé : QR code, joueurs, tableau de la soirée et derniers jeux.
struct RoomTV: View {
    let room: JSON
    let join: URL?
    var body: some View {
        VStack(alignment: .leading, spacing: 30) {
            LobbyView(game: room, join: join)
            let board = room["room_info"]["board"].array.filter { ($0["pts"].int ?? 0) + ($0["drink"].int ?? 0) + ($0["give"].int ?? 0) > 0 }
            if !board.isEmpty {
                Leaderboard(title: "🏆 Tableau de la soirée", rows: board.map { r in
                    (r["name"].string ?? "?", "\(r["pts"].int ?? 0) pts · 🍺 \(r["drink"].int ?? 0)")
                })
                .frame(maxWidth: 820)
            }
        }
    }
}

/// Classement commun (nom + valeur), du premier au dernier.
struct Leaderboard: View {
    let title: String
    let rows: [(name: String, value: String)]
    var limit = 8
    var body: some View {
        // Rang partagé en cas d'égalité ; pas de médaille tant que personne ne se détache (tous à 100, tous à 0).
        let tied = Set(rows.map(\.value)).count <= 1
        VStack(alignment: .leading, spacing: 10) {
            Text(title).font(.title3.bold())
            ForEach(Array(rows.prefix(limit).enumerated()), id: \.offset) { i, row in
                let rank = rows.firstIndex { $0.value == row.value } ?? i
                HStack {
                    Text(tied ? "·" : rank == 0 ? "🥇" : rank == 1 ? "🥈" : rank == 2 ? "🥉" : "\(rank + 1)").font(.headline).frame(width: 48)
                    Text(row.name).font(.headline).lineLimit(1)
                    Spacer()
                    Text(row.value).font(.headline.monospacedDigit()).foregroundStyle(TV.lavender).lineLimit(1).fixedSize()
                }
                .padding(.horizontal, 20).padding(.vertical, 8).card(!tied && rank == 0 ? TV.accent.opacity(0.35) : TV.surface, radius: 18)
            }
        }
    }
}

/// Jeux 3D / 2D (Île, Néon, Braquage) : ils se suivent sur les téléphones ; la télé montre qui joue.
struct ActionGameTV: View {
    let game: JSON
    var body: some View {
        VStack(alignment: .leading, spacing: 30) {
            GameTop(game: game)
            Text("🎮 Partie en direct sur les téléphones").font(.system(size: 54, weight: .heavy))
            Text("Ce jeu se joue en temps réel sur chaque téléphone.").font(.title2).foregroundStyle(TV.muted)
            PlayersRow(players: game["players"].array)
        }
    }
}

/// Repli commun : phase, question, résultats, gagnant, joueurs.
struct GenericTV: View {
    let game: JSON
    var body: some View {
        VStack(alignment: .leading, spacing: 30) {
            GameTop(game: game)
            if let q = game["question"].string, !q.isEmpty {
                Text(q).font(.system(size: 54, weight: .bold)).lineLimit(4).minimumScaleFactor(0.7)
            }
            if let winner = game["winner"].string, !winner.isEmpty {
                Text("🏆 \(game["type"].string == "undercover" ? UndercoverTV.winner(winner) : winner)")
                    .font(.system(size: 54, weight: .heavy)).foregroundStyle(TV.coral)
            }
            if !game["results"].array.isEmpty {
                Leaderboard(title: "Résultats", rows: game["results"].array.map { ($0["name"].string ?? "?", $0["count"].string ?? $0["answer"].string ?? "") })
            }
            PlayersRow(players: game["players"].array)
        }
    }
}

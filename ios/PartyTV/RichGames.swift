import SwiftUI

/// Quiz : la question en grand, les 4 réponses, le chrono et qui a répondu ; à la révélation, la bonne réponse,
/// la répartition des votes et le gagnant ; le classement en permanence.
struct QuizTV: View {
    let game: JSON
    private var quiz: JSON { game["quiz"] }
    private var q: JSON { quiz["q"] }
    private static let letters = ["A", "B", "C", "D"]
    private static let colors: [Color] = [TV.accent, TV.lavender, TV.mint, TV.coral]

    var body: some View {
            VStack(alignment: .leading, spacing: 26) {
                HStack(spacing: 18) {
                    PhaseTag(text: Phase.label(game))
                    if let n = quiz["n"].int { Text("Question \(n)").font(.title3).foregroundStyle(TV.muted) }
                    if let theme = q["theme"].string { Text("\(q["icon"].string ?? "") \(theme)").font(.title3).foregroundStyle(TV.lavender) }
                }
                if !q.isNull {
                    Text(q["text"].string ?? "").font(.system(size: 50, weight: .bold)).lineLimit(3).minimumScaleFactor(0.6)
                    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 20) {
                        ForEach(Array(q["choices"].array.enumerated()), id: \.offset) { i, choice in answer(i, choice.string ?? "") }
                    }
                    HStack(spacing: 30) {
                        if game["phase"].string == "q", let left = q["left"].double {
                            Label("\(Int(left.rounded(.up))) s", systemImage: "timer").font(.title2.monospacedDigit().bold())
                        }
                        Text("\(q["answered"].int ?? 0)/\(q["players"].int ?? 0) ont répondu").font(.title3).foregroundStyle(TV.muted)
                        if let winner = q["winner"].string { Text("⚡ \(winner) le plus rapide").font(.title3.bold()).foregroundStyle(TV.coral) }
                    }
                } else if game["phase"].string == "run" {
                    Text("Chacun grimpe l'échelle à son rythme sur son téléphone.").font(.title).foregroundStyle(TV.muted)
                } else if game["phase"].string == "end" {
                    Text("🏁 Quiz terminé").font(.system(size: 60, weight: .heavy))
                }
            }
    }

    private func answer(_ i: Int, _ text: String) -> some View {
        let reveal = game["phase"].string == "rev"
        let correct = q["correct"].int == i
        let votes = q["dist"][i].int
        return HStack(spacing: 18) {
            Text(Self.letters[i % 4]).font(.title2.heavy()).foregroundStyle(.black)
                .frame(width: 58, height: 58).background(Self.colors[i % 4], in: Circle())
            Text(text).font(.title3.bold()).lineLimit(2).minimumScaleFactor(0.7)
            Spacer()
            if reveal, let votes { Text("\(votes)").font(.title2.monospacedDigit().bold()).foregroundStyle(TV.muted) }
            if reveal && correct { Image(systemName: "checkmark.circle.fill").font(.title).foregroundStyle(TV.mint) }
        }
        .padding(22)
        .card(reveal ? (correct ? TV.mint.opacity(0.35) : TV.surface.opacity(0.5)) : TV.surface, radius: 24)
        .opacity(reveal && !correct ? 0.55 : 1)
    }
}

/// Qui est le plus… ? : la question, qui a voté, puis le décompte (jamais les bulletins) et le classement.
struct LikelyTV: View {
    let game: JSON
    private var L: JSON { game["likely"] }

    var body: some View {
            VStack(alignment: .leading, spacing: 28) {
                HStack(spacing: 18) {
                    PhaseTag(text: Phase.label(game))
                    if let n = L["n"].int { Text("Question \(n)/\(L["count"].int ?? 0)").font(.title3).foregroundStyle(TV.muted) }
                }
                Text(L["q"].string ?? "").font(.system(size: 60, weight: .heavy)).lineLimit(3)
                let result = L["result"]
                if !result.isNull {
                    let winners = result["winners"].array.compactMap { $0["name"].string }
                    if !winners.isEmpty { Text("👉 \(winners.joined(separator: ", "))").font(.system(size: 52, weight: .heavy)).foregroundStyle(TV.coral) }
                    ForEach(Array(result["rows"].array.enumerated()), id: \.offset) { _, row in
                        bar(row["name"].string ?? "?", row["count"].int ?? 0, of: max(1, result["votes"].int ?? 1))
                    }
                } else {
                    Text("\(L["voted"].int ?? 0)/\(L["total"].int ?? 0) ont voté").font(.title2).foregroundStyle(TV.muted)
                    PlayersRow(players: game["players"].array.map { p in
                        voted(p, L["done"].array.contains(p["pid"]))
                    })
                }
            }
    }

    private func bar(_ name: String, _ count: Int, of total: Int) -> some View {
        HStack(spacing: 20) {
            Text(name).font(.title2.bold()).frame(width: 260, alignment: .leading)
            GeometryReader { geo in
                Capsule().fill(TV.accent).frame(width: max(18, geo.size.width * CGFloat(count) / CGFloat(total)))
            }
            .frame(height: 34)
            Text("\(count)").font(.title2.monospacedDigit().bold()).frame(width: 60)
        }
    }
}

/// Purify Test : qui a fini de répondre, puis le classement du plus sulfureux au plus sage (et qui boit).
struct PurityTV: View {
    let game: JSON
    private var P: JSON { game["purity"] }

    var body: some View {
        VStack(alignment: .leading, spacing: 30) {
            PhaseTag(text: Phase.label(game))
            if game["phase"].string == "results" {
                Leaderboard(title: "😈 Du plus sulfureux au plus sage",
                            rows: P["ranking"].array.map { ($0["name"].string ?? "?", "\($0["score"].int ?? 0) %") })
                let drinkers = P["gorgees"].array
                if !drinkers.isEmpty {
                    Text("🍻 " + drinkers.map { "\($0["name"].string ?? "?") boit \($0["sips"].int ?? 0)" }.joined(separator: " · "))
                        .font(.title2.bold()).foregroundStyle(TV.coral)
                }
            } else {
                Text("\(P["count_submitted"].int ?? 0)/\(P["count_players"].int ?? 0) ont terminé le test")
                    .font(.system(size: 60, weight: .heavy))
                ProgressView(value: Double(P["count_submitted"].int ?? 0), total: Double(max(1, P["count_players"].int ?? 1)))
                    .tint(TV.accent).frame(width: 900)
                Text("Chacun répond en secret sur son téléphone : les résultats arrivent ici.").font(.title3).foregroundStyle(TV.muted)
                PlayersRow(players: game["players"].array)
            }
        }
    }
}

/// Undercover : ordre de parole, votes, éliminations (rôle révélé), et les mots seulement à la fin.
struct UndercoverTV: View {
    let game: JSON

    var body: some View {
        VStack(alignment: .leading, spacing: 30) {
            HStack(spacing: 18) {
                PhaseTag(text: Phase.label(game))
                if let round = game["round"].int, round > 0 { Text("Manche \(round)").font(.title3).foregroundStyle(TV.muted) }
            }
            if game["phase"].string == "end" {
                Text("🏆 \(Self.winner(game["winner"].string))").font(.system(size: 60, weight: .heavy)).foregroundStyle(TV.coral)
                let words = game["words"]
                if !words.isNull {
                    HStack(spacing: 40) {
                        word("Civils", words["civil"].string ?? words["civilian"].string)
                        word("Undercover", words["undercover"].string)
                    }
                }
            } else if !game["order"].array.isEmpty {
                Text("Ordre de parole").font(.title2.bold())
                Text(game["order"].array.compactMap(\.string).enumerated().map { "\($0.offset + 1). \($0.element)" }.joined(separator: "   "))
                    .font(.title2).foregroundStyle(TV.lavender)
            }
            let last = game["last"]
            if !last.isNull {
                Text(last["tie"].bool ? "⚖️ Égalité : personne n'est éliminé"
                     : "❌ \(last["name"].string ?? "?") est éliminé·e" + (last["role"].string.map { " — \($0)" } ?? ""))
                    .font(.title.bold())
            }
            if game["phase"].string == "vote" {
                Text("\(game["votes_count"].int ?? 0) vote(s) sur \(game["players"].array.filter { $0["alive"].bool }.count)").font(.title2).foregroundStyle(TV.muted)
            }
            PlayersRow(players: game["players"].array, highlight: Set(game["candidates"].array.compactMap(\.string)))
        }
    }

    static func winner(_ code: String?) -> String {
        switch code {
        case "civils": return "Les civils gagnent"
        case "impostors": return "Les imposteurs gagnent"
        case "white": return "Mr. White gagne"
        default: return "Partie terminée"
        }
    }

    private func word(_ title: String, _ value: String?) -> some View {
        VStack(alignment: .leading) {
            Text(title).font(.title3).foregroundStyle(TV.muted)
            Text(value ?? "?").font(.system(size: 48, weight: .heavy))
        }
        .padding(28).card()
    }
}

/// Qui de nous ? / Je n'ai jamais : la question en grand, qui a voté, puis les résultats.
struct QuestionVoteTV: View {
    let game: JSON

    var body: some View {
        VStack(alignment: .leading, spacing: 32) {
            HStack(spacing: 18) {
                PhaseTag(text: Phase.label(game))
                if let round = game["round"].int, round > 0 { Text("Question \(round)").font(.title3).foregroundStyle(TV.muted) }
            }
            Text(game["question"].string ?? "").font(.system(size: 64, weight: .heavy)).lineLimit(4)
            if !game["results"].array.isEmpty {
                let rows = game["results"].array
                if game["type"].string == "never" {
                    let did = rows.filter { $0["answer"] == .bool(true) || $0["answer"].string == "yes" }.compactMap { $0["name"].string }
                    Text(did.isEmpty ? "Personne ne l'a jamais fait 😇" : "🍻 L'ont déjà fait : \(did.joined(separator: ", "))")
                        .font(.system(size: 44, weight: .bold)).foregroundStyle(TV.coral)
                } else {
                    Leaderboard(title: "Résultats", rows: rows.map { ($0["name"].string ?? "?", "\($0["count"].int ?? 0) vote(s)") })
                }
            } else {
                Text("\(game["votes_count"].int ?? 0)/\(game["players"].array.count) ont voté").font(.title2).foregroundStyle(TV.muted)
            }
            PlayersRow(players: game["players"].array)
        }
    }
}

private extension Font {
    func heavy() -> Font { weight(.heavy) }
}

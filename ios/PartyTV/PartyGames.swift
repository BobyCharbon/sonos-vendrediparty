import SwiftUI

/// Pour ou contre : le dilemme, qui a voté, puis la répartition de « totalement contre » à « totalement pour ».
struct DebateTV: View {
    let game: JSON
    private var D: JSON { game["debate"] }
    private static let scale = ["Totalement contre", "Plutôt contre", "Partagé", "Plutôt pour", "Totalement pour"]
    private static let colors: [Color] = [TV.red, TV.coral, TV.muted, TV.lavender, TV.mint]

    var body: some View {
        VStack(alignment: .leading, spacing: 30) {
            GameTop(game: game, info: D["n"].int.map { "Dilemme \($0)/\(D["count"].int ?? 0)" })
            if let theme = D["q"]["theme"].string { Text(theme).font(.title3).foregroundStyle(TV.lavender) }
            Text(D["q"]["text"].string ?? "").font(.system(size: 58, weight: .heavy)).lineLimit(4).minimumScaleFactor(0.6)
            let result = D["result"]
            if !result.isNull {
                HStack(spacing: 40) {
                    total("👍 Pour", result["pour"].int, TV.mint)
                    total("🤷 Partagé", result["partage"].int, TV.muted)
                    total("👎 Contre", result["contre"].int, TV.red)
                }
                ForEach(0..<5, id: \.self) { i in
                    HStack(spacing: 20) {
                        Text(Self.scale[i]).font(.title3).frame(width: 300, alignment: .leading)
                        GeometryReader { geo in
                            Capsule().fill(Self.colors[i]).frame(width: max(14, geo.size.width * share(result["counts"][i].int, result["votes"].int)))
                        }
                        .frame(height: 30)
                        Text("\(result["counts"][i].int ?? 0)").font(.title3.monospacedDigit().bold()).frame(width: 50)
                    }
                }
            } else {
                Text("\(D["voted"].int ?? 0)/\(D["total"].int ?? 0) ont voté").font(.title2).foregroundStyle(TV.muted)
                PlayersRow(players: game["players"].array.map { voted($0, D["done"].array.contains($0["pid"])) })
            }
        }
    }

    private func share(_ n: Int?, _ total: Int?) -> CGFloat { CGFloat(n ?? 0) / CGFloat(max(1, total ?? 1)) }

    private func total(_ title: String, _ n: Int?, _ color: Color) -> some View {
        VStack(alignment: .leading) {
            Text(title).font(.title3).foregroundStyle(TV.muted)
            Text("\(n ?? 0)").font(.system(size: 60, weight: .heavy)).foregroundStyle(color)
        }
    }
}

/// Coche « a voté » sur une pastille de joueur.
func voted(_ p: JSON, _ done: Bool) -> JSON {
    guard case .object(var o) = p else { return p }
    o["voted"] = .bool(done)
    return .object(o)
}

/// Roulette : le prénom tiré en très grand, les prénoms de la roue et les tirages précédents.
struct RouletteTV: View {
    let game: JSON

    private var picked: String? {
        let spin = game["spin"]
        guard let i = spin["index"].int else { return nil }
        return spin["names"][i].string
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 34) {
            GameTop(game: game)
            if let picked {
                Text("🎯 \(picked)").font(.system(size: 120, weight: .heavy)).foregroundStyle(TV.coral).lineLimit(1).minimumScaleFactor(0.5)
            } else {
                Text("La roue va tourner…").font(.system(size: 60, weight: .heavy))
            }
            Text(game["names"].array.compactMap(\.string).joined(separator: " · ")).font(.title2).foregroundStyle(TV.lavender).lineLimit(3)
            let history = game["history"].array.compactMap(\.string)
            if history.count > 1 {
                Text("Précédents : " + history.dropFirst().prefix(8).joined(separator: ", ")).font(.title3).foregroundStyle(TV.muted)
            }
        }
    }
}

/// Le Divan : la carte question en grand, sa catégorie et à qui c'est le tour.
struct DivanTV: View {
    let game: JSON
    private var V: JSON { game["divan"] }

    var body: some View {
        VStack(alignment: .leading, spacing: 34) {
            GameTop(game: game, info: V["current"]["name"].string.map { "Au tour de \($0)" })
            let card = V["card"]
            if !card.isNull {
                VStack(alignment: .leading, spacing: 20) {
                    Text(V["labels"][card["cat"].string ?? ""].string ?? "").font(.title2.bold()).foregroundStyle(TV.lavender)
                    Text(card["text"].string ?? "").font(.system(size: 60, weight: .heavy)).lineLimit(5).minimumScaleFactor(0.6)
                    if let hearts = V["hearts"].int, hearts > 0 { Text(String(repeating: "❤️", count: min(hearts, 12))).font(.title) }
                }
                .padding(50)
                .frame(maxWidth: .infinity, alignment: .leading)
                .card(TV.surface, radius: 40)
            }
            PlayersRow(players: game["players"].array, highlight: Set([V["current"]["pid"].string].compactMap { $0 }), size: 80)
        }
    }
}

/// Tu me connais ? : qui devine qui, la question, puis la réponse et le verdict.
struct TmcTV: View {
    let game: JSON
    private var T: JSON { game["tmc"] }

    var body: some View {
        let duo = T["duo"]
        VStack(alignment: .leading, spacing: 34) {
            GameTop(game: game)
            if !duo.isNull {
                Text("\(duo["guesser"]["name"].string ?? "?") devine \(duo["subject"]["name"].string ?? "?")")
                    .font(.title.bold()).foregroundStyle(TV.lavender)
                Text(duo["question"].string ?? "").font(.system(size: 60, weight: .heavy)).lineLimit(4).minimumScaleFactor(0.6)
                if let answer = duo["answer"].string {
                    Text("💬 \(answer)").font(.system(size: 48, weight: .bold))
                }
                if let verdict = duo["verdict"].string ?? (duo["verdict"].isNull ? nil : (duo["verdict"].bool ? "ok" : "ko")) {
                    Text(["ok": "✅ Bonne réponse !", "true": "✅ Bonne réponse !", "half": "🤏 À moitié", "ko": "❌ Raté", "false": "❌ Raté"][verdict] ?? verdict)
                        .font(.system(size: 50, weight: .heavy)).foregroundStyle(TV.coral)
                }
            } else {
                PlayersRow(players: game["players"].array)
            }
        }
    }
}

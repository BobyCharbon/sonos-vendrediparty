import SwiftUI

/// 🎭 Le Masque sur la télé : la question, qui a écrit, puis les réponses sans prénom ; à la révélation, masques levés :
/// « C'était X » et qui a voté pour qui (vert juste, rouge faux) ; masques gardés : seulement à qui on a pensé.
/// Aucun vert « par défaut » (avis du 04.11) : le vert ne veut dire que « deviné juste ».
struct MasqueTV: View {
    let game: JSON
    private var V: JSON { game["masque"] }

    var body: some View {
        VStack(alignment: .leading, spacing: 28) {
            Text("\(V["q"]["cat_label"].string ?? "") · \(V["q"]["level_label"].string ?? "")").font(.title3.bold()).foregroundStyle(TV.lavender)
            Text(V["q"]["text"].string ?? "").font(.system(size: game["phase"].string == "write" ? 64 : 44, weight: .heavy))
                .lineLimit(4).minimumScaleFactor(0.6)
                .id(V["q"]["text"].string ?? "").transition(.motion(.push(from: .trailing)))
            switch game["phase"].string {
            case "write":
                let wrote = V["wrote"].array
                Text("✍️ \(wrote.filter { $0["done"].bool == true }.count)/\(wrote.count) ont écrit en secret")
                    .font(.system(size: 44, weight: .heavy)).foregroundStyle(TV.accent).contentTransition(.numericText())
                PlayersRow(players: wrote.map { voted($0, $0["done"].bool == true) })
            case "guess":
                grid(V["slots"].array.filter { $0["hidden"].bool != true }) { slot in
                    Text("« \(slot["text"].string ?? "") »").font(.system(size: 34, weight: .bold)).lineLimit(4).minimumScaleFactor(0.7)
                }
                Text(V["mask"].string == "closed" ? "🤔 Qui a écrit quoi ? 🎭 Masques gardés : personne ne le saura"
                                                  : "🤔 Qui a écrit quoi ? Chacun devine sur son téléphone")
                    .font(.title2.bold()).foregroundStyle(TV.muted)
            case "reveal":
                grid(V["result"].array.filter { $0["hidden"].bool != true }) { row in
                    Self.revealCard(row)
                }
            default:
                EmptyView()
            }
        }
    }

    /// Les réponses en grille, deux colonnes.
    private func grid<Content: View>(_ rows: [JSON], @ViewBuilder content: @escaping (JSON) -> Content) -> some View {
        LazyVGrid(columns: [GridItem(.flexible(), spacing: 24), GridItem(.flexible(), spacing: 24)], alignment: .leading, spacing: 24) {
            ForEach(Array(rows.enumerated()), id: \.offset) { _, row in
                VStack(alignment: .leading, spacing: 12) { content(row) }
                    .padding(28)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .card(TV.surface, radius: 28)
            }
        }
    }

    /// Une réponse révélée : l'auteur bien en clair (ou le masque), le texte, puis les votes.
    @ViewBuilder
    static func revealCard(_ row: JSON) -> some View {
        let open = row["open"].bool == true
        Text(open ? "C'était \(row["author"].string ?? "")" : "🎭 Masque gardé")
            .font(.title2.bold()).foregroundStyle(open ? TV.accent : TV.muted)
        Text("« \(row["text"].string ?? "") »").font(.system(size: 34, weight: .bold)).lineLimit(4).minimumScaleFactor(0.7)
        Text(votesLine(row)).font(.title3).lineLimit(3).minimumScaleFactor(0.7)
    }

    /// Masques levés : « ✓ Bob  ✗ Chloé (pensait Dan) », en vert / rouge. Masques gardés : « On a pensé à Bob ×2 ».
    static func votesLine(_ row: JSON) -> AttributedString {
        let votes = row["votes"].array
        guard !votes.isEmpty else {
            var none = AttributedString("Personne n'a voté pour cette réponse")
            none.foregroundColor = TV.muted
            return none
        }
        if row["open"].bool != true {
            var line = AttributedString("On a pensé à ")
            line.foregroundColor = TV.muted
            for (i, v) in votes.enumerated() {
                let n = v["n"].int ?? 1
                line += AttributedString((i > 0 ? " · " : "") + (v["guess"].string ?? "") + (n > 1 ? " ×\(n)" : ""))
            }
            return line
        }
        var line = AttributedString()
        for (i, v) in votes.enumerated() {
            let right = v["right"].bool == true
            var part = AttributedString((i > 0 ? "   " : "") + (right ? "✓ " : "✗ ") + (v["voter"].string ?? "")
                                        + (right ? "" : " (pensait \(v["guess"].string ?? ""))"))
            part.foregroundColor = right ? TV.mint : TV.red
            line += part
        }
        return line
    }
}

/// 🪞 Le Reflet sur la télé : qui est devant le miroir, son affirmation, les votes, puis le compteur et l'écart.
struct RefletTV: View {
    let game: JSON
    private var V: JSON { game["reflet"] }

    var body: some View {
        VStack(alignment: .leading, spacing: 30) {
            if let name = V["mirror"]["name"].string {
                Text("🪞 \(name)").font(.system(size: 96, weight: .black)).foregroundStyle(TV.lavender).lineLimit(1).minimumScaleFactor(0.5)
                    .id(name).transition(.motion(.push(from: .trailing)))
            }
            switch game["phase"].string {
            case "pick":
                Text("choisit une affirmation sur lui-même et parie en secret…").font(.system(size: 44, weight: .heavy)).foregroundStyle(TV.muted)
            case "vote":
                card
                Text("🤫 \(V["done"].int ?? 0)/\(V["voters"].int ?? 0) ont voté").font(.system(size: 44, weight: .heavy))
                    .foregroundStyle(TV.accent).contentTransition(.numericText())
            case "result":
                card
                let r = V["result"]
                if r["hidden"].bool == true {
                    Text("🤫 Trop peu de votes : le résultat reste secret").font(.system(size: 44, weight: .heavy)).foregroundStyle(TV.muted)
                } else {
                HStack(alignment: .lastTextBaseline, spacing: 30) {
                    Text("\(r["yes"].int ?? 0)/\(r["voters"].int ?? 0)").font(.system(size: 140, weight: .black)).foregroundStyle(TV.mint)
                        .contentTransition(.numericText())
                    VStack(alignment: .leading, spacing: 8) {
                        Text("disent « oui »").font(.title2.bold())
                        Text("Pari : \(r["bet"].int ?? 0) · \(Self.verdict(r["gap"].int ?? 0))").font(.title2).foregroundStyle(TV.muted)
                    }
                }
                }
            default:
                EmptyView()
            }
        }
    }

    private var card: some View {
        Text("« \(V["card"].string ?? "") »").font(.system(size: 60, weight: .heavy)).lineLimit(4).minimumScaleFactor(0.6)
            .padding(46)
            .frame(maxWidth: .infinity, alignment: .leading)
            .card(TV.surface, radius: 40)
    }

    static func verdict(_ gap: Int) -> String {
        gap == 0 ? "🎯 Pile !" : gap == 1 ? "👌 À un près" : "🤯 \(gap) d'écart"
    }
}

import SwiftUI

/// 🎭 Le Masque sur la télé : la question, qui a écrit, puis les réponses sans prénom ; à la révélation, les masques
/// levés (avec qui les avait trouvés) et ceux restés masqués.
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
                answers(V["slots"].array.filter { $0["hidden"].bool != true }.map { ($0["text"].string ?? "", nil, nil) })
                Text("🤔 Qui a écrit quoi ? Chacun devine sur son téléphone").font(.title2.bold()).foregroundStyle(TV.muted)
            case "reveal":
                answers(V["result"].array.filter { $0["hidden"].bool != true }.map { r in
                    (r["text"].string ?? "", r["open"].bool == true ? "🙋 \(r["author"].string ?? "")" : "🎭 Reste masqué",
                     r["open"].bool == true ? r["found"].array.compactMap { $0.string } : nil)
                })
            default:
                EmptyView()
            }
        }
    }

    /// Les réponses en grille : texte, puis l'auteur dévoilé (ou le masque) et qui l'avait trouvé.
    private func answers(_ rows: [(String, String?, [String]?)]) -> some View {
        LazyVGrid(columns: [GridItem(.flexible(), spacing: 24), GridItem(.flexible(), spacing: 24)], alignment: .leading, spacing: 24) {
            ForEach(Array(rows.enumerated()), id: \.offset) { _, row in
                VStack(alignment: .leading, spacing: 12) {
                    Text("« \(row.0) »").font(.system(size: 34, weight: .bold)).lineLimit(4).minimumScaleFactor(0.7)
                    if let who = row.1 {
                        Text(who).font(.title2.bold()).foregroundStyle(row.2 == nil ? TV.muted : TV.mint)
                    }
                    if let found = row.2 {
                        Text(found.isEmpty ? "Personne ne l'avait trouvé" : "Trouvé par \(found.joined(separator: ", "))")
                            .font(.title3).foregroundStyle(TV.muted)
                    }
                }
                .padding(28)
                .frame(maxWidth: .infinity, alignment: .leading)
                .card(TV.surface, radius: 28)
            }
        }
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
                HStack(alignment: .lastTextBaseline, spacing: 30) {
                    Text("\(r["yes"].int ?? 0)/\(r["voters"].int ?? 0)").font(.system(size: 140, weight: .black)).foregroundStyle(TV.mint)
                        .contentTransition(.numericText())
                    VStack(alignment: .leading, spacing: 8) {
                        Text("disent « oui »").font(.title2.bold())
                        Text("Pari : \(r["bet"].int ?? 0) · \(Self.verdict(r["gap"].int ?? 0))").font(.title2).foregroundStyle(TV.muted)
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

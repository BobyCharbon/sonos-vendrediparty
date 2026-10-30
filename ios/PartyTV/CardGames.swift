import SwiftUI

/// Blackjack : la main de la banque, puis chaque joueur avec ses cartes, son total, sa mise et le résultat.
struct BlackjackTV: View {
    let game: JSON
    private var B: JSON { game["bj"] }

    var body: some View {
        VStack(alignment: .leading, spacing: 26) {
            GameTop(game: game)
            HStack(spacing: 30) {
                Text("🏦 Banque").font(.title2.bold())
                CardRow(cards: B["dealer"].array, width: 92)
                if let total = B["dealer_total"].int ?? B["dealer_up"].int { Text("\(total)").font(.system(size: 50, weight: .heavy)) }
            }
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 380), spacing: 24)], alignment: .leading, spacing: 24) {
                ForEach(Array(B["seats"].array.enumerated()), id: \.offset) { _, seat in seatView(seat) }
            }
        }
    }

    private func seatView(_ seat: JSON) -> some View {
        let hand = seat["hand"]
        let turn = B["turn"].string == seat["pid"].string && seat["pid"].string != nil
        return VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(seat["name"].string ?? "?").font(.title3.bold())
                Spacer()
                if (B["drinks"].int ?? 0) == 0 {
                    Text("🪙 \(seat["chips"].int ?? 0)").font(.headline.monospacedDigit()).foregroundStyle(TV.coral)
                }
            }
            if hand.isNull {
                Text("Mise en attente").foregroundStyle(TV.muted)
            } else {
                HStack(spacing: 18) {
                    CardRow(cards: hand["cards"].array, width: 64)
                    VStack(alignment: .leading) {
                        Text("\(hand["total"].int ?? 0)").font(.system(size: 40, weight: .heavy))
                        Text("mise \(hand["bet"].int ?? 0)").font(.caption).foregroundStyle(TV.muted)
                    }
                }
                if let result = hand["result"].string {
                    Text(["win": "🏆 Gagné", "blackjack": "🃏 Blackjack !", "lose": "❌ Perdu", "bust": "💥 Sauté", "push": "🤝 Égalité"][result] ?? result)
                        .font(.headline).foregroundStyle(TV.coral)
                }
            }
        }
        .padding(22)
        .card(turn ? TV.accent.opacity(0.35) : TV.surface, radius: 24)
        .overlay(RoundedRectangle(cornerRadius: 24).stroke(turn ? TV.accent : .clear, lineWidth: 4))
    }
}

/// Casino (roulette à mises) : le dernier numéro, puis chaque joueur, ses jetons misés et son résultat.
struct CasinoTV: View {
    let game: JSON
    private var C: JSON { game["casino"] }

    var body: some View {
        VStack(alignment: .leading, spacing: 28) {
            GameTop(game: game)
            let last = C["spin"].isNull ? C["history"][0] : C["spin"]
            if !last.isNull {
                let number = last["number"].string ?? last["n"].string ?? last.string ?? "?"
                HStack(spacing: 24) {
                    Text(number).font(.system(size: 110, weight: .heavy)).foregroundStyle(.white)
                        .frame(width: 200, height: 200).background(color(last), in: Circle())
                    VStack(alignment: .leading, spacing: 8) {
                        Text(game["phase"].string == "bet" ? "Dernier numéro" : "Numéro sorti").font(.title2).foregroundStyle(TV.muted)
                        if let n = Int(number) {
                            Text(n == 0 ? "Zéro" : "\(n % 2 == 0 ? "Pair" : "Impair") · \(n <= 18 ? "Manque" : "Passe") · \((n - 1) / 12 + 1)ᵉ douzaine")
                                .font(.system(size: 40, weight: .heavy))
                        }
                    }
                }
            }
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 330), spacing: 22)], alignment: .leading, spacing: 22) {
                ForEach(Array(C["table"].array.enumerated()), id: \.offset) { _, seat in
                    VStack(alignment: .leading, spacing: 10) {
                        HStack {
                            Text(seat["name"].string ?? "?").font(.title3.bold())
                            Spacer()
                            if seat["ready"].bool { Image(systemName: "checkmark.circle.fill").foregroundStyle(TV.mint) }
                        }
                        HStack(spacing: 16) {
                            Text("🪙 \(seat["chips"].int ?? 0)").font(.system(size: 34, weight: .bold).monospacedDigit())
                            if let staked = seat["staked"].int, staked > 0 {
                                Text("misé \(staked)").font(.system(size: 30, weight: .semibold)).foregroundStyle(TV.coral)
                            }
                        }
                        if game["phase"].string == "bet" {
                            Text(seat["bets"].array.map { Self.betName($0) }.joined(separator: " · ")).font(.system(size: 26, weight: .semibold))
                                .foregroundStyle(TV.lavender).lineLimit(2)
                        }
                    }
                    .padding(22).card(TV.surface, radius: 24)
                }
            }
        }
    }

    /// « Rouge ×5 », « 17 ×2 » : la mise d'un joueur, comme sur le tapis.
    static func betName(_ bet: JSON) -> String {
        let target = bet["target"].string ?? ""
        let names = ["red": "Rouge", "black": "Noir", "even": "Pair", "odd": "Impair", "low": "1-18", "high": "19-36"]
        let label = bet["kind"].string == "dozen" ? "\(target)ᵉ douzaine" : names[target] ?? target
        return "\(label) ×\(bet["amount"].int ?? 0)"
    }

    private func color(_ spin: JSON) -> Color {
        switch spin["color"].string {
        case "red": return Color(red: 0.8, green: 0.1, blue: 0.15)
        case "green": return Color(red: 0.1, green: 0.55, blue: 0.25)
        default: return .black
        }
    }
}

/// Pyramide : la pyramide de cartes (retournées au fil du jeu), la carte en cours, à qui c'est le tour, les gorgées.
struct PyramidTV: View {
    let game: JSON
    private var P: JSON { game["pyr"] }

    private var rows: [[String]] {
        let cards = P["pyramid"].array.map { $0.string ?? "??" }
        let floors = P["floors"].int ?? 5
        var out: [[String]] = []
        var i = 0
        for size in stride(from: floors, through: 1, by: -1) where i < cards.count {
            out.append(Array(cards[i..<min(i + size, cards.count)]))
            i += size
        }
        return out.reversed()  // la pointe en haut
    }

    var body: some View {
        HStack(alignment: .top, spacing: 50) {
            VStack(spacing: 10) {
                ForEach(Array(rows.enumerated()), id: \.offset) { _, row in
                    HStack(spacing: 10) { ForEach(Array(row.enumerated()), id: \.offset) { _, c in PlayingCard(code: c, width: 70) } }
                }
            }
            VStack(alignment: .leading, spacing: 24) {
                GameTop(game: game, info: "Étage \((P["floor"].int ?? 0) + 1) · \(P["flipped"].int ?? 0)/\(P["size"].int ?? 0) cartes")
                if let turn = P["seats"].array.first(where: { $0["pid"].string == P["turn"].string })?["name"].string {
                    Text("Au tour de \(turn)").font(.title.bold()).foregroundStyle(TV.lavender)
                }
                if let current = P["current"].string { PlayingCard(code: current, width: 120) }
                if let sips = P["step_sips"].int, sips > 0 { Text("🍺 \(sips) gorgée\(sips > 1 ? "s" : "")\(P["double"].bool ? " ×2" : "")").font(.title2.bold()) }
                PlayersRow(players: game["players"].array, highlight: Set([P["turn"].string].compactMap { $0 }), size: 70)
            }
        }
    }
}

/// Biskit Royal : la carte (dés) tirée, par qui, ce qu'il se passe, les règles en cours et qui est le Biskit.
struct BiskitTV: View {
    let game: JSON
    private var K: JSON { game["bk"] }

    var body: some View {
        VStack(alignment: .leading, spacing: 28) {
            GameTop(game: game, info: K["mult"].int.map { $0 > 1 ? "Tout compte ×\($0)" : "" })
            if let turn = K["seats"].array.first(where: { $0["pid"].string == K["turn"].string })?["name"].string {
                Text("Au tour de \(turn)").font(.system(size: 54, weight: .heavy))
            }
            HStack(alignment: .center, spacing: 40) {
                if let card = K["card"].string {
                    PlayingCard(code: card, width: 220).id(card).transition(.asymmetric(insertion: .scale(scale: 0.3).combined(with: .opacity), removal: .opacity))
                }
                VStack(alignment: .leading, spacing: 14) {
                    if let drawer = K["drawer_name"].string { Text("\(drawer) a tiré").font(.system(size: 34, weight: .semibold)).foregroundStyle(TV.muted) }
                    // L'effet de la carte, comme sur les téléphones (« Léa boit 2 », « Cascade : tout le monde boit »).
                    ForEach(Array(K["outcomes"].array.prefix(3).enumerated()), id: \.offset) { _, o in
                        Text(o["head"].string ?? o.string ?? "").font(.system(size: 64, weight: .black)).lineLimit(2).minimumScaleFactor(0.5)
                            .foregroundStyle(o["tone"].string == "give" ? TV.lavender : TV.coral)
                        if let text = o["text"].string, !text.isEmpty { Text(text).font(.system(size: 32, weight: .semibold)).foregroundStyle(TV.muted).lineLimit(2) }
                    }
                }
            }
            .animation(.spring(response: 0.5, dampingFraction: 0.7), value: K["card"].string)
            HStack(spacing: 40) {
                if let biskit = K["biskit"].string { Text("🍪 Biskit : \(biskit)").font(.title2) }
                if let q = K["qmaster"].string { Text("❓ Maître des questions : \(q)").font(.title2) }
                if let t = K["thumb"].string { Text("👍 Pouce : \(t)").font(.title2) }
            }
            .foregroundStyle(TV.lavender)
            let rules = K["rules"].array.compactMap { $0.string ?? $0["text"].string }
            if !rules.isEmpty { Text("📜 " + rules.joined(separator: " · ")).font(.title3).foregroundStyle(TV.muted).lineLimit(3) }
            PlayersRow(players: game["players"].array, highlight: Set([K["turn"].string].compactMap { $0 }), size: 80)
        }
    }
}

/// Président : le pli en cours (cartes posées), à qui c'est le tour, combien de cartes il reste à chacun, les rôles.
struct PresidentTV: View {
    let game: JSON
    private var R: JSON { game["president"] }

    var body: some View {
        VStack(alignment: .leading, spacing: 28) {
            GameTop(game: game, info: R["trick"].int.map { "Pli \($0)" })
            let pile = R["pile"]
            HStack(spacing: 30) {
                if pile.isNull {
                    Text("Table vide").font(.system(size: 44, weight: .bold)).foregroundStyle(TV.muted)
                } else {
                    CardRow(cards: pile["cards"].array.isEmpty ? pile.array : pile["cards"].array, width: 110)
                    if let by = pile["name"].string ?? pile["by"].string { Text("posé par \(by)").font(.title2).foregroundStyle(TV.muted) }
                }
            }
            if let notice = R["notice"].string { Text(notice).font(.title3).foregroundStyle(TV.lavender).lineLimit(2) }
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 300), spacing: 20)], alignment: .leading, spacing: 20) {
                ForEach(Array(R["seats"].array.enumerated()), id: \.offset) { _, s in
                    HStack(spacing: 14) {
                        Text(s["name"].string ?? "?").font(.title3.bold()).lineLimit(1)
                        Spacer()
                        if let role = s["role"].string { Text(role).font(.headline).foregroundStyle(TV.coral) }
                        Text(s["place"].int.map { "\($0)ᵉ" } ?? (s["passed"].bool ? "passe" : "🂠 \(s["count"].int ?? 0)"))
                            .font(.headline.monospacedDigit()).foregroundStyle(TV.muted)
                    }
                    .padding(20)
                    .card(s["turn"].bool ? TV.accent.opacity(0.35) : TV.surface, radius: 22)
                    .overlay(RoundedRectangle(cornerRadius: 22).stroke(s["turn"].bool ? TV.accent : .clear, lineWidth: 4))
                }
            }
        }
    }
}

import SwiftUI

/// Blackjack : la main de la banque, puis chaque joueur avec ses cartes, son total, sa mise et le résultat.
struct BlackjackTV: View {
    let game: JSON
    private var B: JSON { game["bj"] }
    private var drinks: Bool { (B["drinks"].int ?? 0) > 0 }

    var body: some View {
        VStack(alignment: .leading, spacing: 26) {
            HStack(spacing: 30) {
                Text("🏦 Banque").font(.system(size: 44, weight: .heavy))
                CardRow(cards: B["dealer"].array, width: 110)
                if let total = B["dealer_total"].int ?? B["dealer_up"].int { Text("\(total)").font(.system(size: 64, weight: .black)) }
            }
            if game["phase"].string == "bet" {
                let bets = B["seats"].array.filter { !$0["hand"].isNull }.count
                Text("\(bets)/\(B["seats"].array.count) ont misé").font(.system(size: 44, weight: .heavy)).foregroundStyle(TV.lavender)
            }
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 380), spacing: 24)], alignment: .leading, spacing: 24) {
                ForEach(Array(B["seats"].array.enumerated()), id: \.offset) { _, seat in seatView(seat) }
            }
        }
    }

    private func seatView(_ seat: JSON) -> some View {
        let hand = seat["hand"]
        let turn = B["turn"].string == seat["pid"].string && seat["pid"].string != nil
        let bust = hand["status"].string == "bust"
        return VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(seat["name"].string ?? "?").font(.system(size: 38, weight: .heavy)).lineLimit(1).minimumScaleFactor(0.6)
                Spacer()
                if !drinks { Text("🪙 \(seat["chips"].int ?? 0)").font(.system(size: 32, weight: .bold).monospacedDigit()).foregroundStyle(TV.coral) }
            }
            if hand.isNull {
                Text(game["phase"].string == "bet" ? "Réfléchit…" : "Ne joue pas cette main").font(.system(size: 30, weight: .semibold)).foregroundStyle(TV.muted)
            } else if hand["cards"].array.isEmpty {
                Text("Mise \(drinks ? sips(hand["bet"].int ?? 0) : "\(hand["bet"].int ?? 0)")").font(.system(size: 44, weight: .heavy)).foregroundStyle(TV.coral)
            } else {
                HStack(spacing: 18) {
                    CardRow(cards: hand["cards"].array, width: 74)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("\(hand["total"].int ?? 0)").font(.system(size: 50, weight: .black)).foregroundStyle(bust ? TV.red : .white)
                        Text("mise \(hand["bet"].int ?? 0)").font(.system(size: 30, weight: .semibold)).foregroundStyle(TV.muted)
                    }
                }
                if let result = hand["result"].string {
                    Text(["win": "🏆 Gagné", "blackjack": "🃏 Blackjack !", "lose": "❌ Perdu", "push": "🤝 Égalité"][result] ?? result)
                        .font(.system(size: 36, weight: .heavy)).foregroundStyle(result == "lose" ? TV.red : result == "push" ? TV.muted : TV.mint)
                } else if bust {
                    Text("💥 Sauté").font(.system(size: 36, weight: .heavy)).foregroundStyle(TV.red)
                }
            }
        }
        .padding(22)
        .opacity(bust && game["phase"].string == "play" ? 0.6 : 1)
        .card(turn ? TV.accent.opacity(0.35) : TV.surface, radius: 24)
        .overlay(RoundedRectangle(cornerRadius: 24).stroke(turn ? TV.accent : .clear, lineWidth: 5))
        .scaleEffect(turn ? 1.03 : 1)
        .animation(.spring(response: 0.4, dampingFraction: 0.7), value: turn)
    }
}

/// Casino (roulette à mises) : le numéro (caché tant que la bille roule), puis chaque joueur, ses paris et son résultat.
struct CasinoTV: View {
    let game: JSON
    private var C: JSON { game["casino"] }
    /// La bille roule 7 s sur les téléphones : la télé ne dévoile rien avant eux.
    static let rollSeconds = 7.0
    private var rolling: Bool { game["phase"].string == "results" && (C["spin"]["age"].double ?? 99) < Self.rollSeconds }
    private static let reds: Set<Int> = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]

    var body: some View {
        VStack(alignment: .leading, spacing: 28) {
            if game["phase"].string == "bet" {
                let ready = C["table"].array.filter { $0["ready"].bool }.count
                Text("🎰 Faites vos jeux ! \(ready)/\(C["table"].array.count) prêts").font(.system(size: 64, weight: .black)).foregroundStyle(TV.coral)
            }
            if rolling {
                Text("🎲 Rien ne va plus… la bille roule !").font(.system(size: 64, weight: .black)).foregroundStyle(TV.coral)
            } else if let n = (C["spin"].isNull ? C["history"][0] : C["spin"]["number"]).int {
                HStack(spacing: 30) {
                    Text("\(n)").font(.system(size: 120, weight: .black)).foregroundStyle(.white)
                        .frame(width: 220, height: 220).background(Self.color(n), in: Circle())
                    VStack(alignment: .leading, spacing: 8) {
                        Text(game["phase"].string == "bet" ? "Dernier numéro" : "Numéro sorti").font(.system(size: 34, weight: .semibold)).foregroundStyle(TV.muted)
                        Text(n == 0 ? "Zéro" : "\(Self.reds.contains(n) ? "Rouge" : "Noir") · \(n % 2 == 0 ? "Pair" : "Impair") · \(n <= 18 ? "Manque" : "Passe") · \(Self.dozen(n))")
                            .font(.system(size: 44, weight: .heavy))
                    }
                }
            }
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 380), spacing: 22)], alignment: .leading, spacing: 22) {
                ForEach(Array(C["table"].array.enumerated()), id: \.offset) { _, seat in seatView(seat) }
            }
        }
    }

    private func seatView(_ seat: JSON) -> some View {
        let r = seat["result"]
        let shown = game["phase"].string == "results" && !rolling && !r.isNull
        return VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text(seat["name"].string ?? "?").font(.system(size: 38, weight: .heavy)).lineLimit(1).minimumScaleFactor(0.6)
                Spacer()
                if game["phase"].string == "bet" && seat["ready"].bool { Text("Prêt ✓").font(.system(size: 30, weight: .bold)).foregroundStyle(TV.mint) }
            }
            if (C["drinks"].int ?? 0) == 0 { Text("🪙 \(seat["chips"].int ?? 0)").font(.system(size: 32, weight: .bold).monospacedDigit()) }
            let bets = seat["bets"].array
            Text(bets.isEmpty ? (game["phase"].string != "bet" ? "N'a pas misé" : seat["ready"].bool ? "Passe ce tour" : "Réfléchit…") : bets.map { Self.betName($0) }.joined(separator: " · "))
                .font(.system(size: 30, weight: .semibold)).foregroundStyle(TV.lavender).lineLimit(2)
            if shown {
                let drink = r["drink"].int ?? 0, give = r["give"].int ?? 0, net = r["net"].int ?? 0
                Text(drink > 0 ? "🍻 Boit \(drink)" : give > 0 ? "🎁 Distribue \(give)" : net > 0 ? "🏆 +\(net)" : net < 0 ? "❌ \(net)" : "Rien")
                    .font(.system(size: 42, weight: .black))
                    .foregroundStyle(drink > 0 || net < 0 ? TV.coral : give > 0 || net > 0 ? TV.mint : TV.muted)
                    .transition(.scale.combined(with: .opacity))
            }
        }
        .padding(22).card(TV.surface, radius: 24)
    }

    static func dozen(_ n: Int) -> String { ["1re", "2e", "3e"][min(2, (n - 1) / 12)] + " douzaine" }

    /// « Rouge ×5 », « 17 ×2 » : la mise d'un joueur, comme sur le tapis.
    static func betName(_ bet: JSON) -> String {
        let target = bet["target"].string ?? ""
        let names = ["red": "Rouge", "black": "Noir", "even": "Pair", "odd": "Impair", "low": "1-18", "high": "19-36"]
        let label = bet["kind"].string == "dozen" ? (["1": "1re", "2": "2e", "3": "3e"][target] ?? target) + " douzaine" : names[target] ?? target
        return "\(label) ×\(bet["amount"].int ?? 0)"
    }

    static func color(_ n: Int) -> Color {
        n == 0 ? Color(red: 0.1, green: 0.55, blue: 0.25) : reds.contains(n) ? Color(red: 0.8, green: 0.1, blue: 0.15) : .black
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
            if let waiting = K["await"]["name"].string {
                Text("⏳ \(waiting) \(Self.awaitText(K["await"]["kind"].string))").font(.system(size: 64, weight: .black)).foregroundStyle(TV.coral)
                    .lineLimit(2).minimumScaleFactor(0.5)
            } else if let turn = K["seats"].array.first(where: { $0["pid"].string == K["turn"].string })?["name"].string {
                Text("👉 Au tour de \(turn)").font(.system(size: 64, weight: .black)).lineLimit(1).minimumScaleFactor(0.5)
            }
            // Dés de la carte 4 : les deux faces en très grand et le total.
            let d = K["dice"]["d"].array.compactMap(\.int)
            if d.count == 2 {
                let faces = ["", "⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
                HStack(spacing: 30) {
                    Text(faces[d[0]] + " " + faces[d[1]]).font(.system(size: 150))
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Total \(d[0] + d[1])").font(.system(size: 64, weight: .black))
                        Text("lancés par \(K["dice"]["roller_name"].string ?? "?")").font(.system(size: 32, weight: .semibold)).foregroundStyle(TV.muted)
                    }
                }
                .id(K["dice"]["id"].string ?? "")
                .transition(.scale(scale: 0.3).combined(with: .opacity))
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

extension BiskitTV {
    /// Ce que la carte demande au joueur avant de continuer.
    static func awaitText(_ kind: String?) -> String {
        switch kind {
        case "dice": return "lance les dés 🎲"
        case "rule": return "invente une règle"
        case "mate": return "choisit son pote de boisson"
        case "pick", "target": return "désigne qui boit"
        case "question": return "pose une question"
        default: return "doit choisir"
        }
    }
}

/// Président : le pli en cours (cartes posées), à qui c'est le tour, combien de cartes il reste à chacun, les rôles.
struct PresidentTV: View {
    let game: JSON
    private var R: JSON { game["president"] }

    var body: some View {
        VStack(alignment: .leading, spacing: 28) {
            if let turn = R["seats"].array.first(where: { $0["turn"].bool })?["name"].string {
                Text("👉 Au tour de \(turn)").font(.system(size: 72, weight: .black)).foregroundStyle(TV.coral).lineLimit(1).minimumScaleFactor(0.5)
                    .id(turn).transition(.push(from: .trailing))
            }
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
                        Text(s["name"].string ?? "?").font(.system(size: 36, weight: .heavy)).lineLimit(1).minimumScaleFactor(0.5).layoutPriority(1)
                        Spacer()
                        if let role = s["role"].string { Text(role).font(.headline).foregroundStyle(TV.coral) }
                        Text(s["place"].int.map { "\($0)ᵉ" } ?? (s["passed"].bool ? "passe" : "\(s["count"].int ?? 0) cartes"))
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

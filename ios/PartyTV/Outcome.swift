import SwiftUI

/// Ce qu'une manche vient de décider, pour toute la pièce : qui boit, qui distribue, qui gagne, qui perd.
/// Chaque jeu le décrit avec ses propres champs (Outcome.of) ; la télé l'annonce en très grand puis le garde à l'écran.
struct Outcome: Equatable {
    enum Kind: Int, CaseIterable { case win, drink, give, lose, info }

    struct Line: Equatable, Identifiable {
        let name: String
        let kind: Kind
        /// Gorgées, jetons, points… (nil : pas de nombre à montrer).
        var amount: Int?
        /// Précision courte (« Blackjack ! », « 2 votes », « a sauté »…).
        var detail: String?
        var id: String { "\(kind.rawValue)-\(name)-\(detail ?? "")" }
    }

    /// Phrase de titre (« Le 17 noir est sorti », « Personne ne l'a jamais fait »…).
    var headline: String
    var lines: [Line]
    /// Identifie la manche : une nouvelle valeur relance l'annonce.
    var key: String

    var isEmpty: Bool { lines.isEmpty }
    func lines(_ kind: Kind) -> [Line] { lines.filter { $0.kind == kind } }
}

extension Outcome.Kind {
    var title: String {
        switch self {
        case .win: return "Gagnent"
        case .drink: return "Boivent"
        case .give: return "Distribuent"
        case .lose: return "Perdent"
        case .info: return ""
        }
    }

    var symbol: String {
        switch self {
        case .win: return "🏆"
        case .drink: return "🍻"
        case .give: return "🎁"
        case .lose: return "❌"
        case .info: return "👉"
        }
    }

    var color: Color {
        switch self {
        case .win: return TV.mint
        case .drink: return TV.coral
        case .give: return TV.lavender
        case .lose: return TV.red
        case .info: return TV.accent
        }
    }
}

/// « 2 gorgées », « 1 gorgée » : le même vocabulaire que les téléphones.
func sips(_ n: Int) -> String { "\(n) gorgée\(n > 1 ? "s" : "")" }

/// Tableau des résultats, en très grand : une colonne par sorte (gagnent, boivent, distribuent, perdent).
/// Les lignes arrivent l'une après l'autre (ressort) à chaque nouvelle manche.
struct OutcomeBoard: View {
    let outcome: Outcome
    @State private var shown = 0

    var body: some View {
        VStack(alignment: .leading, spacing: 28) {
            if !outcome.headline.isEmpty {
                Text(outcome.headline).font(.system(size: 64, weight: .heavy)).lineLimit(2).minimumScaleFactor(0.6)
                    .transition(.scale(scale: 0.6).combined(with: .opacity))
            }
            HStack(alignment: .top, spacing: 30) {
                ForEach(Outcome.Kind.allCases, id: \.self) { kind in
                    let lines = outcome.lines(kind)
                    if !lines.isEmpty { column(kind, lines) }
                }
            }
        }
        .onAppear { reveal() }
        .onChange(of: outcome.key) { _, _ in reveal() }
    }

    private func reveal() {
        shown = 0
        for i in 0..<outcome.lines.count {
            withAnimation(.spring(response: 0.5, dampingFraction: 0.62).delay(0.25 + Double(i) * 0.18)) { shown = i + 1 }
        }
    }

    private func column(_ kind: Outcome.Kind, _ lines: [Outcome.Line]) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            if kind != .info {
                Text("\(kind.symbol) \(kind.title.uppercased())").font(.system(size: 38, weight: .black)).foregroundStyle(kind.color)
            }
            ForEach(lines) { line in
                let index = outcome.lines.firstIndex(of: line) ?? 0
                row(line).opacity(index < shown ? 1 : 0).scaleEffect(index < shown ? 1 : 0.4, anchor: .leading)
            }
        }
        .padding(30)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(kind.color.opacity(0.16), in: RoundedRectangle(cornerRadius: 34, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 34, style: .continuous).stroke(kind.color.opacity(0.55), lineWidth: 3))
    }

    private func row(_ line: Outcome.Line) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 18) {
            Text(line.name).font(.system(size: 54, weight: .heavy)).lineLimit(1).minimumScaleFactor(0.5)
            Spacer(minLength: 10)
            if let amount = line.amount {
                Text(line.kind == .drink || line.kind == .give ? "\(amount)" : (amount > 0 ? "+\(amount)" : "\(amount)"))
                    .font(.system(size: 60, weight: .black).monospacedDigit()).foregroundStyle(line.kind.color)
                    .contentTransition(.numericText())
            }
        }
        .overlay(alignment: .bottomLeading) {
            if let detail = line.detail {
                Text(detail).font(.system(size: 32, weight: .bold)).foregroundStyle(TV.muted).offset(y: 40)
            }
        }
        .padding(.bottom, line.detail == nil ? 0 : 38)
    }
}

/// Annonce plein écran d'un nouveau résultat (quelques secondes), puis le tableau reste dans la scène.
struct OutcomeFlash: View {
    let outcome: Outcome
    @State private var pop = false

    var body: some View {
        VStack(spacing: 30) {
            if !outcome.headline.isEmpty {
                Text(outcome.headline).font(.system(size: 90, weight: .black)).multilineTextAlignment(.center)
                    .lineLimit(2).minimumScaleFactor(0.5)
            }
            let main = outcome.lines.filter { $0.kind != .info }.prefix(6)
            ForEach(Array(main.enumerated()), id: \.offset) { i, line in
                Text("\(line.kind.symbol) \(line.name) \(Self.verb(line))")
                    .font(.system(size: 76, weight: .heavy)).foregroundStyle(line.kind.color)
                    .lineLimit(1).minimumScaleFactor(0.5)
                    .opacity(pop ? 1 : 0).offset(y: pop ? 0 : 60)
                    .animation(.spring(response: 0.55, dampingFraction: 0.6).delay(0.2 + Double(i) * 0.22), value: pop)
            }
        }
        .padding(70)
        .frame(maxWidth: 1500)
        .glass(cornerRadius: 60)
        .scaleEffect(pop ? 1 : 0.7)
        .animation(.spring(response: 0.45, dampingFraction: 0.7), value: pop)
        .onAppear { pop = true }
    }

    static func verb(_ line: Outcome.Line) -> String {
        let n = line.amount.map { $0 } ?? 0
        switch line.kind {
        case .drink: return line.amount == nil ? "boit" : "boit \(sips(n))"
        case .give: return line.amount == nil ? "distribue" : "distribue \(sips(n))"
        case .win: return line.detail ?? (line.amount.map { "gagne \($0 > 0 ? "+" : "")\($0)" } ?? "gagne")
        case .lose: return line.detail ?? (line.amount.map { "perd \(abs($0))" } ?? "perd")
        case .info: return line.detail ?? ""
        }
    }
}

// MARK: - Résultat de chaque jeu

extension Outcome {
    /// Au-delà, le dernier coup d'un jeu à coups successifs n'est plus annoncé.
    static let freshSeconds = 30.0

    /// Résultat à annoncer pour la partie affichée (nil : rien de décidé à cette phase).
    static func of(_ g: JSON) -> Outcome? {
        let round = "\(g["code"].string ?? "")-\(g["type"].string ?? "")-\(g["round"].int ?? 0)"
        let sipsOption = g["options"]["sips"].int ?? 0
        var o: Outcome?
        switch (g["type"].string, g["phase"].string) {
        case ("never", "results"):
            let did = g["results"].array.filter { $0["answer"].string == "yes" }
            o = Outcome(headline: did.isEmpty ? "😇 Personne ne l'a jamais fait" : "🍻 Ils l'ont déjà fait !",
                        lines: did.map { Line(name: $0["name"].string ?? "?", kind: .drink, amount: sipsOption > 0 ? sipsOption : nil) },
                        key: "never-\(round)")
        case ("whoof", "results"):
            let rows = g["results"].array
            let best = rows.first?["count"].int ?? 0
            let top = rows.filter { ($0["count"].int ?? 0) == best && best > 0 }
            o = Outcome(headline: top.isEmpty ? "Personne n'a voté" : "👑 \(top.compactMap { $0["name"].string }.joined(separator: " & "))",
                        lines: top.map { Line(name: $0["name"].string ?? "?", kind: sipsOption > 0 ? .drink : .info,
                                              amount: sipsOption > 0 ? sipsOption : nil, detail: "\(best) vote\(best > 1 ? "s" : "")") },
                        key: "whoof-\(round)")
        case ("likely", "reveal"):
            let r = g["likely"]["result"]
            let winners = r["winners"].array.compactMap { $0["name"].string }
            o = Outcome(headline: winners.isEmpty ? "Personne n'a été désigné" : "🫵 \(winners.joined(separator: " & "))",
                        lines: winners.map { Line(name: $0, kind: sipsOption > 0 ? .drink : .win, amount: sipsOption > 0 ? sipsOption : 1,
                                                  detail: sipsOption > 0 ? nil : "prend 1 point") },
                        key: "likely-\(g["likely"]["n"].int ?? 0)-\(round)")
        case ("purity", "results"):
            let top = g["purity"]["ranking"].array.first
            o = Outcome(headline: top.map { "😈 \($0["name"].string ?? "?") · \($0["score"].int ?? 0) % impur" } ?? "😇 Que des anges",
                        lines: g["purity"]["gorgees"].array.map { Line(name: $0["name"].string ?? "?", kind: .drink, amount: $0["sips"].int) },
                        key: "purity-\(round)")
        case ("roulette", "spun"):
            guard let i = g["spin"]["index"].int, let name = g["spin"]["names"][i].string else { return nil }
            o = Outcome(headline: "🎯 \(name) a perdu !", lines: [], key: "roulette-\(g["spin"]["at"].string ?? round)")
        case ("blackjack", "results"):
            o = blackjack(g, round)
        case ("casino", "results"):
            o = casino(g)
        case ("quiz", "rev"):
            o = quiz(g)
        case ("undercover", "reveal"), ("undercover", "white_guess"), ("undercover", "end"):
            o = undercover(g, round)
        case ("tmc", "scored"):
            let d = g["tmc"]["duo"]
            let v = d["verdict"].double ?? 0
            let who = d["guesser"]["name"].string ?? "?"
            o = Outcome(headline: v >= 1 ? "✅ Juste !" : v > 0 ? "🤏 Presque !" : "❌ Raté !",
                        lines: v > 0 ? [Line(name: who, kind: .win, amount: Int(v * 2) == 1 ? nil : Int(v), detail: v < 1 ? "+½ point" : "+1 point")] : [],
                        key: "tmc-\(d["question"].string ?? "")-\(who)")
        case ("debate", "reveal"):
            let r = g["debate"]["result"]
            let pour = r["pour"].int ?? 0, contre = r["contre"].int ?? 0
            o = Outcome(headline: pour > contre ? "👍 Plutôt pour" : contre > pour ? "👎 Plutôt contre" : "🤔 Le groupe est partagé",
                        lines: [], key: "debate-\(g["debate"]["n"].int ?? 0)-\(g["debate"]["round"].int ?? 0)")
        case ("president", "end"):
            o = Outcome(headline: "👑 \(g["president"]["ranking"].array.first?["name"].string ?? "?") est Président",
                        lines: g["president"]["ranking"].array.map {
                            Line(name: $0["name"].string ?? "?", kind: ($0["place"].int ?? 0) == 1 ? .win : .info, detail: $0["role"].string)
                        }, key: "president-end-\(round)")
        case ("biskit", _), ("pyramid", _):
            o = fromSipsLog(g)
        default:
            o = nil
        }
        guard var o, !(o.headline.isEmpty && o.lines.isEmpty) else { return nil }
        // Gorgées comptées par le serveur mais pas nommées par le jeu (Quiz : les mauvaises réponses boivent…).
        if o.lines(.drink).isEmpty && o.lines(.give).isEmpty, let sipsNow = fromSipsLog(g), !["biskit", "pyramid"].contains(g["type"].string ?? "") {
            o.lines = o.lines.filter { $0.kind != .lose || $0.amount != nil } + sipsNow.lines
        }
        return o
    }

    private static func blackjack(_ g: JSON, _ round: String) -> Outcome {
        let drinks = (g["bj"]["drinks"].int ?? 0) > 0
        var lines: [Line] = []
        for seat in g["bj"]["seats"].array {
            let h = seat["hand"], name = seat["name"].string ?? "?"
            guard let result = h["result"].string else { continue }
            let label = ["blackjack": "Blackjack !", "push": "Égalité"][result]
            if drinks {
                let s = h["sips"].int ?? 0
                if s < 0 { lines.append(Line(name: name, kind: .drink, amount: -s, detail: h["status"].string == "bust" ? "a sauté" : nil)) }
                else if s > 0 { lines.append(Line(name: name, kind: .give, amount: s, detail: label)) }
                else { lines.append(Line(name: name, kind: .info, detail: "Égalité")) }
            } else {
                let d = h["delta"].int ?? 0
                lines.append(Line(name: name, kind: d > 0 ? .win : d < 0 ? .lose : .info, amount: d == 0 ? nil : d,
                                  detail: label ?? (h["status"].string == "bust" ? "a sauté" : nil)))
            }
        }
        let total = g["bj"]["dealer_total"].int
        return Outcome(headline: total.map { $0 > 21 ? "💥 La banque saute (\($0))" : "🏦 La banque fait \($0)" } ?? "Fin de la main",
                       lines: lines, key: "bj-\(round)")
    }

    private static func casino(_ g: JSON) -> Outcome? {
        let spin = g["casino"]["spin"]
        // La bille roule 7 s sur les téléphones : la télé annonce en même temps qu'eux.
        guard let n = spin["number"].int, (spin["age"].double ?? 99) >= 7 else { return nil }
        let reds: Set<Int> = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
        let color = n == 0 ? "vert" : reds.contains(n) ? "rouge" : "noir"
        var lines: [Line] = []
        for t in g["casino"]["table"].array {
            let r = t["result"], name = t["name"].string ?? "?"
            guard !r.isNull, (r["staked"].int ?? 0) > 0 || (r["drink"].int ?? 0) > 0 else { continue }
            if let d = r["drink"].int, d > 0 { lines.append(Line(name: name, kind: .drink, amount: d)) }
            if let gv = r["give"].int, gv > 0 { lines.append(Line(name: name, kind: .give, amount: gv, detail: r["jackpot"].bool ? "Jackpot !" : nil)) }
            if let net = r["net"].int, net != 0 {
                lines.append(Line(name: name, kind: net > 0 ? .win : .lose, amount: net, detail: r["jackpot"].bool ? "Jackpot !" : nil))
            }
        }
        return Outcome(headline: n == 0 ? "Zéro ! La maison gagne" : "Le \(n) \(color) est sorti !", lines: lines,
                       key: "casino-\(spin["id"].string ?? String(n))")
    }

    private static func quiz(_ g: JSON) -> Outcome {
        let q = g["quiz"]["q"]
        let correct = q["correct"].int.flatMap { q["choices"][$0].string }
        var lines: [Line] = []
        if let winner = q["winner"].string { lines.append(Line(name: winner, kind: .win, detail: "le plus rapide ⚡")) }
        for r in q["res"].array where q["winner"].string == nil {
            let name = r["name"].string ?? "?"
            if r["ok"].bool { lines.append(Line(name: name, kind: .win, amount: r["pts"].int)) }
            else { lines.append(Line(name: name, kind: (g["options"]["sips"].int ?? 0) > 0 ? .drink : .lose,
                                     amount: (g["options"]["sips"].int ?? 0) > 0 ? g["options"]["sips"].int : nil, detail: "raté")) }
        }
        return Outcome(headline: correct.map { "✅ \($0)" } ?? "Réponse", lines: lines, key: "quiz-\(g["quiz"]["n"].int ?? 0)")
    }

    private static func undercover(_ g: JSON, _ round: String) -> Outcome? {
        if g["phase"].string == "end" {
            // Chacun dans son camp : les civils d'un côté, les imposteurs (Undercover, Mr. White) de l'autre.
            let civilsWin = g["winner"].string == "civils"
            let lines = g["players"].array.map { p -> Line in
                let role = p["role"].string ?? "Civil"
                let civil = role == "Civil" || role == "Civils"
                return Line(name: p["name"].string ?? "?", kind: civil == civilsWin ? .win : .lose, detail: civil ? nil : role)
            }
            return Outcome(headline: "🏆 \(UndercoverTV.winner(g["winner"].string))", lines: lines, key: "uc-end-\(round)")
        }
        let last = g["last"]
        if last["tie"].bool { return Outcome(headline: "⚖️ Égalité : on revote", lines: [], key: "uc-tie-\(round)") }
        guard let name = last["name"].string else { return nil }
        return Outcome(headline: "❌ \(name) est éliminé·e" + (last["role"].string.map { " : c'était \($0) !" } ?? ""),
                       lines: [], key: "uc-\(name)-\(round)")
    }

    /// Jeux à coups successifs (Pyramide, Biskit) : les gorgées du dernier coup, d'après le journal du serveur.
    private static func fromSipsLog(_ g: JSON) -> Outcome? {
        let log = g["sips_log"].array
        // Le dernier coup : les gorgées notées dans les 2 s qui précèdent la plus récente, et seulement si elle est fraîche.
        guard let last = log.last, let newest = last["age"].double, newest < Self.freshSeconds else { return nil }
        let recent = log.filter { ($0["age"].double ?? 99) <= newest + 2 }
        var drink: [String: Int] = [:], give: [String: Int] = [:]
        for e in recent {
            let name = e["name"].string ?? "?"
            drink[name, default: 0] += e["drink"].int ?? 0
            give[name, default: 0] += e["give"].int ?? 0
        }
        let lines = drink.filter { $0.value > 0 }.sorted { $0.value > $1.value }.map { Line(name: $0.key, kind: .drink, amount: $0.value) }
            + give.filter { $0.value > 0 }.sorted { $0.value > $1.value }.map { Line(name: $0.key, kind: .give, amount: $0.value) }
        let head = g["bk"]["outcomes"][0]["head"].string ?? ""
        return Outcome(headline: head, lines: lines, key: "log-\(last["n"].int ?? 0)")
    }
}

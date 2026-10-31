import SwiftUI

/// Vrai pendant l'annonce plein écran : le tableau des résultats attend qu'elle parte pour se remplir sous les yeux
/// de la pièce (sinon ses lignes arrivaient cachées derrière l'annonce).
private struct OutcomeFlashingKey: EnvironmentKey { static let defaultValue = false }

extension EnvironmentValues {
    var outcomeFlashing: Bool {
        get { self[OutcomeFlashingKey.self] }
        set { self[OutcomeFlashingKey.self] = newValue }
    }
}

extension Outcome {
    /// Plusieurs personnes au même sort (« Léa, Tom & Nina boivent 2 gorgées ») : une seule ligne, plus grande.
    struct Group: Identifiable {
        let kind: Kind
        let names: [String]
        let amount: Int?
        let detail: String?
        var id: String { "\(kind.rawValue)-\(names.joined(separator: ","))-\(amount ?? 0)-\(detail ?? "")" }

        var who: String {
            guard names.count > 1 else { return names.first ?? "" }
            return names.dropLast().joined(separator: ", ") + " & " + (names.last ?? "")
        }

        /// « boit 2 gorgées », « boivent 2 gorgées », « distribue 3 gorgées », « gagne +20 »…
        var verb: String {
            let many = names.count > 1
            let n = amount ?? 0
            switch kind {
            case .drink:
                let v = many ? "boivent" : "boit"
                return amount == nil ? (detail ?? v) : "\(v) \(sips(n))"
            case .give:
                let v = many ? "distribuent" : "distribue"
                return amount == nil ? v : "\(v) \(sips(n))"
            case .win: return detail ?? (amount.map { "\(many ? "gagnent" : "gagne") \($0 > 0 ? "+" : "")\($0)" } ?? (many ? "gagnent" : "gagne"))
            case .lose: return detail ?? (amount.map { "\(many ? "perdent" : "perd") \(abs($0))" } ?? (many ? "perdent" : "perd"))
            case .info: return detail ?? ""
            }
        }
    }

    /// Les lignes regroupées par sort identique (même sorte, même nombre, même précision), dans l'ordre d'arrivée.
    var groups: [Group] {
        var out: [Group] = []
        for line in lines where line.kind != .info || line.detail != nil {
            if let i = out.firstIndex(where: { $0.kind == line.kind && $0.amount == line.amount && $0.detail == line.detail }) {
                let g = out[i]
                out[i] = Group(kind: g.kind, names: g.names + [line.name], amount: g.amount, detail: g.detail)
            } else {
                out.append(Group(kind: line.kind, names: [line.name], amount: line.amount, detail: line.detail))
            }
        }
        // Même ordre que le tableau : gagnent, boivent, distribuent, perdent (à sorte égale, l'ordre d'arrivée).
        return out.enumerated().sorted { ($0.element.kind.rawValue, $0.offset) < ($1.element.kind.rawValue, $1.offset) }.map(\.element)
    }

    /// La sorte qui domine l'annonce (couleur du liseré, des confettis) : gagner d'abord, puis boire, distribuer…
    var mainKind: Kind { Kind.allCases.first { !lines($0).isEmpty } ?? .info }
}

/// Tableau des résultats, en très grand : une colonne par sorte (gagnent, boivent, distribuent, perdent).
/// Les lignes arrivent l'une après l'autre (ressort) à chaque nouvelle manche, une fois l'annonce plein écran partie.
struct OutcomeBoard: View {
    let outcome: Outcome
    @Environment(\.outcomeFlashing) private var flashing
    @State private var shown = 0
    /// Manche déjà dévoilée : le même résultat ne se rejoue pas à chaque rafraîchissement.
    @State private var revealed: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 28) {
            if !outcome.headline.isEmpty {
                Text(outcome.headline).font(.system(size: 64, weight: .heavy)).lineLimit(2).minimumScaleFactor(0.6)
                    .id(outcome.key)
                    .transition(.motion(.scale(scale: 0.6).combined(with: .opacity)))
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
        .onChange(of: flashing) { _, now in now ? hide() : reveal() }
    }

    private func hide() {
        guard revealed != outcome.key else { return }
        var quiet = Transaction()
        quiet.disablesAnimations = true
        withTransaction(quiet) { shown = 0 }
    }

    private func reveal() {
        guard !flashing else { return hide() }
        guard revealed != outcome.key else { return shown = outcome.lines.count }
        revealed = outcome.key
        hide()
        for i in 0..<outcome.lines.count {
            withAnimation(Motion.pop.delay(0.15 + Double(i) * 0.14)) { shown = i + 1 }
        }
    }

    private func column(_ kind: Outcome.Kind, _ lines: [Outcome.Line]) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            if kind != .info {
                Text("\(kind.symbol) \(kind.title.uppercased())").font(.system(size: 38, weight: .black)).foregroundStyle(kind.color)
            }
            ForEach(lines) { line in
                let index = outcome.lines.firstIndex(of: line) ?? 0
                let on = index < shown
                row(line)
                    .opacity(on ? 1 : 0)
                    .scaleEffect(on || Motion.reduced ? 1 : 0.4, anchor: .leading)
                    .offset(x: on || Motion.reduced ? 0 : -40)
            }
        }
        .padding(30)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(kind.color.opacity(0.16), in: RoundedRectangle(cornerRadius: 34, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 34, style: .continuous).stroke(kind.color.opacity(0.55), lineWidth: 3))
        .transition(.popIn)
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
/// Le titre tombe en grand, puis chaque sort (regroupé : « Léa & Tom boivent 2 gorgées ») arrive par le bas ;
/// une gerbe de confettis aux couleurs du résultat, et une fine barre qui se vide jusqu'au retour au jeu.
struct OutcomeFlash: View {
    static let seconds = 6.0
    /// Au-delà, « + 3 autres » (le tableau de la scène les montre tous).
    static let maxGroups = 5

    let outcome: Outcome
    @State private var pop = false
    @State private var drained = false

    var body: some View {
        let groups = outcome.groups
        VStack(spacing: 30) {
            if !outcome.headline.isEmpty {
                Text(outcome.headline).font(.system(size: 92, weight: .black)).multilineTextAlignment(.center)
                    .lineLimit(2).minimumScaleFactor(0.5)
                    .scaleEffect(pop || Motion.reduced ? 1 : 1.5)
                    .opacity(pop ? 1 : 0)
                    .animation(Motion.animation(.spring(response: 0.42, dampingFraction: 0.58)), value: pop)
            }
            ForEach(Array(groups.prefix(Self.maxGroups).enumerated()), id: \.element.id) { i, group in
                row(group)
                    .opacity(pop ? 1 : 0).offset(y: pop || Motion.reduced ? 0 : 70)
                    .animation(Motion.animation(.spring(response: 0.55, dampingFraction: 0.66)).delay(0.35 + Double(i) * 0.2), value: pop)
            }
            if groups.count > Self.maxGroups {
                Text("+ \(groups.count - Self.maxGroups) autre\(groups.count - Self.maxGroups > 1 ? "s" : "") au tableau")
                    .font(.system(size: 40, weight: .bold)).foregroundStyle(TV.muted)
                    .opacity(pop ? 1 : 0).animation(Motion.animation(.easeOut).delay(1.4), value: pop)
            }
            // Temps qui reste avant le retour au jeu.
            Capsule().fill(.white.opacity(0.12)).frame(height: 8)
                .overlay(alignment: .leading) {
                    GeometryReader { bar in
                        Capsule().fill(outcome.mainKind.color.opacity(0.85)).frame(width: drained ? 0 : bar.size.width)
                    }
                }
                .frame(maxWidth: 600)
                .padding(.top, 10)
        }
        .padding(70)
        .frame(maxWidth: 1500)
        .glass(cornerRadius: 60)
        .overlay(RoundedRectangle(cornerRadius: 60, style: .continuous).stroke(outcome.mainKind.color.opacity(0.6), lineWidth: 4))
        .scaleEffect(pop || Motion.reduced ? 1 : 0.7)
        .animation(Motion.animation(.spring(response: 0.45, dampingFraction: 0.7)), value: pop)
        .background { if !Motion.reduced { ConfettiBurst(kind: outcome.mainKind) } }
        .onAppear {
            pop = true
            withAnimation(.linear(duration: Self.seconds)) { drained = true }
        }
        .accessibilityElement(children: .combine)
    }

    private func row(_ group: Outcome.Group) -> some View {
        HStack(spacing: 26) {
            Text(group.kind.symbol).font(.system(size: 64))
                .frame(width: 104, height: 104)
                .background(group.kind.color.opacity(0.25), in: Circle())
            // Une précision déjà dite par le titre (sentence du Beer pong) n'est pas répétée : seulement qui.
            let verb = !group.verb.isEmpty && outcome.headline.contains(group.verb) ? "" : group.verb
            (Text(group.who + " ").foregroundStyle(.white) + Text(verb).foregroundStyle(group.kind.color))
                .font(.system(size: 72, weight: .heavy))
                .lineLimit(2).minimumScaleFactor(0.45)
        }
        .padding(.horizontal, 30).padding(.vertical, 12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(group.kind.color.opacity(0.12), in: Capsule())
    }
}

/// Gerbe de confettis (et du symbole du résultat : 🏆, 🍻…) lancée une fois depuis le centre, qui retombe et s'efface.
/// Calculée d'après le temps écoulé : rien d'aléatoire d'une image à l'autre, rien qui se relance au rafraîchissement.
struct ConfettiBurst: View {
    let kind: Outcome.Kind
    static let duration = 3.2
    static let count = 70
    @State private var start = Date()

    private struct Piece {
        let angle: Double, speed: Double, spin: Double, size: Double, hue: Int, emoji: Bool
    }

    private static let pieces: [Piece] = (0..<count).map { i in
        // Suite pseudo-aléatoire fixe (même gerbe à chaque fois, bien répartie).
        func r(_ k: Int) -> Double { let x = sin(Double(i * 97 + k * 13) * 12.9898) * 43758.5453; return x - x.rounded(.down) }
        return Piece(angle: -.pi / 2 + (r(1) - 0.5) * .pi * 1.5, speed: 900 + r(2) * 900, spin: (r(3) - 0.5) * 12,
                     size: 14 + r(4) * 18, hue: i % 4, emoji: i % 7 == 0)
    }

    var body: some View {
        TimelineView(.animation) { timeline in
            let t = timeline.date.timeIntervalSince(start)
            Canvas { context, size in
                guard t < Self.duration else { return }
                let colors: [Color] = [kind.color, TV.accent, TV.lavender, TV.coral]
                let symbol = context.resolve(Text(kind == .info ? "🎉" : kind.symbol).font(.system(size: 54)))
                let center = CGPoint(x: size.width / 2, y: size.height * 0.45)
                let fade = max(0, 1 - max(0, t - Self.duration + 1))
                context.opacity = fade
                for p in Self.pieces {
                    let x = center.x + cos(p.angle) * p.speed * t * 0.9
                    let y = center.y + sin(p.angle) * p.speed * t + 900 * t * t
                    let point = CGPoint(x: x, y: y)
                    if p.emoji {
                        context.draw(symbol, at: point)
                    } else {
                        var piece = context
                        piece.translateBy(x: x, y: y)
                        piece.rotate(by: .radians(p.spin * t))
                        piece.fill(Path(CGRect(x: -p.size / 2, y: -p.size / 4, width: p.size, height: p.size / 2)),
                                   with: .color(colors[p.hue]))
                    }
                }
            }
        }
        .frame(width: 2400, height: 1600)
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }
}

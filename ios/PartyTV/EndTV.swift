import SwiftUI

/// Fin de partie : le podium (points, jetons…) qui monte marche par marche, 3e puis 2e puis 1er (suspense), le nom
/// du gagnant qui tombe en grand avec une gerbe de confettis, puis le palmarès des gorgées.
/// Plus rien de la dernière manche (« Au tour de… », « 0/6 ont voté ») : la partie est finie.
struct EndTV: View {
    let game: JSON
    /// Étape du dévoilement : 0 rien, 1 la 3e marche, 2 la 2e, 3 la 1re, 4 le gagnant et les prix.
    @State private var step = 0

    static let heights: [CGFloat] = [300, 200, 140]
    static let stepPause: Duration = .milliseconds(850)
    static let stepWidth: CGFloat = 240

    /// Podium des points ou des jetons seulement : un classement des gorgées n'a pas de gagnant (il a son prix à part).
    private var ranking: [(name: String, value: String)] {
        guard let rows = SideBoard.rows(game), !rows.0.contains("Gorgées") else { return [] }
        return rows.1
    }
    private var players: [JSON] { game["players"].array }
    private var hasPodium: Bool { ranking.count >= 2 && Set(ranking.map(\.value)).count > 1 }

    /// Le gagnant nommé en titre : seul en tête d'un classement de points ou de jetons (pas « le plus désigné »).
    private var champion: String? { Self.champion(of: game) }

    /// Aussi lu par la piste des Zicou (figure de victoire du gagnant).
    static func champion(of game: JSON) -> String? {
        if let name = game["quiz"]["board"][0]["name"].string, (game["quiz"]["board"][0]["pts"].int ?? 0) > 0 { return name }
        guard let rows = SideBoard.rows(game), !rows.0.contains("Gorgées") else { return nil }
        let ranking = rows.1
        guard ranking.count >= 2, Set(ranking.map(\.value)).count > 1, ["Classement", "Jetons", "Points"].contains(rows.0),
              ranking[0].value != ranking[1].value else { return nil }
        return ranking.first?.name
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 36) {
            ZStack(alignment: .leading) {
                if let champion, step >= 4 {
                    Text("🏆 \(champion) gagne !").font(.system(size: 96, weight: .black)).foregroundStyle(TV.coral)
                        .lineLimit(1).minimumScaleFactor(0.5)
                        .transition(.motion(.scale(scale: 1.6).combined(with: .opacity)))
                } else {
                    Text("🏁 Fin de la partie").font(.system(size: 80, weight: .black))
                        .transition(.opacity)
                }
            }
            .frame(height: 120, alignment: .leading)
            HStack(alignment: .bottom, spacing: 40) {
                if hasPodium { podium }
                VStack(alignment: .leading, spacing: 26) {
                    award("🍻 Le plus assoiffé", most("drink"), TV.coral)
                    award("🎁 Le plus généreux", most("give"), TV.lavender)
                }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(alignment: .top) { if step >= 4 && champion != nil && !Motion.reduced { ConfettiBurst(kind: .win) } }
        .task { await unveil() }
    }

    /// 3e, 2e, 1er, puis le gagnant : une marche à la fois. Animations réduites : tout d'un coup, en fondu.
    private func unveil() async {
        guard step == 0 else { return }
        if Motion.reduced { return withAnimation(Motion.update) { step = 4 } }
        let order = hasPodium ? (ranking.count >= 3 ? [1, 2, 3] : [2, 3]) : [3]
        for s in order {
            try? await Task.sleep(for: Self.stepPause)
            withAnimation(.spring(response: 0.6, dampingFraction: 0.62)) { step = s }
        }
        try? await Task.sleep(for: Self.stepPause)
        withAnimation(.spring(response: 0.45, dampingFraction: 0.55)) { step = 4 }
    }

    /// Marche i (0 = 1re) déjà montée ? La 3e d'abord, la 1re en dernier.
    private func risen(_ i: Int) -> Bool { step >= 3 - i }

    /// 2e, 1er, 3e : la plus haute marche au milieu. Hauteur fixe : la scène ne bouge pas pendant que les marches montent.
    private var podium: some View {
        HStack(alignment: .bottom, spacing: 18) {
            ForEach([1, 0, 2].filter { $0 < ranking.count }, id: \.self) { i in
                let up = risen(i)
                VStack(spacing: 14) {
                    VStack(spacing: 14) {
                        Text(["🥇", "🥈", "🥉"][i]).font(.system(size: 70))
                            .modifier(BreathingIf(on: i == 0 && step >= 4))
                        Text(ranking[i].name).font(.system(size: i == 0 ? 60 : 44, weight: .heavy)).lineLimit(1).minimumScaleFactor(0.5)
                        Text(ranking[i].value).font(.system(size: 34, weight: .bold).monospacedDigit()).foregroundStyle(TV.lavender).lineLimit(1).fixedSize()
                    }
                    .opacity(up ? 1 : 0)
                    .offset(y: up || Motion.reduced ? 0 : 40)
                    RoundedRectangle(cornerRadius: 20, style: .continuous)
                        .fill(i == 0 ? TV.accent : TV.surface)
                        .frame(width: Self.stepWidth, height: up ? Self.heights[i] : 10)
                        .overlay(Text("\(i + 1)").font(.system(size: 90, weight: .black)).foregroundStyle(.white.opacity(up ? 0.85 : 0)))
                        .shadow(color: i == 0 && step >= 4 ? TV.accent.opacity(0.7) : .clear, radius: 30)
                }
                .frame(height: Self.heights[0] + 230, alignment: .bottom)
            }
        }
    }

    /// Celui qui a le plus bu (ou distribué) ; à égalité, tous les ex æquo (« Tout le monde » si personne ne se détache).
    private func most(_ key: String) -> (name: String, n: Int)? {
        let all = players.map { ($0["name"].string ?? "?", $0[key].int ?? 0) }
        guard let best = all.map(\.1).max(), best > 0 else { return nil }
        let top = all.filter { $0.1 == best }.map(\.0)
        return (top.count == all.count && all.count > 1 ? "Tout le monde" : top.joined(separator: " & "), best)
    }

    @ViewBuilder private func award(_ title: String, _ who: (name: String, n: Int)?, _ color: Color) -> some View {
        if let who {
            let on = step >= 4
            VStack(alignment: .leading, spacing: 6) {
                Text(title.uppercased()).font(.system(size: 28, weight: .heavy)).foregroundStyle(color)
                Text(who.name).font(.system(size: 70, weight: .black)).lineLimit(1).minimumScaleFactor(0.5)
                Text(sips(who.n)).font(.system(size: 36, weight: .bold)).foregroundStyle(TV.muted)
            }
            .padding(30)
            .frame(minWidth: 360, alignment: .leading)
            .background(color.opacity(0.16), in: RoundedRectangle(cornerRadius: 34, style: .continuous))
            .scaleEffect(on || Motion.reduced ? 1 : 0.6).opacity(on ? 1 : 0)
        }
    }
}

/// Respiration seulement quand `on` (la médaille d'or une fois le gagnant annoncé).
struct BreathingIf: ViewModifier {
    let on: Bool
    var scale: CGFloat = 1.12
    func body(content: Content) -> some View {
        if on { content.breathing(period: 2.2, scale: scale) } else { content }
    }
}

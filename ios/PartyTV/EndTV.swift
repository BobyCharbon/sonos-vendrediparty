import SwiftUI

/// Fin de partie : le podium (points, jetons…) qui monte marche par marche, puis le palmarès des gorgées.
/// Plus rien de la dernière manche (« Au tour de… », « 0/6 ont voté ») : la partie est finie.
struct EndTV: View {
    let game: JSON
    @State private var risen = false

    /// Podium des points ou des jetons seulement : un classement des gorgées n'a pas de gagnant (il a son prix à part).
    private var ranking: [(name: String, value: String)] {
        guard let rows = SideBoard.rows(game), !rows.0.contains("Gorgées") else { return [] }
        return rows.1
    }
    private var players: [JSON] { game["players"].array }

    var body: some View {
        VStack(alignment: .leading, spacing: 36) {
            if let champion = game["quiz"]["board"][0]["name"].string, (game["quiz"]["board"][0]["pts"].int ?? 0) > 0 {
                Text("🏆 \(champion) gagne !").font(.system(size: 96, weight: .black)).foregroundStyle(TV.coral).lineLimit(1).minimumScaleFactor(0.5)
            } else {
                Text("🏁 Fin de la partie").font(.system(size: 80, weight: .black))
            }
            HStack(alignment: .bottom, spacing: 40) {
                if ranking.count >= 2 && Set(ranking.map(\.value)).count > 1 { podium }
                VStack(alignment: .leading, spacing: 26) {
                    award("🍻 Le plus assoiffé", most("drink"), TV.coral)
                    award("🎁 Le plus généreux", most("give"), TV.lavender)
                }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .onAppear { withAnimation(.spring(response: 0.7, dampingFraction: 0.6).delay(0.2)) { risen = true } }
    }

    /// 2e, 1er, 3e : la plus haute marche au milieu.
    private var podium: some View {
        HStack(alignment: .bottom, spacing: 18) {
            ForEach([1, 0, 2].filter { $0 < ranking.count }, id: \.self) { i in
                VStack(spacing: 14) {
                    Text(["🥇", "🥈", "🥉"][i]).font(.system(size: 70))
                    Text(ranking[i].name).font(.system(size: i == 0 ? 60 : 44, weight: .heavy)).lineLimit(1).minimumScaleFactor(0.5)
                    Text(ranking[i].value).font(.system(size: 34, weight: .bold).monospacedDigit()).foregroundStyle(TV.lavender)
                    RoundedRectangle(cornerRadius: 20, style: .continuous)
                        .fill(i == 0 ? TV.accent : TV.surface)
                        .frame(width: 280, height: risen ? [300, 200, 140][i] : 10)
                        .overlay(Text("\(i + 1)").font(.system(size: 90, weight: .black)).foregroundStyle(.white.opacity(0.85)))
                }
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
            VStack(alignment: .leading, spacing: 6) {
                Text(title.uppercased()).font(.system(size: 28, weight: .heavy)).foregroundStyle(color)
                Text(who.name).font(.system(size: 70, weight: .black)).lineLimit(1).minimumScaleFactor(0.5)
                Text(sips(who.n)).font(.system(size: 36, weight: .bold)).foregroundStyle(TV.muted)
            }
            .padding(30)
            .frame(minWidth: 420, alignment: .leading)
            .background(color.opacity(0.16), in: RoundedRectangle(cornerRadius: 34, style: .continuous))
            .scaleEffect(risen ? 1 : 0.6).opacity(risen ? 1 : 0)
        }
    }
}

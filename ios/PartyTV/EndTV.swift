import SwiftUI

/// Fin de partie : le podium (points, jetons…) qui monte marche par marche, puis le palmarès des gorgées.
/// Plus rien de la dernière manche (« Au tour de… », « 0/6 ont voté ») : la partie est finie.
struct EndTV: View {
    let game: JSON
    @State private var risen = false

    private var ranking: [(name: String, value: String)] { SideBoard.rows(game)?.1 ?? [] }
    private var players: [JSON] { game["players"].array }

    var body: some View {
        VStack(alignment: .leading, spacing: 36) {
            Text("🏁 Partie terminée").font(.system(size: 80, weight: .black))
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

    private func most(_ key: String) -> (name: String, n: Int)? {
        players.map { ($0["name"].string ?? "?", $0[key].int ?? 0) }.filter { $0.1 > 0 }.max { $0.1 < $1.1 }.map { ($0.0, $0.1) }
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

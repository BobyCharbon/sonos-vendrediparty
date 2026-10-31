import SwiftUI

/// Beer pong : les deux tables de gobelets face à face (Rouges, Bleus), la sentence en cours ou la dernière, en grand.
struct BeerPongTV: View {
    let game: JSON
    private var B: JSON { game["bp"] }
    static let rows: [Int: [Int]] = [6: [3, 2, 1], 10: [4, 3, 2, 1], 15: [5, 4, 3, 2, 1]]

    var body: some View {
        VStack(alignment: .leading, spacing: 30) {
            if let winner = B["winner"].string {
                Text("🏆 Les \(B["team_names"][winner].string ?? winner) gagnent !").font(.system(size: 90, weight: .black)).foregroundStyle(TV.coral)
            }
            HStack(alignment: .center, spacing: 40) {
                rack("red", color: Color(red: 1, green: 0.3, blue: 0.37))
                Rectangle().fill(.white.opacity(0.4)).frame(width: 6).padding(.vertical, 20)
                rack("blue", color: Color(red: 0.25, green: 0.64, blue: 1))
            }
            .frame(maxWidth: .infinity)
            let pending = B["pending"]
            if !pending.isNull {
                Text("🎯 \(pending["name"].string ?? "?") a perdu un gobelet : la sentence arrive…")
                    .font(.system(size: 52, weight: .black)).foregroundStyle(TV.coral).lineLimit(2).minimumScaleFactor(0.5)
            } else if !B["last"].isNull {
                sentence(B["last"])
            }
        }
    }

    private func rack(_ team: String, color: Color) -> some View {
        let cups = B["racks"][team].array
        let rows = Self.rows[cups.count] ?? [cups.count]
        let starts = rows.indices.map { rows.prefix($0).reduce(0, +) }
        return VStack(spacing: 12) {
            HStack {
                Text("\(team == "red" ? "🔴" : "🔵") \(B["team_names"][team].string ?? team)").font(.system(size: 44, weight: .black))
                Spacer()
                Text("\(B["alive"][team].int ?? 0)/\(cups.count)").font(.system(size: 44, weight: .black).monospacedDigit()).foregroundStyle(color)
                    .contentTransition(.numericText())
            }
            VStack(spacing: 10) {
                ForEach(Array(rows.enumerated()), id: \.offset) { r, n in
                    HStack(spacing: 10) {
                        ForEach(0..<n, id: \.self) { i in
                            let up = cups[safe: starts[r] + i]?.bool ?? false
                            Circle().fill(color.gradient).frame(width: 64, height: 64)
                                .overlay(Circle().stroke(.white.opacity(0.5), lineWidth: 3))
                                .opacity(up ? 1 : 0.12).scaleEffect(up ? 1 : 0.7)
                                .animation(.spring(response: 0.45, dampingFraction: 0.55), value: up)
                        }
                    }
                }
            }
            .rotationEffect(team == "blue" ? .degrees(180) : .zero)  // les deux pointes se font face
            Text(B["players"].array.filter { $0["team"].string == team }.compactMap { $0["name"].string }.joined(separator: " · "))
                .font(.system(size: 30, weight: .semibold)).foregroundStyle(TV.muted).lineLimit(2)
        }
        .padding(30)
        .frame(maxWidth: .infinity)
        .card(color.opacity(0.12), radius: 36)
    }

    private func sentence(_ last: JSON) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("\(Self.icon(last["kind"].string)) \(last["name"].string ?? "?")").font(.system(size: 44, weight: .heavy)).foregroundStyle(TV.lavender)
            Text(last["text"].string ?? "").font(.system(size: 64, weight: .black)).lineLimit(3).minimumScaleFactor(0.5)
            if let hint = last["hint"].string { Text(hint).font(.system(size: 34, weight: .bold)).foregroundStyle(TV.coral) }
        }
        .padding(36)
        .frame(maxWidth: .infinity, alignment: .leading)
        .card(TV.surface, radius: 36)
        .id(last["n"].int ?? 0)
        .transition(.scale(scale: 0.8).combined(with: .opacity))
    }

    static func icon(_ kind: String?) -> String {
        ["sips": "🍺", "shot": "🥃", "dare": "🎭", "wtf": "🤪", "quiz": "🧠", "sport": "💪", "bonus": "🎁", "malus": "💣"][kind ?? ""] ?? "🎯"
    }
}

extension Array {
    subscript(safe index: Int) -> Element? { indices.contains(index) ? self[index] : nil }
}

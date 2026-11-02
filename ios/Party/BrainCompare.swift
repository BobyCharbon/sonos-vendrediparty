import SwiftUI

/// 🧠 Méninges sur la fiche d'un membre : sa Température et ses domaines face aux miens (POST /api/brain/compare).
/// Le serveur ne renvoie que des agrégats (indices 0–2000), jamais le détail des parties de l'autre.
struct BrainCompare: Decodable, Equatable {
    struct Row: Decodable, Equatable, Identifiable {
        let domain: String
        let label: String
        let icon: String
        let me: Int?
        let them: Int?
        var id: String { domain }
    }

    let id: String
    let name: String
    let isSelf: Bool
    let played: Bool
    let temperature: Int
    let mePlayed: Bool
    let meTemperature: Int
    let rows: [Row]
    let verdict: String

    enum CodingKeys: String, CodingKey {
        case id, name, played, temperature, rows, verdict
        case isSelf = "self", mePlayed = "me_played", meTemperature = "me_temperature"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        name = try c.decodeIfPresent(String.self, forKey: .name) ?? "?"
        isSelf = try c.decodeIfPresent(Bool.self, forKey: .isSelf) ?? false
        played = try c.decodeIfPresent(Bool.self, forKey: .played) ?? false
        temperature = try c.decodeIfPresent(Int.self, forKey: .temperature) ?? 0
        mePlayed = try c.decodeIfPresent(Bool.self, forKey: .mePlayed) ?? false
        meTemperature = try c.decodeIfPresent(Int.self, forKey: .meTemperature) ?? 0
        rows = try c.decodeIfPresent([Row].self, forKey: .rows) ?? []
        verdict = try c.decodeIfPresent(String.self, forKey: .verdict) ?? ""
    }

    /// Température en tête, puis chaque domaine joué par l'un ou l'autre.
    var bars: [Row] {
        [Row(domain: "temperature", label: "Température", icon: "🌡️",
             me: mePlayed ? meTemperature : nil, them: played ? temperature : nil)] + rows
    }
}

/// Réponse de /api/brain/compare : seul le membre comparé sert à la fiche.
struct BrainCompareResponse: Decodable {
    let target: BrainCompare?
}

extension PartyAPI {
    func brainCompare(token: String, target: String) async throws -> BrainCompare? {
        let r: BrainCompareResponse = try await postDecoding("/api/brain/compare", body: ["token": token, "target": target])
        return r.target
    }
}

/// Section « 🧠 Méninges » de la fiche : barres côte à côte (toi / le membre) et la phrase-bilan.
struct BrainCompareSection: View {
    let compare: BrainCompare

    static let maxIndex = 2000.0
    static let them = Color.orange

    var body: some View {
        Section {
            if compare.played {
                legend
                ForEach(compare.bars) { row in BrainCompareRow(row: row, other: compare.name) }
            }
            Text(compare.verdict).font(.subheadline).foregroundStyle(.secondary)
        } header: {
            Text("🧠 Méninges")
        }
    }

    private var legend: some View {
        HStack(spacing: 14) {
            Label { Text("Toi") } icon: { Circle().fill(Palette.accent).frame(width: 10, height: 10) }
            Label { Text(compare.name) } icon: { Circle().fill(Self.them).frame(width: 10, height: 10) }
        }
        .font(.caption)
        .foregroundStyle(.secondary)
        .accessibilityHidden(true)
    }
}

private struct BrainCompareRow: View {
    let row: BrainCompare.Row
    let other: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("\(row.icon) \(row.label)").font(.subheadline.weight(.semibold))
            bar(row.me, color: Palette.accent)
            bar(row.them, color: BrainCompareSection.them)
        }
        .padding(.vertical, 2)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(row.label) : toi \(spoken(row.me)), \(other) \(spoken(row.them))")
    }

    private func bar(_ value: Int?, color: Color) -> some View {
        HStack(spacing: 8) {
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(Color.primary.opacity(0.08))
                    Capsule().fill(color)
                        .frame(width: geo.size.width * CGFloat(min(max(Double(value ?? 0), 0), BrainCompareSection.maxIndex) / BrainCompareSection.maxIndex))
                }
            }
            .frame(height: 8)
            Text(value.map(String.init) ?? "—").font(.caption.monospacedDigit()).frame(width: 40, alignment: .trailing)
        }
    }

    private func spoken(_ value: Int?) -> String { value.map { "\($0) degrés M" } ?? "pas encore joué" }
}

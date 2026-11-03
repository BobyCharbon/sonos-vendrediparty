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

        enum CodingKeys: String, CodingKey { case domain, label, icon, me, them }

        init(domain: String, label: String, icon: String, me: Int?, them: Int?) {
            self.domain = domain
            self.label = label
            self.icon = icon
            self.me = me
            self.them = them
        }

        /// Tolérant : libellé ou icône absents → repli ; nombre à virgule ou énorme → borné ; seul le domaine est requis.
        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            domain = try c.decode(String.self, forKey: .domain)
            label = (try? c.decodeIfPresent(String.self, forKey: .label)) ?? domain
            icon = (try? c.decodeIfPresent(String.self, forKey: .icon)) ?? "🧠"
            me = c.flexibleInt(.me)
            them = c.flexibleInt(.them)
        }
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
        // Seul l'identifiant est requis : un champ abîmé (nombre à virgule ou énorme, null, ligne illisible) prend
        // une valeur neutre au lieu de faire disparaître toute la comparaison de la fiche.
        guard let id = c.flexibleID(.id) else {
            throw DecodingError.dataCorruptedError(forKey: .id, in: c, debugDescription: "id manquant")
        }
        self.id = id
        name = (try? c.decodeIfPresent(String.self, forKey: .name)) ?? "?"
        isSelf = (try? c.decodeIfPresent(Bool.self, forKey: .isSelf)) ?? false
        played = (try? c.decodeIfPresent(Bool.self, forKey: .played)) ?? false
        temperature = c.flexibleInt(.temperature) ?? 0
        mePlayed = (try? c.decodeIfPresent(Bool.self, forKey: .mePlayed)) ?? false
        meTemperature = c.flexibleInt(.meTemperature) ?? 0
        rows = c.lossyArray(Row.self, .rows)
        verdict = (try? c.decodeIfPresent(String.self, forKey: .verdict)) ?? ""
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

    /// Part de la barre remplie (0…1), valeur hors bornes ramenée.
    static func ratio(_ value: Int?) -> Double { min(max(Double(value ?? 0), 0), maxIndex) / maxIndex }

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

    @Environment(\.dynamicTypeSize) private var typeSize

    /// Légende : côte à côte ; l'une sous l'autre avec un texte très grand (un nom long écrasait « Toi »).
    private func key(_ text: String, _ color: Color) -> some View {
        HStack(spacing: 6) {
            Circle().fill(color).frame(width: 10, height: 10)
            Text(text).lineLimit(2)
        }
    }

    private var legend: some View {
        let layout = typeSize.isAccessibilitySize ? AnyLayout(VStackLayout(alignment: .leading, spacing: 6))
            : AnyLayout(HStackLayout(spacing: 14))
        return layout {
            key("Toi", Palette.accent).fixedSize()
            key(compare.name, Self.them)
        }
        .font(.caption)
        .foregroundStyle(.secondary)
        .accessibilityHidden(true)
    }
}

private struct BrainCompareRow: View {
    let row: BrainCompare.Row
    let other: String
    @ScaledMetric(relativeTo: .caption) private var numberWidth: CGFloat = 44

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
                        .frame(width: geo.size.width * CGFloat(BrainCompareSection.ratio(value)))
                }
            }
            .frame(height: 8)
            // Même largeur pour les deux barres (comparables), qui grandit avec le texte (Dynamic Type) : le chiffre
            // n'est plus tronqué en « 1… » ; un nombre hors normes rétrécit au lieu d'être coupé.
            Text(value.map(BrainStats.number) ?? "—").font(.caption.monospacedDigit())
                .lineLimit(1).minimumScaleFactor(0.5).frame(width: numberWidth, alignment: .trailing)
        }
    }

    private func spoken(_ value: Int?) -> String { value.map { "\(BrainStats.number($0)) degrés M" } ?? "pas encore joué" }
}

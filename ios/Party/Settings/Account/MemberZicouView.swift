import SwiftUI

/// Zicou sur la fiche profil (avis de l'admin, 4.11), POST /api/pet/profile : l'apparence publique de son Zicou
/// (app/pet_profile.py), jamais ses jauges, pièces ou inventaire. 404 (Zicou éteint en production, membre bloqué) :
/// rien sur la fiche. Même présentation que le web (app/static/pet/profile-zicou.js).
struct MemberZicou: Decodable, Equatable {
    struct Piece: Decodable, Equatable, Hashable {
        let id: String
        let label: String
        let emoji: String
        let rarity: String
        let color: String
        let rarityLabel: String?

        enum CodingKeys: String, CodingKey { case id, label, emoji, rarity, color, rarityLabel = "rarity_label" }

        /// Couleur de la rareté (catalogue : « #RRGGBB », ou « rainbow » pour un Mythique).
        var tint: Color {
            guard color.hasPrefix("#"), let v = UInt32(color.dropFirst(), radix: 16) else { return Color(hex: 0xFF8CC2) }
            return Color(hex: v)
        }
    }

    struct Look: Decodable, Equatable {
        /// Nom seulement s'il a passé le filtre du serveur ; nil sinon (« Son Zicou »).
        let name: String?
        let stage: String
        let emotion: String
        let shiny: Bool
        let gen: Int
        let ageDays: Int
        let pieces: [Piece]
        let best: Piece?

        enum CodingKeys: String, CodingKey { case name, stage, emotion, shiny, gen, best, ageDays = "age_days", pieces = "acc_items" }

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            name = try c.decodeIfPresent(String.self, forKey: .name)
            stage = try c.decodeIfPresent(String.self, forKey: .stage) ?? "adult"
            emotion = try c.decodeIfPresent(String.self, forKey: .emotion) ?? "happy"
            shiny = try c.decodeIfPresent(Bool.self, forKey: .shiny) ?? false
            gen = max(1, try c.decodeIfPresent(Int.self, forKey: .gen) ?? 1)
            ageDays = max(0, try c.decodeIfPresent(Int.self, forKey: .ageDays) ?? 0)
            pieces = (try? c.decodeIfPresent([Piece].self, forKey: .pieces)) ?? []
            best = try? c.decodeIfPresent(Piece.self, forKey: .best)
        }

        var title: String { name ?? "Son Zicou" }
        var age: String {
            if stage == "egg" { return "dans son œuf" }
            return ageDays == 0 ? "né aujourd'hui" : "\(ageDays) jour\(ageDays > 1 ? "s" : "")"
        }
        var subtitle: String { "Génération \(gen) · \(age)" }
        /// La plus belle pièce n'est mise en avant qu'à partir d'Épique.
        var highlight: Piece? { best.flatMap { ["epic", "legendary", "mythic"].contains($0.rarity) ? $0 : nil } }
        var mood: Color { Z.mood[emotion] ?? Z.cyan }
    }

    let member: String
    let me: Bool
    let friend: Bool
    let mine: Bool
    let zicou: Look?

    /// « Adopter le mien » : sur ma fiche, ou quand je regarde quelqu'un sans avoir de Zicou moi-même.
    var offersAdoption: Bool { zicou == nil && (me || !mine) }
    var canVisit: Bool { friend && !me && zicou != nil }
}

extension PartyAPI {
    func memberZicou(token: String, id: String) async throws -> MemberZicou {
        try await postDecoding("/api/pet/profile", body: ["token": token, "member": id])
    }
}

/// Ouvrir l'onglet Zicou de la page (visite d'un ami, ou « Adopter le mien »). Donnée par l'app (PartyApp.swift).
struct OpenZicouAction {
    let open: @MainActor (_ visit: String?) -> Void
}

private struct OpenZicouKey: EnvironmentKey {
    static let defaultValue: OpenZicouAction? = nil
}

extension EnvironmentValues {
    var openZicou: OpenZicouAction? {
        get { self[OpenZicouKey.self] }
        set { self[OpenZicouKey.self] = newValue }
    }
}

/// Le bloc de la fiche : vedette lumineuse s'il a un Zicou, œuf gris terne sinon.
struct MemberZicouView: View {
    let data: MemberZicou
    /// Toucher (visite, adopter) : la fiche se ferme et l'onglet Zicou s'ouvre.
    let open: (_ visit: String?) -> Void

    var body: some View {
        if let look = data.zicou {
            ZicouSpotlight(look: look, member: data.member, canVisit: data.canVisit, open: open)
        } else {
            ZicouEmptyEgg(me: data.me, adopt: data.offersAdoption ? { open(nil) } : nil)
        }
    }
}

private struct ZicouSpotlight: View {
    let look: MemberZicou.Look
    let member: String
    let canVisit: Bool
    let open: (_ visit: String?) -> Void
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var breathe = false
    @State private var wink = false
    @State private var sheen = false

    private static let stageSize: CGFloat = 168
    private static let figureSize: CGFloat = 132

    var body: some View {
        VStack(spacing: 8) {
            Button { if canVisit { Haptics.tap(); open(member) } } label: { stage }
                .buttonStyle(.plain)
                .disabled(!canVisit)
                .accessibilityLabel(spoken)
                .accessibilityHint(canVisit ? "Lui rendre visite" : "")
            VStack(spacing: 3) {
                Text(look.title).font(.title3.weight(.heavy)).multilineTextAlignment(.center)
                if look.shiny {
                    Text("✨ Shiny").font(.caption.weight(.bold)).foregroundStyle(Z.ink)
                        .padding(.horizontal, 8).padding(.vertical, 2)
                        .background(Capsule().fill(LinearGradient(colors: [Color(hex: 0xF4F6FF), Color(hex: 0xB9C1DC), Color(hex: 0xFFC4E6)],
                                                                   startPoint: .leading, endPoint: .trailing)))
                }
                Text(look.subtitle).font(.subheadline).foregroundStyle(.white.opacity(0.78))
            }
            if !look.pieces.isEmpty {
                FlowChips(pieces: look.pieces)
            }
            if let best = look.highlight {
                (Text("Sa plus belle pièce : ") + Text(best.label).bold().foregroundColor(best.tint) + Text(" · \(best.rarityLabel ?? "")"))
                    .font(.footnote).foregroundStyle(.white.opacity(0.7))
            }
            if canVisit {
                Button { Haptics.tap(); open(member) } label: {
                    Text("Lui rendre visite ›").font(.subheadline.weight(.bold)).padding(.horizontal, 16).padding(.vertical, 9)
                        .background(Capsule().fill(.white.opacity(0.12)))
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("member-zicou-visit")
            }
        }
        .foregroundStyle(.white)
        .frame(maxWidth: .infinity)
        .padding(.vertical, 14).padding(.horizontal, 12)
        .background(background)
        .clipShape(RoundedRectangle(cornerRadius: 26, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 26, style: .continuous).strokeBorder(look.mood.opacity(0.38), lineWidth: 1))
        .shadow(color: look.mood.opacity(0.35), radius: 18, y: 10)
        .accessibilityIdentifier("member-zicou")
        .onAppear {
            guard !reduceMotion else { return }
            withAnimation(.easeInOut(duration: 1.8).repeatForever(autoreverses: true)) { breathe = true }
            withAnimation(.easeInOut(duration: 2.4).repeatForever(autoreverses: true).delay(1.2)) { wink = true }
            withAnimation(.easeInOut(duration: 3.8).repeatForever(autoreverses: false)) { sheen = true }
        }
    }

    private var spoken: String {
        "\(look.title), \(PetWidgetState.moodWord(look.emotion))\(look.shiny ? ", shiny" : ""), \(look.subtitle)"
    }

    private var background: some View {
        ZStack {
            LinearGradient(colors: [Color(hex: 0x2A1D5C), Color(hex: 0x1A1238)], startPoint: .top, endPoint: .bottom)
            RadialGradient(colors: [look.mood.opacity(0.42), .clear], center: UnitPoint(x: 0.5, y: 0.18), startRadius: 0, endRadius: 220)
            RadialGradient(colors: [look.mood.opacity(0.2), .clear], center: UnitPoint(x: 0.5, y: 1.1), startRadius: 0, endRadius: 200)
        }
    }

    private var stage: some View {
        ZStack {
            Circle().fill(RadialGradient(colors: [look.mood.opacity(0.6), look.mood.opacity(0.18), .clear],
                                         center: .center, startRadius: 0, endRadius: Self.stageSize / 2))
                .blur(radius: 6)
                .scaleEffect(breathe ? 1.04 : 0.96)
                .opacity(breathe ? 1 : 0.75)
            ZicouFigure(emotion: look.emotion, stage: look.stage)
                .frame(width: Self.figureSize, height: Self.figureSize)
                .scaleEffect(x: breathe ? 1.025 : 1, y: breathe ? 0.985 : 1, anchor: .bottom)
                .offset(y: breathe ? -3 : 0)
                .environment(\.zicouForcedTint, false)
            Image(systemName: "sparkle").font(.system(size: 15, weight: .bold)).foregroundStyle(.white)
                .scaleEffect(wink ? 1 : 0.3).opacity(wink ? 1 : 0).rotationEffect(.degrees(wink ? 45 : 0))
                .offset(x: 46, y: -54)
                .accessibilityHidden(true)
            if look.shiny {
                Circle().fill(LinearGradient(stops: [.init(color: .clear, location: 0.3), .init(color: .white.opacity(0.5), location: 0.46),
                                                     .init(color: Color(hex: 0xC8E6FF).opacity(0.35), location: 0.52), .init(color: .clear, location: 0.66)],
                                             startPoint: UnitPoint(x: sheen ? -0.6 : 1.2, y: 0), endPoint: UnitPoint(x: sheen ? 0.4 : 2.2, y: 1)))
                    .blendMode(.screen)
                    .padding(8)
                    .allowsHitTesting(false)
                    .accessibilityHidden(true)
            }
        }
        .frame(width: Self.stageSize, height: Self.stageSize)
        .contentShape(Circle())
    }
}

/// Ce qu'il porte : une puce par accessoire, bordée de la couleur de sa rareté.
private struct FlowChips: View {
    let pieces: [MemberZicou.Piece]

    private static let perRow = 2

    var body: some View {
        VStack(spacing: 6) {
            ForEach(Array(stride(from: 0, to: pieces.count, by: Self.perRow)), id: \.self) { start in
                HStack(spacing: 6) {
                    ForEach(pieces[start..<min(start + Self.perRow, pieces.count)], id: \.self) { chip($0) }
                }
            }
        }
        .fixedSize(horizontal: false, vertical: true)
    }

    private func chip(_ p: MemberZicou.Piece) -> some View {
        Text("\(p.emoji) \(p.label)").font(.caption).lineLimit(1)
            .padding(.horizontal, 9).padding(.vertical, 3)
            .background(Capsule().fill(.white.opacity(0.08)))
            .overlay(Capsule().strokeBorder(p.tint.opacity(0.6), lineWidth: 1))
    }
}

/// Sans Zicou : rien ne brille. Un œuf gris mat, penché, et l'envie d'en avoir un.
private struct ZicouEmptyEgg: View {
    let me: Bool
    let adopt: (() -> Void)?

    var body: some View {
        VStack(spacing: 8) {
            ZStack(alignment: .bottom) {
                Ellipse().fill(.black.opacity(0.18)).frame(width: 56, height: 10).offset(y: 4)
                DullEgg().fill(Color(hex: 0x6F6A7C))
                    .overlay(DullEgg().stroke(Color(hex: 0x4A4656), lineWidth: 2))
                    .overlay(DullCrack().stroke(Color(hex: 0x4A4656).opacity(0.55), style: StrokeStyle(lineWidth: 1.6, lineCap: .round, lineJoin: .round)))
                    .frame(width: 64, height: 82)
                    .rotationEffect(.degrees(-9))
            }
            .frame(height: 100)
            .accessibilityHidden(true)
            Text("Pas encore de Zicou").font(.headline).foregroundStyle(.secondary)
            Text(me ? "Ton œuf t'attend. Il éclot en 3 minutes." : "Son œuf attend encore d'être adopté.")
                .font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.center)
            if let adopt {
                Button("Adopter le mien") { Haptics.tap(); adopt() }
                    .buttonStyle(.borderedProminent)
                    .tint(Color(hex: 0xD92A73))
                    .accessibilityIdentifier("member-zicou-adopt")
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 14)
        .background(RoundedRectangle(cornerRadius: 26, style: .continuous).fill(.white.opacity(0.04)))
        .overlay(RoundedRectangle(cornerRadius: 26, style: .continuous).strokeBorder(.white.opacity(0.06), lineWidth: 1))
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("member-zicou-none")
    }
}

private struct DullEgg: Shape {
    func path(in rect: CGRect) -> Path {
        let w = rect.width, h = rect.height
        var p = Path()
        p.move(to: CGPoint(x: rect.midX, y: rect.minY))
        p.addCurve(to: CGPoint(x: rect.maxX, y: rect.minY + h * 0.62), control1: CGPoint(x: rect.minX + w * 0.82, y: rect.minY),
                   control2: CGPoint(x: rect.maxX, y: rect.minY + h * 0.36))
        p.addCurve(to: CGPoint(x: rect.midX, y: rect.maxY), control1: CGPoint(x: rect.maxX, y: rect.minY + h * 0.86),
                   control2: CGPoint(x: rect.minX + w * 0.78, y: rect.maxY))
        p.addCurve(to: CGPoint(x: rect.minX, y: rect.minY + h * 0.62), control1: CGPoint(x: rect.minX + w * 0.22, y: rect.maxY),
                   control2: CGPoint(x: rect.minX, y: rect.minY + h * 0.86))
        p.addCurve(to: CGPoint(x: rect.midX, y: rect.minY), control1: CGPoint(x: rect.minX, y: rect.minY + h * 0.36),
                   control2: CGPoint(x: rect.minX + w * 0.18, y: rect.minY))
        return p
    }
}

private struct DullCrack: Shape {
    func path(in rect: CGRect) -> Path {
        let w = rect.width, h = rect.height
        var p = Path()
        p.move(to: CGPoint(x: rect.minX + w * 0.25, y: rect.minY + h * 0.55))
        for (i, x) in [0.37, 0.48, 0.6, 0.72].enumerated() {
            p.addLine(to: CGPoint(x: rect.minX + w * x, y: rect.minY + h * (i.isMultiple(of: 2) ? 0.48 : 0.56)))
        }
        return p
    }
}

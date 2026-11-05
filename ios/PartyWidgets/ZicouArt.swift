import SwiftUI
import WidgetKit

/// Zicou Nuit dessiné en SwiftUI pour les widgets et la Live Activity : même silhouette et mêmes couleurs que
/// tools/icon/zicou-icon.svg et app/static/pet/skin.js (boule à facettes, casque rose, antennes, grands yeux),
/// avec le visage de son humeur. Coordonnées de l'icône (carré de 1024), mises à l'échelle.
/// Rendu teinté / monochrome (écran verrouillé, iOS 18 teinté) : silhouette claire, visage accentué.
struct ZicouFigure: View {
    let emotion: String
    var stage: String = "adult"
    @Environment(\.widgetRenderingMode) private var mode
    @Environment(\.zicouForcedTint) private var forcedTint

    var body: some View {
        GeometryReader { proxy in
            let side = min(proxy.size.width, proxy.size.height)
            ZStack {
                if stage == "egg" || emotion == "egg" {
                    egg
                } else {
                    creature
                }
            }
            .frame(width: 1024, height: 1024)
            .scaleEffect(side / 1024)
            .frame(width: side, height: side)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .aspectRatio(1, contentMode: .fit)
        .accessibilityLabel(PetWidgetState.moodWord(emotion))
    }

    private var colored: Bool { forcedTint.map { !$0 } ?? (mode == .fullColor) }
    private var ghost: Bool { emotion == "ghost" || stage == "dead" }

    // MARK: Personnage

    private var creature: some View {
        ZStack {
            Group {
                // Antennes
                ForEach([(CGPoint(x: 326, y: 326), CGPoint(x: 290, y: 134)), (CGPoint(x: 698, y: 326), CGPoint(x: 734, y: 134))],
                        id: \.0.x) { base, tip in
                    Segment(from: base, to: tip).stroke(Z.ink, style: StrokeStyle(lineWidth: 30, lineCap: .round))
                    Segment(from: base, to: tip).stroke(paint(Z.lilac), style: StrokeStyle(lineWidth: 12, lineCap: .round))
                    Circle().fill(Z.ink).frame(width: 90, height: 90).position(tip)
                    Circle().fill(paint(mood)).frame(width: 69, height: 69).position(tip)
                        .shadow(color: colored ? mood.opacity(0.8) : .clear, radius: 14)
                }
                ball
                // Casque
                Band().stroke(Z.ink, style: StrokeStyle(lineWidth: 82, lineCap: .round))
                Band().stroke(paint(ghost ? Z.ghostDark : Z.pink), style: StrokeStyle(lineWidth: 60, lineCap: .round))
                ForEach([206.0, 818.0], id: \.self) { x in
                    RoundedRectangle(cornerRadius: 69).fill(paint(ghost ? Z.ghostDark : Z.pink))
                        .overlay(RoundedRectangle(cornerRadius: 69).stroke(Z.ink, lineWidth: 14))
                        .frame(width: 150, height: 276).position(x: x, y: 584)
                    Circle().fill(Z.ink).frame(width: 114, height: 114).position(x: x, y: 584)
                    Circle().stroke(paint(mood), lineWidth: 22).frame(width: 114, height: 114).position(x: x, y: 584)
                        .opacity(dim ? 0.5 : 1)
                }
            }
            face.widgetAccentable()
            signs.widgetAccentable()
        }
        .opacity(ghost ? 0.85 : 1)
    }

    private var ball: some View {
        ZStack {
            Circle().fill(colored ? AnyShapeStyle(ballGradient) : AnyShapeStyle(Color.white.opacity(0.25)))
            if colored {
                Facets(palette: ghost ? Z.ghostTiles : Z.tiles, shift: -72).frame(width: 600, height: 600).clipShape(Circle())
                Circle().fill(RadialGradient(colors: [.clear, Z.shade.opacity(0.65)], center: UnitPoint(x: 0.4, y: 0.35),
                                             startRadius: 160, endRadius: 420))
                Ellipse().fill(.white.opacity(0.4)).frame(width: 156, height: 90).rotationEffect(.degrees(-30))
                    .position(x: 398 - 212, y: 449 - 284)   // repère de la boule (600 × 600)
                if emotion == "sick" { Circle().fill(Z.green.opacity(0.28)) }
            }
            Circle().stroke(Z.ink, lineWidth: 16)
        }
        .frame(width: 600, height: 600).position(x: 512, y: 584)
    }

    private var ballGradient: RadialGradient {
        let stops = ghost ? [Color(hex: 0xE9E5FF), Color(hex: 0xC9C2EA), Color(hex: 0x9A94B8)]
                          : [Color(hex: 0x5A3FD0), Color(hex: 0x2D1D86), Color(hex: 0x160D4A)]
        return RadialGradient(colors: stops, center: UnitPoint(x: 0.38, y: 0.32), startRadius: 0, endRadius: 450)
    }

    // MARK: Visage

    private var face: some View {
        ZStack {
            ForEach([404.0, 620.0], id: \.self) { x in eye(x: x) }
            brows
            if ["happy", "party", "hungry"].contains(emotion), colored {
                ForEach([338.5, 685.5], id: \.self) { x in
                    Ellipse().fill(Z.cheek.opacity(0.75)).frame(width: 87, height: 55).position(x: x, y: 693)
                }
            }
            mouth
        }
    }

    @ViewBuilder
    private func eye(x: CGFloat) -> some View {
        switch emotion {
        case "sleep":
            Smile(center: CGPoint(x: x, y: 590), width: 110, depth: 30)
                .stroke(Z.ink, style: StrokeStyle(lineWidth: 22, lineCap: .round))
        case "ghost":
            Cross(center: CGPoint(x: x, y: 584), size: 90).stroke(Z.ink, style: StrokeStyle(lineWidth: 24, lineCap: .round))
        case "tired":
            Capsule().fill(Color.white).overlay(Capsule().stroke(Z.ink, lineWidth: 19))
                .frame(width: 142, height: 70).position(x: x, y: 610)
            Circle().fill(Z.ink).frame(width: 56, height: 56).position(x: x, y: 615)
        default:
            Ellipse().fill(Color.white).overlay(Ellipse().stroke(Z.ink, lineWidth: 19))
                .frame(width: 142, height: 164).position(x: x, y: 584)
            Circle().fill(Z.ink).frame(width: 76, height: 76).position(x: x, y: emotion == "sad" ? 610 : 595)
            Circle().fill(Color.white).frame(width: 33, height: 33).position(x: x - 16, y: 573)
            if emotion == "sick" {
                Circle().stroke(Color.white, lineWidth: 6).frame(width: 40, height: 40).position(x: x, y: 595)
            }
        }
    }

    @ViewBuilder
    private var brows: some View {
        let lift: CGFloat = emotion == "party" ? 26 : ["happy", "hungry"].contains(emotion) ? 14 : 0
        if ["sad", "sick", "hungry"].contains(emotion) {
            ForEach([(CGPoint(x: 464, y: 455), CGPoint(x: 344, y: 470)), (CGPoint(x: 560, y: 455), CGPoint(x: 680, y: 470))],
                    id: \.0.x) { inner, outer in
                Segment(from: CGPoint(x: inner.x, y: inner.y - 22), to: outer)
                    .stroke(Z.ink, style: StrokeStyle(lineWidth: 24.6, lineCap: .round))
            }
        } else if emotion != "sleep" && emotion != "ghost" {
            ForEach([404.0, 620.0], id: \.self) { x in
                Smile(center: CGPoint(x: x, y: 452 - lift), width: 120, depth: -32)
                    .stroke(Z.ink, style: StrokeStyle(lineWidth: 24.6, lineCap: .round))
            }
        }
    }

    @ViewBuilder
    private var mouth: some View {
        switch emotion {
        case "party":
            Grin().fill(Z.ink)
            Grin().stroke(Z.ink, style: StrokeStyle(lineWidth: 20, lineJoin: .round))
        case "hungry":
            Ellipse().fill(Z.ink).frame(width: 70, height: 84).position(x: 512, y: 760)
        case "sad":
            Smile(center: CGPoint(x: 512, y: 780), width: 130, depth: -46)
                .stroke(Z.ink, style: StrokeStyle(lineWidth: 27, lineCap: .round))
        case "tired", "sick", "ghost":
            Wave(center: CGPoint(x: 512, y: 765), width: 150).stroke(Z.ink, style: StrokeStyle(lineWidth: 24, lineCap: .round))
        case "sleep":
            Ellipse().fill(Z.ink).frame(width: 46, height: 34).position(x: 512, y: 760)
        default:
            Smile(center: CGPoint(x: 512, y: 742), width: 142, depth: 71)
                .stroke(colored ? Z.paleLine : Color.white, style: StrokeStyle(lineWidth: 65, lineCap: .round))
            Smile(center: CGPoint(x: 512, y: 742), width: 142, depth: 71)
                .stroke(Z.ink, style: StrokeStyle(lineWidth: 27, lineCap: .round))
        }
    }

    /// Petits signes de l'humeur (paillettes, « z », larme).
    @ViewBuilder
    private var signs: some View {
        switch emotion {
        case "party":
            Sparkle().fill(paint(Z.gold)).frame(width: 110, height: 110).position(x: 150, y: 260)
            Sparkle().fill(paint(Z.cyan)).frame(width: 80, height: 80).position(x: 890, y: 300)
            Sparkle().fill(paint(.white)).frame(width: 64, height: 64).position(x: 900, y: 860)
        case "sleep", "tired":
            Text("z").font(.system(size: 120, weight: .heavy, design: .rounded)).foregroundStyle(paint(Z.lilac))
                .position(x: 850, y: 230)
            Text("z").font(.system(size: 80, weight: .heavy, design: .rounded)).foregroundStyle(paint(Z.lilac))
                .position(x: 930, y: 140)
        case "sad":
            Ellipse().fill(paint(Z.blue)).frame(width: 30, height: 48).position(x: 360, y: 690)
        default:
            EmptyView()
        }
    }

    // MARK: Œuf

    private var egg: some View {
        ZStack {
            EggShape().fill(colored ? AnyShapeStyle(ballGradient) : AnyShapeStyle(Color.white.opacity(0.25)))
            if colored {
                Facets(palette: Z.tiles, shift: 0).clipShape(EggShape())
                EggShape().fill(RadialGradient(colors: [.clear, Z.shade.opacity(0.6)], center: UnitPoint(x: 0.4, y: 0.35),
                                               startRadius: 180, endRadius: 520))
                Ellipse().fill(.white.opacity(0.4)).frame(width: 120, height: 70).rotationEffect(.degrees(-30))
                    .position(x: 400, y: 380)
            }
            EggShape().stroke(Z.ink, lineWidth: 18)
            Crack().stroke(Z.ink, style: StrokeStyle(lineWidth: 16, lineCap: .round, lineJoin: .round)).widgetAccentable()
        }
    }

    // MARK: Couleurs

    private var mood: Color { Z.mood[emotion] ?? Z.cyan }
    private var dim: Bool { ["tired", "sleep", "sad", "sick"].contains(emotion) }

    /// Couleur vive en rendu complet ; blanc en rendu teinté (iOS applique la teinte).
    private func paint(_ color: Color) -> Color { colored ? color : .white }
}

/// Captures hors WidgetKit (aperçus) : rendu teinté imposé (true) ou en couleurs (false) ; nil : celui du système.
private struct ZicouForcedTintKey: EnvironmentKey {
    static let defaultValue: Bool? = nil
}

extension EnvironmentValues {
    var zicouForcedTint: Bool? {
        get { self[ZicouForcedTintKey.self] }
        set { self[ZicouForcedTintKey.self] = newValue }
    }
}

/// Palette de Zicou Nuit (skin.js, zicou-icon.svg).
enum Z {
    static let ink = Color(hex: 0x1B1030)
    static let pink = Color(hex: 0xFF4F9A)
    static let cyan = Color(hex: 0x5EE7FF)
    static let gold = Color(hex: 0xFFB547)
    static let lilac = Color(hex: 0xDDD5F7)
    static let green = Color(hex: 0x57E39B)
    static let blue = Color(hex: 0x7AA2FF)
    static let cheek = Color(hex: 0xFF7AA8)
    static let paleLine = Color(hex: 0xEFE9FF)
    static let shade = Color(hex: 0x0B0624)
    static let ghostDark = Color(hex: 0x9A94B8)
    static let tiles = [0x8F6BFF, 0x6D55F0, 0xB9A6FF, 0x5EE7FF, 0xD9CEFF, 0xFF4F9A, 0x6D55F0, 0xFFB547].map { Color(hex: $0) }
    static let ghostTiles = [0xECE8FF, 0xD6D0F0].map { Color(hex: $0) }
    static let mood: [String: Color] = [
        "egg": Color(hex: 0xB9A6FF), "happy": cyan, "party": pink, "hungry": gold, "tired": Color(hex: 0x8F7BD8),
        "sad": blue, "sick": green, "sleep": Color(hex: 0x6B5BB8), "ghost": Color(hex: 0xCFC8EE),
    ]
    /// Fonds : nuit (sombre), lavande (clair).
    static let night = [Color(hex: 0x2A1873), Color(hex: 0x120C2C)]
    static let day = [Color(hex: 0xF3EEFF), Color(hex: 0xE4DAFF)]
}

extension Color {
    init(hex: UInt32) {
        self.init(red: Double((hex >> 16) & 0xFF) / 255, green: Double((hex >> 8) & 0xFF) / 255, blue: Double(hex & 0xFF) / 255)
    }
}

// MARK: Formes (repère de l'icône, 1024 × 1024)

private struct Segment: Shape {
    let from: CGPoint
    let to: CGPoint

    func path(in rect: CGRect) -> Path {
        Path { $0.move(to: from); $0.addLine(to: to) }
    }
}

/// Arceau du casque (M218 560 C212 194 812 194 806 560).
private struct Band: Shape {
    func path(in rect: CGRect) -> Path {
        Path {
            $0.move(to: CGPoint(x: 218, y: 560))
            $0.addCurve(to: CGPoint(x: 806, y: 560), control1: CGPoint(x: 212, y: 194), control2: CGPoint(x: 812, y: 194))
        }
    }
}

/// Courbe en sourire (depth > 0) ou en arc renversé (depth < 0), centrée sur `center`.
private struct Smile: Shape {
    let center: CGPoint
    let width: CGFloat
    let depth: CGFloat

    func path(in rect: CGRect) -> Path {
        Path {
            $0.move(to: CGPoint(x: center.x - width / 2, y: center.y))
            $0.addQuadCurve(to: CGPoint(x: center.x + width / 2, y: center.y), control: CGPoint(x: center.x, y: center.y + 2 * depth))
        }
    }
}

private struct Wave: Shape {
    let center: CGPoint
    let width: CGFloat

    func path(in rect: CGRect) -> Path {
        Path {
            let w = width / 4
            $0.move(to: CGPoint(x: center.x - 2 * w, y: center.y))
            $0.addQuadCurve(to: CGPoint(x: center.x, y: center.y), control: CGPoint(x: center.x - w, y: center.y - 28))
            $0.addQuadCurve(to: CGPoint(x: center.x + 2 * w, y: center.y), control: CGPoint(x: center.x + w, y: center.y + 28))
        }
    }
}

private struct Cross: Shape {
    let center: CGPoint
    let size: CGFloat

    func path(in rect: CGRect) -> Path {
        Path {
            let h = size / 2
            $0.move(to: CGPoint(x: center.x - h, y: center.y - h)); $0.addLine(to: CGPoint(x: center.x + h, y: center.y + h))
            $0.move(to: CGPoint(x: center.x + h, y: center.y - h)); $0.addLine(to: CGPoint(x: center.x - h, y: center.y + h))
        }
    }
}

/// Grand sourire ouvert (fête).
private struct Grin: Shape {
    func path(in rect: CGRect) -> Path {
        Path {
            $0.move(to: CGPoint(x: 430, y: 730))
            $0.addQuadCurve(to: CGPoint(x: 594, y: 730), control: CGPoint(x: 512, y: 745))
            $0.addQuadCurve(to: CGPoint(x: 430, y: 730), control: CGPoint(x: 512, y: 880))
            $0.closeSubpath()
        }
    }
}

private struct Sparkle: Shape {
    func path(in rect: CGRect) -> Path {
        let c = CGPoint(x: rect.midX, y: rect.midY), r = rect.width / 2, k = r * 0.18
        return Path {
            $0.move(to: CGPoint(x: c.x, y: c.y - r))
            $0.addQuadCurve(to: CGPoint(x: c.x + r, y: c.y), control: CGPoint(x: c.x + k, y: c.y - k))
            $0.addQuadCurve(to: CGPoint(x: c.x, y: c.y + r), control: CGPoint(x: c.x + k, y: c.y + k))
            $0.addQuadCurve(to: CGPoint(x: c.x - r, y: c.y), control: CGPoint(x: c.x - k, y: c.y + k))
            $0.addQuadCurve(to: CGPoint(x: c.x, y: c.y - r), control: CGPoint(x: c.x - k, y: c.y - k))
        }
    }
}

private struct EggShape: Shape {
    func path(in rect: CGRect) -> Path {
        Path {
            $0.move(to: CGPoint(x: 512, y: 190))
            $0.addCurve(to: CGPoint(x: 800, y: 640), control1: CGPoint(x: 690, y: 190), control2: CGPoint(x: 800, y: 440))
            $0.addCurve(to: CGPoint(x: 512, y: 900), control1: CGPoint(x: 800, y: 800), control2: CGPoint(x: 680, y: 900))
            $0.addCurve(to: CGPoint(x: 224, y: 640), control1: CGPoint(x: 344, y: 900), control2: CGPoint(x: 224, y: 800))
            $0.addCurve(to: CGPoint(x: 512, y: 190), control1: CGPoint(x: 224, y: 440), control2: CGPoint(x: 334, y: 190))
            $0.closeSubpath()
        }
    }
}

private struct Crack: Shape {
    func path(in rect: CGRect) -> Path {
        Path { path in
            path.move(to: CGPoint(x: 300, y: 540))
            for (x, y) in [(370, 500), (420, 560), (490, 500), (550, 570), (620, 505), (680, 560), (730, 520)] {
                path.addLine(to: CGPoint(x: x, y: y))
            }
        }
    }
}

/// Facettes de la boule : damier de tuiles colorées, plus claires en haut à gauche (reflet).
private struct Facets: View {
    let palette: [Color]
    /// Décalage vertical : la boule (centrée en 512, 584) est dessinée dans son propre cadre de 600 × 600.
    let shift: CGFloat
    private static let count = 7
    private static let origin: CGFloat = 200
    private static let size: CGFloat = 624 / CGFloat(count)

    var body: some View {
        ZStack {
            ForEach(0..<(Self.count * Self.count), id: \.self) { index in
                let row = index / Self.count, col = index % Self.count
                let light = max(0.12, 1 - Double(row + col) * 0.085)
                Rectangle()
                    .fill(palette[(row * 3 + col * 5) % palette.count])
                    .opacity(light)
                    .frame(width: Self.size - 10, height: Self.size - 10)
                    .position(x: Self.origin + (CGFloat(col) + 0.5) * Self.size, y: 272 + (CGFloat(row) + 0.5) * Self.size)
            }
        }
        .frame(width: 1024, height: 1024)
        .offset(y: shift)
    }
}

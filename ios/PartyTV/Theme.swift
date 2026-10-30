import SwiftUI

/// Couleurs de Party (même nuit violette que le site et l'app iPhone), lisibles de loin sur une télé.
enum TV {
    static let bg = Color(red: 0.08, green: 0.06, blue: 0.16)
    static let surface = Color(red: 0.13, green: 0.10, blue: 0.24)
    static let accent = Color(red: 1, green: 0.31, blue: 0.60)
    static let lavender = Color(red: 0.73, green: 0.65, blue: 1)
    static let mint = Color(red: 0.36, green: 0.89, blue: 0.65)
    static let coral = Color(red: 1, green: 0.70, blue: 0.28)
    static let red = Color(red: 1, green: 0.39, blue: 0.39)
    static let muted = Color.white.opacity(0.62)

    static var backdrop: some View {
        LinearGradient(colors: [Color(red: 0.16, green: 0.07, blue: 0.27), bg, Color(red: 0.05, green: 0.04, blue: 0.11)],
                       startPoint: .topLeading, endPoint: .bottomTrailing)
            .overlay(RadialGradient(colors: [accent.opacity(0.18), .clear], center: .topTrailing, startRadius: 10, endRadius: 900))
            .ignoresSafeArea()
    }
}

extension View {
    /// Verre semi-transparent (Liquid Glass sur tvOS 26, matière floutée avant).
    @ViewBuilder func glass(cornerRadius: CGFloat = 36) -> some View {
        if #available(tvOS 26.0, *) {
            self.glassEffect(.regular, in: RoundedRectangle(cornerRadius: cornerRadius, style: .continuous))
        } else {
            self.background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: cornerRadius, style: .continuous))
        }
    }

    func card(_ color: Color = TV.surface, radius: CGFloat = 28) -> some View {
        background(color.opacity(0.85), in: RoundedRectangle(cornerRadius: radius, style: .continuous))
    }
}

/// Pastille d'un joueur : photo (compte Party) ou initiales, coche quand il a voté, barrée s'il est éliminé.
struct PlayerBadge: View {
    let player: JSON
    var size: CGFloat = 92
    var highlight = false

    private var name: String { player["name"].string ?? "?" }
    private var initials: String { name.split(separator: " ").prefix(2).compactMap(\.first).map(String.init).joined().uppercased() }
    private var out: Bool { player["alive"] == .bool(false) }

    var body: some View {
        VStack(spacing: 10) {
            ZStack(alignment: .bottomTrailing) {
                AsyncImage(url: player["photo"].string.flatMap(URL.init(string:))) { image in
                    image.resizable().scaledToFill()
                } placeholder: {
                    Text(initials.isEmpty ? "?" : initials).font(.system(size: size * 0.36, weight: .heavy)).foregroundStyle(.black)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        .background(Color(hue: Double(abs(name.hashValue) % 360) / 360, saturation: 0.45, brightness: 0.95))
                }
                .frame(width: size, height: size)
                .clipShape(Circle())
                .overlay(Circle().stroke(highlight ? TV.accent : .clear, lineWidth: 6))
                .opacity(out ? 0.35 : 1)
                if player["voted"].bool {
                    Image(systemName: "checkmark.circle.fill").font(.system(size: size * 0.32)).foregroundStyle(TV.mint)
                        .background(Circle().fill(TV.bg))
                }
            }
            Text(name).font(.system(size: 26, weight: .semibold)).lineLimit(1).strikethrough(out)
                .foregroundStyle(out ? TV.muted : .white)
        }
        .frame(width: size + 60)
    }
}

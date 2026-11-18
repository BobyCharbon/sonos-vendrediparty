import SwiftUI
import UIKit

// MARK: - Discussions v2 « Néon club » (maquettes 1-neon, 18.11.2026)
//
// Jetons : les mêmes valeurs que PronoTheme (PronoKit.swift) ; sombre (défaut de Party) ET clair, chaque couleur suit
// le thème de l'appareil. Lavande = toi / ce qui est choisi ; rose = agir ou à lire (non lus, @, bouton principal) ;
// orange = une soirée ; menthe = en ligne / « Je viens ».
// Vues : NeonAvatar (rond : une personne), GroupTile (carré emoji : un groupe, GroupLook.swift), NeonDateTile (petit
// calendrier : une soirée), NeonCountBadge, NeonCircleButton, NeonGlow (lueur du haut de l'écran).

enum ChatNeon {
    // Surfaces
    static let bg = PronoTheme.bg
    static let s1 = PronoTheme.s1
    static let s1b = PronoTheme.s1b
    static let glass = PronoTheme.dynamic(0xFFFFFF, 0xFFFFFF, dark: 0.06, light: 0.72)
    static let glassLine = PronoTheme.dynamic(0xFFFFFF, 0x1D1530, dark: 0.10, light: 0.08)
    static let line = PronoTheme.dynamic(0xFFFFFF, 0x1D1530, dark: 0.07, light: 0.08)
    static let line2 = PronoTheme.line2
    static let halo = PronoTheme.dynamic(0x7B6CF6, 0x7B6CF6, dark: 0.26, light: 0.14)

    // Textes (AA : 7,8:1 et 5,6:1 sur le fond sombre ; 7 et 4,8:1 sur le clair)
    static let t1 = PronoTheme.t1
    static let t2 = PronoTheme.t2
    static let t3 = PronoTheme.t3

    // Accents
    static let lav = PronoTheme.lavInk
    static let lavA = PronoTheme.fixed(0xCBBDFF)
    static let lavB = PronoTheme.lavB
    static let pink = PronoTheme.pink
    /// Texte rose (heure d'un non lu, @citation) : #FF6FAE sur sombre, #C21F68 sur clair (5,2:1).
    static let pinkInk = PronoTheme.dynamic(0xFF6FAE, 0xC21F68)
    static let pinkA = PronoTheme.fixed(0xFF7DB6)
    /// Encre sur rose (6,2:1) : jamais de texte blanc sur le rose.
    static let onPink = PronoTheme.fixed(0x1F0618)
    static let mint = PronoTheme.mintInk
    static let coral = PronoTheme.dynamic(0xFFB347, 0xB25E00)
    /// Pastille d'une discussion en sourdine : grise au lieu de rose (jamais cachée).
    static let muted = PronoTheme.dynamic(0x3A3360, 0xDCD6F0)
    static let mutedInk = PronoTheme.dynamic(0xC9C2E8, 0x3F3760)

    // Bulles (conversation)
    static let mineA = PronoTheme.fixed(0x6E5CF0)
    static let mineB = PronoTheme.fixed(0x5A48DA)
    static let theirs = PronoTheme.dynamic(0x1C1638, 0xFFFFFF)

    static var pinkGradient: LinearGradient {
        LinearGradient(colors: [pinkA, pink], startPoint: .topLeading, endPoint: .bottomTrailing)
    }
    static var lavenderGradient: LinearGradient {
        LinearGradient(colors: [lavA, lav], startPoint: .topLeading, endPoint: .bottomTrailing)
    }
    /// Anneau d'une épinglée non lue : rose → lavande.
    static var ring: AngularGradient {
        AngularGradient(colors: [pink, lavB, lavA, pink], center: .center, angle: .degrees(200))
    }

    // Typo : grand titre heavy arrondi (Bricolage n'est pas embarquée dans l'app), le reste en SF Pro, Dynamic Type.
    static let title: Font = .system(.largeTitle, design: .rounded).weight(.heavy)
    static let name: Font = .system(.body).weight(.semibold)
    static let preview: Font = .subheadline
    static let time: Font = .footnote.monospacedDigit()
    static let label: Font = .caption.weight(.bold)

    /// Grand titre de la barre de navigation (UIKit) : arrondi, très gras, suit Dynamic Type.
    static var largeTitleUIFont: UIFont {
        let base = UIFont.preferredFont(forTextStyle: .largeTitle)
        let heavy = UIFont.systemFont(ofSize: base.pointSize, weight: .heavy)
        let rounded = heavy.fontDescriptor.withDesign(.rounded).map { UIFont(descriptor: $0, size: base.pointSize) } ?? heavy
        return UIFontMetrics(forTextStyle: .largeTitle).scaledFont(for: rounded)
    }

    /// Couleur stable d'une personne parmi les 6 des groupes (même règle que PronoAvatar).
    static func color(for id: String) -> String { PronoAvatar.color(for: id) }
}

/// Une personne : sa photo (lien signé), sinon ses initiales sur le dégradé de sa couleur.
struct NeonAvatar: View {
    let id: String
    let name: String
    var photo: String?
    var size: CGFloat = 54

    private var letters: String {
        let s = name.split(separator: " ").prefix(2).compactMap(\.first).map(String.init).joined().uppercased()
        return s.isEmpty ? "?" : s
    }

    var body: some View {
        AsyncImage(url: photo.flatMap(URL.init(string:)), transaction: Transaction(animation: Motion.pick(Motion.fade))) { phase in
            if let image = phase.image {
                image.resizable().scaledToFill().transition(.opacity)
            } else {
                Text(letters)
                    .font(.system(size: size * 0.36, weight: .bold, design: .rounded))
                    .foregroundStyle(PronoTheme.fixed(0x0E0A1F))
                    .minimumScaleFactor(0.6)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(PronoTheme.group(ChatNeon.color(for: id.isEmpty ? name : id)))
            }
        }
        .frame(width: size, height: size)
        .clipShape(Circle())
        .overlay(Circle().strokeBorder(.white.opacity(0.12), lineWidth: 1))
        .accessibilityHidden(true)
    }
}

/// Une soirée : petit calendrier (jour abrégé + numéro) sur le dégradé de sa couleur (orange par défaut).
struct NeonDateTile: View {
    let start: Date?
    var color: String? = nil
    var size: CGFloat = 54

    private var colors: (from: Color, to: Color, ink: Color) {
        switch color {
        case "mint": return (Color(hex: 0x7CEDBB), Color(hex: 0x22B07D), Color(hex: 0x062A1B))
        case "lemon": return (Color(hex: 0xFFEA9C), Color(hex: 0xFFB347), Color(hex: 0x2A1E04))
        case nil, "coral": return (Color(hex: 0xFFC977), Color(hex: 0xFF7A59), Color(hex: 0x2A1406))
        default:
            let g = GroupLook.gradient(color)
            return (g.from, g.to, Color(hex: 0x1D1530))
        }
    }

    var body: some View {
        let c = colors
        let shape = RoundedRectangle(cornerRadius: size * 0.31, style: .continuous)
        VStack(spacing: size * 0.02) {
            Text(start.map(ChatListText.weekdayShort) ?? "date")
                .font(.system(size: size * 0.185, weight: .heavy)).kerning(0.8).opacity(0.82)
            Text(start.map(ChatListText.dayNumber) ?? "?")
                .font(.system(size: size * 0.41, weight: .heavy, design: .rounded)).monospacedDigit()
        }
        .foregroundStyle(c.ink)
        .frame(width: size, height: size)
        .background(LinearGradient(colors: [c.from, c.to], startPoint: .top, endPoint: .bottomTrailing), in: shape)
        .overlay(shape.strokeBorder(.white.opacity(0.3), lineWidth: 1.5))
        .shadow(color: c.to.opacity(0.45), radius: size * 0.15, y: size * 0.06)
        .accessibilityHidden(true)
    }
}

/// Compte des non lus : rose (encre sombre) ; gris quand la discussion est en sourdine.
struct NeonCountBadge: View {
    let count: Int
    var muted = false

    var body: some View {
        Text(count > 99 ? "99+" : "\(count)")
            .font(.caption.weight(.heavy)).monospacedDigit()
            .foregroundStyle(muted ? ChatNeon.mutedInk : ChatNeon.onPink)
            .contentTransition(.numericText())
            .padding(.horizontal, 6)
            .frame(minWidth: 22, minHeight: 22)
            .background(muted ? AnyShapeStyle(ChatNeon.muted) : AnyShapeStyle(ChatNeon.pinkGradient), in: Capsule())
            .shadow(color: muted ? .clear : ChatNeon.pink.opacity(0.45), radius: 6)
    }
}

/// Rond de verre 44 pt (lune, « … »).
struct NeonCircleLabel: View {
    let systemImage: String
    var active = false

    var body: some View {
        let icon = Image(systemName: systemImage)
            .font(.system(size: 17, weight: .semibold))
            .foregroundStyle(active ? ChatNeon.coral : ChatNeon.t1)
        if #available(iOS 26.0, *) {
            icon  // iOS 26 : la barre pose déjà son verre autour des boutons (sinon deux ronds l'un dans l'autre)
        } else {
            icon
                .frame(width: 44, height: 44)
                .background(ChatNeon.glass, in: Circle())
                .overlay(Circle().strokeBorder(ChatNeon.glassLine, lineWidth: 1))
                .contentShape(Circle())
        }
    }
}

/// Lueur douce en haut de l'écran seulement (le fil reste sur fond uni).
struct NeonGlow: View {
    var body: some View {
        ZStack(alignment: .top) {
            ChatNeon.bg
            RadialGradient(colors: [ChatNeon.halo, .clear], center: UnitPoint(x: 0.15, y: 0), startRadius: 0, endRadius: 320)
            RadialGradient(colors: [ChatNeon.pink.opacity(0.10), .clear], center: UnitPoint(x: 0.95, y: 0.02), startRadius: 0, endRadius: 260)
        }
        .ignoresSafeArea()
        .accessibilityHidden(true)
    }
}

/// Barre de navigation de la liste : grand titre arrondi très gras, fond transparent au repos (la lueur passe dessous),
/// verre en défilant. Réglée sur l'écran lui-même (navigationItem), jamais sur toute l'app.
struct NeonNavigationBar: UIViewControllerRepresentable {
    func makeUIViewController(context: Context) -> Probe { Probe() }
    func updateUIViewController(_ controller: Probe, context: Context) { controller.apply() }

    final class Probe: UIViewController {
        override func didMove(toParent parent: UIViewController?) {
            super.didMove(toParent: parent)
            apply()
        }

        override func viewWillAppear(_ animated: Bool) {
            super.viewWillAppear(animated)
            apply()
        }

        func apply() {
            // L'écran posé dans la pile de navigation (le parent direct du UINavigationController).
            var screen: UIViewController? = self
            while let current = screen, let up = current.parent, !(up is UINavigationController) { screen = up }
            guard let item = screen?.navigationItem, screen?.parent is UINavigationController else { return }
            let title: [NSAttributedString.Key: Any] = [.foregroundColor: UIColor(ChatNeon.t1)]
            var large = title
            large[.font] = ChatNeon.largeTitleUIFont
            let edge = UINavigationBarAppearance()
            edge.configureWithTransparentBackground()
            edge.titleTextAttributes = title
            edge.largeTitleTextAttributes = large
            let standard = UINavigationBarAppearance()
            standard.configureWithDefaultBackground()
            standard.backgroundEffect = UIBlurEffect(style: .systemUltraThinMaterial)
            standard.titleTextAttributes = title
            standard.largeTitleTextAttributes = large
            item.scrollEdgeAppearance = edge
            item.standardAppearance = standard
            item.compactAppearance = standard
        }
    }
}

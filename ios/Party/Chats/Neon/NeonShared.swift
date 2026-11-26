import SwiftUI
import UIKit

// Jetons « Néon club » nés avec les Pronos (18.11) et repris par les Discussions, les Groupes et la modération :
// thème (PronoTheme), visages (PronoFace, PronoAvatar, PronoAvatarStack), style de bouton (PronoKitPressStyle).
// Sortis de Pronos/ (contrôle Apple du 26.11) : ce dossier n'est compilé que dans la BETA, ceux-ci partout.
// Les noms gardent leur préfixe « Prono » (identifiants de code, jamais montrés).

// MARK: - Thème

enum PronoTheme {
    private static func rgb(_ hex: UInt32, _ alpha: CGFloat) -> UIColor {
        UIColor(red: CGFloat((hex >> 16) & 0xFF) / 255, green: CGFloat((hex >> 8) & 0xFF) / 255,
                blue: CGFloat(hex & 0xFF) / 255, alpha: alpha)
    }

    /// Couleur qui suit le thème : sombre (défaut de Party) / clair.
    static func dynamic(_ dark: UInt32, _ light: UInt32, dark darkAlpha: CGFloat = 1, light lightAlpha: CGFloat = 1) -> Color {
        Color(UIColor { $0.userInterfaceStyle == .light ? rgb(light, lightAlpha) : rgb(dark, darkAlpha) })
    }

    static func fixed(_ hex: UInt32, _ alpha: CGFloat = 1) -> Color { Color(rgb(hex, alpha)) }

    // Surfaces
    static let bg = dynamic(0x0E0A1F, 0xF6F3FF)
    /// Scène du dévoilement.
    static let scene = dynamic(0x0A0718, 0xF6F3FF)
    static let s1 = dynamic(0x1A1433, 0xFFFFFF)
    static let s1b = dynamic(0x211943, 0xFBF9FF)
    /// Verre (puces, onglets, boutons ronds), à poser sur .ultraThinMaterial.
    static let glass = dynamic(0x251D47, 0xFFFFFF, dark: 0.80, light: 0.72)
    static let s3 = dynamic(0xFFFFFF, 0x1D1530, dark: 0.06, light: 0.05)
    static let line = dynamic(0xFFFFFF, 0x1D1530, dark: 0.08, light: 0.08)
    static let line2 = dynamic(0xFFFFFF, 0x1D1530, dark: 0.14, light: 0.14)
    static let halo = dynamic(0x7B6CF6, 0x7B6CF6, dark: 0.22, light: 0.10)

    // Textes (AA sur s1)
    static let t1 = dynamic(0xF4F1FF, 0x1D1530)
    static let t2 = dynamic(0xA79FC7, 0x564E78)
    static let t3 = dynamic(0x8C84AE, 0x6E6790)

    // Accents
    static let lavA = fixed(0xB9A7FF)
    static let lavB = fixed(0x7B6CF6)
    static let lavInk = dynamic(0xB9A7FF, 0x6A5AE0)
    /// Lavande d'accent (liens, réactions à moi, focus) : = lavInk.
    static let lav = lavInk
    /// Rose d'action : icônes et texte sur sombre. Jamais de texte blanc dessus.
    static let pink = fixed(0xFF4F9A)
    /// Remplissage des boutons (texte blanc 4,8:1).
    static let pinkFill = fixed(0xD42A76)
    static let pinkInk = dynamic(0xFF6FAE, 0xD42A76)
    static let mint = fixed(0x5BE3A6)
    static let mintInk = dynamic(0x5BE3A6, 0x0A7A4E)
    static let gold = fixed(0xFFE27A)
    static let goldInk = dynamic(0xFFE27A, 0x8A6200)
    /// Raté : gris neutre, jamais rouge.
    static let miss = fixed(0x8B84A8)
    static let amber = fixed(0xFFB347)
    static let amberInk = dynamic(0xFFB347, 0xB25E00)
    /// Retrait (se retirer d'un trophée, arrêter).
    static let retract = fixed(0xFF7A8A)

    // Patates
    static let patate = fixed(0xF5C27A)
    static let patateInk = dynamic(0xF5C27A, 0xA0601A)
    static let patateDeep = fixed(0xFF9F5A)
    /// Encre sur fond patate.
    static let patateOn = fixed(0x2A1A06)

    static var lavender: LinearGradient {
        LinearGradient(colors: [lavA, lavB], startPoint: .topLeading, endPoint: .bottomTrailing)
    }

    static var patateTrack: LinearGradient {
        LinearGradient(colors: [patate, patateDeep], startPoint: .leading, endPoint: .trailing)
    }

    /// Dégradé 135° d'une couleur de groupe (« sky », « mint »… ; inconnue : rose).
    static func group(_ color: String?) -> LinearGradient {
        let g = GroupLook.gradient(color)
        return LinearGradient(colors: [g.from, g.to], startPoint: .topLeading, endPoint: .bottomTrailing)
    }

    /// Les 6 couleurs des groupes (confettis, avatars sans photo).
    static let groupColors = ["pink", "coral", "mint", "sky", "lavender", "lemon"]

    enum Radius {
        static let card: CGFloat = 24
        static let inner: CGFloat = 16
        static let pill: CGFloat = 20
        static let tile: CGFloat = 14
        static let button: CGFloat = 18
        static let chip: CGFloat = 14
        static let yesNo: CGFloat = 28
    }

    enum Space {
        static let gutter: CGFloat = 16
        static let screen: CGFloat = 20
        static let cards: CGFloat = 14
        static let sections: CGFloat = 28
    }

    // Typo (polices système, Dynamic Type)
    enum QuestionSize { case compact, card, hero, display }

    /// Question : SF Rounded Heavy. compact 17, carte 22, vedette 28, affiche 34.
    static func question(_ size: QuestionSize = .card) -> Font {
        switch size {
        case .compact: return .system(.headline, design: .rounded).weight(.heavy)
        case .card: return .system(.title2, design: .rounded).weight(.heavy)
        case .hero: return .system(.title, design: .rounded).weight(.heavy)
        case .display: return .system(.largeTitle, design: .rounded).weight(.heavy)
        }
    }

    /// Grand titre d'écran (« Pronos »).
    static let title: Font = .system(.largeTitle, design: .rounded).weight(.heavy)

    /// Chiffres : SF Expanded Heavy, tabulaires.
    static func digits(_ style: Font.TextStyle = .body) -> Font {
        .system(style).weight(.heavy).width(.expanded).monospacedDigit()
    }

    /// Grands chiffres (sac 56, curseur 68, récolte 30) : taille suivie par Dynamic Type.
    static func digits(size: CGFloat) -> Font {
        .system(size: UIFontMetrics.default.scaledValue(for: size), weight: .heavy).width(.expanded).monospacedDigit()
    }

    // Mouvement
    /// Toucher, choix : ressort 0,35 / 0,7.
    static let press = Animation.spring(response: 0.35, dampingFraction: 0.7)
    /// Sceau posé : ressort 0,42 / 0,62.
    static let seal = Animation.spring(response: 0.42, dampingFraction: 0.62)
    /// Sceau qui craque (dévoilement).
    static let crack = Animation.easeOut(duration: 0.24)
    /// Apparition d'une carte : 420 ms ease-out-quint.
    static let rise = Animation.timingCurve(0.22, 1, 0.36, 1, duration: 0.42)
    /// Réduire les animations : fondu 150 ms à la place.
    static func motion(_ animation: Animation, reduced: Bool) -> Animation {
        reduced ? .easeInOut(duration: 0.15) : animation
    }
}

struct PronoFace: Codable, Hashable, Identifiable {
    let id: String
    let name: String
    /// Lien signé de la photo (ajouté par le serveur).
    var photo: String?
    var me: Bool?
    /// Trophée : voix reçues par le ou la lauréat·e (result.people).
    var votes: Int?

    var label: String { me == true ? "Toi" : name }

    /// « LB », « M » : initiales du sceau et de l'avatar sans photo.
    var initials: String {
        let letters = name.split(separator: " ").prefix(2).compactMap(\.first).map(String.init).joined().uppercased()
        return letters.isEmpty ? "?" : letters
    }
}

// MARK: - Visages

/// Visage : la vraie photo (lien signé) quand elle existe, sinon les initiales sur un dégradé stable.
struct PronoAvatar: View {
    let face: PronoFace
    var size: CGFloat = 28
    var ring: Color? = nil
    /// Petit ✓ menthe en bas à droite sur mon visage.
    var showsMe = false

    /// Couleur stable d'une personne (même au relancement) parmi les 6 couleurs des groupes.
    static func color(for id: String) -> String {
        let sum = id.unicodeScalars.reduce(UInt32(5381)) { ($0 &* 33) &+ $1.value }
        return PronoTheme.groupColors[Int(sum % UInt32(PronoTheme.groupColors.count))]
    }

    var body: some View {
        AsyncImage(url: face.photo.flatMap(URL.init(string:)), transaction: Transaction(animation: .easeInOut(duration: 0.2))) { phase in
            if let image = phase.image {
                image.resizable().scaledToFill().transition(.opacity)
            } else {
                Text(face.initials)
                    .font(.system(size: size * 0.38, weight: .heavy, design: .rounded))
                    .foregroundStyle(PronoTheme.fixed(0x1D1530))
                    .minimumScaleFactor(0.6)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(PronoTheme.group(Self.color(for: face.id)))
            }
        }
        .frame(width: size, height: size)
        .clipShape(Circle())
        .overlay { if let ring { Circle().stroke(ring, lineWidth: 2) } }
        .overlay(alignment: .bottomTrailing) {
            if showsMe && face.me == true {
                Image(systemName: "checkmark")
                    .font(.system(size: size * 0.24, weight: .black))
                    .foregroundStyle(PronoTheme.fixed(0x0E0A1F))
                    .frame(width: size * 0.46, height: size * 0.46)
                    .background(PronoTheme.mint, in: Circle())
                    .offset(x: 3, y: 3)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(face.label)
    }
}

/// Visages qui se chevauchent (le 1er au-dessus), puis « +N ».
struct PronoAvatarStack: View {
    let faces: [PronoFace]
    var extra: Int = 0
    var size: CGFloat = 28
    var ring: Color = PronoTheme.s1
    var max: Int = 4

    var body: some View {
        let shown = Array(faces.prefix(max))
        let more = extra + Swift.max(0, faces.count - shown.count)
        HStack(spacing: -size * 0.22) {
            ForEach(Array(shown.enumerated()), id: \.element.id) { i, f in
                PronoAvatar(face: f, size: size, ring: ring).zIndex(Double(shown.count - i))
            }
            if more > 0 {
                Text("+\(more)")
                    .font(.system(size: size * 0.38, weight: .heavy).monospacedDigit())
                    .foregroundStyle(PronoTheme.t1)
                    .frame(width: size, height: size)
                    .background(PronoTheme.s1b, in: Circle())
                    .overlay(Circle().stroke(ring, lineWidth: 2))
                    .overlay(Circle().inset(by: 2).stroke(PronoTheme.line2, lineWidth: 1))
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(shown.map(\.label).joined(separator: ", ") + (more > 0 ? " et \(more) autre\(more > 1 ? "s" : "")" : ""))
    }
}

// MARK: - Toucher

struct PronoKitPressStyle: ButtonStyle {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed && !reduceMotion ? 0.97 : 1)
            .animation(reduceMotion ? nil : PronoTheme.press, value: configuration.isPressed)
    }
}

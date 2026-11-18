import SwiftUI
import UIKit

// MARK: - Mode d'emploi (Pronos v2, direction C « Néon club », maquettes du 18.11.2026)
//
// Couleurs, typo, rayons : PronoTheme (sombre ET clair : chaque couleur suit le thème de l'appareil).
//   PronoTheme.bg / s1 / s1b / glass / s3 / line / line2 / t1 / t2 / t3, lavA / lavB / lavInk, pink (accents),
//   pinkFill (#D42A76, REMPLISSAGE des boutons), mint, gold, miss (raté, jamais rouge), amber, patate, patateInk.
//   PronoTheme.lavender (dégradé), PronoTheme.group("sky") (dégradé 135° d'une couleur de groupe).
//   PronoTheme.question(.card | .hero | .compact | .display), PronoTheme.title, PronoTheme.digits(.title2),
//   PronoTheme.digits(size: 56) (suit Dynamic Type), PronoTheme.Radius.card (24)…, PronoTheme.motion(_:reduced:).
//
// Vues :
//   PronoCoverBand(color: "sky", emoji: "⚽", photo: nil, height: 64, featured: false)
//   PronoCoverBand(group: prono.group, height: 236)   PronoCoverBand(card: card)   (événement : lavande + 📅)
//   PronoContextChip(emoji: "⚽", text: "Baby-foot du jeudi")             puce sombre posée sur la couverture
//   PronoKindIcon(kind: "yesno")                                          « ◐ Oui / Non » (PronoKind.label(kind))
//   PronoShapeMark(shape: .triangle, size: 14, filled: true)              ▲ ◆ ● ■ ⬢ ★ (PronoShape.at(index))
//   (couleurs de groupe = noms de la base : pink, coral, mint, sky, lavender, lemon ; inconnue : pink)
//   PronoSeal(emoji: "🦩", color: "pink", size: 30)                       sceau festonné + 🔒
//   PronoSeal(face: face, color: "pink", size: 36, me: true, broken: crack, appearDelay: 0.06 * i)
//       broken = le sceau craque (2 moitiés en zigzag s'écartent et s'effacent) et le visage apparaît dessous :
//       withAnimation(PronoTheme.motion(PronoTheme.crack, reduced:)) { crack = true }
//   PronoSealRow(faces: p.answered, total: p.players, color: "pink", emoji: "🦩", max: 6, size: 30, showsPending: true)
//   PronoAvatar(face: face, size: 40, ring: PronoTheme.s1, showsMe: true) photo signée, sinon initiales sur dégradé
//   PronoAvatarStack(faces: card.faces, extra: 3, size: 28, ring: PronoTheme.s1)
//   PronoCountdown(closesAt: p.closes /* Date? */, style: .chip | .large)   PronoCountdown(closesAt: p.closesAt /* ISO */)
//       paliers : > 24 h date calme ; 1–24 h « Dans 2 h 14 » ; < 1 h minutes ambre (point qui respire) ;
//       < 60 s anneau rose qui se vide ; fini « Fermé ». .large = rangée « Fin des réponses · Samedi, 21 h · 2 j 04 h 12 min ».
//   PatateBadge(n: 18, tone: .harvest)  (.neutral « 42 🥔 », .harvest « +18 🥔 », .compost « 5 🥔 au compost »,
//       .refund « 5 🥔 rendues », .planted « 5 🥔 plantées » ; alias .plain / .win / .lav, et .gold ;
//       large: true pour la récolte du dévoilement)
//   PronoBagChip(balance: 85, action: { … })   PronoBagChip(bag: bag)    « Ton sac : 85 🥔 »
//   PronoNoValueNote(refill: true)             rappel « aucune valeur » (sous chaque sac et chaque curseur)
//   PronoFieldLabel(total: 120, planters: 5)   « 🥔 120 dans le champ · 5 joueurs »
//   PronoChoicePill(label: "Suisse", shape: .triangle, selected: true, result: nil, style: .large) { … }
//   PronoChoicePill(index: 0, label: "Oui", selected: false, style: .large) { … }   result: .right | .wrong
//   PronoChoicePill(label: "Oui", index: 0, selected: false) { … }       (style .compact par défaut : cartes)
//   PronoGlassCard(padding: 18, radius: 24, solid: false, tint: nil) { … }
//   PronoSectionLabel("Ça ferme bientôt", trailing: "un toucher")
//   PronoPrimaryButton("Sceller ma réponse", systemImage: "lock.fill", busy: busy) { … }   (ou title: "…")
//   PronoKitPressStyle()                          style de bouton : échelle 0,97 au toucher (ressort)
//   PronoPatateSlider(value: $stake, limit: bag.plantable)   curseur 0–20 + puces Sans / 5 / 10 / 20
//   PronoHaptics.selection() / .success() / .soft() / .light() / .sealCrack() / .reveal(reduced:)
//   PronoConfetti(active: right && !unanimous, style: .party | .gold)   jamais pour un raté ni des unanimes
//   PronoSpotlight(color: PronoTheme.lavA, width: 360, height: 120, cone: true)   à placer / animer par l'écran
//   PronoBreathingDot(color:), PronoRing(fraction:), PronoSealShape(lobes:amplitude:), PronoCrackHalf(left:)
//
// Store (PronosStore.swift) : store.features.patates (await store.refreshFeatures()), store.showsPatates(prono|card),
//   bag(groupID:eventID:) -> PronoBag, bagHistory(groupID:eventID:) -> [PronoBagMove],
//   season(groupID:month: "2026-11-01"?) -> PronoSeason, contest(id:reason:), contestVote(id:fair:), react(id:emoji:),
//   optout(id:out:) -> Prono, templates() -> [PronoTemplate] ; PronosStore.reactions ; PronoFormat (time, field,
//   harvest, move, month, countdown…), PronoPatates (noValue, split, tenths), PronoKind (label, symbol), PronoTab.
//
// Tout mouvement passe par « Réduire les animations » (@Environment(\.accessibilityReduceMotion)) : fondu 150 ms,
// aucun confetti, aucune haptique rythmée. Toujours forme + couleur + texte (jamais la couleur seule). Cibles ≥ 44 pt.
// Vocabulaire : planter, le champ, ta récolte, au compost, ton sac, rendues, saison. Jamais d'argent ni de jeu d'argent.

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

// MARK: - Formes des réponses (▲ ◆ ● ■ ⬢ ★) : toujours forme + couleur + texte

enum PronoShape: Int, CaseIterable, Identifiable {
    case triangle, diamond, circle, square, hexagon, star

    var id: Int { rawValue }

    /// Forme de l'option n (on recommence après ★).
    static func at(_ index: Int) -> PronoShape { allCases[((index % allCases.count) + allCases.count) % allCases.count] }

    var glyph: String { ["▲", "◆", "●", "■", "⬢", "★"][rawValue] }
    var symbol: String { ["triangle.fill", "diamond.fill", "circle.fill", "square.fill", "hexagon.fill", "star.fill"][rawValue] }
    /// VoiceOver.
    var name: String { ["triangle", "losange", "rond", "carré", "hexagone", "étoile"][rawValue] }

    var color: Color {
        switch self {
        case .triangle: return PronoTheme.dynamic(0xFF6FAE, 0xC8327A)
        case .diamond: return PronoTheme.dynamic(0x6CC7FF, 0x1F6FD1)
        case .circle: return PronoTheme.dynamic(0xFFB347, 0xB86A00)
        case .square: return PronoTheme.dynamic(0xB9A7FF, 0x6A5AE0)
        case .hexagon: return PronoTheme.dynamic(0x5BE3A6, 0x0A7A4E)
        case .star: return PronoTheme.dynamic(0xFFE27A, 0x8A6200)
        }
    }
}

struct PronoShapeMark: View {
    let shape: PronoShape
    var size: CGFloat = 14
    var filled = true
    var color: Color? = nil

    var body: some View {
        Image(systemName: filled ? shape.symbol : shape.symbol.replacingOccurrences(of: ".fill", with: ""))
            .font(.system(size: size, weight: .bold))
            .foregroundStyle(color ?? shape.color)
            .accessibilityHidden(true)
    }
}

// MARK: - Type, couverture, puces

struct PronoKindIcon: View {
    let kind: String
    /// Sur la couverture : puce claire ; sinon : puce de verre.
    var onCover = true

    var body: some View {
        HStack(spacing: 5) {
            if kind == "award" { Text("🏆").font(.caption2) } else {
                Image(systemName: PronoKind.symbol(kind)).font(.system(size: 10, weight: .bold))
            }
            Text(PronoKind.label(kind)).font(.footnote.weight(.semibold)).lineLimit(1)
        }
        .foregroundStyle(onCover ? PronoTheme.fixed(0x1D1530) : PronoTheme.t1)
        .padding(.horizontal, 10)
        .frame(minHeight: 26)
        .background(onCover ? AnyShapeStyle(Color.white.opacity(0.92)) : AnyShapeStyle(PronoTheme.s3), in: Capsule())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Type : \(PronoKind.label(kind))")
    }
}

/// Puce sombre en verre posée sur la couverture (« ⚽ Baby-foot du jeudi »).
struct PronoContextChip: View {
    let emoji: String?
    let text: String

    var body: some View {
        HStack(spacing: 6) {
            if let emoji { Text(emoji).font(.footnote) }
            Text(text).font(.footnote.weight(.semibold)).lineLimit(1)
        }
        .foregroundStyle(.white)
        .padding(.leading, 8).padding(.trailing, 10)
        .frame(minHeight: 26)
        .background(.ultraThinMaterial.opacity(0.6), in: Capsule())
        .background(Color(red: 14 / 255, green: 10 / 255, blue: 31 / 255).opacity(0.55), in: Capsule())
        .environment(\.colorScheme, .dark)
    }
}

/// Bande de couverture : dégradé du groupe, emoji en filigrane incliné, photo du groupe si elle existe, fondu vers la
/// carte en bas. featured : le dégradé glisse lentement (vedette seulement, coupé par Réduire les animations).
struct PronoCoverBand: View {
    var color: String?
    var emoji: String?
    var photo: String?
    var height: CGFloat = 64
    var featured = false
    /// Couleur du fondu du bas (la surface de la carte).
    var fadeTo: Color = PronoTheme.s1

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var drift = false

    init(color: String?, emoji: String?, photo: String? = nil, height: CGFloat = 64, featured: Bool = false, fadeTo: Color = PronoTheme.s1) {
        self.color = color
        self.emoji = emoji
        self.photo = photo
        self.height = height
        self.featured = featured
        self.fadeTo = fadeTo
    }

    /// Couverture d'un prono de groupe ; sans groupe : lavande + 📅 (événement) ou 🔮.
    init(group: PronoGroupRef?, event: PronoEventRef? = nil, height: CGFloat = 64, featured: Bool = false, fadeTo: Color = PronoTheme.s1) {
        self.init(color: group?.color ?? "lavender", emoji: group?.emoji ?? (event != nil ? "📅" : "🔮"), photo: group?.photo,
                  height: height, featured: featured, fadeTo: fadeTo)
    }

    /// Couverture d'une carte de la liste.
    init(card: PronoCard, height: CGFloat = 64, featured: Bool = false) {
        if let cover = card.cover {
            self.init(color: cover.color, emoji: cover.emoji, photo: cover.photo, height: height, featured: featured)
        } else {
            self.init(group: card.group, event: card.event, height: height, featured: featured)
        }
    }

    private var photoURL: URL? {
        guard let photo, photo.hasPrefix("https://") || photo.hasPrefix("http://") else { return nil }
        return URL(string: photo)
    }

    var body: some View {
        let g = GroupLook.gradient(color)
        ZStack(alignment: .topTrailing) {
            LinearGradient(colors: [g.from, g.to],
                           startPoint: drift ? .top : .topLeading,
                           endPoint: drift ? .bottomTrailing : .trailing)
            if let url = photoURL {
                AsyncImage(url: url, transaction: Transaction(animation: .easeInOut(duration: 0.2))) { phase in
                    if let image = phase.image { image.resizable().scaledToFill().transition(.opacity) } else { Color.clear }
                }
                .frame(height: height).clipped()
            } else if let emoji {
                let big = min(212, max(112, height * 1.6))
                Text(emoji)
                    .font(.system(size: big))
                    .saturation(0.6)
                    .opacity(height > 120 ? 0.16 : 0.22)
                    .rotationEffect(.degrees(-14))
                    .offset(x: big * 0.12, y: -big * 0.22)
                    .accessibilityHidden(true)
            }
            LinearGradient(colors: [.clear, fadeTo], startPoint: .top, endPoint: .bottom)
                .frame(height: min(height * 0.55, 120))
                .frame(maxHeight: .infinity, alignment: .bottom)
        }
        .frame(height: height)
        .frame(maxWidth: .infinity)
        .clipped()
        .onAppear {
            guard featured, !reduceMotion else { return }
            withAnimation(.easeInOut(duration: 14).repeatForever(autoreverses: true)) { drift = true }
        }
        .accessibilityHidden(true)
    }
}

// MARK: - Sceau

/// Cercle festonné : r(θ) = R·(1 − a·(1 − cos nθ)/2).
struct PronoSealShape: Shape {
    var lobes = 12
    var amplitude: CGFloat = 0.07

    func path(in rect: CGRect) -> Path {
        let c = CGPoint(x: rect.midX, y: rect.midY)
        let radius = min(rect.width, rect.height) / 2
        let steps = lobes * 12
        var p = Path()
        for i in 0...steps {
            let t = CGFloat(i) / CGFloat(steps) * 2 * .pi
            let r = radius * (1 - amplitude * (1 - cos(CGFloat(lobes) * t)) / 2)
            let point = CGPoint(x: c.x + r * cos(t), y: c.y + r * sin(t))
            if i == 0 { p.move(to: point) } else { p.addLine(to: point) }
        }
        p.closeSubpath()
        return p
    }
}

/// Moitié gauche ou droite d'un sceau, coupée en zigzag (les deux moitiés s'emboîtent).
struct PronoCrackHalf: Shape {
    let left: Bool

    func path(in r: CGRect) -> Path {
        let zig: [CGFloat] = [0, 0.16, -0.12, 0.14, -0.16, 0.1, 0]
        let outer = left ? r.minX - r.width : r.maxX + r.width
        var p = Path()
        p.move(to: CGPoint(x: outer, y: r.minY - r.height))
        p.addLine(to: CGPoint(x: r.midX, y: r.minY - r.height))
        for (i, z) in zig.enumerated() {
            p.addLine(to: CGPoint(x: r.midX + z * r.width * 0.3, y: r.minY + r.height * CGFloat(i) / CGFloat(zig.count - 1)))
        }
        p.addLine(to: CGPoint(x: r.midX, y: r.maxY + r.height))
        p.addLine(to: CGPoint(x: outer, y: r.maxY + r.height))
        p.closeSubpath()
        return p
    }
}

/// Sceau de cire d'une réponse cachée : dégradé du groupe, emoji ou initiales, 🔒 (ou ✓ menthe pour le mien).
/// broken : il craque, ses deux moitiés s'écartent et s'effacent, le visage (face) apparaît dessous.
struct PronoSeal: View {
    var face: PronoFace? = nil
    var emoji: String? = nil
    var color: String? = nil
    var size: CGFloat = 30
    var me = false
    var locked = true
    var broken = false
    /// Apparition « sceau posé » (échelle 0,4 → 1, rotation −20° → 0) après ce délai ; nil : déjà posé.
    var appearDelay: Double? = nil

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var shown: Bool

    init(face: PronoFace? = nil, emoji: String? = nil, color: String? = nil, size: CGFloat = 30, me: Bool = false,
         locked: Bool = true, broken: Bool = false, appearDelay: Double? = nil) {
        self.face = face
        self.emoji = emoji
        self.color = color
        self.size = size
        self.me = me || face?.me == true
        self.locked = locked
        self.broken = broken
        self.appearDelay = appearDelay
        _shown = State(initialValue: appearDelay == nil)
    }

    private var ink: Color { PronoTheme.fixed(0x1D1530) }

    private var wax: some View {
        ZStack {
            PronoSealShape().fill(PronoTheme.group(color))
            Circle().inset(by: size * 0.14).stroke(ink.opacity(0.16), lineWidth: max(1, size / 20))
            if let emoji {
                Text(emoji).font(.system(size: size * 0.42))
            } else if let face {
                Text(face.initials)
                    .font(.system(size: size * 0.34, weight: .heavy, design: .rounded))
                    .foregroundStyle(me ? ink : ink.opacity(0.8))
                    .minimumScaleFactor(0.6)
            }
        }
        .frame(width: size, height: size)
    }

    var body: some View {
        let k = size / 30
        ZStack {
            if broken, let face {
                PronoAvatar(face: face, size: size)
                    .transition(.scale(scale: 0.5).combined(with: .opacity))
            }
            wax.clipShape(PronoCrackHalf(left: true))
                .offset(x: broken ? -7 * k : 0)
                .rotationEffect(.degrees(broken ? -28 : 0))
                .opacity(broken ? 0 : 1)
            wax.clipShape(PronoCrackHalf(left: false))
                .offset(x: broken ? 7 * k : 0)
                .rotationEffect(.degrees(broken ? 28 : 0))
                .opacity(broken ? 0 : 1)
        }
        .frame(width: size, height: size)
        .overlay(alignment: .bottomTrailing) {
            if !broken && (locked || me) {
                Image(systemName: me ? "checkmark" : "lock.fill")
                    .font(.system(size: size * 0.2, weight: .black))
                    .foregroundStyle(me ? ink : PronoTheme.gold)
                    .frame(width: size * 0.42, height: size * 0.42)
                    .background(me ? PronoTheme.mint : PronoTheme.fixed(0x0E0A1F), in: Circle())
                    .offset(x: 2 * k, y: 2 * k)
                    .transition(.opacity)
            }
        }
        .shadow(color: me && !broken ? GroupLook.gradient(color).to.opacity(0.7) : .clear, radius: 8)
        .scaleEffect(shown ? 1 : 0.4)
        .rotationEffect(.degrees(shown ? 0 : -20))
        .opacity(shown ? 1 : 0)
        .onAppear {
            guard !shown else { return }
            if reduceMotion { shown = true; return }
            withAnimation(PronoTheme.seal.delay(appearDelay ?? 0)) { shown = true }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(broken ? (face?.label ?? "Réponse dévoilée") : (me ? "Ta réponse, scellée" : "Réponse scellée"))
    }
}

/// Rangée de sceaux : ceux qui ont joué (initiales seulement, jamais leur réponse), puis « +N ».
/// showsPending : « · 3 pas encore » (le nombre seulement, jamais de nom).
struct PronoSealRow: View {
    let faces: [PronoFace]
    var total: Int? = nil
    var color: String? = nil
    var emoji: String? = nil
    var max: Int = 6
    var size: CGFloat = 30
    var showsPending = false
    /// Sceaux posés un à un à l'apparition (60 ms d'écart).
    var animated = true

    var body: some View {
        let shown = Array(faces.prefix(max))
        let extra = faces.count - shown.count
        let pending = Swift.max(0, (total ?? faces.count) - faces.count)
        HStack(spacing: 5) {
            ForEach(Array(shown.enumerated()), id: \.element.id) { i, f in
                PronoSeal(face: emoji == nil ? f : nil, emoji: emoji, color: color, size: size, me: f.me == true,
                          appearDelay: animated ? 0.06 * Double(i) : nil)
            }
            if extra > 0 {
                Text("+\(extra)").font(PronoTheme.digits(.footnote)).foregroundStyle(PronoTheme.t2).padding(.leading, 4)
            }
            if showsPending && pending > 0 {
                Text("· \(pending) pas encore").font(.footnote.weight(.medium)).foregroundStyle(PronoTheme.t3)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(faces.count > 1 ? "\(faces.count) réponses scellées" : "\(faces.count) réponse scellée"
                            + (showsPending && pending > 0 ? ", \(pending) pas encore" : ""))
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

// MARK: - Compte à rebours

struct PronoCountdown: View {
    enum Style { case chip, large }

    let closesAt: Date?
    var style: Style = .chip

    init(closesAt: Date?, style: Style = .chip) {
        self.closesAt = closesAt
        self.style = style
    }

    init(iso: String, style: Style = .chip) {
        self.init(closesAt: PronoFormat.date(iso), style: style)
    }

    /// closes_at tel que la base le renvoie.
    init(closesAt iso: String, style: Style = .chip) {
        self.init(closesAt: PronoFormat.date(iso), style: style)
    }

    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        if let closesAt {
            TimelineView(.periodic(from: .now, by: 1)) { context in
                switch style {
                case .chip: chip(closesAt, now: context.date)
                case .large: large(closesAt, now: context.date)
                }
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(PronoFormat.countdownSpoken(until: closesAt))
        }
    }

    private func chip(_ end: Date, now: Date) -> some View {
        let tier = PronoFormat.tier(until: end, now: now)
        let text = PronoFormat.countdown(until: end, now: now)
        let tone: Color = tier == .soon ? PronoTheme.amberInk : tier == .last ? PronoTheme.pinkInk : PronoTheme.t2
        let fill: Color = tier == .soon ? PronoTheme.amber.opacity(0.14) : tier == .last ? PronoTheme.pink.opacity(0.14) : PronoTheme.s3
        let stroke: Color = tier == .soon ? PronoTheme.amber.opacity(0.35) : tier == .last ? PronoTheme.pink.opacity(0.4) : PronoTheme.line2
        return HStack(spacing: 7) {
            switch tier {
            case .later: Image(systemName: "calendar").font(.system(size: 13, weight: .semibold))
            case .today: Image(systemName: "clock").font(.system(size: 13, weight: .semibold))
            case .soon: PronoBreathingDot(color: PronoTheme.amber)
            case .last: PronoRing(fraction: max(0, end.timeIntervalSince(now)) / 60).frame(width: 22, height: 22)
            case .over: Image(systemName: "lock.fill").font(.system(size: 12, weight: .semibold))
            }
            Text(text)
                .font(tier == .later ? .footnote.weight(.bold) : PronoTheme.digits(.footnote))
                .contentTransition(.numericText(countsDown: true))
                .animation(reduceMotion ? nil : Motion.snappy, value: text)
                .lineLimit(1)
        }
        .foregroundStyle(tone)
        .padding(.leading, tier == .last ? 6 : 10).padding(.trailing, 12)
        .frame(minHeight: 32)
        .background(fill, in: Capsule())
        .overlay(Capsule().stroke(stroke, lineWidth: 1))
    }

    private func large(_ end: Date, now: Date) -> some View {
        let tier = PronoFormat.tier(until: end, now: now)
        let tone: Color = tier == .soon ? PronoTheme.amberInk : tier == .last ? PronoTheme.pinkInk : PronoTheme.t1
        return HStack(spacing: 12) {
            Group {
                if tier == .last {
                    PronoRing(fraction: max(0, end.timeIntervalSince(now)) / 60).frame(width: 26, height: 26)
                } else {
                    Image(systemName: "clock").font(.system(size: 20, weight: .semibold)).foregroundStyle(PronoTheme.lavInk)
                }
            }
            .frame(width: 44, height: 44)
            .background(PronoTheme.lavA.opacity(0.16), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            VStack(alignment: .leading, spacing: 1) {
                Text(tier == .over ? "Réponses fermées" : "Fin des réponses").font(.footnote.weight(.semibold)).foregroundStyle(PronoTheme.t2)
                Text(PronoKitFormat.endLabel(end)).font(.subheadline.weight(.bold)).foregroundStyle(PronoTheme.t1)
            }
            Spacer(minLength: 8)
            if tier != .over {
                HStack(alignment: .firstTextBaseline, spacing: 3) {
                    ForEach(Array(PronoFormat.countdownParts(until: end, now: now).enumerated()), id: \.offset) { _, part in
                        Text(part.value).font(PronoTheme.digits(.title2)).foregroundStyle(tone)
                            .contentTransition(.numericText(countsDown: true))
                        Text(part.unit).font(.caption.weight(.semibold)).foregroundStyle(PronoTheme.t2).padding(.trailing, 4)
                    }
                }
                .animation(reduceMotion ? nil : Motion.snappy, value: PronoFormat.countdown(until: end, now: now))
                .lineLimit(1).minimumScaleFactor(0.7)
            }
        }
    }
}

enum PronoKitFormat {
    /// « Samedi, 21 h » / « Samedi, 21 h 30 » (heure de Suisse).
    static func endLabel(_ d: Date) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "fr_CH")
        f.timeZone = TimeZone(identifier: "Europe/Zurich")
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = f.timeZone
        f.dateFormat = cal.component(.minute, from: d) == 0 ? "EEEE, H 'h'" : "EEEE, H 'h' mm"
        let s = f.string(from: d)
        return s.prefix(1).uppercased() + s.dropFirst()
    }
}

/// Point qui respire (< 1 h) : opacité 1 → 0,35, 1,6 s ; fixe avec Réduire les animations.
struct PronoBreathingDot: View {
    var color: Color = PronoTheme.amber
    var size: CGFloat = 7
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var dim = false

    var body: some View {
        Circle().fill(color).frame(width: size, height: size)
            .opacity(dim ? 0.35 : 1)
            .onAppear {
                guard !reduceMotion else { return }
                withAnimation(.easeInOut(duration: 1.6).repeatForever(autoreverses: true)) { dim = true }
            }
            .accessibilityHidden(true)
    }
}

/// Anneau rose qui se vide (dernière minute).
struct PronoRing: View {
    let fraction: Double
    var color: Color = PronoTheme.pink

    var body: some View {
        ZStack {
            Circle().stroke(color.opacity(0.22), lineWidth: 3)
            Circle().trim(from: 0, to: min(1, max(0, fraction)))
                .stroke(color, style: StrokeStyle(lineWidth: 3, lineCap: .round))
                .rotationEffect(.degrees(-90))
                .animation(.linear(duration: 1), value: fraction)
        }
        .accessibilityHidden(true)
    }
}

// MARK: - Patates

struct PatateBadge: View {
    /// .plain = .neutral, .win = .harvest, .lav = .refund ; .gold : « 42 🥔 » en or.
    enum Tone { case neutral, harvest, compost, refund, planted, plain, win, lav, gold }

    let n: Int
    var tone: Tone = .neutral
    var large = false

    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private var text: String {
        switch tone {
        case .neutral, .plain, .gold: return "\(n) 🥔"
        case .harvest, .win: return "+\(n) 🥔"
        case .compost: return "\(n) 🥔 au compost"
        case .refund, .lav: return "\(n) 🥔 rendues"
        case .planted: return "\(n) 🥔 plantées"
        }
    }

    private var color: Color {
        switch tone {
        case .neutral, .plain: return PronoTheme.patateInk
        case .harvest, .win: return PronoTheme.mintInk
        case .compost: return PronoTheme.miss
        case .refund, .lav: return PronoTheme.lavInk
        case .planted: return PronoTheme.t2
        case .gold: return PronoTheme.goldInk
        }
    }

    private var spoken: String {
        let p = n > 1 ? "patates" : "patate"
        switch tone {
        case .neutral, .plain, .gold: return "\(n) \(p)"
        case .harvest, .win: return "Ta récolte : \(n) \(p)"
        case .compost: return "\(n) \(p) au compost"
        case .refund, .lav: return "\(n) \(p) rendue\(n > 1 ? "s" : "")"
        case .planted: return "\(n) \(p) plantée\(n > 1 ? "s" : "")"
        }
    }

    var body: some View {
        Text(text)
            .font(large ? PronoTheme.digits(size: 30) : PronoTheme.digits(.subheadline))
            .foregroundStyle(color)
            .contentTransition(.numericText(countsDown: false))
            .animation(reduceMotion ? nil : Motion.snappy, value: n)
            .lineLimit(1)
            .accessibilityLabel(spoken)
    }
}

/// « Ton sac : 85 🥔 » : capsule patate. action : ouvrir le sac (haptique .soft).
struct PronoBagChip: View {
    let balance: Int
    var action: (() -> Void)? = nil

    init(balance: Int, action: (() -> Void)? = nil) {
        self.balance = balance
        self.action = action
    }

    init(bag: PronoBag, action: (() -> Void)? = nil) {
        self.init(balance: bag.balance, action: action)
    }

    private var label: some View {
        HStack(spacing: 4) {
            Text("Ton sac :").font(.subheadline.weight(.semibold))
            Text("\(balance)").font(PronoTheme.digits(.subheadline))
            Text("🥔").font(.subheadline)
        }
        .foregroundStyle(PronoTheme.patateInk)
        .padding(.horizontal, 14)
        .frame(minHeight: 34)
        .background(PronoTheme.patate.opacity(0.12), in: Capsule())
        .overlay(Capsule().stroke(PronoTheme.patate.opacity(0.45), lineWidth: 1))
    }

    var body: some View {
        Group {
            if let action {
                Button { PronoHaptics.soft(); action() } label: { label }
                    .buttonStyle(PronoKitPressStyle())
                    .frame(minHeight: 44)
            } else {
                label
            }
        }
        .accessibilityLabel("Ton sac : \(balance) patate\(balance > 1 ? "s" : "")")
    }
}

/// Rappel obligatoire sous chaque sac et chaque curseur.
struct PronoNoValueNote: View {
    var refill = false

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 8) {
            Image(systemName: "info.circle").font(.footnote).foregroundStyle(PronoTheme.t3).accessibilityHidden(true)
            Text(PronoPatates.noValue + (refill ? " " + PronoPatates.refillNote : ""))
                .font(.footnote).foregroundStyle(PronoTheme.t3)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
    }
}

/// « 🥔 120 dans le champ · 5 joueurs » : jamais de multiplicateur ni de chance avant le dévoilement.
struct PronoFieldLabel: View {
    let total: Int
    let planters: Int

    var body: some View {
        HStack(spacing: 6) {
            Text("🥔").font(.footnote)
            Text("\(total)").font(PronoTheme.digits(.footnote)).foregroundStyle(PronoTheme.t1)
            Text("dans le champ · \(planters) \(planters > 1 ? "joueurs" : "joueur")").font(.footnote.weight(.medium))
        }
        .foregroundStyle(PronoTheme.t2)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(PronoFormat.field(total: total, planters: planters).replacingOccurrences(of: "🥔", with: "patates"))
    }
}

/// Curseur 0–20 (au pas de 1) + puces Sans / 5 / 10 / 20. limit : jamais plus que le sac.
/// .impact(.soft) tous les 5 crans et sur une puce, .selection entre les deux.
struct PronoPatateSlider: View {
    @Binding var value: Int
    var limit: Int = PronoPatates.maxStake
    var showsChips = true

    let maxValue = PronoPatates.maxStake
    let thumb: CGFloat = 40

    private func set(_ v: Int) {
        let clamped = min(max(0, v), min(limit, maxValue))
        guard clamped != value else { return }
        if clamped % 5 == 0 { PronoHaptics.soft() } else { PronoHaptics.selection() }
        value = clamped
    }

    var body: some View {
        VStack(spacing: 10) {
            GeometryReader { geo in
                let usable = max(1, geo.size.width - thumb)
                let x = usable * CGFloat(value) / CGFloat(maxValue)
                let cap = usable * CGFloat(min(limit, maxValue)) / CGFloat(maxValue)
                ZStack(alignment: .leading) {
                    Capsule().fill(PronoTheme.s3).frame(height: 10).padding(.horizontal, thumb / 2)
                    if limit < maxValue {
                        Capsule().fill(PronoTheme.line).frame(width: max(0, usable - cap), height: 10)
                            .offset(x: thumb / 2 + cap)
                    }
                    Capsule().fill(PronoTheme.patateTrack).frame(width: x + 1, height: 10).offset(x: thumb / 2)
                    Circle()
                        .fill(PronoTheme.fixed(0xFFF4E0))
                        .overlay(Text("🥔").font(.system(size: 20)))
                        .frame(width: thumb, height: thumb)
                        .shadow(color: PronoTheme.patate.opacity(0.3), radius: 8)
                        .offset(x: x)
                }
                .frame(height: 44)
                .contentShape(Rectangle())
                .gesture(DragGesture(minimumDistance: 0).onChanged { g in
                    set(Int(((g.location.x - thumb / 2) / usable * CGFloat(maxValue)).rounded()))
                })
            }
            .frame(height: 44)
            .accessibilityElement()
            .accessibilityLabel("Patates à planter")
            .accessibilityValue(value == 0 ? "Sans patates" : "\(value) patate\(value > 1 ? "s" : "")")
            .accessibilityAdjustableAction { direction in
                switch direction {
                case .increment: set(value + 1)
                case .decrement: set(value - 1)
                @unknown default: break
                }
            }
            HStack {
                ForEach([0, 5, 10, 15, 20], id: \.self) { n in
                    Text("\(n)").font(PronoTheme.digits(.caption)).foregroundStyle(PronoTheme.t3)
                    if n != 20 { Spacer() }
                }
            }
            .padding(.horizontal, thumb / 2 - 6)
            .accessibilityHidden(true)
            if showsChips {
                HStack(spacing: 8) {
                    ForEach([0, 5, 10, 20], id: \.self) { n in
                        let on = value == n
                        Button {
                            guard value != n else { return }
                            PronoHaptics.soft()
                            value = n
                        } label: {
                            Text(n == 0 ? "Sans" : "\(n)")
                                .font(n == 0 ? .body.weight(.bold) : PronoTheme.digits(.body))
                                .foregroundStyle(on ? PronoTheme.patateOn : PronoTheme.t1)
                                .frame(maxWidth: .infinity, minHeight: 44)
                                .background(on ? AnyShapeStyle(PronoTheme.patate) : AnyShapeStyle(PronoTheme.s3),
                                            in: RoundedRectangle(cornerRadius: PronoTheme.Radius.chip, style: .continuous))
                        }
                        .buttonStyle(PronoKitPressStyle())
                        .disabled(n > limit)
                        .opacity(n > limit ? 0.4 : 1)
                        .accessibilityLabel(n == 0 ? "Sans patates" : "\(n) patates")
                        .accessibilityAddTraits(on ? .isSelected : [])
                    }
                }
            }
        }
    }
}

// MARK: - Réponses

/// Pastille de réponse : forme + couleur DE LA FORME + texte. large : 64 pt (fiche) ; compact : 44 pt (cartes).
struct PronoChoicePill: View {
    enum Style { case large, compact }
    enum Result { case right, wrong }

    let label: String
    let shape: PronoShape
    var selected = false
    var result: Result? = nil
    var style: Style = .large
    let action: () -> Void

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.isEnabled) private var isEnabled

    init(label: String, shape: PronoShape, selected: Bool = false, result: Result? = nil, style: Style = .large,
         action: @escaping () -> Void) {
        self.label = label
        self.shape = shape
        self.selected = selected
        self.result = result
        self.style = style
        self.action = action
    }

    init(index: Int, label: String, selected: Bool = false, result: Result? = nil, style: Style = .large,
         action: @escaping () -> Void) {
        self.init(label: label, shape: PronoShape.at(index), selected: selected, result: result, style: style, action: action)
    }

    /// Ordre des listes (I2) : forme d'après l'index, pastille compacte par défaut.
    init(label: String, index: Int, selected: Bool = false, result: Result? = nil, style: Style = .compact,
         action: @escaping () -> Void) {
        self.init(label: label, shape: PronoShape.at(index), selected: selected, result: result, style: style, action: action)
    }

    private var tint: Color { result == .right ? PronoTheme.mint : result == .wrong ? PronoTheme.miss : shape.color }
    private var radius: CGFloat { style == .large ? PronoTheme.Radius.pill : PronoTheme.Radius.chip }

    var body: some View {
        Button {
            PronoHaptics.selection()
            action()
        } label: {
            Group {
                if style == .large { large } else { compact }
            }
            .background {
                let r = RoundedRectangle(cornerRadius: radius, style: .continuous)
                if selected || result == .right {
                    r.fill(LinearGradient(colors: [tint.opacity(0.22), tint.opacity(0.06)], startPoint: .leading, endPoint: .trailing))
                } else {
                    r.fill(PronoTheme.s3)
                }
            }
            .overlay(RoundedRectangle(cornerRadius: radius, style: .continuous)
                .strokeBorder(selected || result == .right ? tint : PronoTheme.line2, lineWidth: selected || result == .right ? 1.5 : 1))
            .shadow(color: selected && !reduceMotion ? tint.opacity(0.3) : .clear, radius: 17)
            .opacity(result == .wrong ? 0.55 : 1)
            .scaleEffect(result == .right && !reduceMotion ? 1.03 : 1)
            .animation(PronoTheme.motion(PronoTheme.press, reduced: reduceMotion), value: selected)
            .animation(PronoTheme.motion(PronoTheme.press, reduced: reduceMotion), value: result)
        }
        .buttonStyle(PronoKitPressStyle())
        .accessibilityLabel(label + (result == .right ? ", bonne réponse" : ""))
        .accessibilityHint("Forme : \(shape.name)")
        .accessibilityAddTraits(selected ? .isSelected : [])
    }

    private var large: some View {
        HStack(spacing: 14) {
            PronoShapeMark(shape: shape, size: 18, color: selected ? PronoTheme.fixed(0x1D1530) : tint)
                .frame(width: 44, height: 44)
                .background(selected ? AnyShapeStyle(tint) : AnyShapeStyle(tint.opacity(0.16)),
                            in: RoundedRectangle(cornerRadius: PronoTheme.Radius.tile, style: .continuous))
            Text(label)
                .font(.system(.title3, design: .rounded).weight(.bold))
                .foregroundStyle(PronoTheme.t1)
                .multilineTextAlignment(.leading)
                .frame(maxWidth: .infinity, alignment: .leading)
            Group {
                if result == .right {
                    Text("✓ Bonne réponse").font(.caption.weight(.heavy)).foregroundStyle(PronoTheme.mintInk)
                } else if selected {
                    Image(systemName: "checkmark").font(.system(size: 13, weight: .black)).foregroundStyle(PronoTheme.fixed(0x1D1530))
                        .frame(width: 26, height: 26).background(tint, in: Circle())
                } else if result == nil {
                    Circle().strokeBorder(PronoTheme.t3, lineWidth: 2).frame(width: 26, height: 26)
                }
            }
            .accessibilityHidden(true)
        }
        .padding(.horizontal, 10).padding(.trailing, 6)
        .frame(minHeight: 64)
    }

    private var compact: some View {
        HStack(spacing: 8) {
            if result == .right {
                Image(systemName: "checkmark").font(.system(size: 13, weight: .black)).foregroundStyle(PronoTheme.mintInk)
            } else {
                PronoShapeMark(shape: shape, size: 11, color: tint)
            }
            Text(label).font(.body.weight(.semibold)).foregroundStyle(selected ? tint : PronoTheme.t1).lineLimit(1)
        }
        .padding(.horizontal, 12)
        .frame(maxWidth: .infinity, minHeight: 44)
    }
}

// MARK: - Cartes, étiquettes, boutons

struct PronoGlassCard<Content: View>: View {
    var padding: CGFloat = 18
    var radius: CGFloat = PronoTheme.Radius.card
    /// Carte pleine (s1 + ombre) au lieu du verre.
    var solid = false
    /// Filet coloré (sinon le filet discret).
    var tint: Color? = nil
    let content: Content

    init(padding: CGFloat = 18, radius: CGFloat = PronoTheme.Radius.card, solid: Bool = false, tint: Color? = nil,
         @ViewBuilder content: () -> Content) {
        self.padding = padding
        self.radius = radius
        self.solid = solid
        self.tint = tint
        self.content = content()
    }

    var body: some View {
        let shape = RoundedRectangle(cornerRadius: radius, style: .continuous)
        content
            .padding(padding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background {
                if solid {
                    shape.fill(PronoTheme.s1)
                } else {
                    shape.fill(.ultraThinMaterial).overlay(shape.fill(PronoTheme.s3))
                }
            }
            .overlay(shape.strokeBorder(tint ?? PronoTheme.line, lineWidth: 1))
            .shadow(color: solid ? .black.opacity(0.35) : .clear, radius: 20, y: 12)
    }
}

/// Étiquette de section : CAPITALES 11 pt gras, +0,08 em ; à droite, une aide discrète.
struct PronoSectionLabel: View {
    let text: String
    var trailing: String? = nil

    init(_ text: String, trailing: String? = nil) {
        self.text = text
        self.trailing = trailing
    }

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(text.uppercased())
                .font(.caption2.weight(.bold))
                .tracking(0.9)
                .foregroundStyle(PronoTheme.t2)
                .accessibilityAddTraits(.isHeader)
            Spacer(minLength: 8)
            if let trailing { Text(trailing).font(.footnote).foregroundStyle(PronoTheme.t3) }
        }
    }
}

/// Bouton principal : remplissage #D42A76 (texte blanc), 58 pt, rayon 18.
struct PronoPrimaryButton: View {
    let title: String
    var systemImage: String? = nil
    var busy = false
    let action: () -> Void

    @Environment(\.isEnabled) private var isEnabled

    init(_ title: String, systemImage: String? = nil, busy: Bool = false, action: @escaping () -> Void) {
        self.title = title
        self.systemImage = systemImage
        self.busy = busy
        self.action = action
    }

    init(title: String, systemImage: String? = nil, busy: Bool = false, action: @escaping () -> Void) {
        self.init(title, systemImage: systemImage, busy: busy, action: action)
    }

    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                if busy {
                    ProgressView().tint(.white)
                } else if let systemImage {
                    Image(systemName: systemImage).font(.system(size: 17, weight: .bold))
                }
                Text(title).font(.system(.title3, design: .rounded).weight(.heavy)).lineLimit(1).minimumScaleFactor(0.8)
            }
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity, minHeight: 58)
            .background(LinearGradient(colors: [PronoTheme.fixed(0xE2397F), PronoTheme.pinkFill, PronoTheme.fixed(0xBC1F66)],
                                       startPoint: .top, endPoint: .bottom),
                        in: RoundedRectangle(cornerRadius: PronoTheme.Radius.button, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: PronoTheme.Radius.button, style: .continuous)
                .strokeBorder(.white.opacity(0.18), lineWidth: 1))
            .shadow(color: PronoTheme.pink.opacity(isEnabled ? 0.45 : 0), radius: 16, y: 10)
            .opacity(isEnabled ? 1 : 0.45)
        }
        .buttonStyle(PronoKitPressStyle())
        .disabled(busy)
        .accessibilityLabel(title)
    }
}

/// Échelle 0,97 pendant l'appui, retour au ressort (rien avec Réduire les animations).
struct PronoKitPressStyle: ButtonStyle {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed && !reduceMotion ? 0.97 : 1)
            .animation(reduceMotion ? nil : PronoTheme.press, value: configuration.isPressed)
    }
}

// MARK: - Haptique (iPhone seulement)

enum PronoHaptics {
    /// Changer de réponse, puce, onglet, cran de molette.
    static func selection() { UISelectionFeedbackGenerator().selectionChanged() }
    /// Réponse scellée, bonne réponse dévoilée.
    static func success() { UINotificationFeedbackGenerator().notificationOccurred(.success) }
    /// Patate posée (puce, cran de 5), ouvrir le sac, bandeau « LE RÉSULTAT ».
    static func soft() { UIImpactFeedbackGenerator(style: .soft).impactOccurred() }
    /// Réaction.
    static func light() { UIImpactFeedbackGenerator(style: .light).impactOccurred() }
    /// Un sceau qui craque (8 au plus).
    static func sealCrack() { UIImpactFeedbackGenerator(style: .light).impactOccurred(intensity: 0.5) }
    /// Temps mort du dévoilement : « lub-dub » ×2 (650/760, 880/990 ms après l'appel moins 650). Rien si réduit.
    static func reveal(reduced: Bool) {
        guard !reduced else { return }
        let soft = UIImpactFeedbackGenerator(style: .soft)
        soft.prepare()
        for (delay, intensity) in [(0.0, 0.55), (0.11, 0.35), (0.23, 0.55), (0.34, 0.35)] {
            DispatchQueue.main.asyncAfter(deadline: .now() + delay) { soft.impactOccurred(intensity: intensity) }
        }
    }
}

// MARK: - Confettis et projecteur

/// Confettis : une seule salve (90 morceaux, 1,2 s) quand `active` passe à vrai. Jamais pour un raté ni des unanimes ;
/// rien avec Réduire les animations. .gold : paillettes dorées (trophée).
struct PronoConfetti: View {
    enum Style { case party, gold }

    var active: Bool
    var style: Style = .party
    var count = 90
    var duration = 1.2

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var start: Date?

    private var colors: [Color] {
        switch style {
        case .party: return PronoTheme.groupColors.flatMap { let g = GroupLook.gradient($0); return [g.from, g.to] }
        case .gold: return [PronoTheme.gold, PronoTheme.fixed(0xFFD34D), PronoTheme.fixed(0xFFF4C2), PronoTheme.amber]
        }
    }

    var body: some View {
        ZStack {
            if let start, !reduceMotion {
                TimelineView(.animation) { context in
                    let t = context.date.timeIntervalSince(start)
                    Canvas { gc, size in
                        guard t < duration else { return }
                        draw(&gc, size: size, t: t)
                    }
                }
            }
        }
        .allowsHitTesting(false)
        .accessibilityHidden(true)
        .onAppear { if active { fire() } }
        .onChange(of: active) { on in if on { fire() } }
    }

    private func fire() {
        guard !reduceMotion else { return }
        let now = Date()
        start = now
        DispatchQueue.main.asyncAfter(deadline: .now() + duration + 0.1) { if start == now { start = nil } }
    }

    private func draw(_ gc: inout GraphicsContext, size: CGSize, t: Double) {
        var seed: UInt64 = 0x9E3779B97F4A7C15
        func rnd() -> Double {
            seed = seed &* 6364136223846793005 &+ 1442695040888963407
            return Double(seed >> 33) / Double(1 << 31)
        }
        let palette = colors
        let fade = t > duration * 0.7 ? 1 - (t - duration * 0.7) / (duration * 0.3) : 1
        for i in 0..<count {
            let x0 = size.width * (0.5 + (rnd() - 0.5) * 0.3)
            let y0 = size.height * 0.38
            let vx = (rnd() - 0.5) * size.width * 1.4
            let vy = -(300 + rnd() * 420)
            let spin = (rnd() - 0.5) * 12
            let w = style == .gold ? 4 + rnd() * 3 : 5 + rnd() * 4
            let h = style == .gold ? w : 8 + rnd() * 6
            let x = x0 + vx * t
            let y = y0 + vy * t + 0.5 * 1100 * t * t
            var piece = gc
            piece.opacity = fade
            piece.translateBy(x: x, y: y)
            piece.rotate(by: .radians(spin * t + Double(i)))
            let rect = CGRect(x: -w / 2, y: -h / 2, width: w, height: h)
            let path = style == .gold ? Path(ellipseIn: rect) : Path(roundedRect: rect, cornerRadius: 1.5)
            piece.fill(path, with: .color(palette[i % palette.count]))
        }
    }
}

/// Projecteur du dévoilement : ellipse de lumière (et cône depuis le haut). L'écran le place et l'anime.
struct PronoSpotlight: View {
    var color: Color = PronoTheme.lavA
    var width: CGFloat = 360
    var height: CGFloat = 120
    var cone = true
    var coneHeight: CGFloat = 320

    var body: some View {
        ZStack(alignment: .bottom) {
            if cone {
                PronoCone()
                    .fill(LinearGradient(colors: [color.opacity(0.0), color.opacity(0.18)], startPoint: .top, endPoint: .bottom))
                    .frame(width: width, height: coneHeight)
                    .offset(y: -height / 2)
            }
            Ellipse()
                .fill(RadialGradient(colors: [color.opacity(0.35), color.opacity(0)], center: .center, startRadius: 0, endRadius: width / 2))
                .frame(width: width, height: height)
        }
        .blendMode(.screen)
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }
}

private struct PronoCone: Shape {
    func path(in r: CGRect) -> Path {
        var p = Path()
        p.move(to: CGPoint(x: r.midX - 12, y: r.minY))
        p.addLine(to: CGPoint(x: r.midX + 12, y: r.minY))
        p.addLine(to: CGPoint(x: r.maxX, y: r.maxY))
        p.addLine(to: CGPoint(x: r.minX, y: r.maxY))
        p.closeSubpath()
        return p
    }
}

// MARK: - Commodités (noms utilisés par la fiche et le dévoilement, I3)

extension PronoCountdown {
    /// Date sûre : la carte complète (style .large, 3 paliers). Puce : PronoCountdown(closesAt: date, style: .chip).
    init(closesAt: Date) {
        self.init(closesAt: Optional(closesAt), style: .large)
    }
}

extension PronoPatateSlider {
    /// Curseur seul (la fiche dessine ses propres puces Sans / 5 / 10 / 20) ; maximum : jamais plus que le sac.
    init(value: Binding<Int>, maximum: Int) {
        self.init(value: value, limit: maximum, showsChips: false)
    }
}

extension PronoChoicePill {
    /// Grande pastille de la fiche ; forme et couleur d'après l'index de l'option.
    init(label: String, shape index: Int, selected: Bool, action: @escaping () -> Void) {
        self.init(label: label, shape: PronoShape.at(index), selected: selected, style: .large, action: action)
    }
}

extension PronoConfetti {
    /// Une salve à l'apparition.
    init() {
        self.init(active: true)
    }
}

extension PronoHaptics {
    /// « lub-dub » ×2 ; rien avec Réduire les animations.
    static func reveal() { reveal(reduced: Motion.reduced) }
}

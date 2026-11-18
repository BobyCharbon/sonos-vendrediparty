import SwiftUI

// Pronos v2 (18.11.2026, direction C « Néon club », maquettes 1-* et 4-classement) : « Mes pronos », page Pronos d'un
// groupe, classement de la saison, sac. Les patates n'ont aucune valeur (conformité 🔴) : rappel sous chaque sac ;
// tout ce qui touche aux patates est caché si la base (`patates_on`) ou le site (`features.patates`) les éteint.
// Vocabulaire : planter, le champ, ta récolte, au compost, ton sac, rendues, saison — jamais d'autre mot.

/// Couleurs des Pronos v1, gardées pour les écrans qui s'en servent encore (fiche, création).
enum PronoLook {
    static let lavender = Color(hex: 0xB9A7FF)
    static let lemon = Color(hex: 0xFFE27A)
    static let mint = Color(hex: 0x5BE3A6)
    static let coral = Color(hex: 0xFFB347)
    static let accent = Color(hex: 0xFF4F9A)
    static let action = Color(hex: 0xD42A76)
    static let surface = Color(hex: 0x221A3D)
    static let surface2 = Color(hex: 0x2C2350)
}

/// Visages qui se chevauchent (qui a joué, les gagnants).
struct PronoFaces: View {
    let faces: [PronoFace]
    var size: CGFloat = 26

    var body: some View {
        HStack(spacing: -size * 0.3) {
            ForEach(faces) { f in
                Initials(name: f.name, photo: f.photo, size: size)
                    .overlay(Circle().stroke(AppConfig.background, lineWidth: 2))
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(faces.map(\.label).joined(separator: ", "))
    }
}

struct PronoChip: View {
    let text: String
    let tone: Color
    var filled = false

    var body: some View {
        Text(text)
            .font(.caption.weight(.bold))
            .foregroundStyle(filled ? .white : tone)
            .padding(.horizontal, 9).padding(.vertical, 4)
            .background(filled ? AnyShapeStyle(PronoLook.action) : AnyShapeStyle(tone.opacity(0.16)), in: Capsule())
    }
}

/// « Pour l'honneur » : des points au classement du groupe, rien d'autre.
struct PronoHonour: View {
    let points: Int?

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Text("🏅").accessibilityHidden(true)
            (Text("Pour l'honneur. ").bold().foregroundColor(PronoTheme.t1)
             + Text(points.map { "Une bonne réponse = \(PronoFormat.points($0)) au classement du groupe." } ?? "Des points au classement du groupe, rien d'autre."))
                .font(.footnote).foregroundStyle(PronoTheme.t2)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(PronoTheme.mint.opacity(0.09), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).stroke(PronoTheme.mint.opacity(0.3), lineWidth: 1))
        .accessibilityElement(children: .combine)
    }
}

/// Rappel OBLIGATOIRE sous chaque sac (conformité 🔴) : les patates n'ont aucune valeur.
struct PronoNoValue: View {
    var block = false
    static let text = "Les patates n'ont aucune valeur : elles ne s'achètent pas, ne se vendent pas, ne s'échangent pas."

    var body: some View {
        if block {
            HStack(alignment: .top, spacing: 12) {
                Text("🥔").font(.title3).accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 4) {
                    Text(Self.text).font(.subheadline).foregroundStyle(PronoTheme.t1)
                    Text("Juste pour le plaisir de voir juste entre amis.").font(.footnote).foregroundStyle(PronoTheme.t2)
                }
            }
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(PronoTheme.lav.opacity(0.08), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(PronoTheme.lav.opacity(0.2), lineWidth: 1))
            .accessibilityElement(children: .combine)
            .accessibilityIdentifier("prono-no-value")
        } else {
            HStack(alignment: .top, spacing: 8) {
                Image(systemName: "info.circle").font(.caption).foregroundStyle(PronoTheme.t3).accessibilityHidden(true)
                Text(Self.text).font(.caption).foregroundStyle(PronoTheme.t2)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .accessibilityElement(children: .combine)
            .accessibilityIdentifier("prono-no-value")
        }
    }
}

// MARK: - Outils

/// Heure de Suisse, mois et jours en français.
enum PronoDates {
    static let zone = TimeZone(identifier: "Europe/Zurich") ?? .current

    static var calendar: Calendar {
        var c = Calendar(identifier: .gregorian)
        c.timeZone = zone
        c.locale = Locale(identifier: "fr_CH")
        c.firstWeekday = 2
        return c
    }

    static func format(_ date: Date, _ pattern: String) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "fr_CH")
        f.timeZone = zone
        f.dateFormat = pattern
        return f.string(from: date)
    }

    /// « 2026-11-01 » → date (début du mois).
    static func day(_ s: String) -> Date? {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = zone
        f.dateFormat = "yyyy-MM-dd"
        return f.date(from: String(s.prefix(10))) ?? PronoFormat.date(s)
    }

    static func monthKey(_ d: Date) -> String { format(d, "yyyy-MM-01") }
    static func monthName(_ d: Date) -> String { format(d, "MMMM") }
    static func monthShort(_ d: Date) -> String {
        let n = monthName(d)
        return n.count > 5 ? String(n.prefix(4)).capitalized + "." : n.capitalized
    }

    /// « de novembre » / « d'octobre ».
    static func ofMonth(_ d: Date) -> String {
        let n = monthName(d)
        return ["a", "o"].contains(n.prefix(1)) ? "d'\(n)" : "de \(n)"
    }

    static func daysLeftInMonth(_ now: Date = Date()) -> Int {
        let c = calendar
        guard let range = c.range(of: .day, in: .month, for: now) else { return 0 }
        return range.count - c.component(.day, from: now)
    }

    /// Remontée du sac : « lundi 23 nov. à 0 h ».
    static func refill(_ iso: String?) -> String {
        guard let iso, let d = PronoFormat.date(iso) else { return "lundi à 0 h" }
        return format(d, "EEEE d MMM") + " à 0 h"
    }

    static func dayHeader(_ d: Date) -> String {
        let c = calendar
        if c.isDateInToday(d) { return "Aujourd'hui" }
        if c.isDateInYesterday(d) { return "Hier" }
        return format(d, "EEEE d MMMM").capitalized(firstOnly: true)
    }

    static func isTonight(_ d: Date, now: Date = Date()) -> Bool { d > now && calendar.isDate(d, inSameDayAs: now) }
}

private extension PronoCard {
    /// Fin du prono (date).
    var endDate: Date? { PronoFormat.date(closesAt) }
}

private extension String {
    func capitalized(firstOnly: Bool) -> String { prefix(1).uppercased() + dropFirst() }
}

enum PronoKindText {
    static func label(_ kind: String) -> String {
        switch kind {
        case "choice": return "Choix"
        case "yesno": return "Oui / Non"
        case "overunder": return "Plus / Moins"
        case "number": return "Nombre"
        case "when": return "Heure"
        case "person": return "Une personne"
        case "majority": return "Devine la bande"
        case "award": return "Trophée"
        case "text": return "Réponse libre"
        default: return "Prono"
        }
    }
}

/// Les trois onglets de « Mes pronos » (décision de l'intégrateur).
enum PronoListTab: Int, CaseIterable {
    case play, wait, done

    var title: String { ["À jouer", "En attente", "Terminés"][rawValue] }
    var id: String { ["prono-tab-play", "prono-tab-wait", "prono-tab-done"][rawValue] }

    static func of(_ c: PronoCard) -> PronoListTab {
        switch c.state {
        case "open": return c.answered ? .wait : .play
        case "closed": return .wait
        default: return .done
        }
    }
}

/// Le terrain d'un sac : un groupe ou un événement.
struct PronoTerrain: Identifiable, Hashable {
    let key: String
    let groupID: String?
    let eventID: String?
    let name: String
    let emoji: String
    let color: String?

    var id: String { key }

    static func of(_ c: PronoCard) -> PronoTerrain? {
        if let g = c.group {
            return PronoTerrain(key: "g:" + g.id, groupID: g.id, eventID: nil, name: g.name, emoji: c.cover?.emoji ?? g.emoji, color: c.cover?.color ?? g.color)
        }
        if let e = c.event {
            return PronoTerrain(key: "e:" + e.id, groupID: nil, eventID: e.id, name: e.title, emoji: c.cover?.emoji ?? "📅", color: c.cover?.color ?? "coral")
        }
        return nil
    }
}

/// Fiche à ouvrir, avec le choix touché sur la carte (jamais de réponse directe depuis la liste).
struct PronoOpen: Hashable {
    let id: String
    var preselect: String?
}

/// Rapporte l'appui (carte qui s'enfonce tout entière, pastilles comprises).
private struct PressReport: ButtonStyle {
    @Binding var pressed: Bool

    func makeBody(configuration: Configuration) -> some View {
        configuration.label.onChange(of: configuration.isPressed) { pressed = $0 }
    }
}

/// Bord festonné d'un sceau de cire (12 lobes).
struct PronoScallop: Shape {
    var lobes = 12

    func path(in rect: CGRect) -> Path {
        let c = CGPoint(x: rect.midX, y: rect.midY)
        let r = min(rect.width, rect.height) / 2
        var p = Path()
        let steps = lobes * 8
        for i in 0...steps {
            let a = Double(i) / Double(steps) * 2 * .pi
            let rr = r * (0.92 + 0.08 * cos(Double(lobes) * a))
            let pt = CGPoint(x: c.x + rr * cos(a), y: c.y + rr * sin(a))
            if i == 0 { p.move(to: pt) } else { p.addLine(to: pt) }
        }
        p.closeSubpath()
        return p
    }
}

/// Trois sceaux qui flottent (états vides) : « ? » ou mes initiales.
struct PronoGhostSeals: View {
    var text = "?"
    var color: String? = "lavender"
    @Environment(\.accessibilityReduceMotion) private var reduce
    @State private var float = false

    var body: some View {
        let g = GroupLook.gradient(color)
        HStack(spacing: -8) {
            ForEach(0..<3, id: \.self) { i in
                let size: CGFloat = i == 1 ? 60 : 44
                PronoScallop()
                    .fill(LinearGradient(colors: [g.from, g.to], startPoint: .topLeading, endPoint: .bottomTrailing))
                    .overlay(PronoScallop().fill(RadialGradient(colors: [.white.opacity(0.5), .clear], center: UnitPoint(x: 0.34, y: 0.28), startRadius: 0, endRadius: size * 0.4)))
                    .overlay(Text(text).font(.system(size: size * 0.36, weight: .heavy, design: .rounded)).foregroundStyle(Color(hex: 0x1D1530).opacity(0.8)))
                    .frame(width: size, height: size)
                    .rotationEffect(.degrees([-12, 0, 10][i]))
                    .offset(y: float && !reduce ? (i == 1 ? -4 : 4) : 0)
                    .zIndex(i == 1 ? 1 : 0)
            }
        }
        .overlay(alignment: .topLeading) { Text("✦").font(.caption).foregroundStyle(PronoTheme.gold).offset(x: 4, y: -2) }
        .overlay(alignment: .bottomTrailing) { Text("✦").font(.caption2).foregroundStyle(PronoTheme.gold).offset(x: 6, y: 2) }
        .frame(height: 76)
        .accessibilityHidden(true)
        .onAppear {
            guard !reduce else { return }
            withAnimation(.easeInOut(duration: 1.6).repeatForever(autoreverses: true)) { float = true }
        }
    }
}

/// Puce d'un terrain (emoji sur le dégradé du groupe).
struct PronoTerrainDot: View {
    let emoji: String
    let color: String?
    var size: CGFloat = 26

    var body: some View {
        let g = GroupLook.gradient(color)
        Circle()
            .fill(LinearGradient(colors: [g.from, g.to], startPoint: .topLeading, endPoint: .bottomTrailing))
            .overlay(Text(emoji).font(.system(size: size * 0.54)))
            .frame(width: size, height: size)
            .accessibilityHidden(true)
    }
}

/// « 🥔 » + nombre aux chiffres larges.
struct PronoPotatoNumber: View {
    let value: Int
    var size: CGFloat = 17
    var sign = false
    var tone: Color = PronoTheme.t1

    var body: some View {
        HStack(spacing: 3) {
            Text(sign && value > 0 ? "+\(value)" : value < 0 ? "−\(-value)" : "\(value)")
                .font(.system(size: size, weight: .heavy).width(.expanded)).monospacedDigit()
                .contentTransition(.numericText(countsDown: value < 0))
            Text("🥔").font(.system(size: size * 0.8))
        }
        .foregroundStyle(tone)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(sign && value > 0 ? "plus \(value) patates" : "\(value) patates")
    }
}

/// Onglets segmentés (fond qui glisse) : À jouer / En attente / Terminés, ou Saison / Points.
struct PronoSegments<Tab: Hashable>: View {
    let tabs: [(tab: Tab, title: String, count: Int?, hot: Bool, id: String)]
    @Binding var selection: Tab
    @Namespace private var ns
    @Environment(\.accessibilityReduceMotion) private var reduce

    var body: some View {
        HStack(spacing: 4) {
            ForEach(Array(tabs.enumerated()), id: \.offset) { _, t in
                let on = t.tab == selection
                Button {
                    guard !on else { return }
                    PronoHaptics.selection()
                    withAnimation(Motion.pick(.spring(response: 0.35, dampingFraction: 0.86), reduced: reduce)) { selection = t.tab }
                } label: {
                    HStack(spacing: 6) {
                        Text(t.title).font(.subheadline.weight(.semibold)).lineLimit(1).minimumScaleFactor(0.8)
                        if let n = t.count, n > 0 {
                            Text("\(n)").font(.caption.weight(.heavy)).monospacedDigit()
                                .foregroundStyle(t.hot ? .white : PronoTheme.t1)
                                .padding(.horizontal, 6).frame(minWidth: 20, minHeight: 20)
                                .background(t.hot ? PronoTheme.pinkFill : PronoTheme.line2, in: Capsule())
                        }
                    }
                    .foregroundStyle(on ? PronoTheme.t1 : PronoTheme.t2)
                    .frame(maxWidth: .infinity, minHeight: 36)
                    .background {
                        if on {
                            RoundedRectangle(cornerRadius: 11, style: .continuous).fill(PronoTheme.s1)
                                .shadow(color: .black.opacity(0.4), radius: 8, y: 4)
                                .matchedGeometryEffect(id: "seg", in: ns)
                        }
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityAddTraits(on ? .isSelected : [])
                .accessibilityLabel(t.title + (t.count.map { $0 > 0 ? ", \($0)" : "" } ?? ""))
                .accessibilityIdentifier(t.id)
            }
        }
        .padding(4)
        .frame(minHeight: 44)
        .background(PronoTheme.s3, in: RoundedRectangle(cornerRadius: 15, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 15, style: .continuous).stroke(PronoTheme.line, lineWidth: 1))
    }
}

/// Étiquette de section en capitales (11/14, +0,08 em).
struct PronoCaps: View {
    let text: String
    var trailing: String? = nil

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(text.uppercased()).font(.caption2.weight(.bold)).kerning(0.9).foregroundStyle(PronoTheme.t2)
                .accessibilityAddTraits(.isHeader)
            Spacer()
            if let trailing { Text(trailing).font(.footnote.weight(.medium)).foregroundStyle(PronoTheme.t2) }
        }
        .padding(.top, 16)
    }
}

// MARK: - Carte d'un prono

/// Carte jouable d'un prono (1-kit.css « .card ») : couverture, question, aperçu des réponses, pied.
/// Un toucher sur la carte ouvre la fiche ; un toucher sur une pastille l'ouvre avec ce choix présélectionné.
struct PronoListCard: View {
    let card: PronoCard
    let patates: Bool
    /// Page d'un groupe : pas de couverture, le type et l'auteur au-dessus de la question.
    var compact = false
    let open: (String?) -> Void

    @State private var pressed = false
    @Environment(\.accessibilityReduceMotion) private var reduce

    private var tab: PronoListTab { PronoListTab.of(card) }
    private var terrain: PronoTerrain? { PronoTerrain.of(card) }
    private var urgent: Bool { tab == .play && (card.closesSoon ?? closesWithinHour) }
    private var closesWithinHour: Bool { (card.endDate?.timeIntervalSinceNow ?? .infinity) < 3600 }
    private var missed: Bool { card.state == "done" && card.answered && !card.won }
    private var shape: RoundedRectangle { RoundedRectangle(cornerRadius: 24, style: .continuous) }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            top.allowsHitTesting(false).accessibilityHidden(true)
            middle.padding(.horizontal, 18)
            foot.allowsHitTesting(false).accessibilityHidden(true)
        }
        .background {
            Button { open(nil) } label: { shape.fill(Color.clear).contentShape(shape) }
                .buttonStyle(PressReport(pressed: $pressed))
                .accessibilityLabel(a11y)
                .accessibilityHint("Ouvre le prono")
                .accessibilityIdentifier("prono-card-" + card.id)
        }
        // Un toucher hors des pastilles et des boutons (texte, blocs) ouvre aussi la fiche ; les boutons gardent la main.
        .contentShape(shape)
        .onTapGesture { open(nil) }
        .background(PronoTheme.s1, in: shape)
        .clipShape(shape)
        .overlay(shape.strokeBorder(border, lineWidth: urgent || (card.state == "done" && card.won) ? 1.5 : 1))
        .shadow(color: glow, radius: urgent || card.won ? 18 : 12, y: 10)
        .scaleEffect(pressed && !reduce ? 0.97 : 1)
        .animation(Motion.pick(.spring(response: 0.35, dampingFraction: 0.7), reduced: reduce), value: pressed)
    }

    private var border: Color {
        if urgent { return PronoTheme.pink.opacity(0.5) }
        if card.state == "done" && card.won { return PronoTheme.mint.opacity(0.42) }
        return PronoTheme.line
    }

    private var glow: Color {
        if urgent { return PronoTheme.pink.opacity(0.35) }
        if card.state == "done" && card.won { return PronoTheme.mint.opacity(0.25) }
        return .black.opacity(0.35)
    }

    // MARK: haut : couverture, question, ligne du champ

    @ViewBuilder private var top: some View {
        if compact {
            HStack(spacing: 6) {
                PronoKindIcon(kind: card.kind)
                Text(PronoKindText.label(card.kind).uppercased()).font(.caption2.weight(.heavy)).kerning(0.6)
                    .foregroundStyle(PronoTheme.lav)
                Text("· par \(card.creator.me == true ? "toi" : card.creator.name)").font(.caption.weight(.medium)).foregroundStyle(PronoTheme.t2)
            }
            .padding(.horizontal, 18).padding(.top, 16).padding(.bottom, 6)
        } else {
            ZStack(alignment: .top) {
                PronoCoverBand(color: terrain?.color, emoji: terrain?.emoji, photo: card.cover?.photo, height: 64)
                    .saturation(card.state == "done" ? (missed ? 0.25 : 0.75) : 1)
                    .mask(LinearGradient(stops: [.init(color: .black, location: 0.45), .init(color: .clear, location: 1)], startPoint: .top, endPoint: .bottom))
                HStack(spacing: 8) {
                    if let terrain {
                        HStack(spacing: 6) {
                            Text(terrain.emoji).font(.footnote)
                            Text(terrain.name).font(.footnote.weight(.semibold)).lineLimit(1)
                        }
                        .foregroundStyle(.white)
                        .padding(.leading, 8).padding(.trailing, 10).frame(height: 26)
                        .background(Color(hex: 0x0E0A1F).opacity(0.55), in: Capsule())
                    }
                    Spacer(minLength: 4)
                    HStack(spacing: 5) {
                        PronoKindIcon(kind: card.kind)
                        Text(PronoKindText.label(card.kind)).font(.caption.weight(.bold)).lineLimit(1)
                    }
                    .foregroundStyle(Color(hex: 0x1D1530))
                    .padding(.horizontal, 10).frame(height: 26)
                    .background(.white.opacity(0.88), in: Capsule())
                }
                .padding(12)
            }
            .frame(height: 64)
        }
        VStack(alignment: .leading, spacing: 6) {
            Text(card.question)
                .font(.system(compact ? .title3 : .title2, design: .rounded).weight(.heavy))
                .foregroundStyle(PronoTheme.t1)
                .fixedSize(horizontal: false, vertical: true)
            meta
        }
        .padding(.horizontal, 18).padding(.top, 2)
    }

    @ViewBuilder private var meta: some View {
        if tab != .done {
            HStack(spacing: 6) {
                if card.kind == "award" {
                    Text("Pour l'honneur")
                    dot
                    Text("dévoilé dès 3 votes")
                } else if patates, card.patates == true {
                    Text("🥔")
                    (Text("\(card.fieldTotal ?? 0)").bold().foregroundColor(PronoTheme.t1) + Text(" dans le champ"))
                    if let n = card.planters { dot; Text("\(n) planteur\(n > 1 ? "s" : "")") }
                    if let rule = rule { dot; Text(rule) }
                } else {
                    Text(rule ?? "Pour l'honneur")
                    dot
                    Text(PronoFormat.points(card.points))
                }
            }
            .font(.footnote.weight(.medium))
            .foregroundStyle(PronoTheme.t2)
            .lineLimit(2)
        }
    }

    private var rule: String? {
        switch card.kind {
        case "number", "when": return "le plus proche l'emporte"
        case "majority": return "la réponse la plus choisie l'emporte"
        default: return nil
        }
    }

    private var dot: some View { Circle().fill(PronoTheme.t3).frame(width: 3, height: 3) }

    // MARK: milieu : aperçu jouable, scellé ou résultat

    @ViewBuilder private var middle: some View {
        switch tab {
        case .play: preview.padding(.top, 14)
        case .wait: sealed.padding(.top, 14)
        case .done: result.padding(.top, 14)
        }
    }

    @ViewBuilder private var preview: some View {
        let options = card.options ?? []
        switch card.kind {
        case "yesno" where options.count == 2:
            HStack(spacing: 10) {
                yesNo(options[0], yes: true)
                yesNo(options[1], yes: false)
            }
        case "choice", "majority", "overunder":
            if !options.isEmpty {
                let shown = Array(options.prefix(6))
                LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 8), count: shown.count == 3 ? 3 : 2), spacing: 8) {
                    ForEach(Array(shown.enumerated()), id: \.element.id) { i, o in
                        PronoChoicePill(label: o.label, index: i, selected: false) { pick(o.id) }
                            .accessibilityLabel("Choisir \(o.label)")
                            .accessibilityHint("Ouvre le prono avec ce choix")
                            .accessibilityIdentifier("prono-pill-\(card.id)-\(i)")
                    }
                }
            }
        case "person", "award":
            if let people = card.candidates, !people.isEmpty {
                HStack(spacing: 10) {
                    ForEach(Array(people.prefix(5).enumerated()), id: \.element.id) { i, f in
                        Button { pick(f.id) } label: {
                            VStack(spacing: 5) {
                                Initials(name: f.name, photo: f.photo, size: 44)
                                Text(f.label.split(separator: " ").first.map(String.init) ?? f.label)
                                    .font(.caption.weight(.semibold)).foregroundStyle(PronoTheme.t2).lineLimit(1)
                            }
                            .frame(maxWidth: .infinity)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(PressableStyle(scale: 0.94))
                        .accessibilityLabel("Choisir \(f.label)")
                        .accessibilityIdentifier("prono-pill-\(card.id)-\(i)")
                    }
                    if people.count > 5 {
                        Button { open(nil) } label: {
                            VStack(spacing: 5) {
                                Circle().strokeBorder(PronoTheme.line2, style: StrokeStyle(lineWidth: 1, dash: [3, 3]))
                                    .background(Circle().fill(PronoTheme.s3))
                                    .overlay(Text("+\(people.count - 5)").font(.footnote.weight(.bold)).foregroundStyle(PronoTheme.t2))
                                    .frame(width: 44, height: 44)
                                Text("Tous").font(.caption.weight(.semibold)).foregroundStyle(PronoTheme.t2)
                            }
                            .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.plain)
                        .accessibilityLabel("Voir tout le monde")
                    }
                }
            }
        default:
            EmptyView()
        }
    }

    private func yesNo(_ o: PronoOption, yes: Bool) -> some View {
        let tone = yes ? PronoTheme.mint : PronoTheme.pink
        return Button { pick(o.id) } label: {
            HStack(spacing: 8) {
                Image(systemName: yes ? "checkmark" : "xmark").font(.body.weight(.heavy))
                Text(o.label).font(.system(.title3, design: .rounded).weight(.heavy))
            }
            .foregroundStyle(tone)
            .frame(maxWidth: .infinity, minHeight: 52)
            .background(LinearGradient(colors: [tone.opacity(0.2), tone.opacity(0.08)], startPoint: .topLeading, endPoint: .bottomTrailing),
                        in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(tone.opacity(0.35), lineWidth: 1))
        }
        .buttonStyle(PressableStyle(scale: 0.96))
        .accessibilityLabel("Choisir \(o.label)")
        .accessibilityHint("Ouvre le prono avec ce choix")
        .accessibilityIdentifier("prono-pill-\(card.id)-\(yes ? 0 : 1)")
    }

    private func pick(_ id: String) {
        PronoHaptics.selection()
        open(id)
    }

    @ViewBuilder private var sealed: some View {
        let stake = patates && card.patates == true ? (card.myStake ?? 0) : 0
        if card.state == "open" {
            HStack(spacing: 12) {
                mySeal
                VStack(alignment: .leading, spacing: 2) {
                    Text("Ta réponse est scellée").font(.subheadline.weight(.bold)).foregroundStyle(PronoTheme.t1)
                    Text(stake > 0 ? "Scellée · \(stake) 🥔 plantées" : "Personne ne la voit avant le dévoilement")
                        .font(.footnote.weight(.medium)).foregroundStyle(PronoTheme.t2)
                }
                .accessibilityElement(children: .combine)
                Spacer(minLength: 4)
                Button { open(nil) } label: {
                    Text("Modifier").font(.subheadline.weight(.bold)).foregroundStyle(PronoTheme.lav)
                        .padding(.horizontal, 12).frame(minHeight: 44)
                        .background(PronoTheme.lav.opacity(0.12), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                }
                .buttonStyle(PressableStyle())
                .accessibilityIdentifier("prono-card-edit-" + card.id)
            }
            .padding(12)
            .background(PronoTheme.s3, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(PronoTheme.line, lineWidth: 1))
        } else {
            VStack(spacing: 12) {
                HStack(spacing: 12) {
                    if card.answered { mySeal }
                    VStack(alignment: .leading, spacing: 2) {
                        Text(card.answered ? "Ta réponse est scellée" : "Tu n'as pas joué").font(.subheadline.weight(.bold)).foregroundStyle(PronoTheme.t1)
                        Text(card.mine ? (card.kind == "when" ? "Tu organises : touche dès que c'est arrivé." : "Tu organises : donne le résultat.")
                             : stake > 0 ? "Fermé · \(stake) 🥔 plantées · on attend le résultat" : "Fermé · on attend le résultat")
                            .font(.footnote.weight(.medium)).foregroundStyle(PronoTheme.t2)
                    }
                    Spacer(minLength: 0)
                }
                .padding(12)
                .background(PronoTheme.s3, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(PronoTheme.line, lineWidth: 1))
                .accessibilityElement(children: .combine)
                if card.mine {
                    Button { PronoHaptics.selection(); open(nil) } label: {
                        Text(card.kind == "when" ? "🚪 C'est arrivé !" : "Donner le résultat")
                            .font(.system(.headline, design: .rounded).weight(.heavy))
                            .foregroundStyle(Color(hex: 0x0E0A1F))
                            .frame(maxWidth: .infinity, minHeight: 52)
                            .background(LinearGradient(colors: [Color(hex: 0x7BF0BD), Color(hex: 0x3FCF8E)], startPoint: .topLeading, endPoint: .bottomTrailing),
                                        in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                            .shadow(color: PronoTheme.mint.opacity(0.4), radius: 12, y: 8)
                    }
                    .buttonStyle(PressableStyle())
                    .accessibilityIdentifier("prono-card-result-" + card.id)
                }
            }
        }
    }

    private var mySeal: some View {
        let g = GroupLook.gradient(terrain?.color ?? "lavender")
        return PronoScallop()
            .fill(LinearGradient(colors: [g.from, g.to], startPoint: .topLeading, endPoint: .bottomTrailing))
            .overlay(Image(systemName: "lock.fill").font(.caption2.weight(.bold)).foregroundStyle(Color(hex: 0x1D1530).opacity(0.75)))
            .frame(width: 36, height: 36)
            .overlay(alignment: .bottomTrailing) {
                Image(systemName: "checkmark.circle.fill").font(.caption).foregroundStyle(Color(hex: 0x0E0A1F), PronoTheme.mint)
                    .offset(x: 3, y: 3)
            }
            .shadow(color: g.to.opacity(0.6), radius: 8)
            .accessibilityHidden(true)
    }

    @ViewBuilder private var result: some View {
        let showPatates = patates && card.patates == true
        let stake = showPatates ? (card.myStake ?? 0) : 0
        if card.state == "cancelled" {
            verdictRow(title: "Prono annulé", sub: stake > 0 ? "Tes patates sont rendues" : nil, tone: PronoTheme.t2) {
                if stake > 0 { returned(stake) }
            }
        } else if card.kind == "award", let w = card.winners?.first {
            HStack(spacing: 14) {
                Initials(name: w.name, photo: w.photo, size: 56)
                    .overlay(Circle().stroke(PronoTheme.gold, lineWidth: 3))
                    .overlay(alignment: .top) { Text("👑").font(.title3).offset(y: -18) }
                    .shadow(color: PronoTheme.gold.opacity(0.45), radius: 12)
                VStack(alignment: .leading, spacing: 3) {
                    Text((card.award ?? "Trophée de la soirée").uppercased()).font(.caption2.weight(.heavy)).kerning(0.6).foregroundStyle(PronoTheme.gold)
                    Text(w.label).font(.system(.title2, design: .rounded).weight(.heavy)).foregroundStyle(PronoTheme.t1)
                    Text("pour l'honneur").font(.footnote).foregroundStyle(PronoTheme.t2)
                }
                Spacer(minLength: 0)
            }
            .padding(.top, 6)
            .accessibilityElement(children: .combine)
        } else if card.won {
            let right = card.winnersCount ?? card.winners?.count ?? 1
            let unanimous = right > 1 && right >= card.answeredCount
            if unanimous {
                verdictRow(title: "🤝 Unanimes !", sub: "Les \(right) avaient vu juste.", tone: PronoTheme.lav) {
                    if stake > 0 { returned(stake) }
                }
            } else {
                verdictRow(title: "🔮 Tu l'avais vu !", sub: right < card.answeredCount ? "★ Seul\(right > 1 ? "s" : "") \(right) sur \(card.answeredCount) l'avai\(right > 1 ? "ent" : "t") vu" : nil, tone: PronoTheme.mint) {
                    if showPatates, let h = card.myHarvest, h > 0 {
                        PronoPotatoNumber(value: h, size: 28, sign: true, tone: PronoTheme.mint)
                    } else if showPatates, stake > 0 {
                        Text("Récolte après le temps de contester").font(.caption.weight(.semibold)).foregroundStyle(PronoTheme.t2)
                            .multilineTextAlignment(.trailing).frame(maxWidth: 130, alignment: .trailing)
                    }
                }
            }
        } else if card.answered {
            verdictRow(title: "Pas cette fois", sub: winnersLine, tone: PronoTheme.t2) {
                if showPatates, let h = card.myHarvest {
                    if h > 0 && h == stake { returned(h) } else if h == 0 && stake > 0 {
                        HStack(spacing: 6) {
                            PronoPotatoNumber(value: stake, size: 17, tone: PronoTheme.miss)
                            Text("au compost").font(.footnote.weight(.semibold)).foregroundStyle(PronoTheme.miss)
                        }
                    }
                }
            }
        } else {
            verdictRow(title: "Tu n'as pas joué", sub: winnersLine, tone: PronoTheme.t2) { EmptyView() }
        }
    }

    private var winnersLine: String {
        guard let w = card.winners, !w.isEmpty else { return "Personne n'avait vu juste." }
        let n = card.winnersCount ?? w.count
        return n == 1 ? "\(w[0].label) avait vu juste" : "\(n) avaient vu juste"
    }

    private func returned(_ n: Int) -> some View {
        HStack(spacing: 4) {
            Image(systemName: "arrow.uturn.backward").font(.caption.weight(.bold))
            Text("\(n)").font(.subheadline.weight(.heavy).width(.expanded)).monospacedDigit()
            Text("🥔").font(.caption)
        }
        .foregroundStyle(PronoTheme.lav)
        .padding(.horizontal, 10).frame(height: 30)
        .background(PronoTheme.lav.opacity(0.14), in: Capsule())
        .overlay(Capsule().stroke(PronoTheme.lav.opacity(0.35), lineWidth: 1))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(n) patates rendues")
    }

    private func verdictRow<Trailing: View>(title: String, sub: String?, tone: Color, @ViewBuilder trailing: () -> Trailing) -> some View {
        HStack(alignment: .center, spacing: 10) {
            VStack(alignment: .leading, spacing: 3) {
                Text(title).font(.system(.title3, design: .rounded).weight(.heavy)).foregroundStyle(tone)
                if let sub { Text(sub).font(.footnote.weight(.semibold)).foregroundStyle(PronoTheme.t2) }
            }
            Spacer(minLength: 6)
            trailing()
        }
        .padding(14)
        .background(PronoTheme.s3, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(PronoTheme.line, lineWidth: 1))
        .accessibilityElement(children: .combine)
    }

    // MARK: pied

    private var foot: some View {
        VStack(spacing: 0) {
            Rectangle().fill(PronoTheme.line).frame(height: 1).padding(.top, 14)
            HStack(spacing: 10) {
                switch tab {
                case .play:
                    if !card.faces.isEmpty { PronoAvatarStack(faces: Array(card.faces.prefix(3)), extra: max(0, card.answeredCount - min(3, card.faces.count))) }
                    (Text("\(card.answeredCount)").bold().foregroundColor(PronoTheme.t1) + Text(card.kind == "award" ? " ont voté" : " ont joué"))
                        .font(.footnote.weight(.semibold)).foregroundStyle(PronoTheme.t2).lineLimit(1)
                    Spacer(minLength: 4)
                    PronoCountdown(closesAt: card.closesAt)
                case .wait:
                    PronoSealRow(faces: card.faces, total: card.answeredCount, color: terrain?.color)
                    Spacer(minLength: 4)
                    if card.state == "open" {
                        PronoCountdown(closesAt: card.closesAt)
                    } else {
                        Label("Fermé", systemImage: "lock.fill").font(.footnote.weight(.bold)).foregroundStyle(PronoTheme.t2)
                            .padding(.horizontal, 12).frame(height: 32)
                            .background(PronoTheme.s3, in: Capsule()).overlay(Capsule().stroke(PronoTheme.line, lineWidth: 1))
                    }
                case .done:
                    if let w = card.winners, !w.isEmpty, card.kind != "award" { PronoAvatarStack(faces: Array(w.prefix(3)), extra: max(0, (card.winnersCount ?? w.count) - min(3, w.count))) }
                    Text(card.state == "cancelled" ? "Annulé" : "\(card.answeredCount) \(card.kind == "award" ? "ont voté" : "ont joué")")
                        .font(.footnote.weight(.semibold)).foregroundStyle(PronoTheme.t2)
                    Spacer(minLength: 4)
                    Text(PronoFormat.short(card.closesAt)).font(.footnote.weight(.semibold)).foregroundStyle(PronoTheme.t2)
                }
            }
            .frame(minHeight: 44)
            .padding(.vertical, 8)
        }
        .padding(.horizontal, 18)
        .padding(.bottom, 4)
    }

    private var a11y: String {
        var parts = [card.question, PronoKindText.label(card.kind)]
        if let terrain { parts.append(terrain.name) }
        switch tab {
        case .play: parts.append("à jouer, \(PronoFormat.stateLine(state: card.state, closesAt: card.closesAt, revealed: card.revealed))")
        case .wait: parts.append(card.state == "open" ? "ta réponse est scellée" : "fermé, on attend le résultat")
        case .done: parts.append(card.state == "cancelled" ? "annulé" : card.won ? "tu avais vu juste" : "terminé")
        }
        if patates, card.patates == true, tab != .done { parts.append("\(card.fieldTotal ?? 0) patates dans le champ") }
        parts.append("\(card.answeredCount) sur \(card.players) ont joué")
        return parts.joined(separator: ", ")
    }
}

/// Rangée compacte (page d'un groupe : En attente, Terminés).
struct PronoCompactRow: View {
    let card: PronoCard
    let patates: Bool

    var body: some View {
        HStack(spacing: 12) {
            icon
            VStack(alignment: .leading, spacing: 2) {
                Text(card.question).font(.system(.callout, design: .rounded).weight(.heavy)).foregroundStyle(PronoTheme.t1)
                    .lineLimit(2).multilineTextAlignment(.leading)
                Text(subline).font(.footnote.weight(.medium)).foregroundStyle(PronoTheme.t2).lineLimit(2)
            }
            Spacer(minLength: 6)
            trailing
        }
        .padding(.horizontal, 16).padding(.vertical, 12)
        .frame(minHeight: 72)
        .contentShape(Rectangle())
    }

    private var showPatates: Bool { patates && card.patates == true }

    @ViewBuilder private var icon: some View {
        if card.state == "open" || card.state == "closed" {
            let g = GroupLook.gradient(card.group?.color ?? "lavender")
            PronoScallop().fill(LinearGradient(colors: [g.from, g.to], startPoint: .topLeading, endPoint: .bottomTrailing))
                .overlay(Image(systemName: "lock.fill").font(.caption2.weight(.bold)).foregroundStyle(Color(hex: 0x1D1530).opacity(0.75)))
                .frame(width: 40, height: 40).frame(width: 44, height: 44)
                .accessibilityHidden(true)
        } else {
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(card.won ? PronoTheme.mint.opacity(0.14) : PronoTheme.s3)
                .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).stroke(card.won ? PronoTheme.mint.opacity(0.4) : PronoTheme.line, lineWidth: 1))
                .overlay(Group {
                    if card.won { Image(systemName: "checkmark").font(.body.weight(.heavy)).foregroundStyle(PronoTheme.mint) } else { PronoKindIcon(kind: card.kind).foregroundStyle(PronoTheme.t2) }
                })
                .frame(width: 44, height: 44)
                .accessibilityHidden(true)
        }
    }

    private var subline: String {
        switch card.state {
        case "open":
            let stake = showPatates ? (card.myStake ?? 0) : 0
            return "Scellée" + (stake > 0 ? " · \(stake) 🥔" : "") + " · \(card.answeredCount) ont joué"
        case "closed": return card.mine ? "Fermé · à toi de donner le résultat" : "Fermé · on attend le résultat"
        case "cancelled": return "Annulé"
        default:
            if let w = card.winners, !w.isEmpty {
                let n = card.winnersCount ?? w.count
                return n == 1 ? "\(w[0].label) avait vu juste" : "★ \(n) sur \(card.answeredCount) l'avaient vu"
            }
            return "Personne n'avait vu juste"
        }
    }

    @ViewBuilder private var trailing: some View {
        switch card.state {
        case "open":
            PronoCountdown(closesAt: card.closesAt)
        case "closed":
            Image(systemName: "lock.fill").font(.footnote).foregroundStyle(PronoTheme.t2)
                .frame(width: 36, height: 36).background(PronoTheme.s3, in: Circle())
        default:
            if showPatates, let h = card.myHarvest {
                let stake = card.myStake ?? 0
                if card.won && h > stake {
                    PatateBadge(n: h, tone: .win)
                } else if h > 0 && h == stake {
                    PatateBadge(n: h, tone: .lav)
                } else if h == 0 && stake > 0 {
                    VStack(spacing: 0) {
                        Text("\(stake) 🥔").font(.footnote.weight(.heavy)).foregroundStyle(PronoTheme.miss)
                        Text("au compost").font(.caption2).foregroundStyle(PronoTheme.miss)
                    }
                }
            }
        }
    }
}

// MARK: - « Mes pronos » et page d'un groupe

/// App « Pronos » (Réglages › Autres apps) : « Mes pronos » ; avec un groupe : la page Pronos du groupe.
struct PronosListView: View {
    @ObservedObject var store: PronosStore
    var group: String?
    var groupName: String?

    var body: some View {
        if let group {
            PronoGroupPage(store: store, group: group, groupName: groupName)
        } else {
            PronosMineView(store: store)
        }
    }
}

/// Tout ce qu'une page de pronos ouvre : fiche (choix présélectionné), création (modèle), sac.
private struct PronoNavigation: ViewModifier {
    @ObservedObject var store: PronosStore
    let group: String?
    @Binding var opened: PronoOpen?
    @Binding var creating: Bool
    let template: PronoTemplate?
    let reload: () async -> Void

    func body(content: Content) -> some View {
        content
            .navigationDestination(isPresented: $creating) {
                PronoNewView(store: store, group: group, event: nil, template: template) { id in
                    creating = false
                    opened = PronoOpen(id: id)
                    Task { await reload() }
                }
            }
            .navigationDestination(isPresented: Binding(get: { opened != nil }, set: { if !$0 { opened = nil; Task { await reload() } } })) {
                if let opened { PronoDetailView(store: store, id: opened.id, preselect: opened.preselect) }
            }
    }
}

/// « Mes pronos » (maquettes 1-liste-*) : en-tête, sac en vedette, bulles des sacs, onglets, cartes.
struct PronosMineView: View {
    @ObservedObject var store: PronosStore
    @State private var cards: [PronoCard]?
    @State private var bags: [String: PronoBag] = [:]
    @State private var terrain: String?
    @State private var tab: PronoListTab = .play
    @State private var tabChosen = false
    @State private var templates: [PronoTemplate] = []
    @State private var error: String?
    @State private var creating = false
    @State private var template: PronoTemplate?
    @State private var opened: PronoOpen?
    @State private var bagSheet: PronoTerrain?

    private var patates: Bool { store.features.patates && (cards ?? []).contains { $0.patatesOn == true } }
    private func showPatates(_ c: PronoCard) -> Bool { store.features.patates && c.patatesOn == true }

    private var terrains: [PronoTerrain] {
        var seen = Set<String>()
        return (cards ?? []).filter { showPatates($0) && $0.patates == true }.compactMap(PronoTerrain.of).filter { seen.insert($0.key).inserted }
    }

    private func list(_ t: PronoListTab) -> [PronoCard] { (cards ?? []).filter { PronoListTab.of($0) == t } }

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 0, pinnedViews: [.sectionHeaders]) {
                header.padding(.horizontal, 16)
                if let error { Text(error).font(.footnote).foregroundStyle(PronoTheme.pink).padding(16) }
                if patates, !terrains.isEmpty { bagArea }
                if let cards {
                    if cards.isEmpty {
                        PronoFirstCard(templates: templates, color: "lavender") { t in template = t; creating = true }
                            .padding(16)
                        if !patates { PronoHonour(points: nil).padding(.horizontal, 16) }
                    } else {
                        Section {
                            tabContent.padding(.horizontal, 16)
                        } header: {
                            PronoSegments(tabs: PronoListTab.allCases.map { t in
                                (tab: t, title: t.title, count: t == .done ? nil : list(t).count, hot: t == .play, id: t.id)
                            }, selection: Binding(get: { tab }, set: { tab = $0; tabChosen = true }))
                            .padding(.horizontal, 16).padding(.vertical, 8)
                            .background(PronoTheme.bg.opacity(0.96))
                            .accessibilityIdentifier("pronos-tabs")
                        }
                        if !patates { PronoHonour(points: nil).padding(16) }
                    }
                } else {
                    ProgressView().frame(maxWidth: .infinity).padding(.top, 60)
                }
            }
            .padding(.bottom, 32)
        }
        .background(background)
        .navigationTitle("")
        .navigationBarTitleDisplayMode(.inline)
        .refreshable { await load() }
        .task { await load() }
        .modifier(PronoNavigation(store: store, group: nil, opened: $opened, creating: $creating, template: template, reload: load))
        .sheet(item: $bagSheet) { t in
            PronoBagSheet(store: store, terrain: t, planted: planted(t), settled: settledIDs)
        }
    }

    private var background: some View {
        ZStack(alignment: .top) {
            PronoTheme.bg
            RadialGradient(colors: [Color(hex: 0x7B6CF6).opacity(0.22), .clear], center: UnitPoint(x: 0.7, y: 0), startRadius: 0, endRadius: 420)
                .frame(height: 420)
        }
        .ignoresSafeArea()
    }

    // MARK: en-tête

    private var header: some View {
        HStack(alignment: .bottom, spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                Text("Pronos").font(.system(.largeTitle, design: .rounded).weight(.heavy)).foregroundStyle(PronoTheme.t1)
                    .accessibilityAddTraits(.isHeader)
                summary.font(.subheadline.weight(.medium)).foregroundStyle(PronoTheme.t2)
            }
            Spacer()
            Button { Haptics.tap(); template = nil; creating = true } label: {
                Image(systemName: "plus").font(.title3.weight(.bold)).foregroundStyle(.white)
                    .frame(width: 44, height: 44)
                    .background(LinearGradient(colors: [Color(hex: 0xFF5FA6), PronoTheme.pinkFill], startPoint: .top, endPoint: .bottom), in: Circle())
                    .shadow(color: PronoTheme.pink.opacity(0.6), radius: 12, y: 8)
            }
            .buttonStyle(PressableStyle(scale: 0.92))
            .accessibilityLabel("Nouveau prono")
            .accessibilityIdentifier("pronos-new")
        }
        .padding(.top, 4)
    }

    private var summary: Text {
        guard let cards, !cards.isEmpty else { return Text("Devine, scelle, dévoile.") }
        let play = list(.play).count, wait = list(.wait).count
        let tonight = cards.filter { ($0.state == "open" || $0.state == "closed") && ($0.endDate.map { PronoDates.isTonight($0) } ?? false) }.count
        var t = play > 0 ? Text("\(play) à jouer").bold().foregroundColor(PronoTheme.t1) : Text("Tout est joué").bold().foregroundColor(PronoTheme.t1)
        if tonight > 0 { t = t + Text(" · \(tonight) dévoilement\(tonight > 1 ? "s" : "") ce soir") } else if play == 0, wait > 0 { t = t + Text(" · \(wait) en attente") }
        return t
    }

    // MARK: sac en vedette

    private var current: PronoTerrain? {
        terrains.first { $0.key == terrain } ?? terrains.first { bags[$0.key] != nil }
    }

    @ViewBuilder private var bagArea: some View {
        if let t = current, let bag = bags[t.key] {
            VStack(alignment: .leading, spacing: 12) {
                PronoBagHero(terrain: t, bag: bag, planted: planted(t)) { PronoHaptics.soft(); bagSheet = t }
                if terrains.count > 1 {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 8) {
                            ForEach(terrains) { x in bubble(x) }
                        }
                        .padding(.horizontal, 16)
                    }
                    .padding(.horizontal, -16)
                }
                PronoNoValue()
            }
            .padding(.horizontal, 16).padding(.top, 20).padding(.bottom, 8)
        }
    }

    private func bubble(_ t: PronoTerrain) -> some View {
        let on = t.key == current?.key
        let g = GroupLook.gradient(t.color)
        return Button {
            PronoHaptics.selection()
            Motion.animate(Motion.snappy) { terrain = t.key }
        } label: {
            HStack(spacing: 7) {
                PronoTerrainDot(emoji: t.emoji, color: t.color)
                Text(t.name).font(.subheadline.weight(.semibold)).foregroundStyle(PronoTheme.t1).lineLimit(1)
                if let b = bags[t.key] { Text("\(b.balance)").font(.footnote.weight(.heavy).width(.expanded)).monospacedDigit().foregroundStyle(PronoTheme.t2) }
            }
            .padding(.leading, 6).padding(.trailing, 12).frame(minHeight: 44)
            .background(on ? PronoTheme.s1 : PronoTheme.s3, in: Capsule())
            .overlay(Capsule().stroke(on ? g.to.opacity(0.7) : PronoTheme.line, lineWidth: on ? 1.5 : 1))
        }
        .buttonStyle(PressableStyle())
        .accessibilityLabel("\(t.name), \(bags[t.key]?.balance ?? 0) patates")
        .accessibilityAddTraits(on ? .isSelected : [])
        .accessibilityIdentifier("prono-bag-chip-" + t.key)
    }

    private func planted(_ t: PronoTerrain) -> (n: Int, pronos: Int) {
        let live = (cards ?? []).filter { PronoTerrain.of($0)?.key == t.key && ($0.state == "open" || $0.state == "closed") && ($0.myStake ?? 0) > 0 }
        return (live.reduce(0) { $0 + ($1.myStake ?? 0) }, live.count)
    }

    private var settledIDs: Set<String> { Set((cards ?? []).filter { $0.state == "done" || $0.state == "cancelled" }.map(\.id)) }

    // MARK: onglets

    @ViewBuilder private var tabContent: some View {
        let items = list(tab)
        switch tab {
        case .play:
            if items.isEmpty {
                allPlayed
            } else {
                let sorted = items.sorted { ($0.endDate ?? .distantFuture) < ($1.endDate ?? .distantFuture) }
                let soon = sorted.filter { $0.closesSoon ?? (($0.endDate?.timeIntervalSinceNow ?? .infinity) < 3600) }
                section(soon.isEmpty ? nil : "Ça ferme bientôt", soon)
                section(soon.isEmpty ? nil : "Plus tard", sorted.filter { !soon.contains($0) })
            }
        case .wait:
            if items.isEmpty {
                PronoEmptyNote(title: "Rien en attente", text: "Joue un prono : ta réponse restera scellée jusqu'au dévoilement.")
            } else {
                let sorted = items.sorted { ($0.endDate ?? .distantFuture) < ($1.endDate ?? .distantFuture) }
                section("Scellés · tu peux encore changer", sorted.filter { $0.state == "open" })
                section("Fermés · on attend le résultat", sorted.filter { $0.state == "closed" })
            }
        case .done:
            if items.isEmpty {
                PronoEmptyNote(title: "Pas encore de résultat", text: "Les pronos dévoilés arrivent ici, avec ta récolte.")
            } else {
                let sorted = items.sorted { ($0.endDate ?? .distantPast) > ($1.endDate ?? .distantPast) }
                let week = Date().addingTimeInterval(-7 * 86_400)
                section("Cette semaine", sorted.filter { ($0.endDate ?? .distantPast) >= week })
                section("Plus tôt", sorted.filter { ($0.endDate ?? .distantPast) < week })
            }
        }
    }

    @ViewBuilder private func section(_ title: String?, _ items: [PronoCard]) -> some View {
        if !items.isEmpty {
            if let title { PronoCaps(text: title).padding(.bottom, 12).padding(.top, 8) }
            VStack(spacing: 14) {
                ForEach(Array(items.enumerated()), id: \.element.id) { i, card in
                    PronoListCard(card: card, patates: showPatates(card)) { pre in
                        opened = PronoOpen(id: card.id, preselect: pre)
                    }
                    .modifier(PronoRise(index: i))
                }
            }
            .padding(.top, title == nil ? 12 : 0)
        }
    }

    private var allPlayed: some View {
        let next = list(.wait).filter { $0.state == "open" }.min { ($0.endDate ?? .distantFuture) < ($1.endDate ?? .distantFuture) }
        return VStack(spacing: 10) {
            PronoGhostSeals(text: "✓", color: current?.color ?? "lavender")
            Text("Tu as tout joué").font(.system(.title2, design: .rounded).weight(.heavy)).foregroundStyle(PronoTheme.t1)
            if let next {
                (Text("Tes réponses sont scellées.\nProchain dévoilement : ") + Text(PronoFormat.short(next.closesAt)).bold().foregroundColor(PronoTheme.t1) + Text("\n" + next.question))
                    .font(.subheadline).foregroundStyle(PronoTheme.t2).multilineTextAlignment(.center)
            } else {
                Text("Tes réponses sont scellées.").font(.subheadline).foregroundStyle(PronoTheme.t2)
            }
            if !list(.wait).isEmpty {
                Button { PronoHaptics.selection(); Motion.animate(Motion.snappy) { tab = .wait } } label: {
                    Text("Voir mes pronos en attente").font(.headline).foregroundStyle(PronoTheme.t1)
                        .frame(maxWidth: .infinity, minHeight: 52)
                        .background(PronoTheme.s3, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(PronoTheme.line2, lineWidth: 1))
                }
                .buttonStyle(PressableStyle())
                .padding(.top, 6)
                .accessibilityIdentifier("prono-see-waiting")
            }
        }
        .padding(24)
        .frame(maxWidth: .infinity)
        .background(PronoTheme.s1, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).stroke(PronoTheme.line, lineWidth: 1))
        .padding(.top, 12)
    }

    // MARK: chargement

    private func load() async {
        do {
            let list: [PronoCard] = try await store.call("prono_list", [:])
            Motion.animate(Motion.smooth) { cards = list }
            if !tabChosen {
                // « Tout est joué » reste sur À jouer s'il y a des pronos en attente ; sinon les résultats.
                tab = list.contains { PronoListTab.of($0) != .done } ? .play : .done
            }
            error = nil
            await store.refreshBadge()
        } catch {
            self.error = PronosStore.message(error)
            if cards == nil { cards = [] }
        }
        if cards?.isEmpty == true, templates.isEmpty { templates = (try? await store.templates()) ?? [] }
        await loadBags()
    }

    private func loadBags() async {
        guard patates else { return }
        let ts = Array(terrains.prefix(8))
        var found: [String: PronoBag] = [:]
        await withTaskGroup(of: (String, PronoBag?).self) { group in
            for t in ts {
                group.addTask { @MainActor in (t.key, try? await store.bag(groupID: t.groupID, eventID: t.eventID)) }
            }
            for await (key, bag) in group { if let bag { found[key] = bag } }
        }
        Motion.animate(Motion.smooth) { bags = found }
        if terrain == nil {
            // Le sac du prono le plus urgent d'abord.
            let urgent = list(.play).sorted { ($0.endDate ?? .distantFuture) < ($1.endDate ?? .distantFuture) }.compactMap(PronoTerrain.of).first { found[$0.key] != nil }
            terrain = urgent?.key ?? ts.first { found[$0.key] != nil }?.key
        }
    }
}

/// Apparition d'une carte : montée de 12 pt + fondu, décalée de 50 ms (coupée par Réduire les animations).
private struct PronoRise: ViewModifier {
    let index: Int
    @Environment(\.accessibilityReduceMotion) private var reduce
    @State private var shown = false

    func body(content: Content) -> some View {
        content
            .opacity(shown || reduce ? 1 : 0)
            .offset(y: shown || reduce ? 0 : 12)
            .onAppear {
                guard !shown else { return }
                withAnimation(.timingCurve(0.22, 1, 0.36, 1, duration: 0.42).delay(Double(min(index, 6)) * 0.05)) { shown = true }
            }
    }
}

/// Petit état vide d'un onglet.
struct PronoEmptyNote: View {
    let title: String
    let text: String

    var body: some View {
        VStack(spacing: 8) {
            Text(title).font(.system(.title3, design: .rounded).weight(.heavy)).foregroundStyle(PronoTheme.t1)
            Text(text).font(.subheadline).foregroundStyle(PronoTheme.t2).multilineTextAlignment(.center)
        }
        .padding(24)
        .frame(maxWidth: .infinity)
        .background(PronoTheme.s1, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).stroke(PronoTheme.line, lineWidth: 1))
        .padding(.top, 12)
        .accessibilityElement(children: .combine)
    }
}

/// « Lance le premier prono » (1-vides) : sceaux « ? », 3 modèles en un toucher, « Partir de zéro ».
struct PronoFirstCard: View {
    let templates: [PronoTemplate]
    var color: String?
    let start: (PronoTemplate?) -> Void

    var body: some View {
        let g = GroupLook.gradient(color)
        VStack(spacing: 12) {
            PronoGhostSeals(text: "?", color: color).padding(.top, 6)
            Text("Lance le premier prono").font(.system(.title2, design: .rounded).weight(.heavy)).foregroundStyle(PronoTheme.t1)
                .multilineTextAlignment(.center)
            Text("Une question, des réponses scellées, puis le grand dévoilement.")
                .font(.subheadline).foregroundStyle(PronoTheme.t2).multilineTextAlignment(.center).frame(maxWidth: 280)
            if !templates.isEmpty {
                PronoCaps(text: "En un toucher").padding(.top, -4)
                ForEach(templates.prefix(3)) { t in
                    Button { Haptics.tap(); start(t) } label: {
                        HStack(spacing: 12) {
                            Circle().fill(LinearGradient(colors: [g.from, g.to], startPoint: .topLeading, endPoint: .bottomTrailing))
                                .overlay(Text(t.emoji).font(.body)).frame(width: 32, height: 32)
                            Text(t.title).font(.body.weight(.semibold)).foregroundStyle(PronoTheme.t1).lineLimit(2).multilineTextAlignment(.leading)
                            Spacer(minLength: 6)
                            Text(PronoKindText.label(t.kind)).font(.footnote.weight(.semibold)).foregroundStyle(PronoTheme.t2)
                        }
                        .padding(.horizontal, 12).frame(minHeight: 48)
                        .background(PronoTheme.s3, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(PronoTheme.line2, lineWidth: 1))
                    }
                    .buttonStyle(PressableStyle(scale: 0.97))
                    .accessibilityHint("Ouvre la création avec cette question")
                    .accessibilityIdentifier("prono-template-" + t.id)
                }
            }
            PronoPrimaryButton(title: "Partir de zéro", systemImage: "plus") { Haptics.tap(); start(nil) }
                .accessibilityIdentifier("prono-from-scratch")
                .padding(.top, 4)
        }
        .padding(.horizontal, 20).padding(.vertical, 24)
        .frame(maxWidth: .infinity)
        .background(g.to.opacity(0.06), in: RoundedRectangle(cornerRadius: 24, style: .continuous))
        .background(PronoTheme.s1, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).strokeBorder(g.to.opacity(0.6), style: StrokeStyle(lineWidth: 1.5, dash: [5, 4])))
    }
}

/// Le sac en vedette de la liste (1-liste : « Ton sac · … 86 🥔 remonte à 100 lundi à 0 h »).
struct PronoBagHero: View {
    let terrain: PronoTerrain
    let bag: PronoBag
    let planted: (n: Int, pronos: Int)
    let open: () -> Void
    @ScaledMetric(relativeTo: .largeTitle) private var big: CGFloat = 56
    @Environment(\.accessibilityReduceMotion) private var reduce
    @State private var drift = false

    var body: some View {
        let g = GroupLook.gradient(terrain.color)
        Button(action: open) {
            VStack(alignment: .leading, spacing: 0) {
                HStack(spacing: 6) {
                    Text("Ton sac ·").foregroundStyle(PronoTheme.t2)
                    Text(terrain.name).bold().foregroundStyle(PronoTheme.t1).lineLimit(1)
                    Spacer()
                    Image(systemName: "chevron.right").font(.footnote.weight(.semibold)).foregroundStyle(PronoTheme.t2)
                }
                .font(.footnote.weight(.semibold))
                HStack(alignment: .lastTextBaseline, spacing: 14) {
                    HStack(alignment: .lastTextBaseline, spacing: 4) {
                        Text("\(bag.balance)").font(.system(size: big, weight: .heavy).width(.expanded)).monospacedDigit()
                            .contentTransition(.numericText()).foregroundStyle(PronoTheme.t1)
                        Text("🥔").font(.system(size: big * 0.54))
                    }
                    Group {
                        if bag.balance >= 100 {
                            Text("Ton sac est plein")
                        } else {
                            Text("remonte à ") + Text("100").bold().foregroundColor(PronoTheme.t1) + Text("\nlundi à 0 h")
                        }
                    }
                    .font(.footnote.weight(.semibold)).foregroundStyle(PronoTheme.t2)
                }
                .padding(.top, 6)
                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        Capsule().fill(PronoTheme.line2)
                        Capsule().fill(LinearGradient(colors: [g.from, g.to], startPoint: .leading, endPoint: .trailing))
                            .frame(width: geo.size.width * min(1, Double(bag.balance) / 100))
                    }
                }
                .frame(height: 6).padding(.top, 14)
                HStack(spacing: 8) {
                    tile(planted.pronos > 0 ? "Plantées · \(planted.pronos) prono\(planted.pronos > 1 ? "s" : "")" : "Plantées", value: planted.n, tone: PronoTheme.t1, sign: false)
                    tile("Récolte \(PronoDates.ofMonth(Date()))", value: bag.season?.harvestNet ?? 0, tone: (bag.season?.harvestNet ?? 0) > 0 ? PronoTheme.mint : PronoTheme.t1, sign: true)
                }
                .padding(.top, 14)
            }
            .padding(.horizontal, 18).padding(.vertical, 16)
            .background {
                ZStack(alignment: .topTrailing) {
                    PronoTheme.s1
                    RadialGradient(colors: [g.to.opacity(0.55), .clear], center: .topTrailing, startRadius: 0, endRadius: 240)
                        .offset(x: drift ? -18 : 0, y: drift ? 10 : 0)
                    Text(terrain.emoji).font(.system(size: 150)).opacity(0.16).rotationEffect(.degrees(-14)).offset(x: 22, y: -30)
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).stroke(PronoTheme.line, lineWidth: 1))
            .shadow(color: .black.opacity(0.45), radius: 20, y: 14)
        }
        .buttonStyle(PressableStyle(scale: 0.98))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Ton sac, \(terrain.name) : \(bag.balance) patates. \(bag.balance >= 100 ? "Ton sac est plein." : "Remonte à 100 lundi à 0 heure.")")
        .accessibilityHint("Ouvre ton sac et ton historique")
        .accessibilityIdentifier("prono-bag")
        .onAppear {
            guard !reduce else { return }
            withAnimation(.easeInOut(duration: 14).repeatForever(autoreverses: true)) { drift = true }
        }
    }

    private func tile(_ title: String, value: Int, tone: Color, sign: Bool) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title).font(.caption.weight(.semibold)).foregroundStyle(PronoTheme.t2).lineLimit(1)
            PronoPotatoNumber(value: value, size: 17, sign: sign, tone: tone)
        }
        .padding(.horizontal, 12).padding(.vertical, 10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(PronoTheme.s3, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).stroke(PronoTheme.line, lineWidth: 1))
    }
}

// MARK: - Page Pronos d'un groupe (1-groupe, 1-vides)

struct PronoGroupPage: View {
    @ObservedObject var store: PronosStore
    let group: String
    var groupName: String?
    @State private var cards: [PronoCard]?
    @State private var board: PronoBoard?
    @State private var season: PronoSeason?
    @State private var bag: PronoBag?
    @State private var templates: [PronoTemplate] = []
    @State private var error: String?
    @State private var view = 0
    @State private var creating = false
    @State private var template: PronoTemplate?
    @State private var opened: PronoOpen?
    @State private var bagSheet: PronoTerrain?
    @State private var showSeason = false

    private var ref: PronoGroupRef? { cards?.first { $0.group?.id == group }?.group }
    private var color: String? { cards?.first { $0.group?.id == group }?.cover?.color ?? ref?.color ?? "lavender" }
    private var emoji: String { cards?.first { $0.group?.id == group }?.cover?.emoji ?? ref?.emoji ?? "🔮" }
    private var name: String { ref?.name ?? groupName ?? "Pronos" }
    private var terrain: PronoTerrain { PronoTerrain(key: "g:" + group, groupID: group, eventID: nil, name: name, emoji: emoji, color: color) }

    /// Patates : le site ET la base (les cartes, ou le sac si le groupe n'a pas encore de prono).
    private var patates: Bool {
        guard store.features.patates else { return false }
        if let cards, !cards.isEmpty { return cards.contains { $0.patatesOn == true } }
        return bag != nil
    }

    private func list(_ t: PronoListTab) -> [PronoCard] { (cards ?? []).filter { PronoListTab.of($0) == t } }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                hero
                VStack(alignment: .leading, spacing: 0) {
                    PronoPrimaryButton(title: "Nouveau prono", systemImage: "plus") { Haptics.tap(); template = nil; creating = true }
                        .accessibilityIdentifier("pronos-new")
                        .padding(.top, 20)
                    if let error { Text(error).font(.footnote).foregroundStyle(PronoTheme.pink).padding(.top, 10) }
                    if let cards {
                        if cards.isEmpty {
                            PronoFirstCard(templates: templates, color: color) { t in template = t; creating = true }.padding(.top, 20)
                        }
                        standings
                        if !cards.isEmpty { pronos }
                    } else {
                        ProgressView().frame(maxWidth: .infinity).padding(.top, 40)
                    }
                    Group {
                        if patates { PronoNoValue() } else { PronoHonour(points: nil) }
                    }
                    .padding(.top, 24)
                }
                .padding(.horizontal, 16)
            }
            .padding(.bottom, 32)
        }
        .background(PronoTheme.bg.ignoresSafeArea())
        .navigationTitle("")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(.hidden, for: .navigationBar)
        .toolbar {
            if patates, let bag {
                ToolbarItem(placement: .primaryAction) {
                    Button { PronoHaptics.soft(); bagSheet = terrain } label: {
                        HStack(spacing: 4) {
                            Text("\(bag.balance)").font(.subheadline.weight(.heavy).width(.expanded)).monospacedDigit()
                            Text("🥔").font(.footnote)
                        }
                        .foregroundStyle(PronoTheme.t1)
                        .padding(.horizontal, 12).frame(height: 36)
                        .background(.ultraThinMaterial, in: Capsule())
                    }
                    .accessibilityLabel("Ton sac : \(bag.balance) patates")
                    .accessibilityIdentifier("prono-bag-chip")
                }
            }
        }
        .refreshable { await load() }
        .task { await load() }
        .modifier(PronoNavigation(store: store, group: group, opened: $opened, creating: $creating, template: template, reload: load))
        .navigationDestination(isPresented: $showSeason) {
            PronoSeasonView(store: store, group: group, terrain: terrain, bag: bag)
        }
        .sheet(item: $bagSheet) { t in
            PronoBagSheet(store: store, terrain: t, planted: planted, settled: Set(list(.done).map(\.id)))
        }
    }

    private var planted: (n: Int, pronos: Int) {
        let live = (cards ?? []).filter { ($0.state == "open" || $0.state == "closed") && ($0.myStake ?? 0) > 0 }
        return (live.reduce(0) { $0 + ($1.myStake ?? 0) }, live.count)
    }

    // MARK: couverture

    private var hero: some View {
        let g = GroupLook.gradient(color)
        let running = list(.play).count + list(.wait).count
        return VStack(alignment: .leading, spacing: 4) {
            GroupTile(emoji: emoji, color: color, size: 72)
                .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).stroke(PronoTheme.bg, lineWidth: 3))
                .padding(.bottom, 8)
            Text(name).font(.system(.title, design: .rounded).weight(.heavy)).foregroundStyle(PronoTheme.t1)
                .accessibilityAddTraits(.isHeader)
            Text(cards?.isEmpty == true ? "Pronos · aucun pour l'instant" : "Pronos · \(running) en cours")
                .font(.subheadline).foregroundStyle(PronoTheme.t2)
        }
        .padding(.horizontal, 16)
        .padding(.top, 110)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(alignment: .top) {
            ZStack(alignment: .topTrailing) {
                LinearGradient(colors: [g.from, g.to], startPoint: .topLeading, endPoint: .bottomTrailing)
                Text(emoji).font(.system(size: 230)).opacity(0.2).rotationEffect(.degrees(-14)).offset(x: 40, y: 10)
            }
            .frame(height: 340)
            .mask(LinearGradient(stops: [.init(color: .black, location: 0.5), .init(color: .clear, location: 1)], startPoint: .top, endPoint: .bottom))
            .offset(y: -140)
            .accessibilityHidden(true)
        }
    }

    // MARK: classements : saison (patates) / points

    @ViewBuilder private var standings: some View {
        if patates {
            PronoSegments(tabs: [(tab: 0, title: "Saison 🥔", count: nil, hot: false, id: "prono-season-tab"),
                                 (tab: 1, title: "Points", count: nil, hot: false, id: "prono-points-tab")], selection: $view)
                .accessibilityIdentifier("pronos-tabs")
                .padding(.top, 24)
        }
        if patates && view == 0 {
            PronoCaps(text: "Saison \(PronoDates.ofMonth(Date()))", trailing: "encore \(PronoDates.daysLeftInMonth()) jour\(PronoDates.daysLeftInMonth() > 1 ? "s" : "")")
                .padding(.bottom, 12)
            PronoSeasonCard(season: season, color: color) { PronoHaptics.selection(); showSeason = true }
        } else if let board {
            PronoCaps(text: "Classement aux points").padding(.bottom, 12)
            PronoBoardView(board: board, store: store, group: group) { await load() }
        }
    }

    // MARK: pronos du groupe

    @ViewBuilder private var pronos: some View {
        let play = list(.play).sorted { ($0.endDate ?? .distantFuture) < ($1.endDate ?? .distantFuture) }
        if !play.isEmpty {
            PronoCaps(text: "À jouer · \(play.count)").padding(.bottom, 12).padding(.top, 12)
            VStack(spacing: 14) {
                ForEach(Array(play.enumerated()), id: \.element.id) { i, card in
                    PronoListCard(card: card, patates: patates && card.patatesOn == true, compact: true) { pre in
                        opened = PronoOpen(id: card.id, preselect: pre)
                    }
                    .modifier(PronoRise(index: i))
                }
            }
        }
        compactList("En attente", list(.wait).sorted { ($0.endDate ?? .distantFuture) < ($1.endDate ?? .distantFuture) })
        compactList("Terminés", list(.done).sorted { ($0.endDate ?? .distantPast) > ($1.endDate ?? .distantPast) })
    }

    @ViewBuilder private func compactList(_ title: String, _ items: [PronoCard]) -> some View {
        if !items.isEmpty {
            PronoCaps(text: "\(title) · \(items.count)").padding(.bottom, 12).padding(.top, 12)
            VStack(spacing: 0) {
                ForEach(Array(items.enumerated()), id: \.element.id) { i, card in
                    if i > 0 { Rectangle().fill(PronoTheme.line).frame(height: 1).padding(.leading, 72) }
                    Button { Haptics.tap(); opened = PronoOpen(id: card.id) } label: {
                        PronoCompactRow(card: card, patates: patates && card.patatesOn == true)
                    }
                    .buttonStyle(PressableStyle(scale: 0.98))
                    .accessibilityElement(children: .combine)
                    .accessibilityIdentifier("prono-card-" + card.id)
                }
            }
            .background(PronoTheme.s1, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).stroke(PronoTheme.line, lineWidth: 1))
        }
    }

    private func load() async {
        do {
            let list: [PronoCard] = try await store.call("prono_list", ["group_id": group])
            Motion.animate(Motion.smooth) { cards = list }
            error = nil
        } catch {
            self.error = PronosStore.message(error)
            if cards == nil { cards = [] }
        }
        if store.features.patates {
            bag = try? await store.bag(groupID: group, eventID: nil)
            if patates { season = try? await store.season(groupID: group, month: nil) }
        }
        board = try? await store.call("prono_board", ["group_id": group])
        if cards?.isEmpty == true, templates.isEmpty { templates = (try? await store.templates()) ?? [] }
        await store.refreshBadge()
    }
}

// MARK: - Podium

/// Une marche du podium : visage, nom, valeur (récolte nette ou points), justesse.
struct PronoPodiumEntry: Identifiable {
    let face: PronoFace
    let value: String
    let tone: Color
    var sub: String?
    var id: String { face.id }
}

/// Podium 2-1-3 : les marches montent (3, puis 2, puis 1), la couronne tombe sur le 1er.
struct PronoPodium: View {
    /// Dans l'ordre du classement (1er, 2e, 3e).
    let entries: [PronoPodiumEntry]
    var color: String?
    var big = false
    var ghost: [PronoFace] = []

    @Environment(\.accessibilityReduceMotion) private var reduce
    @State private var risen: [Bool] = [false, false, false]
    @State private var crown = false

    var body: some View {
        let order = [1, 0, 2]
        let heights: [CGFloat] = big ? [132, 100, 76] : [88, 64, 48]
        HStack(alignment: .bottom, spacing: 8) {
            ForEach(order, id: \.self) { rank in
                step(rank: rank, height: heights[rank])
            }
        }
        .frame(maxWidth: .infinity)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(entries.isEmpty ? "Podium vide" : entries.enumerated().map { "\($0.offset + 1)\($0.offset == 0 ? "er" : "e") : \($0.element.face.label), \($0.element.value)" }.joined(separator: ". "))
        .onAppear(perform: play)
    }

    @ViewBuilder private func step(rank: Int, height: CGFloat) -> some View {
        let e = rank < entries.count ? entries[rank] : nil
        let g = GroupLook.gradient(color)
        let avatar: CGFloat = big ? (rank == 0 ? 76 : 56) : (rank == 0 ? 60 : 48)
        VStack(spacing: 4) {
            if let e {
                Initials(name: e.face.name, photo: e.face.photo, size: avatar)
                    .overlay(Circle().stroke(rank == 0 ? PronoTheme.gold : .clear, lineWidth: 3))
                    .shadow(color: rank == 0 ? PronoTheme.gold.opacity(0.5) : .clear, radius: 12)
                    .overlay(alignment: .top) {
                        if rank == 0 {
                            Text("👑").font(.system(size: big ? 34 : 24))
                                .rotationEffect(.degrees(crown || reduce ? -8 : -20))
                                .offset(y: (crown || reduce ? -0.42 : -1.1) * avatar)
                                .opacity(crown || reduce ? 1 : 0)
                        }
                    }
                    .scaleEffect(risen[rank] || reduce ? 1 : 0.4)
                    .opacity(risen[rank] || reduce ? 1 : 0)
                Text(e.face.label).font(.subheadline.weight(.bold)).foregroundStyle(PronoTheme.t1).lineLimit(1)
                Text(e.value).font(.subheadline.weight(.heavy).width(.expanded)).monospacedDigit().foregroundStyle(e.tone)
                if let sub = e.sub { Text(sub).font(.caption).foregroundStyle(PronoTheme.t2).lineLimit(1) }
            } else if rank < ghost.count {
                Initials(name: ghost[rank].name, photo: nil, size: avatar).grayscale(1).opacity(0.45)
            } else {
                Color.clear.frame(width: 1, height: avatar)
            }
            let shape = UnevenRoundedRectangle(topLeadingRadius: big ? 18 : 14, bottomLeadingRadius: 4, bottomTrailingRadius: 4, topTrailingRadius: big ? 18 : 14, style: .continuous)
            Text("\(rank + 1)")
                .font(.system(size: big ? 40 : 22, weight: .black).width(.expanded))
                .foregroundStyle(rank == 0 ? PronoTheme.gold : PronoTheme.t1)
                .padding(.top, 8)
                .frame(maxWidth: .infinity, alignment: .top)
                .frame(height: risen[rank] || reduce ? height : 0, alignment: .top)
                .background(e == nil ? AnyShapeStyle(Color.clear) : AnyShapeStyle(LinearGradient(colors: [(rank == 0 ? PronoTheme.gold : g.to).opacity(0.22), Color.white.opacity(0.04)], startPoint: .top, endPoint: .bottom)), in: shape)
                .overlay(alignment: .top) {
                    if e == nil {
                        shape.strokeBorder(PronoTheme.line2, style: StrokeStyle(lineWidth: 1.5, dash: [4, 4]))
                    } else {
                        shape.stroke(rank == 0 ? PronoTheme.gold.opacity(0.8) : g.to.opacity(0.6), lineWidth: 2).mask(LinearGradient(colors: [.black, .clear], startPoint: .top, endPoint: .center))
                    }
                }
                .clipped()
        }
        .frame(maxWidth: .infinity)
    }

    private func play() {
        guard !reduce else { risen = [true, true, true]; crown = true; return }
        guard !risen.contains(true) else { return }
        let spring = Animation.spring(response: 0.5, dampingFraction: 0.7)
        let steps: [(rank: Int, at: Double)] = [(2, 0.2), (1, 0.45), (0, 0.7)]
        for s in steps where s.rank < entries.count {
            DispatchQueue.main.asyncAfter(deadline: .now() + s.at) {
                withAnimation(spring) { risen[s.rank] = true }
                if s.rank == 0 { Haptics.press() } else { PronoHaptics.soft() }
            }
        }
        for s in steps where s.rank >= entries.count { risen[s.rank] = true }
        if !entries.isEmpty {
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.15) {
                withAnimation(.spring(response: 0.4, dampingFraction: 0.5)) { crown = true }
                PronoHaptics.success()
            }
        }
    }
}

/// Récolte nette : + menthe, 0 clair, − gris (jamais rouge).
private func harvestText(_ n: Int) -> (String, Color) {
    if n > 0 { return ("+\(n) 🥔", PronoTheme.mint) }
    if n < 0 { return ("−\(-n) 🥔", Color(hex: 0xC9C4DD)) }
    return ("0 🥔", PronoTheme.t1)
}

/// Carte « Saison de … » de la page du groupe : podium, ma ligne, « Tout le classement ».
struct PronoSeasonCard: View {
    let season: PronoSeason?
    var color: String?
    let more: () -> Void

    var body: some View {
        VStack(spacing: 14) {
            let rows = season?.rows ?? []
            PronoPodium(entries: rows.prefix(3).map { r in
                let h = harvestText(r.harvestNet)
                return PronoPodiumEntry(face: r.user, value: h.0, tone: h.1)
            }, color: color)
            .padding(.top, 16)
            if rows.isEmpty {
                Text("Le premier prono lance la saison.").font(.subheadline).foregroundStyle(PronoTheme.t2)
            } else {
                if let me = season?.me { PronoSeasonRow(row: me, mine: true) }
                Button(action: more) {
                    HStack(spacing: 4) { Text("Tout le classement"); Image(systemName: "chevron.right").font(.footnote.weight(.bold)) }
                        .font(.body.weight(.semibold)).foregroundStyle(PronoTheme.lav).frame(minHeight: 44)
                }
                .accessibilityIdentifier("prono-season-all")
            }
        }
        .padding(16)
        .background(PronoTheme.s1, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).stroke(PronoTheme.line, lineWidth: 1))
    }
}

/// Une ligne du classement de la saison : rang, ▲▼, visage, justesse, récolte nette.
struct PronoSeasonRow: View {
    let row: PronoSeason.Row
    var mine = false

    var body: some View {
        let h = harvestText(row.harvestNet)
        let pct = row.played > 0 ? Int((Double(row.right) / Double(row.played) * 100).rounded()) : 0
        HStack(spacing: 10) {
            Text("\(row.rank)").font(.title3.weight(.heavy).width(.expanded)).monospacedDigit().foregroundStyle(PronoTheme.t2).frame(minWidth: 22)
            move.frame(width: 30)
            Initials(name: row.user.name, photo: row.user.photo, size: 36)
                .overlay(Circle().stroke(mine ? PronoTheme.lav : .clear, lineWidth: 2))
            VStack(alignment: .leading, spacing: 1) {
                Text(row.user.label).font(.body.weight(.semibold)).foregroundStyle(PronoTheme.t1).lineLimit(1)
                Text("\(row.right)/\(row.played) justes · \(pct) %").font(.footnote).foregroundStyle(PronoTheme.t2)
            }
            Spacer(minLength: 6)
            Text(h.0).font(.headline.weight(.heavy).width(.expanded)).monospacedDigit().foregroundStyle(h.1)
        }
        .padding(.horizontal, 12)
        .frame(minHeight: 60)
        .background(mine ? PronoTheme.lav.opacity(0.10) : .clear, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(mine ? PronoTheme.lav.opacity(0.45) : .clear, lineWidth: 1.5))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(row.rank)\(row.rank == 1 ? "er" : "e"), \(row.user.label), \(row.right) justes sur \(row.played), récolte \(row.harvestNet) patates\(moveA11y)")
    }

    @ViewBuilder private var move: some View {
        if let m = row.move, m != 0 {
            Text(m > 0 ? "▲\(m)" : "▼\(-m)").font(.caption.weight(.heavy)).foregroundStyle(m > 0 ? PronoTheme.mint : PronoTheme.t2)
        } else {
            Text("").font(.caption)
        }
    }

    private var moveA11y: String {
        guard let m = row.move, m != 0 else { return "" }
        return m > 0 ? ", monte de \(m)" : ", descend de \(-m)"
    }
}

/// Classement de la saison du groupe (4-classement) : mois, podium, titres du mois, toute la saison, ton sac.
struct PronoSeasonView: View {
    @ObservedObject var store: PronosStore
    let group: String
    let terrain: PronoTerrain
    let bag: PronoBag?
    @State private var month = PronoDates.monthKey(Date())
    @State private var season: PronoSeason?
    @State private var error: String?
    @State private var bagSheet: PronoTerrain?
    @State private var shown = false
    @Environment(\.accessibilityReduceMotion) private var reduce

    private var months: [Date] {
        let c = PronoDates.calendar
        let start = c.date(from: c.dateComponents([.year, .month], from: Date())) ?? Date()
        return (0..<4).reversed().compactMap { c.date(byAdding: .month, value: -$0, to: start) }
    }

    private var monthDate: Date { PronoDates.day(month) ?? Date() }
    private var isCurrent: Bool { month == PronoDates.monthKey(Date()) }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Classement · \(terrain.emoji) \(terrain.name)".uppercased()).font(.caption2.weight(.bold)).kerning(0.9).foregroundStyle(PronoTheme.t2)
                    Text("Saison \(PronoDates.ofMonth(monthDate))").font(.system(.largeTitle, design: .rounded).weight(.heavy)).foregroundStyle(PronoTheme.t1)
                        .accessibilityAddTraits(.isHeader)
                    Text(isCurrent ? "En cours · encore \(PronoDates.daysLeftInMonth()) jours · \(season?.rows.count ?? 0) joueurs" : "Terminée · \(season?.rows.count ?? 0) joueurs")
                        .font(.subheadline).foregroundStyle(PronoTheme.t2)
                }
                .padding(.top, 12)
                monthPicker.padding(.top, 16)
                if let error { Text(error).font(.footnote).foregroundStyle(PronoTheme.pink).padding(.top, 8) }
                if let season {
                    let rows = season.rows
                    PronoPodium(entries: rows.prefix(3).map { r in
                        let h = harvestText(r.harvestNet)
                        return PronoPodiumEntry(face: r.user, value: h.0, tone: h.1, sub: "\(r.right) juste\(r.right > 1 ? "s" : "") sur \(r.played)")
                    }, color: terrain.color, big: true)
                    .id(month)
                    .padding(.top, 28)
                    if rows.isEmpty {
                        Text("Pas encore de prono réglé ce mois-ci.").font(.subheadline).foregroundStyle(PronoTheme.t2)
                            .frame(maxWidth: .infinity).padding(.top, 12)
                    } else {
                        titles(rows)
                        PronoCaps(text: "Toute la saison", trailing: "Récolte nette").padding(.top, 12).padding(.bottom, 10)
                        VStack(spacing: 0) {
                            ForEach(Array(rows.enumerated()), id: \.element.id) { i, r in
                                if i > 0 && r.user.me != true && rows[i - 1].user.me != true {
                                    Rectangle().fill(PronoTheme.line).frame(height: 1).padding(.leading, 120)
                                }
                                PronoSeasonRow(row: r, mine: r.user.me == true)
                                    .offset(y: shown || reduce ? 0 : CGFloat((r.move ?? 0)) * 60)
                                    .opacity(shown || reduce ? 1 : 0)
                            }
                        }
                        .padding(8)
                        .background(PronoTheme.s1, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
                        .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).stroke(PronoTheme.line, lineWidth: 1))
                    }
                } else {
                    ProgressView().frame(maxWidth: .infinity).padding(.top, 60)
                }
                (Text("Comment on classe ? ").bold().foregroundColor(PronoTheme.t1)
                 + Text("À la récolte nette de la saison : ce que tes pronos t'ont rendu, moins ce que tu as planté. Ton sac n'y compte pas. Nouvelle saison le 1er de chaque mois."))
                    .font(.subheadline).foregroundStyle(PronoTheme.t2)
                    .padding(18)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(PronoTheme.s1, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).stroke(PronoTheme.line, lineWidth: 1))
                    .padding(.top, 16)
                if let bag {
                    Button { PronoHaptics.soft(); bagSheet = terrain } label: {
                        HStack(spacing: 14) {
                            Text("🥔").font(.title2).frame(width: 52, height: 52).background(PronoTheme.s3, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Ton sac").font(.headline).foregroundStyle(PronoTheme.t1)
                                Text(bag.balance >= 100 ? "Ton sac est plein" : "Remonte à 100 lundi s'il est en dessous").font(.footnote).foregroundStyle(PronoTheme.t2)
                            }
                            Spacer(minLength: 6)
                            PronoPotatoNumber(value: bag.balance, size: 28)
                        }
                        .padding(16)
                        .background(PronoTheme.s1, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                        .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).stroke(PronoTheme.line, lineWidth: 1))
                    }
                    .buttonStyle(PressableStyle(scale: 0.98))
                    .accessibilityIdentifier("prono-season-bag")
                    .padding(.top, 14)
                }
                PronoNoValue().padding(.top, 16)
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 32)
        }
        .background(alignment: .top) {
            ZStack(alignment: .top) {
                PronoTheme.bg
                let g = GroupLook.gradient(terrain.color)
                LinearGradient(colors: [g.to.opacity(0.55), .clear], startPoint: .top, endPoint: .bottom).frame(height: 300)
            }
            .ignoresSafeArea()
        }
        .navigationTitle("")
        .navigationBarTitleDisplayMode(.inline)
        .task(id: month) { await load() }
        .sheet(item: $bagSheet) { t in PronoBagSheet(store: store, terrain: t, planted: nil, settled: []) }
    }

    private var monthPicker: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(months, id: \.self) { d in
                    let key = PronoDates.monthKey(d)
                    let on = key == month
                    Button {
                        guard !on else { return }
                        PronoHaptics.selection()
                        shown = false
                        month = key
                    } label: {
                        Text(key == PronoDates.monthKey(Date()) ? PronoDates.monthName(d).capitalized : PronoDates.monthShort(d))
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(on ? Color(hex: 0x1D1530) : PronoTheme.t1)
                            .padding(.horizontal, 16).frame(minHeight: 44)
                            .background(on ? AnyShapeStyle(PronoTheme.t1) : AnyShapeStyle(PronoTheme.s3), in: Capsule())
                            .overlay(Capsule().stroke(on ? .clear : PronoTheme.line, lineWidth: 1))
                    }
                    .buttonStyle(PressableStyle())
                    .accessibilityAddTraits(on ? .isSelected : [])
                    .accessibilityLabel("Saison " + PronoDates.ofMonth(d))
                    .accessibilityIdentifier("prono-month-" + String(key.prefix(7)))
                }
            }
        }
    }

    /// Titres du mois, tirés du classement seul (aucune donnée de plus) : justesse, assiduité, plus belle montée.
    @ViewBuilder private func titles(_ rows: [PronoSeason.Row]) -> some View {
        let pct: (PronoSeason.Row) -> Double = { $0.played > 0 ? Double($0.right) / Double($0.played) : 0 }
        let seer = rows.filter { $0.played >= 3 }.max { pct($0) < pct($1) }
        let busy = rows.max { $0.played < $1.played }
        let climber = rows.filter { ($0.move ?? 0) > 0 }.max { ($0.move ?? 0) < ($1.move ?? 0) }
        let items: [(String, String, PronoFace, String)] = [
            seer.map { ("🔮", "Voyant·e du mois", $0.user, "\(Int((pct($0) * 100).rounded())) % de justesse") },
            busy.map { ("🎯", "Toujours là", $0.user, "\($0.played) pronos joués") },
            climber.map { ("🚀", "Belle montée", $0.user, "▲\($0.move ?? 0) places") },
        ].compactMap { $0 }
        if !items.isEmpty {
            PronoCaps(text: "Les titres du mois").padding(.top, 20).padding(.bottom, 10)
            HStack(alignment: .top, spacing: 10) {
                ForEach(Array(items.enumerated()), id: \.offset) { i, t in
                    VStack(alignment: .leading, spacing: 8) {
                        Text(t.0).font(.title2)
                        Text(t.1).font(.footnote.weight(.bold)).foregroundStyle(PronoTheme.t2).fixedSize(horizontal: false, vertical: true)
                        HStack(spacing: 6) {
                            Initials(name: t.2.name, photo: t.2.photo, size: 24)
                            Text(t.2.label).font(.subheadline.weight(.bold)).foregroundStyle(PronoTheme.t1).lineLimit(1)
                        }
                        Text(t.3).font(.caption).foregroundStyle(PronoTheme.t2)
                    }
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .topLeading)
                    .background(PronoTheme.s1, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).stroke(PronoTheme.line, lineWidth: 1))
                    .accessibilityElement(children: .combine)
                    .opacity(shown || reduce ? 1 : 0)
                    .offset(y: shown || reduce ? 0 : 12)
                    .animation(Motion.pick(.easeOut(duration: 0.4).delay(Double(i) * 0.06)), value: shown)
                }
            }
        }
    }

    private func load() async {
        do {
            let s = try await store.season(groupID: group, month: month)
            season = s
            error = nil
            // Les lignes glissent depuis leur ancien rang, après le podium.
            if reduce { shown = true } else {
                try? await Task.sleep(nanoseconds: 1_250_000_000)
                withAnimation(.spring(response: 0.55, dampingFraction: 0.82)) { shown = true }
            }
        } catch {
            self.error = PronosStore.message(error)
        }
    }
}

// MARK: - Classement aux points

/// Classement du groupe aux points (onglet « Points ») : podium 2-1-3 puis la liste.
struct PronoBoardView: View {
    let board: PronoBoard
    @ObservedObject var store: PronosStore
    let group: String
    let reload: () async -> Void
    @State private var confirmReset = false

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("\(board.since.map { "Depuis le \(PronoFormat.short($0))" } ?? "Depuis le début") · \(board.pronos) prono\(board.pronos > 1 ? "s" : "")")
                .font(.footnote).foregroundStyle(PronoTheme.t2)
            if board.rows.isEmpty {
                VStack(spacing: 6) {
                    PronoPodium(entries: [], color: "lavender")
                    Text("Pas encore de points").font(.headline).foregroundStyle(PronoTheme.t1)
                    Text("Le classement se remplit à chaque résultat donné.").font(.footnote).foregroundStyle(PronoTheme.t2)
                }
                .frame(maxWidth: .infinity).padding(16)
                .background(PronoTheme.s1, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
            } else {
                PronoPodium(entries: board.rows.prefix(3).map {
                    PronoPodiumEntry(face: $0.user, value: PronoFormat.points($0.points), tone: PronoTheme.gold, sub: "\($0.right) sur \($0.played)")
                }, color: "lavender")
                .padding(.vertical, 8)
                VStack(spacing: 0) {
                    ForEach(Array(board.rows.enumerated()), id: \.element.id) { i, row in
                        if i > 0 { Rectangle().fill(PronoTheme.line).frame(height: 1).padding(.leading, 90) }
                        HStack(spacing: 12) {
                            Text("\(i + 1)").font(.title3.weight(.heavy).width(.expanded)).monospacedDigit().foregroundStyle(PronoTheme.t2).frame(minWidth: 26)
                            Initials(name: row.user.name, photo: row.user.photo, size: 36)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(row.user.label).font(.body.weight(.semibold)).foregroundStyle(PronoTheme.t1)
                                Text("\(row.right) juste\(row.right > 1 ? "s" : "") sur \(row.played)").font(.footnote).foregroundStyle(PronoTheme.t2)
                            }
                            Spacer()
                            Text("\(row.points)").font(.headline.weight(.heavy).width(.expanded)).monospacedDigit().foregroundStyle(PronoTheme.gold)
                        }
                        .padding(.horizontal, 12).frame(minHeight: 60)
                        .background(row.user.me == true ? PronoTheme.lav.opacity(0.10) : .clear, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(row.user.me == true ? PronoTheme.lav.opacity(0.45) : .clear, lineWidth: 1.5))
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel("\(i + 1)\(i == 0 ? "er" : "e"), \(row.user.label), \(PronoFormat.points(row.points)), \(row.right) justes sur \(row.played)")
                    }
                }
                .padding(8)
                .background(PronoTheme.s1, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).stroke(PronoTheme.line, lineWidth: 1))
                if board.manage {
                    Button(role: .destructive) { confirmReset = true } label: { Text("Remettre les points à zéro").frame(maxWidth: .infinity, minHeight: 44) }
                        .buttonStyle(.bordered)
                        .accessibilityIdentifier("prono-board-reset")
                        .confirmationDialog("Repartir de zéro ?", isPresented: $confirmReset, titleVisibility: .visible) {
                            Button("Oui, repartir de zéro", role: .destructive) {
                                Task { try? await store.run("prono_board_reset", ["group_id": group]); await reload() }
                            }
                        } message: { Text("Les points de tout le groupe repartent de zéro. Les pronos restent.") }
                }
            }
        }
    }
}

// MARK: - Sac (1-sac)

/// Feuille « Ton sac » : solde en jauge ronde, prochaine remontée, tuiles, comment ça marche, historique à soi seul.
struct PronoBagSheet: View {
    @ObservedObject var store: PronosStore
    let terrain: PronoTerrain
    /// Plantées en ce moment (cartes de la liste) ; nil : calculé depuis l'historique.
    let planted: (n: Int, pronos: Int)?
    /// Pronos terminés (« parties au compost » sur les plantations sans récolte ni retour).
    let settled: Set<String>
    @Environment(\.dismiss) private var dismiss
    @Environment(\.accessibilityReduceMotion) private var reduce
    @State private var bag: PronoBag?
    @State private var history: [PronoBagMove] = []
    @State private var me: PronoSeason.Row?
    @State private var fill: Double = 0
    @State private var error: String?
    @ScaledMetric(relativeTo: .largeTitle) private var big: CGFloat = 64

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 0) {
                    HStack(spacing: 8) {
                        PronoTerrainDot(emoji: terrain.emoji, color: terrain.color, size: 30)
                        Text(terrain.name).font(.subheadline.weight(.semibold)).foregroundStyle(PronoTheme.t2).lineLimit(1)
                    }
                    .padding(.leading, 4).padding(.trailing, 14).frame(height: 40)
                    .background(PronoTheme.s3, in: Capsule()).overlay(Capsule().stroke(PronoTheme.line, lineWidth: 1))
                    Text("Ton sac").font(.system(.title, design: .rounded).weight(.heavy)).foregroundStyle(PronoTheme.t1)
                        .padding(.top, 12).accessibilityAddTraits(.isHeader)
                    if let error { Text(error).font(.footnote).foregroundStyle(PronoTheme.pink).padding(.top, 8) }
                    if let bag {
                        gauge(bag).padding(.top, 8)
                        refill(bag).padding(.top, 16)
                        tiles(bag).padding(.top, 20)
                    } else if error == nil {
                        ProgressView().frame(height: 240)
                    }
                    howItWorks.padding(.top, 8)
                    historyList
                    PronoNoValue(block: true).padding(.top, 20)
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 32)
            }
            .background(PronoTheme.s1.ignoresSafeArea())
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button { dismiss() } label: {
                        Image(systemName: "xmark").font(.footnote.weight(.bold)).foregroundStyle(PronoTheme.t1)
                            .frame(width: 32, height: 32).background(PronoTheme.s3, in: Circle())
                            .frame(width: 44, height: 44)
                    }
                    .accessibilityLabel("Fermer le sac")
                    .accessibilityIdentifier("prono-bag-close")
                }
            }
        }
        .presentationDetents([.large])
        .presentationDragIndicator(.visible)
        .preferredColorScheme(.dark)
        .accessibilityIdentifier("prono-bag-sheet")
        .task { await load() }
    }

    private func gauge(_ bag: PronoBag) -> some View {
        let g = GroupLook.gradient(terrain.color)
        return VStack(spacing: 4) {
            Text("100").font(.caption.weight(.semibold)).foregroundStyle(PronoTheme.t2).accessibilityHidden(true)
            ZStack {
                Circle().stroke(PronoTheme.line2, lineWidth: 14)
                Circle().trim(from: 0, to: fill)
                    .stroke(AngularGradient(colors: [g.from, g.to, g.from], center: .center), style: StrokeStyle(lineWidth: 14, lineCap: .round))
                    .rotationEffect(.degrees(-90))
                VStack(spacing: 4) {
                    Text("\(bag.balance)").font(.system(size: big, weight: .heavy).width(.expanded)).monospacedDigit()
                        .contentTransition(.numericText()).foregroundStyle(PronoTheme.t1)
                    Text("🥔 dans ton sac").font(.footnote.weight(.semibold)).foregroundStyle(PronoTheme.t2)
                }
            }
            .frame(width: 196, height: 196)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(bag.balance) patates dans ton sac")
    }

    private func refill(_ bag: PronoBag) -> some View {
        Label(bag.balance >= 100 ? "Ton sac est plein" : "Remonte à 100 \(PronoDates.refill(bag.refillAt))", systemImage: "arrow.clockwise")
            .font(.subheadline.weight(.semibold)).foregroundStyle(PronoTheme.lav)
            .padding(.horizontal, 14).frame(minHeight: 32)
            .background(PronoTheme.lav.opacity(0.12), in: Capsule())
            .overlay(Capsule().stroke(PronoTheme.lav.opacity(0.3), lineWidth: 1))
    }

    private var plantedNow: (n: Int, pronos: Int) {
        if let planted { return planted }
        var by: [String: Int] = [:]
        for m in history where m.prono != nil && !settled.contains(m.prono!.id) {
            switch m.reason {
            case "plant", "unplant": by[m.prono!.id, default: 0] -= m.delta
            case "harvest", "refund": by[m.prono!.id] = nil
            default: break
            }
        }
        let live = by.values.filter { $0 > 0 }
        return (live.reduce(0, +), live.count)
    }

    private func tiles(_ bag: PronoBag) -> some View {
        let p = plantedNow
        let harvest = bag.season?.harvestNet ?? 0
        return HStack(spacing: 8) {
            tile("Plantées", value: PronoPotatoNumber(value: p.n, size: 22), sub: p.pronos > 0 ? "dans \(p.pronos) prono\(p.pronos > 1 ? "s" : "")" : "rien en terre")
            tile("Récolte", value: PronoPotatoNumber(value: harvest, size: 22, sign: true, tone: harvest > 0 ? PronoTheme.mint : PronoTheme.t1), sub: "en \(PronoDates.monthName(Date()))")
            if let me {
                tile("Justesse", value: Text("\(me.right)/\(me.played)").font(.system(size: 22, weight: .heavy).width(.expanded)).monospacedDigit().foregroundStyle(PronoTheme.t1), sub: "vues justes")
            }
        }
    }

    private func tile<V: View>(_ title: String, value: V, sub: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title.uppercased()).font(.caption2.weight(.bold)).kerning(0.8).foregroundStyle(PronoTheme.t2)
            value
            Text(sub).font(.caption).foregroundStyle(PronoTheme.t2).lineLimit(1)
        }
        .padding(12)
        .frame(maxWidth: .infinity, minHeight: 92, alignment: .leading)
        .background(PronoTheme.s3, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(PronoTheme.line, lineWidth: 1))
        .accessibilityElement(children: .combine)
    }

    private var howItWorks: some View {
        VStack(alignment: .leading, spacing: 0) {
            PronoCaps(text: "Comment ça marche").padding(.bottom, 10)
            VStack(spacing: 0) {
                how("🥔", Text("100 patates").bold() + Text(" au départ, un sac par groupe et par soirée."))
                Rectangle().fill(PronoTheme.line).frame(height: 1).padding(.leading, 56)
                how("↻", Text("Chaque ") + Text("lundi").bold() + Text(", ton sac remonte à 100 s'il est plus bas."))
                Rectangle().fill(PronoTheme.line).frame(height: 1).padding(.leading, 56)
                how("🌱", Text("Plante ") + Text("1 à 20 🥔").bold() + Text(" par prono. Ceux qui voient juste se partagent le champ."))
            }
            .padding(.horizontal, 12)
            .background(PronoTheme.s3, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).stroke(PronoTheme.line, lineWidth: 1))
        }
    }

    private func how(_ icon: String, _ text: Text) -> some View {
        HStack(spacing: 12) {
            Text(icon).font(.body).frame(width: 32, height: 32).background(PronoTheme.bg.opacity(0.6), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                .accessibilityHidden(true)
            text.font(.subheadline).foregroundStyle(PronoTheme.t2)
            Spacer(minLength: 0)
        }
        .padding(.vertical, 10)
        .frame(minHeight: 48)
    }

    @ViewBuilder private var historyList: some View {
        let days = groupedHistory
        HStack {
            PronoCaps(text: "Ton historique")
            Label("toi seul le vois", systemImage: "lock.fill").font(.footnote.weight(.semibold)).foregroundStyle(PronoTheme.t2).padding(.top, 16)
        }
        .padding(.top, 12).padding(.bottom, 4)
        if days.isEmpty {
            Text("Rien pour l'instant : plante tes premières patates sur un prono.").font(.subheadline).foregroundStyle(PronoTheme.t2)
                .frame(maxWidth: .infinity, alignment: .leading).padding(.vertical, 8)
        }
        ForEach(days, id: \.title) { day in
            Text(day.title).font(.footnote.weight(.semibold)).foregroundStyle(PronoTheme.t2)
                .frame(maxWidth: .infinity, alignment: .leading).padding(.top, 14).padding(.bottom, 8)
            VStack(spacing: 0) {
                ForEach(Array(day.moves.enumerated()), id: \.offset) { i, m in
                    if i > 0 { Rectangle().fill(PronoTheme.line).frame(height: 1).padding(.leading, 60) }
                    moveRow(m)
                }
            }
            .padding(.horizontal, 12)
            .background(PronoTheme.s3, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).stroke(PronoTheme.line, lineWidth: 1))
        }
    }

    private var groupedHistory: [(title: String, moves: [PronoBagMove])] {
        var out: [(title: String, moves: [PronoBagMove])] = []
        let c = PronoDates.calendar
        var lastDay: Date?
        for m in history.sorted(by: { (PronoFormat.date($0.at) ?? .distantPast) > (PronoFormat.date($1.at) ?? .distantPast) }) {
            let d = PronoFormat.date(m.at) ?? Date()
            if let last = lastDay, c.isDate(last, inSameDayAs: d) {
                out[out.count - 1].moves.append(m)
            } else {
                out.append((PronoDates.dayHeader(d), [m]))
                lastDay = d
            }
        }
        return out
    }

    /// Une plantation d'un prono terminé sans récolte ni retour : « parties au compost ».
    private func composted(_ m: PronoBagMove) -> Bool {
        guard m.reason == "plant", let id = m.prono?.id, settled.contains(id) else { return false }
        return !history.contains { $0.prono?.id == id && ($0.reason == "harvest" || $0.reason == "refund") }
    }

    private func moveRow(_ m: PronoBagMove) -> some View {
        let info: (icon: String, title: String, sub: String?, tone: Color) = {
            switch m.reason {
            case "plant": return ("🌱", composted(m) ? "Plantées · parties au compost" : "Plantées", m.prono?.question, PronoTheme.t1)
            case "unplant": return ("↩︎", "Reprises", m.prono?.question, PronoTheme.lav)
            case "refund": return ("↩︎", "Rendues", m.prono?.question, PronoTheme.lav)
            case "harvest": return ("🧺", "Ta récolte", m.prono?.question, PronoTheme.mint)
            case "refill": return ("↻", "Remontée du lundi", "Ton sac est revenu à 100", PronoTheme.mint)
            default: return ("🥔", "Sac de départ", "100 patates pour commencer", PronoTheme.mint)
            }
        }()
        return HStack(spacing: 12) {
            Text(info.icon).font(.body).frame(width: 36, height: 36).background(PronoTheme.bg.opacity(0.6), in: Circle()).accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 1) {
                Text(info.title).font(.body.weight(.semibold)).foregroundStyle(PronoTheme.t1)
                if let sub = info.sub { Text(sub).font(.footnote).foregroundStyle(PronoTheme.t2).lineLimit(1) }
            }
            Spacer(minLength: 6)
            Text(m.delta > 0 ? "+\(m.delta)" : "−\(-m.delta)")
                .font(.body.weight(.heavy).width(.expanded)).monospacedDigit().foregroundStyle(info.tone)
        }
        .padding(.vertical, 10)
        .frame(minHeight: 60)
        .accessibilityElement(children: .combine)
    }

    private func load() async {
        do {
            let b = try await store.bag(groupID: terrain.groupID, eventID: terrain.eventID)
            bag = b
            withAnimation(Motion.pick(.timingCurve(0.22, 1, 0.36, 1, duration: 0.7), reduced: reduce)) { fill = min(1, Double(b.balance) / 100) }
            error = nil
        } catch {
            self.error = PronosStore.message(error)
        }
        history = (try? await store.bagHistory(groupID: terrain.groupID, eventID: terrain.eventID)) ?? []
        if let g = terrain.groupID { me = (try? await store.season(groupID: g, month: nil))?.me }
    }
}

// MARK: - Ouverture par la page web ou une notification

/// Pronos ouverts par la page web (PartyNative.pronos) ou une notification : liste, prono ou création, par-dessus la page.
struct PronoRouteView: View {
    @ObservedObject var store: PronosStore
    @State var route: PronoRoute
    let close: () -> Void

    var body: some View {
        NavigationStack {
            Group {
                switch route {
                case .list(let group): PronosListView(store: store, group: group)
                case .open(let id): PronoDetailView(store: store, id: id)
                case .create(let group, let event):
                    PronoNewView(store: store, group: group, event: event) { id in Motion.animate(Motion.smooth) { route = .open(id) } }
                }
            }
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button { close() } label: { Image(systemName: "xmark").font(.body.weight(.semibold)) }
                        .accessibilityLabel("Fermer les pronos")
                        .accessibilityIdentifier("pronos-close")
                }
            }
        }
        .preferredColorScheme(.dark)
    }
}

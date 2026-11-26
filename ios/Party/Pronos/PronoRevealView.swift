// Compilé dans la BETA seulement (et les recettes E2E_HOOKS) : absent du binaire de l'App Store (Pronos, contrôle Apple du 26.11).
#if BETA || E2E_HOOKS

import SwiftUI
import UIKit

// Pronos v2 (18.11.2026, direction C « Néon club ») : le dévoilement, rituel joué UNE fois par prono et par personne
// (maquettes 4-devoilement et 4-trophee), puis la fiche montre le résultat (PronoDetailView). Les patates sont fictives,
// gratuites et sans valeur : on dit « planter », « le champ », « ta récolte », « au compost », « rendues ».

/// Rend facultatif un champ que le store déclare facultatif ou non (les clés v2 sont « toutes facultatives côté écran »).
func pronoOpt<T>(_ value: T?) -> T? { value }

/// Couleurs de la direction C (sombre / clair), d'après l'en-tête des maquettes 3- et 4-.
enum PronoInk {
    static func dyn(_ dark: UInt32, _ light: UInt32, _ darkAlpha: CGFloat = 1, _ lightAlpha: CGFloat = 1) -> Color {
        Color(UIColor { $0.userInterfaceStyle == .light ? ui(light, lightAlpha) : ui(dark, darkAlpha) })
    }

    private static func ui(_ hex: UInt32, _ alpha: CGFloat) -> UIColor {
        UIColor(red: CGFloat((hex >> 16) & 0xFF) / 255, green: CGFloat((hex >> 8) & 0xFF) / 255, blue: CGFloat(hex & 0xFF) / 255, alpha: alpha)
    }

    static let bg = dyn(0x0E0A1F, 0xF6F3FF)
    static let scene = dyn(0x0A0718, 0xF6F3FF)
    static let s1 = dyn(0x1A1433, 0xFFFFFF)
    static let glass = dyn(0xFFFFFF, 0xFFFFFF, 0.06, 0.72)
    static let line = dyn(0xFFFFFF, 0x1A1433, 0.10, 0.09)
    static let t1 = dyn(0xF4F1FF, 0x1A1433)
    static let t2 = dyn(0xA79FC7, 0x5B547A)
    static let t3 = dyn(0x8C84AE, 0x6E6790)
    static let lavender = dyn(0xB9A7FF, 0x6A5AE0)
    static let lavenderDeep = Color(hex: 0x7B6CF6)
    static let mint = dyn(0x5BE3A6, 0x16865A)
    static let crown = dyn(0xFFE27A, 0x8A6A00)
    static let gold = Color(hex: 0xFFE27A)
    static let miss = Color(hex: 0x8B84A8)
    static let soon = dyn(0xFFB347, 0xB86A00)
    static let retreat = dyn(0xFF7A8A, 0xC8324A)
    static let patate = dyn(0xF5C27A, 0xA0601A)
    static let patateFill = Color(hex: 0xF5C27A)
    static let onPatate = Color(hex: 0x2A1A06)
    static let actionFrom = Color(hex: 0xF2468F)
    static let action = Color(hex: 0xD42A76)

    /// Couleur d'une forme : ▲ rose, ◆ ciel, ● orange, ■ lavande, ⬢ menthe, ★ citron.
    static func shape(_ i: Int) -> Color {
        switch i % 6 {
        case 0: return dyn(0xFF6FAE, 0xC8327A)
        case 1: return dyn(0x6CC7FF, 0x1F6FD1)
        case 2: return dyn(0xFFB347, 0xB86A00)
        case 3: return dyn(0xB9A7FF, 0x6A5AE0)
        case 4: return dyn(0x5BE3A6, 0x16865A)
        default: return dyn(0xFFE27A, 0x8A6A00)
        }
    }
}

/// Forme + couleur + nom d'une réponse : la couleur seule ne porte jamais l'information.
struct PronoMark: Hashable {
    let symbol: String
    let color: Color
    let name: String

    static let shapes = ["triangle.fill", "diamond.fill", "circle.fill", "square.fill", "hexagon.fill", "star.fill"]
    static let names = ["triangle", "losange", "rond", "carré", "hexagone", "étoile"]

    static func of(kind: String, index: Int) -> PronoMark {
        switch (kind, index) {
        case ("yesno", 0): return PronoMark(symbol: "checkmark", color: PronoInk.shape(1), name: "oui")
        case ("yesno", _): return PronoMark(symbol: "xmark", color: PronoInk.shape(0), name: "non")
        case ("overunder", 0): return PronoMark(symbol: "arrowtriangle.up.fill", color: PronoInk.shape(2), name: "plus")
        case ("overunder", _): return PronoMark(symbol: "arrowtriangle.down.fill", color: PronoInk.shape(3), name: "moins")
        default: return PronoMark(symbol: shapes[index % 6], color: PronoInk.shape(index), name: names[index % 6])
        }
    }
}

/// Tuile d'une forme (pastilles de réponse, dévoilement).
struct PronoMarkTile: View {
    let mark: PronoMark
    var size: CGFloat = 44
    var filled = false
    var tint: Color?

    var body: some View {
        let color = tint ?? mark.color
        RoundedRectangle(cornerRadius: size * 0.32, style: .continuous)
            .fill(filled ? AnyShapeStyle(color) : AnyShapeStyle(color.opacity(0.16)))
            .overlay(Image(systemName: mark.symbol).font(.system(size: size * 0.4, weight: .heavy)).foregroundStyle(filled ? Color(hex: 0x1D1530) : color))
            .frame(width: size, height: size)
            .accessibilityHidden(true)
    }
}

/// Lecture des réponses, quel que soit le type.
enum PronoRead {
    static let optionKinds: Set<String> = ["choice", "yesno", "overunder", "majority"]
    static let zurich = TimeZone(identifier: "Europe/Zurich") ?? .current

    static func time(_ iso: String?) -> String {
        guard let iso, let d = PronoFormat.date(iso) else { return "—" }
        return time(d)
    }

    static func time(_ d: Date) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "fr_CH")
        f.timeZone = zurich
        f.dateFormat = "HH:mm"
        return f.string(from: d)
    }

    /// « ce soir, 21 h », « demain 18 h 30 », « samedi 21 h », « sam. 21.11 à 21 h ».
    static func moment(_ d: Date) -> String {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = zurich
        let f = DateFormatter()
        f.locale = Locale(identifier: "fr_CH")
        f.timeZone = zurich
        let minute = cal.component(.minute, from: d)
        let hour = "\(cal.component(.hour, from: d)) h\(minute > 0 ? String(format: " %02d", minute) : "")"
        if cal.isDateInToday(d) { return cal.component(.hour, from: d) >= 18 ? "ce soir, \(hour)" : "aujourd'hui, \(hour)" }
        if cal.isDateInTomorrow(d) { return "demain \(hour)" }
        if let days = cal.dateComponents([.day], from: Date(), to: d).day, days < 6 {
            f.dateFormat = "EEEE"
            return "\(f.string(from: d)) \(hour)"
        }
        f.dateFormat = "EEE d.MM"
        return "\(f.string(from: d)) à \(hour)"
    }

    /// « 11 h », « 23 min », « 2 j » jusqu'à une date.
    static func remaining(_ iso: String?) -> String? {
        guard let iso, let d = PronoFormat.date(iso) else { return nil }
        let s = d.timeIntervalSinceNow
        guard s > 0 else { return nil }
        if s >= 86_400 { return "\(Int(s / 86_400)) j" }
        if s >= 3_600 { return "\(Int(s / 3_600)) h" }
        return "\(max(1, Int(s / 60))) min"
    }

    static func answer(_ p: Prono, option: String?, number: Double?, text: String?, person: PronoFace?, personId: String?, at: String?) -> String {
        if optionKinds.contains(p.kind) { return p.options.first { $0.id == option }?.label ?? "—" }
        switch p.kind {
        case "number": return number.map(PronoFormat.number) ?? "—"
        case "when": return time(at)
        case "person", "award": return (person ?? p.candidates?.first { $0.id == personId })?.label ?? "—"
        default: return text ?? "Réponse masquée"
        }
    }

    static func mine(_ p: Prono) -> String? {
        guard let m = p.myAnswer else { return nil }
        return answer(p, option: m.optionId, number: m.number, text: m.text, person: nil, personId: m.personId, at: m.answerAt)
    }

    static func result(_ p: Prono) -> String {
        if optionKinds.contains(p.kind) {
            return (p.options.first { $0.correct == true } ?? p.options.first { $0.id == p.result?.optionId })?.label ?? ""
        }
        switch p.kind {
        case "number": return p.result?.number.map(PronoFormat.number) ?? ""
        case "when": return pronoOpt(p.result?.time).map { time($0) } ?? ""
        case "person", "award": return (p.result?.person ?? p.winners?.first)?.label ?? ""
        default: return ""
        }
    }

    static func markIndex(_ p: Prono, option: String?) -> Int? { p.options.firstIndex { $0.id == option } }

    static func value(_ p: Prono, _ a: PronoShownAnswer) -> Double? {
        p.kind == "when" ? pronoOpt(a.answerAt).flatMap(PronoFormat.date).map { $0.timeIntervalSince1970 / 60 } : a.number
    }

    static func resultValue(_ p: Prono) -> Double? {
        p.kind == "when" ? pronoOpt(p.result?.time).flatMap(PronoFormat.date).map { $0.timeIntervalSince1970 / 60 } : p.result?.number
    }

    /// Catégorie du trophée (« 💃 Roi / Reine de la piste ») : son emoji et son nom.
    static func award(_ p: Prono) -> (emoji: String, name: String) {
        let raw = (pronoOpt(p.award) ?? "").trimmingCharacters(in: .whitespaces)
        guard let first = raw.first, let scalar = first.unicodeScalars.first, scalar.properties.isEmoji, scalar.value > 0x238C else {
            return ("🏆", raw.isEmpty ? "Trophée de la soirée" : raw)
        }
        let rest = raw.dropFirst().trimmingCharacters(in: .whitespaces)
        return (String(first), rest.isEmpty ? "Trophée de la soirée" : rest)
    }

    /// Ma récolte : celle versée par la base, sinon la part du champ selon ce que chacun a planté (arrondi vers le bas).
    static func harvest(_ p: Prono) -> Int {
        if let h = p.myAnswer?.harvest { return h }
        guard p.myAnswer?.winner == true, let stake = p.myAnswer?.stake, stake > 0 else { return 0 }
        let answers = p.answers ?? []
        let winners = answers.filter(\.winner).reduce(0) { $0 + ($1.stake ?? 0) }
        let field = pronoOpt(p.field)?.total ?? answers.reduce(0) { $0 + ($1.stake ?? 0) }
        return winners > 0 ? stake * field / winners : stake
    }
}

/// Paillettes dorées qui montent dans le faisceau (trophée) : jamais de confettis pour un trophée.
struct PronoGoldSparkles: View {
    let start: Date

    var body: some View {
        TimelineView(.animation) { timeline in
            Canvas { ctx, size in
                let elapsed = timeline.date.timeIntervalSince(start)
                for i in 0..<40 {
                    let life = (elapsed - Double(i) * 0.0375) / 1.4
                    guard life > 0, life < 1 else { continue }
                    let seed = Double((i * 7919) % 100) / 100
                    let x = size.width * (0.28 + 0.44 * seed) + sin(life * 6 + Double(i)) * 8
                    let y = size.height * (0.95 - 0.9 * life)
                    let r = 2 + 3 * Double((i * 31) % 10) / 10
                    ctx.opacity = 1 - life
                    ctx.fill(Path(ellipseIn: CGRect(x: x, y: y, width: r, height: r)), with: .color(i % 3 == 0 ? .white : PronoInk.gold))
                }
            }
        }
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }
}

/// Le dévoilement (4-devoilement, 4-trophee). Un toucher n'importe où va à la fin ; « Réduire les animations » et
/// VoiceOver posent l'état final. `onClose` : « Voir tout », « Passer » puis fermer.
struct PronoRevealView: View {
    let prono: Prono
    let patates: Bool
    let onClose: () -> Void

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var t = -1
    @State private var spot = 0
    @State private var spotX: CGFloat = 0
    @State private var shownHarvest = 0
    @State private var sparklesStart: Date?
    @State private var task: Task<Void, Never>?
    @Namespace private var spotlight

    private static let end = 99_999

    // MARK: Données

    struct Row: Identifiable {
        let id: String
        let label: String
        let mark: PronoMark?
        let faces: [PronoFace]
        let count: Int
        let good: Bool
        let stake: Int
    }

    private var answers: [PronoShownAnswer] { prono.answers ?? [] }
    private var players: Int { max(answers.count, prono.answered.count) }
    private var field: Int { pronoOpt(prono.field)?.total ?? answers.reduce(0) { $0 + ($1.stake ?? 0) } }
    private var myStake: Int { prono.myAnswer?.stake ?? 0 }
    private var played: Bool { prono.myAnswer != nil }
    private var right: Bool { prono.myAnswer?.winner == true }
    private var unanimous: Bool { pronoOpt(prono.unanimous) ?? (answers.count > 1 && answers.allSatisfy(\.winner)) }
    private var harvest: Int { PronoRead.harvest(prono) }
    private var rightCount: Int { pronoOpt(prono.rarity)?.right ?? answers.filter(\.winner).count }
    private var ofCount: Int { pronoOpt(prono.rarity)?.of ?? answers.count }

    private var rows: [Row] {
        let byOption = pronoOpt(pronoOpt(prono.field)?.byOption) ?? []
        if PronoRead.optionKinds.contains(prono.kind) {
            return prono.options.enumerated().map { i, o in
                let who = answers.filter { $0.optionId == o.id }
                return Row(id: o.id, label: o.label, mark: .of(kind: prono.kind, index: i), faces: meFirst(who.map(\.user)),
                           count: o.count ?? who.count, good: o.correct == true || prono.result?.optionId == o.id,
                           stake: byOption.first { $0.optionId == o.id }?.total ?? who.reduce(0) { $0 + ($1.stake ?? 0) })
            }
        }
        switch prono.kind {
        case "person":
            let groups = Dictionary(grouping: answers) { $0.person?.id ?? "" }
            return groups.map { key, list in
                Row(id: key, label: list.first?.person?.label ?? "—", mark: nil, faces: meFirst(list.map(\.user)), count: list.count,
                    good: (prono.result?.person?.id ?? prono.winners?.first?.id) == key, stake: list.reduce(0) { $0 + ($1.stake ?? 0) })
            }
            .sorted { ($0.good ? 1 : 0, $0.count) > ($1.good ? 1 : 0, $1.count) }
            .prefix(5).map { $0 }
        case "number", "when":
            let truth = PronoRead.resultValue(prono) ?? 0
            let groups = Dictionary(grouping: answers) { PronoRead.value(prono, $0) ?? .infinity }
            return groups.sorted { abs($0.key - truth) < abs($1.key - truth) }.prefix(5).map { value, list in
                let first = list[0]
                let label = prono.kind == "when" ? PronoRead.time(first.answerAt) : PronoRead.answer(prono, option: nil, number: first.number, text: nil, person: nil, personId: nil, at: nil)
                return Row(id: "\(value)", label: label, mark: nil, faces: meFirst(list.map(\.user)), count: list.count,
                           good: list.contains(where: \.winner), stake: list.reduce(0) { $0 + ($1.stake ?? 0) })
            }
        default:
            return answers.sorted { ($0.winner ? 1 : 0) > ($1.winner ? 1 : 0) }.prefix(6).map { a in
                Row(id: a.user.id, label: a.hidden == true ? "Réponse masquée" : (a.text ?? "—"), mark: nil, faces: [a.user], count: 1, good: a.winner, stake: a.stake ?? 0)
            }
        }
    }

    private func meFirst(_ faces: [PronoFace]) -> [PronoFace] {
        faces.filter { $0.me == true } + faces.filter { $0.me != true }
    }

    private var goodIndex: Int { rows.firstIndex(where: \.good) ?? 0 }

    private var sealFaces: [PronoFace] { Array(meFirst(answers.map(\.user)).prefix(8)) }

    // MARK: Vue

    var body: some View {
        ZStack {
            scene
            if prono.kind == "award" { trophy } else { result }
            if t >= 2150, right, !unanimous, !reduceMotion {
                PronoConfetti().allowsHitTesting(false).accessibilityHidden(true)
            }
            topBar
        }
        .contentShape(Rectangle())
        .onTapGesture { seekEnd() }
        .accessibilityIdentifier("prono-reveal")
        .onAppear(perform: start)
        .onDisappear { task?.cancel() }
        .preferredColorScheme(.dark)
    }

    private var scene: some View {
        let g = GroupLook.gradient(prono.group?.color)
        return ZStack {
            PronoInk.scene
            Circle().fill(prono.kind == "award" ? PronoInk.gold.opacity(0.18) : g.to.opacity(0.35)).frame(width: 320).blur(radius: 60).offset(x: -120, y: -320)
            Circle().fill(prono.kind == "award" ? Color.clear : PronoInk.lavenderDeep.opacity(0.35)).frame(width: 300).blur(radius: 60).offset(x: 140, y: -280)
            RadialGradient(colors: [.clear, .black.opacity(0.55)], center: .center, startRadius: 180, endRadius: 520)
                .opacity(t >= 0 ? 1 : 0)
        }
        .ignoresSafeArea()
        .accessibilityHidden(true)
    }

    private var topBar: some View {
        VStack {
            HStack {
                Button { onClose() } label: {
                    Image(systemName: "chevron.left").font(.body.weight(.bold)).foregroundStyle(PronoInk.t1)
                        .frame(width: 44, height: 44).background(.ultraThinMaterial, in: Circle())
                }
                .accessibilityLabel("Fermer le dévoilement")
                Spacer()
                if t < 2600 {
                    Button("Passer") { seekEnd() }
                        .font(.subheadline.weight(.bold)).foregroundStyle(PronoInk.t1)
                        .padding(.horizontal, 16).frame(minHeight: 44)
                        .background(.ultraThinMaterial, in: Capsule())
                        .accessibilityIdentifier("prono-reveal-skip")
                        .transition(.opacity)
                }
            }
            .padding(.horizontal, 16)
            Spacer()
        }
    }

    private var place: some View {
        HStack(spacing: 6) {
            if let g = prono.group { Text(g.emoji); Text(g.name) } else if let e = prono.event { Text("🎉"); Text(e.title) }
        }
        .font(.subheadline.weight(.semibold)).foregroundStyle(PronoInk.t1)
        .padding(.horizontal, 14).frame(minHeight: 34)
        .background((prono.kind == "award" ? Color.white.opacity(0.06) : GroupLook.gradient(prono.group?.color).to.opacity(0.18)), in: Capsule())
        .overlay(Capsule().stroke(GroupLook.gradient(prono.group?.color).to.opacity(prono.kind == "award" ? 0 : 0.5), lineWidth: 1))
    }

    private func banner(_ text: String, gold: Bool) -> some View {
        Text(text)
            .font(.system(size: 15, weight: .black).width(.compressed)).kerning(2.1)
            .foregroundStyle(Color(hex: 0x1D1530))
            .padding(.horizontal, 16).frame(height: 30)
            .background(LinearGradient(colors: gold ? [PronoInk.gold, Color(hex: 0xFFB347)] : [Color(hex: 0xD9CFFF), PronoInk.lavender], startPoint: .leading, endPoint: .trailing),
                        in: RoundedRectangle(cornerRadius: 6, style: .continuous))
            .shadow(color: (gold ? PronoInk.gold : PronoInk.lavender).opacity(0.45), radius: 18)
            .scaleEffect(t >= 0 ? 1 : 1.35)
            .rotationEffect(.degrees(t >= 0 ? -3 : -9))
            .opacity(t >= 0 ? 1 : 0)
            .accessibilityAddTraits(.isHeader)
    }

    // MARK: Le résultat (choix, oui/non, plus/moins, majorité, personne, nombre, heure, libre)

    private var result: some View {
        ScrollView {
            VStack(spacing: 18) {
                place.padding(.top, 8)
                banner("LE RÉSULTAT", gold: false)
                Text(prono.question)
                    .font(.system(size: 28, weight: .heavy, design: .rounded))
                    .multilineTextAlignment(.center).foregroundStyle(PronoInk.t1)
                    .lineLimit(3).minimumScaleFactor(0.8).frame(maxWidth: 330)
                stats
                if t < 1120 { seals.transition(.opacity.combined(with: .scale(scale: 0.9))) }
                if prono.kind == "number" || prono.kind == "when" { truth }
                VStack(spacing: 10) {
                    ForEach(Array(rows.enumerated()), id: \.element.id) { j, row in
                        rowView(row, index: j)
                    }
                }
                rarity
                if t >= 1950 { youCard.transition(.move(edge: .bottom).combined(with: .opacity)) }
            }
            .padding(.horizontal, 16).padding(.top, 52).padding(.bottom, 32)
        }
    }

    private var stats: some View {
        HStack(spacing: 4) {
            Text("\(players)").fontWeight(.heavy).monospacedDigit()
            Text(players > 1 ? "ont joué" : "a joué")
            if patates, field > 0 {
                Text("·")
                Text("\(field)").fontWeight(.heavy).monospacedDigit()
                Text("🎊 sur la piste")
            }
        }
        .font(.subheadline).foregroundStyle(PronoInk.t2)
        .accessibilityElement(children: .combine)
    }

    private var seals: some View {
        HStack(spacing: 8) {
            ForEach(Array(sealFaces.enumerated()), id: \.element.id) { i, face in
                let cracked = t >= 60 + i * 60
                ZStack {
                    Initials(name: face.name, photo: face.photo, size: 36)
                        .overlay(Circle().stroke(face.me == true ? Color.white : .clear, lineWidth: 2))
                        .scaleEffect(cracked ? 1 : 0.5).opacity(cracked ? 1 : 0)
                    PronoSeal(emoji: prono.group?.emoji ?? "🔮", color: prono.group?.color, size: 36, broken: cracked)
                        .rotationEffect(.degrees(cracked ? 28 : 0))
                        .opacity(cracked ? 0 : 1)
                    Circle().stroke(PronoInk.lavender, lineWidth: 2).frame(width: 36, height: 36)
                        .scaleEffect(cracked ? 1.8 : 0.8).opacity(cracked && t < 60 + i * 60 + 260 ? 0.8 : 0)
                }
                .frame(width: 36, height: 36)
            }
        }
        .accessibilityHidden(true)
    }

    private var truth: some View {
        VStack(spacing: 2) {
            Text(prono.kind == "when" ? "L'heure exacte" : "Le vrai compte").font(.footnote.weight(.semibold)).foregroundStyle(PronoInk.mint)
            Text(PronoRead.result(prono))
                .font(.system(size: 54, weight: .heavy).width(.expanded)).monospacedDigit()
                .foregroundStyle(PronoInk.mint)
        }
        .opacity(t >= 1100 ? 1 : 0).scaleEffect(t >= 1100 ? 1 : 0.8)
        .accessibilityElement(children: .combine)
    }

    private func rowView(_ row: Row, index j: Int) -> some View {
        let lit = row.good && t >= 1100
        let dim = !row.good && t >= 1100
        let total = max(1, rows.map(\.count).reduce(0, +))
        let maxCount = max(1, rows.map(\.count).max() ?? 1)
        let grown = t >= 1420 + j * 70
        let shownCounts = t >= 1650
        return VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 12) {
                if let mark = row.mark {
                    PronoMarkTile(mark: mark, size: 34, filled: lit, tint: lit ? PronoInk.mint : (dim ? PronoInk.miss : nil))
                }
                Text(row.label).font(.system(size: 20, weight: .bold, design: .rounded)).foregroundStyle(PronoInk.t1).lineLimit(2)
                Spacer(minLength: 8)
                if shownCounts {
                    Text("\(row.count)").font(.system(size: 22, weight: .heavy).width(.expanded)).monospacedDigit().foregroundStyle(PronoInk.t1)
                    Text("\(row.count * 100 / total) %").font(.subheadline).monospacedDigit().foregroundStyle(PronoInk.t2)
                }
            }
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(Color.white.opacity(0.07))
                    Capsule().fill(lit ? AnyShapeStyle(LinearGradient(colors: [PronoInk.mint, Color(hex: 0x22B07D)], startPoint: .leading, endPoint: .trailing)) : AnyShapeStyle(PronoInk.lavender.opacity(0.35)))
                        .frame(width: grown ? max(10, geo.size.width * CGFloat(row.count) / CGFloat(maxCount) * 0.62) : 0)
                    if t >= 1120, !row.faces.isEmpty {
                        PronoAvatarStack(faces: Array(row.faces.prefix(6)), extra: max(0, row.faces.count - 6), size: 24)
                            .offset(x: grown ? max(0, geo.size.width * CGFloat(row.count) / CGFloat(maxCount) * 0.62 - 12) : 0)
                            .offset(y: unanimousWave(row) ? -10 : 0)
                            .transition(.scale(scale: 0.4).combined(with: .opacity))
                    }
                }
            }
            .frame(height: 24)
        }
        .padding(.horizontal, 16).padding(.vertical, 14)
        .background {
            ZStack {
                RoundedRectangle(cornerRadius: 20, style: .continuous).fill(lit ? PronoInk.mint.opacity(0.14) : Color.white.opacity(0.05))
                if t >= 600, t < 1100 + 400, spot == j {
                    PronoSpotlight(color: lit ? PronoInk.mint : PronoInk.lavender)
                        .matchedGeometryEffect(id: "spot", in: spotlight)
                }
            }
        }
        .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).stroke(lit ? PronoInk.mint : Color.white.opacity(0.10), lineWidth: lit ? 2 : 1))
        .overlay(alignment: .topTrailing) {
            if lit {
                Label("Bonne réponse", systemImage: "checkmark").font(.footnote.weight(.heavy))
                    .foregroundStyle(Color(hex: 0x1D1530))
                    .padding(.horizontal, 10).padding(.vertical, 4)
                    .background(PronoInk.mint, in: Capsule())
                    .offset(x: -12, y: -12)
                    .transition(.scale(scale: 0.4).combined(with: .opacity))
            }
        }
        .shadow(color: lit ? PronoInk.mint.opacity(0.35) : .clear, radius: 18)
        .scaleEffect(lit ? 1.03 : 1)
        .opacity(dim ? 0.55 : 1)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(row.label) : \(row.count) réponse\(row.count > 1 ? "s" : "")\(row.good ? ", bonne réponse" : "")")
    }

    private func unanimousWave(_ row: Row) -> Bool { unanimous && row.good && t >= 2150 && t < 2450 && !reduceMotion }

    @ViewBuilder
    private var rarity: some View {
        if t >= 1800 {
            Group {
                if unanimous {
                    VStack(spacing: 6) {
                        Text("🤝").font(.system(size: 44))
                        Text("Unanimes !").font(.system(size: 44, weight: .heavy, design: .rounded)).foregroundStyle(PronoInk.lavender)
                        Text(patates ? "Tout le monde récupère ses confettis." : "Tout le monde avait vu juste.").font(.subheadline).foregroundStyle(PronoInk.t2)
                    }
                } else if rightCount == 0 {
                    Text(patates ? "Personne ne l'avait vu : tout le monde récupère ses confettis." : "Personne ne l'avait vu.")
                        .font(.subheadline.weight(.semibold)).foregroundStyle(PronoInk.t2).multilineTextAlignment(.center)
                } else {
                    Text("🔮 \(rightCount == 1 ? "Seul·e 1" : "Seuls \(rightCount)") sur \(ofCount) l'avai\(rightCount == 1 ? "t" : "ent") vu")
                        .font(.subheadline.weight(.bold)).foregroundStyle(PronoInk.gold)
                        .padding(.horizontal, 16).frame(minHeight: 36)
                        .background(PronoInk.gold.opacity(0.12), in: Capsule())
                        .overlay(Capsule().stroke(PronoInk.gold.opacity(0.35), lineWidth: 1))
                }
            }
            .transition(.scale(scale: 0.6).combined(with: .opacity))
        }
    }

    private var youCard: some View {
        let tone: Color = !played ? PronoInk.miss : (unanimous ? PronoInk.lavender : (right ? PronoInk.mint : PronoInk.miss))
        return VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .center, spacing: 14) {
                ZStack {
                    Circle().fill(right && !unanimous ? PronoInk.mint : tone.opacity(0.18))
                    if unanimous { Text("🤝").font(.title2) } else if right {
                        Image(systemName: "checkmark").font(.title2.weight(.heavy)).foregroundStyle(Color(hex: 0x1D1530))
                    } else {
                        Circle().stroke(PronoInk.miss, lineWidth: 3).frame(width: 22, height: 22)
                    }
                }
                .frame(width: 56, height: 56)
                VStack(alignment: .leading, spacing: 3) {
                    Text(youTitle).font(.system(size: 20, weight: .bold, design: .rounded)).foregroundStyle(PronoInk.t1)
                    Text(youDetail).font(.subheadline).foregroundStyle(PronoInk.t2).fixedSize(horizontal: false, vertical: true)
                }
                Spacer(minLength: 6)
                youFigure
            }
            if right, !unanimous, patates, myStake > 0, !(pronoOpt(prono.settled) ?? false) {
                Label("En attente 12 h, le temps de contester", systemImage: "hourglass").font(.footnote).foregroundStyle(PronoInk.t2)
            }
            if t >= 2600 {
                HStack(spacing: 10) {
                    if right, !unanimous {
                        ShareLink(item: "🔮 J'avais vu juste : « \(prono.question) » (Party)") {
                            Text("🔮 Partager").font(.headline).frame(maxWidth: .infinity, minHeight: 52)
                        }
                        .buttonStyle(.plain).foregroundStyle(PronoInk.t1)
                        .background(Color.white.opacity(0.06), in: Capsule()).overlay(Capsule().stroke(Color.white.opacity(0.12)))
                    } else {
                        Button { onClose() } label: { Text("Réactions 😂").font(.headline).frame(maxWidth: .infinity, minHeight: 52) }
                            .buttonStyle(.plain).foregroundStyle(PronoInk.t1)
                            .background(Color.white.opacity(0.06), in: Capsule()).overlay(Capsule().stroke(Color.white.opacity(0.12)))
                    }
                    Button { onClose() } label: { Text("Voir tout ›").font(.headline).frame(maxWidth: .infinity, minHeight: 52) }
                        .buttonStyle(.plain).foregroundStyle(PronoInk.t1)
                        .background(Color.white.opacity(0.06), in: Capsule()).overlay(Capsule().stroke(Color.white.opacity(0.12)))
                        .accessibilityIdentifier("prono-reveal-done")
                }
                .transition(.opacity)
            }
        }
        .padding(18)
        .background(Color(hex: 0x251D47).opacity(0.8), in: RoundedRectangle(cornerRadius: 24, style: .continuous))
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
        .overlay(alignment: .top) { Capsule().fill(tone).frame(height: 2).padding(.horizontal, 24) }
        .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).stroke(Color.white.opacity(0.10), lineWidth: 1))
        .accessibilityElement(children: .contain)
    }

    private var youTitle: String {
        if !played { return "Tu n'as pas joué" }
        if unanimous { return "Vu juste, comme tous" }
        return right ? "Tu avais vu juste" : "Pas cette fois"
    }

    private var youDetail: String {
        if !played { return "La prochaine fois, peut-être !" }
        if unanimous { return patates ? "Personne ne perd rien." : "Tout le monde a ses points." }
        if right {
            return patates && myStake > 0 ? "Tu en avais lancé \(myStake) 🎊" : "+\(PronoFormat.points(prono.points)) au classement"
        }
        let said = PronoRead.mine(prono) ?? "—"
        let good = PronoRead.result(prono)
        return good.isEmpty ? "Tu avais dit \(said)." : "Tu avais dit \(said). La bonne : \(good)."
    }

    @ViewBuilder
    private var youFigure: some View {
        if played, patates, myStake > 0 {
            VStack(alignment: .trailing, spacing: 0) {
                Text(unanimous || rightCount == 0 ? "RENDUS" : (right ? "TU RAMASSES" : "AU BALAI"))
                    .font(.caption.weight(.heavy)).kerning(1.2)
                    .foregroundStyle(right && !unanimous ? PronoInk.mint : PronoInk.t2)
                HStack(spacing: 2) {
                    Text(right && !unanimous ? "+\(shownHarvest)" : "\(myStake)")
                        .contentTransition(.numericText())
                        .font(.system(size: 34, weight: .heavy).width(.expanded)).monospacedDigit()
                        .foregroundStyle(right && !unanimous ? PronoInk.mint : (unanimous ? PronoInk.lavender : PronoInk.miss))
                    Text("🎊").font(.title2).rotationEffect(.degrees(-12))
                }
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(right && !unanimous ? "Tu ramasses \(harvest) confettis" : (unanimous || rightCount == 0 ? "\(myStake) confettis rendus" : "\(myStake) confettis au balai"))
        }
    }

    // MARK: Trophée de la soirée

    private var laureate: PronoFace? { prono.result?.person ?? prono.winners?.first }

    private var votes: Int {
        guard let id = laureate?.id else { return 0 }
        return answers.filter { $0.person?.id == id }.count
    }

    private var award: (emoji: String, name: String) { PronoRead.award(prono) }

    private var trophy: some View {
        let cracked = t >= 1800
        return ScrollView {
            VStack(spacing: 18) {
                place.padding(.top, 8)
                banner("TROPHÉE DE LA SOIRÉE", gold: true)
                HStack(spacing: 10) {
                    Text(award.emoji).font(.system(size: 40)).scaleEffect(t >= 250 ? 1 : 0.3).opacity(t >= 250 ? 1 : 0)
                    Text(award.name).font(.system(size: 30, weight: .heavy, design: .rounded)).foregroundStyle(PronoInk.t1)
                        .opacity(t >= 250 ? 1 : 0).offset(y: t >= 250 ? 0 : 10)
                }
                .multilineTextAlignment(.center)
                ZStack {
                    Ellipse().fill(PronoInk.gold.opacity(cracked ? 0.22 : 0.08)).frame(width: 260, height: 46).blur(radius: 14).offset(y: 120)
                    PronoSpotlight(color: cracked ? Color(red: 1, green: 0.94, blue: 0.78) : PronoInk.gold)
                        .frame(width: cracked ? 200 : 240, height: 340)
                        .offset(x: cracked ? 0 : spotX, y: -40)
                        .opacity(t >= 600 ? 1 : 0)
                    if let face = laureate, cracked {
                        Initials(name: face.name, photo: face.photo, size: 136)
                            .padding(6)
                            .overlay(Circle().stroke(AngularGradient(colors: [PronoInk.gold, Color(hex: 0xFFB347), PronoInk.gold], center: .center), lineWidth: 6))
                            .shadow(color: PronoInk.gold.opacity(0.6), radius: 40)
                            .transition(.scale(scale: 0.6).combined(with: .opacity))
                    } else {
                        ZStack {
                            Circle().fill(LinearGradient(colors: [PronoInk.gold, Color(hex: 0xFFB347)], startPoint: .top, endPoint: .bottom))
                            Text("🏆").font(.system(size: 48))
                        }
                        .frame(width: 136, height: 136)
                        .rotationEffect(.degrees(t >= 1300 && t < 1800 ? ([1420, 1680].contains(t) ? -4 : 4) : 0))
                    }
                    if let start = sparklesStart { PronoGoldSparkles(start: start).frame(width: 300, height: 340) }
                }
                .frame(height: 300)
                if cracked, let face = laureate {
                    VStack(spacing: 4) {
                        Text(face.label).font(.system(size: 40, weight: .heavy, design: .rounded)).foregroundStyle(PronoInk.t1)
                            .offset(y: t >= 2000 ? 0 : 14).opacity(t >= 2000 ? 1 : 0)
                        Text("choisi·e par \(votes) des \(answers.count) votants").font(.subheadline).foregroundStyle(PronoInk.t2)
                            .opacity(t >= 2200 ? 1 : 0)
                    }
                }
                if t >= 3000 {
                    VStack(spacing: 12) {
                        Text("Pour la gloire : aucun trophée ne rapporte de confettis.").font(.footnote).foregroundStyle(PronoInk.t3)
                            .opacity(patates ? 1 : 0)
                        HStack(spacing: 10) {
                            Button { onClose() } label: { Text("👏 Applaudir").font(.headline).frame(maxWidth: .infinity, minHeight: 52) }
                                .buttonStyle(.plain).foregroundStyle(.white).background(PronoInk.action, in: Capsule())
                                .accessibilityIdentifier("prono-reveal-done")
                            if let face = laureate {
                                ShareLink(item: "🏆 \(award.name) : \(face.name) (Party)") {
                                    Text("Partager").font(.headline).frame(maxWidth: .infinity, minHeight: 52)
                                }
                                .buttonStyle(.plain).foregroundStyle(PronoInk.t1)
                                .background(Color.white.opacity(0.06), in: Capsule()).overlay(Capsule().stroke(Color.white.opacity(0.12)))
                            }
                        }
                    }
                    .transition(.opacity)
                }
            }
            .padding(.horizontal, 16).padding(.top, 52).padding(.bottom, 32)
        }
        .accessibilityElement(children: .contain)
    }

    private var finished: Bool { t >= Self.end }

    // MARK: Chronologie (ms)

    private var announcement: String {
        if prono.kind == "award" {
            guard let face = laureate else { return "Trophée de la soirée, \(award.name)." }
            return "Trophée de la soirée, \(award.name) : \(face.name), choisi·e par \(votes) des \(answers.count) votants."
        }
        var s = "Bonne réponse : \(PronoRead.result(prono))."
        if played {
            if unanimous { s += " Unanimes, tout le monde avait vu juste." } else if right {
                s += " Tu avais vu juste"
                if patates, myStake > 0 { s += ", tu ramasses \(harvest) confettis\((pronoOpt(prono.settled) ?? false) ? "" : ", en attente 12 heures")" }
                s += "."
            } else { s += " Pas cette fois." }
        }
        return s
    }

    private func start() {
        guard t < 0 else { return }
        if reduceMotion || UIAccessibility.isVoiceOverRunning {
            seekEnd()
            if right, !unanimous { PronoHaptics.success() }
            UIAccessibility.post(notification: .announcement, argument: announcement)
            return
        }
        var steps: [(Int, () -> Void)] = []
        func at(_ ms: Int, _ animation: Animation? = Motion.bouncy, _ extra: @escaping () -> Void = {}) {
            steps.append((ms, {
                if let animation { withAnimation(animation) { t = ms } } else { t = ms }
                extra()
            }))
        }
        let light = UIImpactFeedbackGenerator(style: .light)
        if prono.kind == "award" {
            at(0, .spring(response: 0.35, dampingFraction: 0.55)) { PronoHaptics.soft() }
            at(250, .spring(response: 0.3, dampingFraction: 0.5))
            at(600, .easeOut(duration: 0.3)) { withAnimation(.easeInOut(duration: 0.35)) { spotX = -70 } }
            at(700, nil) { PronoHaptics.reveal() }
            at(950, nil) { withAnimation(.easeInOut(duration: 0.35)) { spotX = 70 } }
            at(1000, nil) { PronoHaptics.reveal() }
            at(1300, .easeInOut(duration: 0.12)) { withAnimation(.easeInOut(duration: 0.4)) { spotX = 0 } }
            at(1420, .easeInOut(duration: 0.12))
            at(1560, .easeInOut(duration: 0.12))
            at(1680, .easeInOut(duration: 0.12))
            at(1800, .spring(response: 0.4, dampingFraction: 0.55)) { PronoHaptics.success() }
            at(2000, .spring(response: 0.45, dampingFraction: 0.8))
            at(2200, .easeOut(duration: 0.3))
            at(2300, nil) { sparklesStart = Date() }
            at(3000, .easeOut(duration: 0.3))
            at(3800, nil) { t = Self.end; sparklesStart = nil }
        } else {
            at(0, .spring(response: 0.35, dampingFraction: 0.55)) { PronoHaptics.soft() }
            for i in 0..<sealFaces.count { at(60 + i * 60, .spring(response: 0.3, dampingFraction: 0.55)) { light.impactOccurred(intensity: 0.5) } }
            at(600, .easeInOut(duration: 0.2)) { spot = 0 }
            let target = goodIndex
            if target > 0 {
                for k in 1...target { at(600 + k * 500 / target, .easeInOut(duration: Double(500 / target) / 1000)) { spot = k } }
            }
            at(650, nil) { PronoHaptics.reveal() }
            at(880, nil) { PronoHaptics.reveal() }
            at(1100, .spring(response: 0.35, dampingFraction: 0.6)) { if rightCount > 0 { PronoHaptics.success() } }
            at(1120, .spring(response: 0.45, dampingFraction: 0.72))
            for j in 0..<rows.count { at(1420 + j * 70, .spring(response: 0.5, dampingFraction: 0.62)) }
            at(1650, .easeOut(duration: 0.26))
            at(1800, .spring(response: 0.35, dampingFraction: 0.55))
            at(1950, .spring(response: 0.45, dampingFraction: 0.8)) { if right, !unanimous { PronoHaptics.success() } }
            if right, !unanimous, harvest > 0 {
                let n = min(harvest, 15)
                for k in 1...n { steps.append((2100 + k * 450 / n, { withAnimation(.easeOut(duration: 0.08)) { shownHarvest = harvest * k / n } })) }
            }
            at(2150, unanimous ? .spring(response: 0.3, dampingFraction: 0.6) : nil)
            if unanimous { at(2450, .spring(response: 0.3, dampingFraction: 0.6)) }
            at(2600, .easeOut(duration: 0.3))
            at(3500, nil) { t = Self.end }
        }
        steps.sort { $0.0 < $1.0 }
        task = Task { @MainActor in
            var last = 0
            for (ms, run) in steps {
                if ms > last { try? await Task.sleep(nanoseconds: UInt64(ms - last) * 1_000_000) }
                if Task.isCancelled { return }
                last = ms
                run()
            }
            UIAccessibility.post(notification: .announcement, argument: announcement)
        }
    }

    private func seekEnd() {
        task?.cancel()
        task = nil
        withAnimation(Motion.pick(.easeOut(duration: 0.15))) {
            t = Self.end
            spot = goodIndex
            spotX = 0
            shownHarvest = harvest
            sparklesStart = nil
        }
    }
}
#endif

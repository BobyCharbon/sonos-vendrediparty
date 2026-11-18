import SwiftUI

// Pièces « Néon club » des écrans Personnes (maquettes 1-neon : 2, 2b, 3). Jetons de PronoTheme (mêmes valeurs que les
// maquettes) en attendant ChatNeon.swift ; rose = agir, lavande = choisi, orange = une soirée.

enum PeopleNeon {
    /// Rose d'action : dégradé #FF7DB6 → #FF4F9A, encre #1F0618 (6,2:1 ; jamais de blanc sur rose, 3,1:1).
    static let pinkTop = PronoTheme.fixed(0xFF7DB6)
    static let pinkInk = PronoTheme.fixed(0x1F0618)
    static let orange = LinearGradient(colors: [PronoTheme.fixed(0xFFC977), PronoTheme.fixed(0xFF7A59)],
                                       startPoint: .topLeading, endPoint: .bottomTrailing)
    static let lavenderTile = LinearGradient(colors: [PronoTheme.fixed(0xCBBDFF), PronoTheme.fixed(0x7B6CF6)],
                                             startPoint: .topLeading, endPoint: .bottomTrailing)
    static let ring = LinearGradient(colors: [PronoTheme.lavA, PronoTheme.pink], startPoint: .top, endPoint: .bottom)
}

/// Fond des écrans : nuit de Party, une lueur douce seulement en haut.
struct PeopleBackground: View {
    var tint: Color = PronoTheme.lavB

    var body: some View {
        PronoTheme.bg
            .overlay(alignment: .top) {
                RadialGradient(colors: [tint.opacity(0.28), .clear], center: .top, startRadius: 0, endRadius: 360)
                    .frame(height: 360)
                    .allowsHitTesting(false)
            }
            .ignoresSafeArea()
    }
}

/// Bouton principal rose (58 pt, rayon 18), encre sombre.
struct PeoplePinkButton: View {
    let title: String
    var systemImage: String? = nil
    var busy = false
    let action: () -> Void
    @Environment(\.isEnabled) private var isEnabled

    var body: some View {
        Button(action: action) {
            HStack(spacing: 10) {
                if busy { ProgressView().tint(PeopleNeon.pinkInk) } else if let systemImage {
                    Image(systemName: systemImage).font(.body.weight(.bold))
                }
                Text(title).font(.system(.title3, design: .rounded).weight(.heavy)).lineLimit(1).minimumScaleFactor(0.7)
            }
            .foregroundStyle(PeopleNeon.pinkInk)
            .frame(maxWidth: .infinity, minHeight: 56)
            .padding(.horizontal, 12)
            .background(LinearGradient(colors: [PeopleNeon.pinkTop, PronoTheme.pink], startPoint: .top, endPoint: .bottom),
                        in: RoundedRectangle(cornerRadius: PronoTheme.Radius.button, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: PronoTheme.Radius.button, style: .continuous).strokeBorder(.white.opacity(0.25), lineWidth: 1))
            .shadow(color: PronoTheme.pink.opacity(isEnabled ? 0.45 : 0), radius: 18, y: 10)
            .opacity(isEnabled ? 1 : 0.45)
        }
        .buttonStyle(PronoKitPressStyle())
        .disabled(busy)
        .accessibilityLabel(title)
    }
}

/// Bouton secondaire (verre sombre, filet discret).
struct PeopleGhostButton: View {
    let title: String
    var systemImage: String? = nil
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                if let systemImage { Image(systemName: systemImage).foregroundStyle(PronoTheme.lav) }
                Text(title).font(.headline)
            }
            .foregroundStyle(PronoTheme.t1)
            .frame(minHeight: 56)
            .padding(.horizontal, 18)
            .background(PronoTheme.s1b, in: RoundedRectangle(cornerRadius: PronoTheme.Radius.button, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: PronoTheme.Radius.button, style: .continuous).strokeBorder(PronoTheme.line2, lineWidth: 1))
        }
        .buttonStyle(PronoKitPressStyle())
    }
}

/// Étiquette de section : icône + CAPITALES espacées, et une action à droite.
struct PeopleSectionLabel: View {
    let text: String
    var systemImage: String? = nil
    var trailing: String? = nil
    var action: (() -> Void)? = nil

    var body: some View {
        HStack(spacing: 8) {
            if let systemImage { Image(systemName: systemImage).font(.footnote.weight(.semibold)).foregroundStyle(PronoTheme.t2) }
            Text(text.uppercased()).font(.footnote.weight(.bold)).tracking(1.4).foregroundStyle(PronoTheme.t2)
                .accessibilityAddTraits(.isHeader)
            Spacer(minLength: 8)
            if let trailing, let action {
                Button(trailing, action: action).font(.body.weight(.semibold)).foregroundStyle(PronoTheme.lav).frame(minHeight: 44)
            }
        }
    }
}

/// Rond de sélection (44 pt de cible par la ligne qui le porte).
struct PeopleCheck: View {
    let on: Bool

    var body: some View {
        ZStack {
            Circle().strokeBorder(on ? .clear : PronoTheme.line2, lineWidth: 2)
            if on {
                Circle().fill(PronoTheme.pink)
                Image(systemName: "checkmark").font(.system(size: 13, weight: .black)).foregroundStyle(PeopleNeon.pinkInk)
            }
        }
        .frame(width: 28, height: 28)
        .accessibilityHidden(true)
    }
}

/// Visage d'une personne (photo signée, sinon initiales sur sa couleur), avec l'anneau néon quand elle est choisie.
struct PeopleFace: View {
    let person: ChatPerson
    var size: CGFloat = 40
    var selected = false

    var body: some View {
        PronoAvatar(face: person.face, size: size)
            .padding(selected ? 4 : 0)
            .overlay { if selected { Circle().strokeBorder(PeopleNeon.ring, lineWidth: 3) } }
            .overlay(alignment: .bottomTrailing) {
                if selected {
                    Image(systemName: "checkmark").font(.system(size: size * 0.16, weight: .black))
                        .foregroundStyle(PeopleNeon.pinkInk)
                        .frame(width: size * 0.34, height: size * 0.34)
                        .background(PronoTheme.pink, in: Circle())
                        .overlay(Circle().stroke(PronoTheme.bg, lineWidth: 3))
                        .offset(x: 2, y: 2)
                }
            }
            .shadow(color: selected ? PronoTheme.pink.opacity(0.35) : .clear, radius: 10)
            .accessibilityHidden(true)
    }
}

/// Tuile date d'une soirée (« VEN. » / « 21 ») : orange pour une soirée, lavande pour une soirée passée.
struct PeopleDateTile: View {
    let start: String?
    var past = false

    var body: some View {
        let t = PeopleDate.tile(start)
        VStack(spacing: 0) {
            Text(t?.weekday ?? "📅").font(.system(size: 10, weight: .heavy)).tracking(1)
            Text(t?.day ?? "").font(.system(.title3, design: .rounded).weight(.heavy)).monospacedDigit()
        }
        .foregroundStyle(PronoTheme.fixed(0x2A1206))
        .frame(width: 52, height: 52)
        .background(past ? AnyShapeStyle(PeopleNeon.lavenderTile) : AnyShapeStyle(PeopleNeon.orange),
                    in: RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(.white.opacity(0.3), lineWidth: 1))
        .accessibilityHidden(true)
    }
}

/// Mise en page en lignes qui passent à la ligne (puces « À : »).
struct PeopleFlow: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? .infinity
        var x: CGFloat = 0, y: CGFloat = 0, line: CGFloat = 0, widest: CGFloat = 0
        for s in subviews {
            let size = s.sizeThatFits(.unspecified)
            if x > 0 && x + size.width > width { y += line + spacing; x = 0; line = 0 }
            x += size.width + spacing
            line = max(line, size.height)
            widest = max(widest, x - spacing)
        }
        return CGSize(width: min(widest, width), height: y + line)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, line: CGFloat = 0
        for s in subviews {
            let size = s.sizeThatFits(.unspecified)
            if x > bounds.minX && x + size.width > bounds.maxX { y += line + spacing; x = bounds.minX; line = 0 }
            s.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(size))
            x += size.width + spacing
            line = max(line, size.height)
        }
    }
}

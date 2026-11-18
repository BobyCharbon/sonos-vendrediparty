import SwiftUI

/// Jetons « Néon club » de la conversation (maquette 1-neon/4-conversation), sur ceux des Pronos (PronoTheme) en
/// attendant ChatNeon (I1) : nuit #0E0A1F, ma bulle #6E5CF0 → #5A48DA (texte blanc), celle des autres #1C1638 avec un
/// liseré lavande, lavande = moi / choisi, rose = agir, orange = une soirée, menthe = « je viens ».
enum ConvNeon {
    static let bg = PronoTheme.bg
    static let surface = PronoTheme.s1
    static let surface2 = PronoTheme.s1b
    static let glass = PronoTheme.glass
    static let line = PronoTheme.line
    static let line2 = PronoTheme.line2
    static let t1 = PronoTheme.t1
    static let t2 = PronoTheme.t2
    static let t3 = PronoTheme.t3
    static let lav = PronoTheme.lavA
    static let lavDeep = PronoTheme.lavB
    static let pink = PronoTheme.pink
    static let mint = PronoTheme.mint
    static let coral = PronoTheme.fixed(0xFF7A59)
    static let peach = PronoTheme.fixed(0xFFC977)
    static let mineA = PronoTheme.fixed(0x6E5CF0)
    static let mineB = PronoTheme.fixed(0x5A48DA)
    static let theirs = PronoTheme.fixed(0x1C1638)
    static let theirsLine = PronoTheme.fixed(0xB9A7FF, 0.10)
    /// Fond des citations dans ma bulle, des réactions mises par moi.
    static let quoteOnMine = PronoTheme.fixed(0x0E0A1F, 0.28)
    static let reactMine = PronoTheme.fixed(0x2E2560)

    static var mine: LinearGradient {
        LinearGradient(colors: [mineA, mineB], startPoint: .topLeading, endPoint: .bottomTrailing)
    }

    static var lavender: LinearGradient { PronoTheme.lavender }

    static var evening: LinearGradient {
        LinearGradient(colors: [peach, coral], startPoint: .topLeading, endPoint: .bottomTrailing)
    }

    /// Couleur du nom d'une personne : le clair de sa couleur de groupe (même teinte que sa pastille).
    static func name(_ id: String) -> Color { GroupLook.gradient(PronoAvatar.color(for: id)).from }

    /// Lueur douce, seulement en haut de l'écran ; le fil reste sur fond uni.
    static var halo: some View {
        RadialGradient(colors: [PronoTheme.halo, .clear], center: .top, startRadius: 0, endRadius: 320)
            .frame(height: 260).frame(maxHeight: .infinity, alignment: .top)
            .allowsHitTesting(false)
    }
}

/// Photo d'une personne, sinon ses initiales sur le dégradé de sa couleur (fini les teintes pastel hors palette).
struct ConvFace: View {
    let id: String
    let name: String
    var photo: String?
    var size: CGFloat = 32

    private var letters: String {
        let l = name.split(separator: " ").prefix(2).compactMap(\.first).map(String.init).joined().uppercased()
        return l.isEmpty ? "?" : l
    }

    var body: some View {
        AsyncImage(url: photo.flatMap(URL.init(string:)), transaction: Transaction(animation: Motion.pick(Motion.fade))) { phase in
            if let image = phase.image {
                image.resizable().scaledToFill().transition(.opacity)
            } else {
                Text(letters).font(.system(size: size * 0.38, weight: .heavy, design: .rounded))
                    .foregroundStyle(PronoTheme.fixed(0x1D1530)).minimumScaleFactor(0.6)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(PronoTheme.group(PronoAvatar.color(for: id)))
            }
        }
        .frame(width: size, height: size)
        .clipShape(Circle())
        .accessibilityHidden(true)
    }
}

/// Petit calendrier orange d'une soirée : « VEN. » puis « 21 ».
struct EveningTile: View {
    let date: Date?
    var size: CGFloat = 50

    var body: some View {
        VStack(spacing: 0) {
            Text(date.map { Self.day($0) } ?? "—").font(.system(size: size * 0.2, weight: .heavy)).tracking(0.8)
            Text(date.map { String(Calendar.current.component(.day, from: $0)) } ?? "?")
                .font(.system(size: size * 0.44, weight: .heavy, design: .rounded)).monospacedDigit()
        }
        .foregroundStyle(PronoTheme.fixed(0x2A1206))
        .frame(width: size, height: size)
        .background(ConvNeon.evening, in: RoundedRectangle(cornerRadius: size * 0.3, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: size * 0.3, style: .continuous).strokeBorder(.white.opacity(0.3), lineWidth: 1))
        .accessibilityHidden(true)
    }

    static func day(_ date: Date) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "fr_CH")
        f.dateFormat = "EEE"
        return f.string(from: date).uppercased()
    }
}

/// Carte d'une soirée Party dans un message : date, titre, heure et lieu, présents, « Voir » (fiche de l'événement).
struct EventCardBubble: View {
    let card: ChatEventCard
    let onOpen: (@MainActor () -> Void)?

    private var line: String {
        var parts: [String] = []
        if let d = card.date { parts.append(Self.hour(d)) }
        if let place = card.place, !place.isEmpty { parts.append(place) }
        return parts.joined(separator: " · ")
    }

    static func hour(_ d: Date) -> String {
        let c = Calendar.current.dateComponents([.hour, .minute], from: d)
        return "\(c.hour ?? 0) h" + ((c.minute ?? 0) > 0 ? String(format: " %02d", c.minute ?? 0) : "")
    }

    private var mineLabel: String? {
        switch card.mine {
        case "yes": return "Tu viens"
        case "maybe": return "Peut-être"
        case "no": return "Pas présent"
        case "invited": return "Tu es invité"
        default: return nil
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 12) {
                EveningTile(date: card.date)
                VStack(alignment: .leading, spacing: 2) {
                    Label("Soirée Party", systemImage: "sparkle").font(.caption2.weight(.heavy)).tracking(0.8).textCase(.uppercase)
                        .foregroundStyle(ConvNeon.coral)
                    Text(card.title).font(.system(.headline, design: .rounded).weight(.heavy)).foregroundStyle(ConvNeon.t1)
                        .lineLimit(2)
                    if !line.isEmpty { Text(line).font(.subheadline).foregroundStyle(ConvNeon.t2).lineLimit(1) }
                }
                Spacer(minLength: 0)
            }
            HStack(spacing: 8) {
                if let going = card.going, going > 0 {
                    Text(going == 1 ? "1 présent" : "\(going) présents").font(.footnote).foregroundStyle(ConvNeon.t2)
                }
                if let mineLabel {
                    Label(mineLabel, systemImage: card.mine == "yes" ? "checkmark" : "circle")
                        .labelStyle(.titleAndIcon).font(.footnote.weight(.semibold))
                        .foregroundStyle(card.mine == "yes" ? ConvNeon.mint : ConvNeon.t2)
                }
                Spacer(minLength: 0)
                if let onOpen {
                    Button {
                        Haptics.tap()
                        onOpen()
                    } label: {
                        Text("Voir").font(.subheadline.weight(.bold)).foregroundStyle(PronoTheme.fixed(0x120B26))
                            .padding(.horizontal, 18).frame(minHeight: 44)
                            .background(ConvNeon.lavender, in: Capsule())
                    }
                    .buttonStyle(PressableStyle(scale: 0.94))
                    .accessibilityLabel("Voir la soirée \(card.title)")
                    .accessibilityIdentifier("chat-event-open")
                }
            }
        }
        .padding(12)
        .frame(maxWidth: 300, alignment: .leading)
        .background(ConvNeon.surface, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(alignment: .top) {
            LinearGradient(colors: [ConvNeon.peach, ConvNeon.coral, ConvNeon.pink], startPoint: .leading, endPoint: .trailing)
                .frame(height: 3)
        }
        .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).strokeBorder(ConvNeon.coral.opacity(0.3), lineWidth: 1))
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("chat-event-card")
    }
}

/// Soirée jointe à un message mais pas visible pour moi (privée, supprimée) : rien n'est montré d'elle.
struct EventCardUnavailable: View {
    var body: some View {
        Label("Soirée indisponible", systemImage: "calendar.badge.exclamationmark").font(.subheadline)
            .foregroundStyle(ConvNeon.t2).padding(12)
            .background(ConvNeon.surface, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
    }
}

/// Citation d'un groupe ou d'une soirée en tête d'un message direct (« Répondre en privé »).
struct PrivateQuoteBlock: View {
    let quote: PrivateQuote
    let mine: Bool

    var body: some View {
        HStack(spacing: 8) {
            RoundedRectangle(cornerRadius: 2).fill(mine ? ConvNeon.lav : ConvNeon.coral).frame(width: 4)
            VStack(alignment: .leading, spacing: 1) {
                Label(quote.from == "event" ? "Soirée « \(quote.title) »" : "Groupe « \(quote.title) »",
                      systemImage: "arrowshape.turn.up.left").font(.caption2.weight(.bold))
                    .foregroundStyle(mine ? PronoTheme.fixed(0xE6DFFF) : ConvNeon.t2).lineLimit(1)
                Text(quote.author).font(.caption.weight(.bold)).foregroundStyle(mine ? PronoTheme.fixed(0xE6DFFF) : ConvNeon.lav)
                Text(quote.excerpt).font(.caption).foregroundStyle(mine ? .white.opacity(0.82) : ConvNeon.t2).lineLimit(3)
            }
            Spacer(minLength: 0)
        }
        .padding(6)
        .background(mine ? ConvNeon.quoteOnMine : PronoTheme.fixed(0x0E0A1F, 0.35), in: RoundedRectangle(cornerRadius: 12))
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Réponse privée à \(quote.author), \(quote.from == "event" ? "soirée" : "groupe") \(quote.title) : \(quote.excerpt)")
    }
}

/// « écrit… » : trois points qui respirent (immobiles avec Réduire les animations), dans une bulle des autres.
struct TypingBubble: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var lit = false

    var body: some View {
        HStack(spacing: 5) {
            ForEach(0..<3, id: \.self) { i in
                Circle().fill(ConvNeon.lav).frame(width: 8, height: 8)
                    .opacity(reduceMotion ? 0.4 + 0.3 * Double(i) : (lit ? 1 : 0.35))
                    .animation(reduceMotion ? nil : .easeInOut(duration: 0.6).repeatForever().delay(Double(i) * 0.2), value: lit)
            }
        }
        .padding(.horizontal, 16).padding(.vertical, 13)
        .background(ConvNeon.theirs, in: UnevenRoundedRectangle(cornerRadii: .init(topLeading: 22, bottomLeading: 8, bottomTrailing: 22, topTrailing: 22)))
        .onAppear { lit = true }
        .accessibilityHidden(true)
    }
}

/// Bandeau d'une demande de message : chez le destinataire, « X veut t'écrire » et ses quatre boutons ; chez
/// l'expéditeur, « Demande envoyée ».
struct RequestBanner: View {
    let request: MessageRequest
    let name: String
    let sent: Bool
    var onAccept: () -> Void = {}
    var onDelete: () -> Void = {}
    var onBlock: () -> Void = {}
    var onReport: () -> Void = {}

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            switch request {
            case .incoming:
                Label("\(name) veut t'écrire", systemImage: "envelope.badge").font(.system(.headline, design: .rounded).weight(.heavy))
                    .foregroundStyle(ConvNeon.t1)
                Text("Accepte pour lui répondre. Tant que tu n'acceptes pas, \(name) ne sait pas que tu as lu son message.")
                    .font(.subheadline).foregroundStyle(ConvNeon.t2).fixedSize(horizontal: false, vertical: true)
                Button(action: onAccept) {
                    Text("Accepter").font(.headline).foregroundStyle(PronoTheme.fixed(0x120B26))
                        .frame(maxWidth: .infinity, minHeight: 48)
                        .background(ConvNeon.lavender, in: Capsule())
                }
                .buttonStyle(PressableStyle(scale: 0.97))
                .accessibilityIdentifier("request-accept")
                HStack(spacing: 8) {
                    small("Supprimer", "trash", id: "request-delete", action: onDelete)
                    small("Bloquer", "hand.raised", id: "request-block", action: onBlock)
                    small("Signaler", "exclamationmark.bubble", id: "request-report", action: onReport)
                }
            case .outgoing:
                Label(sent ? "Demande envoyée" : "Ce sera une demande de message", systemImage: sent ? "paperplane.fill" : "envelope")
                    .font(.system(.headline, design: .rounded).weight(.heavy)).foregroundStyle(ConvNeon.t1)
                Text(sent ? "\(name) verra ton message. Tu pourras écrire à nouveau dès que ta demande sera acceptée."
                          : "Un seul message, texte seulement, jusqu'à ce que \(name) accepte.")
                    .font(.subheadline).foregroundStyle(ConvNeon.t2).fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(ConvNeon.glass, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).strokeBorder(ConvNeon.line2, lineWidth: 1))
        .padding(.horizontal, 12).padding(.vertical, 8)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("chat-request")
    }

    private func small(_ title: String, _ icon: String, id: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Label(title, systemImage: icon).font(.subheadline.weight(.semibold))
                .foregroundStyle(title == "Supprimer" ? ConvNeon.t1 : PronoTheme.pinkInk)
                .frame(maxWidth: .infinity, minHeight: 44)
                .background(ConvNeon.surface, in: Capsule())
                .overlay(Capsule().strokeBorder(ConvNeon.line2, lineWidth: 1))
        }
        .buttonStyle(PressableStyle(scale: 0.96))
        .accessibilityIdentifier(id)
    }
}

/// Signaler un message : motif, commentaire, et « Joindre les 10 messages précédents » (décochée) pour que la
/// modération comprenne le contexte (conformité C7).
struct MessageReportSheet: View {
    let model: ConversationModel
    let target: ReportTarget
    @Environment(\.dismiss) private var dismiss
    @State private var reason: ReportReason?
    @State private var comment = ""
    @State private var context = false
    @State private var sent = false
    @State private var sending = false
    @State private var error: String?

    var body: some View {
        NavigationStack {
            Form {
                if sent {
                    Section {
                        Label("Merci, c'est envoyé", systemImage: "checkmark.seal.fill").font(.headline)
                        Text("Un modérateur va regarder. La personne n'est pas prévenue que c'est toi.").foregroundStyle(ConvNeon.t2)
                    }
                    .listRowBackground(ConvNeon.surface)
                } else {
                    Section {
                        ForEach(ReportReason.allCases) { r in
                            Button {
                                Haptics.selection()
                                reason = r
                            } label: {
                                HStack {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(r.label).foregroundStyle(ConvNeon.t1)
                                        Text(r.hint).font(.caption).foregroundStyle(ConvNeon.t2)
                                    }
                                    Spacer()
                                    if reason == r { Image(systemName: "checkmark").foregroundStyle(ConvNeon.lav) }
                                }
                                .frame(minHeight: 44)
                            }
                            .accessibilityAddTraits(reason == r ? .isSelected : [])
                            .accessibilityIdentifier("report-\(r.rawValue)")
                        }
                    } header: {
                        Text("Pourquoi signaler \(target.label) ?")
                    }
                    .listRowBackground(ConvNeon.surface)
                    Section {
                        Toggle("Joindre les 10 messages précédents", isOn: $context)
                            .tint(ConvNeon.lavDeep)
                            .accessibilityIdentifier("report-context")
                        TextField("Commentaire (facultatif)", text: $comment, axis: .vertical)
                            .lineLimit(2...5)
                            .onChange(of: comment) { value in if value.count > 500 { comment = String(value.prefix(500)) } }
                    } footer: {
                        Text(context ? "Le modérateur reçoit une copie de ce message et des 10 messages d'avant (texte, auteur, heure)."
                                     : "Le modérateur reçoit une copie de ce message seulement.")
                    }
                    .listRowBackground(ConvNeon.surface)
                    if let error {
                        Section { Text(error).foregroundStyle(PronoTheme.pinkInk) }.listRowBackground(ConvNeon.surface)
                    }
                }
            }
            .scrollContentBackground(.hidden)
            .background(ConvNeon.bg.ignoresSafeArea())
            .navigationTitle("Signaler")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button(sent ? "Fermer" : "Annuler") { dismiss() } }
                if !sent {
                    ToolbarItem(placement: .confirmationAction) {
                        Button("Envoyer") {
                            guard let reason else { return }
                            sending = true
                            Task {
                                defer { sending = false }
                                do {
                                    try await model.report(target, reason: reason, comment: comment, context: context)
                                    Haptics.success()
                                    Motion.animate { sent = true }
                                } catch {
                                    self.error = error.localizedDescription
                                }
                            }
                        }
                        .disabled(reason == nil || sending)
                        .accessibilityIdentifier("report-send")
                    }
                }
            }
        }
        .tint(ConvNeon.lav)
        .preferredColorScheme(.dark)
    }
}

/// Infos d'une conversation (direct, groupe, soirée) en Néon : fond de nuit, lignes sur surface, accents lavande.
struct ConvNeonForm: ViewModifier {
    func body(content: Content) -> some View {
        content
            .scrollContentBackground(.hidden)
            .background(ZStack { ConvNeon.bg; ConvNeon.halo }.ignoresSafeArea())
            .toolbarBackground(ConvNeon.bg, for: .navigationBar)
            .tint(ConvNeon.lav)
    }
}

extension View {
    func convNeonForm() -> some View { modifier(ConvNeonForm()) }

    /// Mini-profil d'une personne (route de l'app), sinon sa fiche native.
    func personSheet(_ person: Binding<PersonRef?>, store: ChatsStore, routes: ConversationRoutes, canWrite: Bool = true) -> some View {
        sheet(item: person) { p in
            if let make = routes.miniProfile {
                make(p.id)
            } else if canWrite {
                MemberCardView(store: store.privacy, memberID: p.id)
            } else {
                MemberCardView(store: store.privacy, memberID: p.id).environment(\.writeDirect, nil)
            }
        }
    }
}

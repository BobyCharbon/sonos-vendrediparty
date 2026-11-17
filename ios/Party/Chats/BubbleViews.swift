import SwiftUI

// Fil d'une discussion façon WhatsApp (17.11.2026) : fond à motif, bulles à queue, nom de l'auteur en couleur, heure et ✓
// dans la bulle, citations, réactions, glisser vers la droite pour répondre, appui long pour la barre de réactions.

/// Une action de l'appui long (et de VoiceOver) : Répondre, Copier, Épingler, Signaler, Supprimer.
struct BubbleAction: Identifiable {
    let id: String
    let title: String
    let icon: String
    var destructive = false
    let run: () -> Void
}

/// Bulle soulevée par un appui long : son cadre à l'écran (coordonnées globales) et sa copie, montrée au-dessus du voile.
struct BubbleFocus: Identifiable {
    let message: Conversation.Message
    let frame: CGRect
    let preview: AnyView
    var id: String { message.id }
}

/// Forme d'une bulle : coins arrondis, petite queue en haut, côté de l'auteur (à droite pour moi), en tête de série.
/// La place de la queue est toujours réservée : les bulles d'une même série restent alignées.
struct BubbleShape: Shape {
    static let tail: CGFloat = 7
    let mine: Bool
    let showTail: Bool
    var radius: CGFloat = 16

    func path(in rect: CGRect) -> Path {
        let t = Self.tail
        // Dessinée pour « moi » (queue à droite), puis retournée pour les autres.
        let b = CGRect(x: rect.minX, y: rect.minY, width: max(0, rect.width - t), height: rect.height)
        let r = min(radius, b.height / 2, b.width / 2)
        var p = Path()
        p.move(to: CGPoint(x: b.minX + r, y: b.minY))
        if showTail {
            p.addLine(to: CGPoint(x: b.maxX + t - 2, y: b.minY))
            p.addQuadCurve(to: CGPoint(x: b.maxX + t - 2.5, y: b.minY + 3), control: CGPoint(x: b.maxX + t + 0.8, y: b.minY + 0.6))
            p.addQuadCurve(to: CGPoint(x: b.maxX, y: b.minY + min(14, max(r, b.height - r))),
                           control: CGPoint(x: b.maxX + 1.5, y: b.minY + 7))
        } else {
            p.addLine(to: CGPoint(x: b.maxX - r, y: b.minY))
            p.addArc(tangent1End: CGPoint(x: b.maxX, y: b.minY), tangent2End: CGPoint(x: b.maxX, y: b.minY + r), radius: r)
        }
        p.addLine(to: CGPoint(x: b.maxX, y: b.maxY - r))
        p.addArc(tangent1End: CGPoint(x: b.maxX, y: b.maxY), tangent2End: CGPoint(x: b.maxX - r, y: b.maxY), radius: r)
        p.addLine(to: CGPoint(x: b.minX + r, y: b.maxY))
        p.addArc(tangent1End: CGPoint(x: b.minX, y: b.maxY), tangent2End: CGPoint(x: b.minX, y: b.maxY - r), radius: r)
        p.addLine(to: CGPoint(x: b.minX, y: b.minY + r))
        p.addArc(tangent1End: CGPoint(x: b.minX, y: b.minY), tangent2End: CGPoint(x: b.minX + r, y: b.minY), radius: r)
        p.closeSubpath()
        guard !mine else { return p }
        return p.applying(CGAffineTransform(a: -1, b: 0, c: 0, d: 1, tx: 2 * rect.minX + rect.width, ty: 0))
    }
}

/// Fond de la discussion : la couleur de l'app et un motif discret de petits dessins de fête (notes, étoiles, cadeaux…),
/// dessiné ici (aucune image), légèrement penchés, comme le papier peint de WhatsApp.
struct ChatWallpaper: View {
    private static let symbols = ["music.note", "sparkles", "star", "heart", "gift", "face.smiling", "headphones",
                                  "moon.stars", "bolt", "camera", "music.mic", "theatermasks", "music.quarternote.3", "sun.max"]

    var body: some View {
        ZStack {
            AppConfig.background
            RadialGradient(colors: [Color(uiColor: AppConfig.uiAccent).opacity(0.07), .clear], center: .top,
                           startRadius: 0, endRadius: 520)
            Canvas { context, size in
                let step: CGFloat = 54
                var row = 0
                var y: CGFloat = 14
                while y < size.height + step {
                    var col = 0
                    var x: CGFloat = row.isMultiple(of: 2) ? 14 : 14 + step / 2
                    while x < size.width + step {
                        let seed = row &* 31 &+ col &* 17
                        var c = context
                        c.opacity = 0.055
                        c.translateBy(x: x, y: y)
                        c.rotate(by: .degrees(Double(seed % 50) - 25))
                        var image = c.resolve(Image(systemName: Self.symbols[(row &* 5 &+ col &* 3) % Self.symbols.count]))
                        image.shading = .color(.white)
                        let side: CGFloat = seed.isMultiple(of: 3) ? 14 : 18
                        c.draw(image, in: CGRect(x: -side / 2, y: -side / 2, width: side, height: side))
                        x += step
                        col += 1
                    }
                    y += step * 0.86
                    row += 1
                }
            }
        }
        .ignoresSafeArea()
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }
}

/// Séparateur de jour, centré : « Aujourd'hui », « Hier », « Lundi », « 12 novembre ».
struct DayPill: View {
    let label: String

    var body: some View {
        Text(label).font(.caption.weight(.semibold)).foregroundStyle(.white.opacity(0.85))
            .padding(.horizontal, 12).padding(.vertical, 5)
            .background(Color(red: 0.13, green: 0.11, blue: 0.21).opacity(0.92), in: Capsule())
            .overlay(Capsule().stroke(Color.white.opacity(0.06)))
            .accessibilityAddTraits(.isHeader)
    }
}

/// « 3 nouveaux messages » : bande posée avant le premier message non lu, à l'ouverture.
struct UnreadDivider: View {
    let count: Int

    var body: some View {
        Text(count > 1 ? "\(count) nouveaux messages" : "1 nouveau message")
            .font(.caption.weight(.semibold)).foregroundStyle(.white.opacity(0.9))
            .padding(.vertical, 6)
            .frame(maxWidth: .infinity)
            .background(Color.white.opacity(0.08))
            .accessibilityAddTraits(.isHeader)
            .accessibilityIdentifier("chat-unread")
    }
}

/// Heure (et « modifié », horloge pendant l'envoi, coche une fois reçu) en bas à droite de la bulle.
struct MessageMeta: View {
    let message: Conversation.Message
    var onPhoto = false

    var body: some View {
        HStack(spacing: 3) {
            if message.edited && !message.deleted { Text("modifié") }
            Text(message.date?.formatted(date: .omitted, time: .shortened) ?? "")
            if message.mine && !message.deleted {
                Image(systemName: message.pending ? "clock" : "checkmark").font(.system(size: 9, weight: .bold))
                    .contentTransition(.opacity)
            }
        }
        .font(.caption2.monospacedDigit())
        .foregroundStyle(onPhoto ? Color.white : message.mine && !message.deleted ? Color.black.opacity(0.55) : Color.secondary)
        .padding(.horizontal, onPhoto ? 6 : 0).padding(.vertical, onPhoto ? 2 : 0)
        .background(onPhoto ? AnyShapeStyle(Color.black.opacity(0.45)) : AnyShapeStyle(Color.clear), in: Capsule())
        .accessibilityHidden(true)
    }

    /// Texte invisible de même largeur : le texte du message s'arrête avant l'heure, qui se loge sur sa dernière ligne.
    static func spacer(for m: Conversation.Message) -> String {
        let time = m.date?.formatted(date: .omitted, time: .shortened) ?? ""
        return "\u{2003}" + (m.edited ? "modifié " : "") + time + (m.mine ? " ✓" : "")
    }
}

/// Citation dans une bulle : trait de la couleur de l'auteur, son nom, l'extrait ; un toucher remonte au message.
struct QuoteBlock: View {
    let reply: Conversation.Reply
    let mine: Bool
    let onTap: () -> Void

    var body: some View {
        let color = mine ? Color.black.opacity(0.7) : ChatTimeline.nameColor(for: reply.author ?? reply.name)
        Button(action: onTap) {
            HStack(spacing: 8) {
                RoundedRectangle(cornerRadius: 2).fill(color).frame(width: 4)
                VStack(alignment: .leading, spacing: 1) {
                    Text(reply.name).font(.caption.weight(.semibold)).foregroundStyle(color).lineLimit(1)
                    Text(reply.text).font(.caption).foregroundStyle(mine ? Color.black.opacity(0.65) : Color.secondary).lineLimit(2)
                }
                Spacer(minLength: 0)
            }
            .padding(.vertical, 6).padding(.trailing, 6)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.black.opacity(mine ? 0.1 : 0.22), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        }
        .buttonStyle(.plain)
        .disabled(reply.id == nil)
        .accessibilityLabel("Réponse à \(reply.name) : \(reply.text)")
        .accessibilityHint(reply.id == nil ? "" : "Touche pour voir le message d'origine")
    }
}

/// Le dessin d'une bulle (sans gestes) : sert dans le fil et, soulevée, au-dessus du voile de l'appui long.
struct BubbleBody: View {
    let message: Conversation.Message
    let first: Bool
    /// Groupe ou événement : nom des autres en tête de série (pas à deux).
    let showAuthor: Bool
    let names: [String]
    @ObservedObject var player: VoicePlayer
    let onQuote: () -> Void

    private var accent: Color { Color(uiColor: AppConfig.uiAccent) }
    static let others = Color(red: 0.16, green: 0.13, blue: 0.28)

    var body: some View {
        let photoOnly = message.photo != nil && message.body.isEmpty && !message.deleted
        let inset: CGFloat = message.photo == nil || message.deleted ? 0 : 6
        VStack(alignment: .leading, spacing: 4) {
            if showAuthor && first && !message.mine {
                PersonName(id: message.author, pseudo: message.authorName, pseudoFont: .caption2)
                    .font(.subheadline.weight(.semibold)).foregroundStyle(ChatTimeline.nameColor(for: message.author))
                    .padding(.horizontal, inset).padding(.top, inset == 0 ? 0 : 3)
            }
            if message.pinned && !message.deleted {
                (Text(Image(systemName: "pin.fill")) + Text(" Épinglé")).font(.caption2.weight(.bold))
                    .foregroundStyle(message.mine ? Color.black.opacity(0.6) : accent)
                    .padding(.horizontal, inset)
            }
            if let reply = message.reply, !message.deleted {
                QuoteBlock(reply: reply, mine: message.mine, onTap: onQuote)
            }
            if let photo = message.photo.flatMap(URL.init(string:)), !message.deleted {
                AsyncImage(url: photo) { image in image.resizable().scaledToFill() } placeholder: {
                    ZStack { Color.white.opacity(0.06); ProgressView() }
                }
                .frame(width: 240, height: 240).clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                .overlay(alignment: .bottomTrailing) { if photoOnly { MessageMeta(message: message, onPhoto: true).padding(6) } }
                .accessibilityLabel("Photo de \(message.authorName)")
            }
            if let seconds = message.audioSeconds, !message.deleted {
                VoiceBubble(player: player, id: message.id, url: message.audio.flatMap(URL.init(string:)), seconds: seconds, mine: message.mine)
                HStack { Spacer(); MessageMeta(message: message) }
            }
            if message.deleted {
                HStack(spacing: 6) {
                    Label(message.body, systemImage: "nosign").font(.subheadline.italic())
                    MessageMeta(message: message)
                }
                .foregroundStyle(.secondary)
            } else if !message.body.isEmpty {
                // L'heure se loge sur la dernière ligne s'il y a la place (espace invisible de sa largeur), sinon dessous.
                (Text(Mentions.highlighted(message.body, names: names, color: message.mine ? .black : accent))
                    + Text(MessageMeta.spacer(for: message)).font(.caption2.monospacedDigit()).foregroundColor(.clear))
                    .font(.body)
                    .tint(message.mine ? Color.black : accent)
                    .padding(.horizontal, inset)
                    .overlay(alignment: .bottomTrailing) { MessageMeta(message: message).padding(.trailing, inset).offset(y: 2) }
                    .fixedSize(horizontal: false, vertical: true)
            } else if message.photo == nil && message.audioSeconds == nil {
                MessageMeta(message: message)
            }
        }
        .foregroundStyle(message.mine && !message.deleted ? Color.black : Color.white)
        .padding(.horizontal, message.photo == nil || message.deleted ? 11 : 3).padding(.vertical, message.photo == nil || message.deleted ? 7 : 3)
        .padding(message.mine ? .trailing : .leading, BubbleShape.tail)
        .background(message.deleted ? Color.white.opacity(0.07) : message.mine ? accent : Self.others,
                    in: BubbleShape(mine: message.mine, showTail: first))
        .shadow(color: .black.opacity(0.18), radius: 1, y: 1)
    }
}

/// Une ligne du fil : la bulle (à droite pour moi, à gauche pour les autres, photo de l'auteur en tête de série dans
/// un groupe), ses réactions ; glisser vers la droite = répondre (retour haptique au seuil) ; appui long = la bulle se
/// soulève avec la barre de réactions et le menu.
struct ChatBubble: View {
    let message: Conversation.Message
    let first: Bool
    let showAuthor: Bool
    let names: [String]
    /// Peut réagir (membre de la discussion).
    let canReact: Bool
    /// Peut répondre (membre, discussion ouverte à l'écriture).
    let canReply: Bool
    let actions: [BubbleAction]
    /// Bulle soulevée en ce moment : l'originale s'efface, sa copie est au-dessus du voile.
    let lifted: Bool
    @ObservedObject var player: VoicePlayer
    let onReact: (String) -> Void
    let onReply: () -> Void
    let onQuote: () -> Void
    let onFocus: (CGRect, AnyView) -> Void

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var frame = FrameBox()
    @State private var dx: CGFloat = 0
    @State private var armed = false
    @State private var swiping = false

    private var accent: Color { Color(uiColor: AppConfig.uiAccent) }
    private var avatar: CGFloat { 28 }
    private var swipable: Bool { canReply && !message.deleted && !message.pending }
    private var focusable: Bool { !message.pending && (!actions.isEmpty || (canReact && !message.deleted)) }
    static let threshold: CGFloat = 58

    private var body_: BubbleBody {
        BubbleBody(message: message, first: first, showAuthor: showAuthor, names: names, player: player, onQuote: onQuote)
    }

    var body: some View {
        HStack(alignment: .top, spacing: 4) {
            if message.mine {
                Spacer(minLength: 52)
            } else if showAuthor {
                if first { Initials(name: message.authorName, photo: message.authorPhoto, size: avatar) } else { Color.clear.frame(width: avatar, height: 1) }
            }
            VStack(alignment: message.mine ? .trailing : .leading, spacing: 0) {
                body_
                    .background(GeometryReader { geo in
                        Color.clear
                            .onAppear { frame.rect = geo.frame(in: .global) }
                            .onChange(of: geo.frame(in: .global)) { frame.rect = $0 }
                    })
                    // En cours d'envoi : bulle légèrement estompée, qui s'affirme une fois le message reçu.
                    .opacity(lifted ? 0 : message.pending ? 0.7 : 1)
                    .onLongPressGesture(minimumDuration: 0.32) {
                        guard focusable, dx == 0 else { return }
                        onFocus(frame.rect, AnyView(body_))
                    }
                if !message.reactions.isEmpty {
                    ReactionChips(message: message, canWrite: canReact, onReact: onReact)
                        .offset(y: -4).padding(.horizontal, 12).padding(.bottom, -4)
                        .opacity(lifted ? 0 : 1)
                        .motionTransition(.scale(scale: 0.6, anchor: message.mine ? .trailing : .leading).combined(with: .opacity))
                }
            }
            if !message.mine { Spacer(minLength: 52) }
        }
        .offset(x: dx)
        .background(alignment: .leading) { replyHint }
        .contentShape(Rectangle())
        .simultaneousGesture(swipe, including: swipable ? .all : .subviews)
        .motion(Motion.smooth, value: message.pending)
        .motion(Motion.bouncy, value: message.reactions.map { "\($0.emoji)\($0.count)\($0.mine)" })
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibility)
        .accessibilityHint(focusable ? "Glisse vers la droite pour répondre ; appui long pour réagir et voir les actions" : "")
        .accessibilityActions {
            if focusable && canReact && !message.deleted {
                Button("Réagir") { onFocus(frame.rect, AnyView(body_)) }
            }
            ForEach(actions) { action in Button(action.title, action: action.run) }
        }
    }

    /// Flèche de réponse qui apparaît sous le doigt pendant le glissé, et grossit au seuil.
    private var replyHint: some View {
        let progress = min(1, dx / Self.threshold)
        return Image(systemName: "arrowshape.turn.up.left.fill")
            .font(.system(size: 14, weight: .bold))
            .foregroundStyle(armed ? Color.black : Color.white)
            .frame(width: 30, height: 30)
            .background(armed ? accent : Color.white.opacity(0.14), in: Circle())
            .scaleEffect(reduceMotion ? 1 : 0.55 + 0.45 * progress + (armed ? 0.08 : 0))
            .opacity(progress)
            .offset(x: max(-30, min(10, dx - 40)))
            .accessibilityHidden(true)
    }

    /// Glissé horizontal vers la droite : la bulle suit le doigt (avec résistance), retour au relâcher.
    private var swipe: some Gesture {
        DragGesture(minimumDistance: 14, coordinateSpace: .local)
            .onChanged { value in
                let w = value.translation.width, h = value.translation.height
                if !swiping {
                    // Seulement un geste franchement horizontal vers la droite : le défilement garde la main.
                    guard w > 0, abs(w) > abs(h) * 1.6 else { return }
                    swiping = true
                }
                let pulled = max(0, w)
                let resisted = pulled < Self.threshold ? pulled : Self.threshold + (pulled - Self.threshold) * 0.3
                dx = min(resisted, 96)
                let over = dx >= Self.threshold
                if over != armed {
                    armed = over
                    if over { Haptics.press() } else { Haptics.selection() }
                }
            }
            .onEnded { _ in
                let reply = armed
                swiping = false
                armed = false
                Motion.animate(Motion.bouncy) { dx = 0 }
                if reply { onReply() }
            }
    }

    private var accessibility: String {
        let who = message.mine ? "Toi" : ContactNames.shared.label(for: message.author, pseudo: message.authorName).text
        let time = message.pending ? "envoi en cours" : message.date?.formatted(date: .omitted, time: .shortened) ?? ""
        return "\(who), \(time) : \(message.deleted ? message.body : message.preview)"
    }
}

/// Cadre d'une bulle à l'écran, gardé sans redessiner la vue (lu seulement à l'appui long).
final class FrameBox {
    var rect: CGRect = .zero
}

/// Le dessin d'une annonce (carte pleine largeur, en-tête 📣, bord de couleur), sans gestes.
struct AnnouncementBody: View {
    let message: Conversation.Message
    let names: [String]
    @ObservedObject var player: VoicePlayer

    private var accent: Color { Color(uiColor: AppConfig.uiAccent) }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 6) {
                Image(systemName: "megaphone.fill")
                Text("ANNONCE").font(.caption.weight(.heavy)).tracking(0.8)
                Text("· \(message.mine ? "toi" : message.authorName)").font(.caption.weight(.semibold)).foregroundStyle(.secondary).lineLimit(1)
                Spacer(minLength: 0)
                if message.pending { Image(systemName: "clock") } else {
                    Text(message.date?.formatted(date: .omitted, time: .shortened) ?? "").font(.caption2.monospacedDigit())
                        .foregroundStyle(.secondary)
                }
            }
            .font(.caption).foregroundStyle(accent)
            if let photo = message.photo.flatMap(URL.init(string:)) {
                AsyncImage(url: photo) { image in image.resizable().scaledToFill() } placeholder: { ProgressView() }
                    .frame(maxWidth: .infinity).frame(height: 200).clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
            }
            if let seconds = message.audioSeconds {
                VoiceBubble(player: player, id: message.id, url: message.audio.flatMap(URL.init(string:)), seconds: seconds, mine: false)
            }
            let text = ConversationView.clean(message.body)
            if !text.isEmpty {
                Text(Mentions.highlighted(text, names: names, color: accent)).font(.body.weight(.medium))
                    .tint(accent)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        // Opaque (le motif du fond ne passe pas dessous) : la teinte de l'app sur le violet des bulles.
        .background(Color(red: 0.24, green: 0.12, blue: 0.27), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).stroke(accent.opacity(0.85), lineWidth: 1.5))
    }
}

/// Annonce de l'organisation dans le fil : la carte, ses réactions ; appui long comme une bulle.
struct AnnouncementCard: View {
    let message: Conversation.Message
    let names: [String]
    let canReact: Bool
    let canReply: Bool
    let actions: [BubbleAction]
    let lifted: Bool
    @ObservedObject var player: VoicePlayer
    let onReact: (String) -> Void
    let onReply: () -> Void
    let onFocus: (CGRect, AnyView) -> Void

    @State private var frame = FrameBox()

    private var card: AnnouncementBody { AnnouncementBody(message: message, names: names, player: player) }
    private var focusable: Bool { !message.pending && (!actions.isEmpty || canReact) }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            card
                .background(GeometryReader { geo in
                    Color.clear
                        .onAppear { frame.rect = geo.frame(in: .global) }
                        .onChange(of: geo.frame(in: .global)) { frame.rect = $0 }
                })
                .opacity(lifted ? 0 : message.pending ? 0.7 : 1)
                .onLongPressGesture(minimumDuration: 0.32) {
                    guard focusable else { return }
                    onFocus(frame.rect, AnyView(card))
                }
            if !message.reactions.isEmpty {
                ReactionChips(message: message, canWrite: canReact, onReact: onReact)
                    .offset(y: -5).padding(.horizontal, 12).padding(.bottom, -5)
                    .opacity(lifted ? 0 : 1)
            }
        }
        .padding(.vertical, 6)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Annonce de \(message.mine ? "toi" : message.authorName) : \(ConversationView.clean(message.preview))")
        .accessibilityActions {
            if focusable && canReact { Button("Réagir") { onFocus(frame.rect, AnyView(card)) } }
            ForEach(actions) { action in Button(action.title, action: action.run) }
        }
        .accessibilityIdentifier("chat-announcement")
    }
}

/// Réactions sous la bulle (à cheval sur son bord) : un toucher ajoute ou retire la mienne.
struct ReactionChips: View {
    let message: Conversation.Message
    let canWrite: Bool
    let onReact: (String) -> Void

    private var accent: Color { Color(uiColor: AppConfig.uiAccent) }

    var body: some View {
        HStack(spacing: 4) {
            ForEach(message.reactions, id: \.emoji) { r in
                Button { onReact(r.emoji) } label: {
                    HStack(spacing: 3) {
                        Text(verbatim: r.emoji).font(.system(size: 14))
                        if r.count > 1 {
                            Text("\(r.count)").font(.caption2.weight(.semibold)).foregroundStyle(.secondary)
                                .contentTransition(.numericText())
                        }
                    }
                    .padding(.horizontal, 7).padding(.vertical, 3)
                    .background(Color(red: 0.11, green: 0.09, blue: 0.2), in: Capsule())
                    .overlay(Capsule().stroke(r.mine ? accent : Color.white.opacity(0.12), lineWidth: r.mine ? 1.5 : 1))
                }
                .buttonStyle(PressableStyle(scale: 0.9))
                .disabled(!canWrite)
                .accessibilityLabel("\(r.emoji) \(r.count)\(r.mine ? ", retirer ma réaction" : "")")
                .motionTransition(.scale(scale: 0.6).combined(with: .opacity))
            }
        }
    }
}

/// Point rouge de l'enregistrement : il bat doucement (immobile avec Réduire les animations).
struct RecordingDot: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var dim = false

    var body: some View {
        Circle().fill(.red).frame(width: 10, height: 10)
            .opacity(dim ? 0.3 : 1)
            .onAppear {
                guard !reduceMotion else { return }
                withAnimation(.easeInOut(duration: 0.7).repeatForever(autoreverses: true)) { dim = true }
            }
    }
}

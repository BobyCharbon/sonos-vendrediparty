import SwiftUI

/// Visuel d'une discussion : rond = une personne, carré emoji = un groupe (Membres Vendredi Party : logo officiel),
/// petit calendrier = une soirée.
struct ChatAvatar: View {
    let chat: ChatSummary
    var size: CGFloat = 54
    @ObservedObject private var contacts = ContactNames.shared

    var body: some View {
        switch chat.kind {
        case .direct:
            NeonAvatar(id: chat.userID ?? chat.id, name: contacts.label(for: chat.userID, pseudo: chat.name).primary,
                       photo: chat.photo, size: size)
        case .event:
            NeonDateTile(start: ChatDates.parse(chat.eventStart), color: chat.color, size: size)
                .saturation(chat.eventPast ? 0.35 : 1)
        case .group:
            GroupTile(emoji: chat.emoji ?? "👯", color: chat.color, photo: chat.photo, system: chat.system, size: size)
        }
    }
}

/// Une ligne de la liste : nom + heure, aperçu (auteur, @citation en rose, ✓✓ Vu), @, sourdine, non lus.
struct ChatListRow: View {
    let chat: ChatSummary
    var now = Date()
    @ObservedObject private var contacts = ContactNames.shared

    /// Message direct : « Nom du contact · pseudo » (contacts de l'iPhone) ; groupe, soirée : son nom.
    private var title: String { chat.direct ? contacts.label(for: chat.userID, pseudo: chat.name).text : chat.name }
    private var muted: Bool { chat.isMuted(now: now) }
    private var hot: Bool { chat.needsReading && !muted }

    var body: some View {
        HStack(spacing: 12) {
            ChatAvatar(chat: chat)
            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 8) {
                    Text(title)
                        .font(.body.weight(chat.needsReading ? .bold : .semibold))
                        .foregroundStyle(ChatNeon.t1)
                        .lineLimit(1)
                    if chat.isEvent {
                        Text(chat.eventPast ? "Passé" : "Événement")
                            .font(.caption2.weight(.bold)).kerning(0.6).textCase(.uppercase)
                            .foregroundStyle(chat.eventPast ? ChatNeon.t3 : ChatNeon.coral)
                    }
                    Spacer(minLength: 4)
                    Text(ChatListText.time(chat.lastAt, now: now))
                        .font(ChatNeon.time.weight(hot ? .semibold : .regular))
                        .foregroundStyle(hot ? ChatNeon.pinkInk : ChatNeon.t3)
                }
                HStack(spacing: 6) {
                    preview
                    Spacer(minLength: 4)
                    trailing
                }
            }
        }
        .frame(minHeight: 78)
        .contentShape(Rectangle())
        .motion(Motion.bouncy, value: chat.unread)
        .motion(Motion.smooth, value: chat.last)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(ChatListText.accessibility(chat, now: now))
    }

    @ViewBuilder private var preview: some View {
        HStack(spacing: 4) {
            if chat.outgoingRequest {
                Image(systemName: "paperplane").font(.footnote).foregroundStyle(ChatNeon.lav)
            } else if chat.seenByOther == true {
                HStack(spacing: -6) { Image(systemName: "checkmark"); Image(systemName: "checkmark") }
                    .font(.caption.weight(.bold)).foregroundStyle(ChatNeon.lav)
                    .accessibilityLabel("Vu")
            }
            Text(Self.styled(ChatListText.subtitle(chat), kind: chat.kind, strong: chat.needsReading))
                .font(ChatNeon.preview)
                .lineLimit(1)
        }
    }

    @ViewBuilder private var trailing: some View {
        if chat.mention && chat.unread > 0 {
            Text("@")
                .font(.subheadline.weight(.heavy))
                .foregroundStyle(ChatNeon.pinkInk)
                .frame(width: 22, height: 22)
                .overlay(Circle().strokeBorder(ChatNeon.pink, lineWidth: 2))
                .accessibilityLabel("On te cite")
        }
        if muted {
            Image(systemName: "bell.slash.fill").font(.footnote).foregroundStyle(ChatNeon.t3).accessibilityLabel("Sourdine")
        }
        if chat.unread > 0 {
            NeonCountBadge(count: chat.unread, muted: muted)
                .motionTransition(.scale(scale: 0.4).combined(with: .opacity))
        } else if chat.markedUnread {
            Circle().fill(muted ? ChatNeon.muted : ChatNeon.pink).frame(width: 12, height: 12)
                .accessibilityLabel("Marquée non lue")
        }
    }

    /// « Noé : » en clair, @citations en rose ; le reste en secondaire (en clair aussi quand c'est à lire).
    static func styled(_ text: String, kind: ChatKind, strong: Bool) -> AttributedString {
        var out = AttributedString()
        var body = Substring(text)
        if let range = text.range(of: " : "), text.distance(from: text.startIndex, to: range.lowerBound) <= 40 {
            var who = AttributedString(String(text[..<range.upperBound]))
            who.foregroundColor = ChatNeon.t1
            who.font = ChatNeon.preview.weight(.medium)
            out += who
            body = text[range.upperBound...]
        }
        for (i, word) in body.split(separator: " ", omittingEmptySubsequences: false).enumerated() {
            var piece = AttributedString((i > 0 ? " " : "") + word)
            if word.hasPrefix("@") && word.count > 1 {
                piece.foregroundColor = ChatNeon.pinkInk
                piece.font = ChatNeon.preview.weight(.semibold)
            } else {
                piece.foregroundColor = strong ? ChatNeon.t1 : ChatNeon.t2
            }
            out += piece
        }
        return out
    }
}

/// Épinglée en haut : grande tuile, anneau rose → lavande quand il y a à lire, compte des non lus.
struct ChatPinnedTile: View {
    let chat: ChatSummary
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var spin = 0.0

    private var round: Bool { chat.kind == .direct }

    var body: some View {
        let unread = chat.needsReading && !chat.isMuted()
        VStack(spacing: 7) {
            ZStack(alignment: .topTrailing) {
                ChatAvatar(chat: chat, size: 64)
                    .padding(2)
                    .background(ChatNeon.bg, in: RoundedRectangle(cornerRadius: round ? 40 : 22, style: .continuous))
                    .padding(3)
                    .background {
                        if unread {
                            RoundedRectangle(cornerRadius: round ? 40 : 24, style: .continuous)
                                .fill(ChatNeon.ring)
                                .rotationEffect(.degrees(spin))
                                .shadow(color: ChatNeon.pink.opacity(0.5), radius: 9)
                        }
                    }
                if chat.unread > 0 {
                    NeonCountBadge(count: chat.unread, muted: chat.isMuted()).offset(x: 4, y: -4)
                }
            }
            Text(chat.name)
                .font(.footnote.weight(.semibold))
                .foregroundStyle(unread ? ChatNeon.t1 : ChatNeon.t2)
                .lineLimit(1)
                .frame(maxWidth: 86)
        }
        .frame(width: 88)
        .padding(.vertical, 6)
        .contentShape(Rectangle())
        // L'anneau tourne une fois à l'arrivée d'un message, puis reste fixe.
        .onChange(of: chat.unread) { _ in
            guard !reduceMotion, unread else { return }
            withAnimation(.easeInOut(duration: 0.9)) { spin += 360 }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(ChatListText.accessibility(chat))
        .accessibilityAddTraits(.isButton)
    }
}

/// « Demandes » et « Archivées » : deux boutons plats sous les épinglées.
struct ChatSlimLink: View {
    let title: String
    let systemImage: String
    var count = 0
    var dot = false

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: systemImage).foregroundStyle(ChatNeon.lav)
            Text(title).font(.subheadline.weight(.semibold)).foregroundStyle(ChatNeon.t1)
            Spacer(minLength: 4)
            if dot {
                Circle().fill(ChatNeon.pink).frame(width: 8, height: 8).shadow(color: ChatNeon.pink, radius: 4)
            }
            if count > 0 {
                Text("\(count)").font(.subheadline.weight(.semibold)).monospacedDigit().foregroundStyle(ChatNeon.t3)
            }
        }
        .padding(.horizontal, 12)
        .frame(maxWidth: .infinity, minHeight: 44)
        .background(ChatNeon.glass, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(ChatNeon.glassLine, lineWidth: 1))
        .contentShape(Rectangle())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(count > 0 ? "\(title), \(count)" : title)
        .accessibilityAddTraits(.isButton)
    }
}

/// Puce de filtre : lavande quand elle est choisie ; « Non lus » porte son compte en rose.
struct ChatFilterChip: View {
    let filter: ChatFilter
    let selected: Bool
    var count = 0
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 6) {
                Text(filter.label)
                if count > 0 {
                    Text("\(count)")
                        .font(.caption.weight(.heavy)).monospacedDigit()
                        .foregroundStyle(ChatNeon.onPink)
                        .padding(.horizontal, 6).frame(minWidth: 20, minHeight: 20)
                        .background(ChatNeon.pink, in: Capsule())
                }
            }
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(selected ? PronoTheme.fixed(0x120B26) : ChatNeon.t2)
            .padding(.horizontal, 14)
            .frame(minHeight: 36)
            .background {
                if selected {
                    Capsule().fill(ChatNeon.lavenderGradient).shadow(color: ChatNeon.lavA.opacity(0.5), radius: 8, y: 4)
                } else {
                    Capsule().fill(ChatNeon.glass).overlay(Capsule().strokeBorder(ChatNeon.glassLine, lineWidth: 1))
                }
            }
            .frame(minHeight: 44)
            .contentShape(Capsule())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(count > 0 ? "\(filter.label), \(count)" : filter.label)
        .accessibilityAddTraits(selected ? [.isSelected] : [])
    }
}

/// Toucher d'une ligne : léger fond lavande, sans chevron (comme Messages).
struct ChatRowPressStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .background(configuration.isPressed ? ChatNeon.halo.opacity(0.5) : .clear)
    }
}

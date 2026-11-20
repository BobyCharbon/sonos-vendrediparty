import SwiftUI

/// Gestes d'une ligne (liste, Archivées) : glisser à droite = Lu / Non lu + Épingler ; à gauche = Archiver + Sourdine ;
/// appui long = aperçu + menu (Lu, Épingler, Sourdine 1 h / 8 h / 1 sem. / Toujours, Archiver, Voir le profil, Bloquer).
struct ChatRowActions: ViewModifier {
    let chat: ChatSummary
    @ObservedObject var store: ChatsStore
    /// Choisir la durée d'une sourdine (glisser) ; bloquer après confirmation ; mini-profil (nil : pas disponible).
    let askMute: (ChatSummary) -> Void
    let askBlock: (ChatSummary) -> Void
    let showProfile: ((String) -> Void)?
    /// Réorganiser les épinglées (tuiles, s'il y en a au moins deux).
    var reorderPins: (() -> Void)? = nil

    private var muted: Bool { chat.isMuted() }

    func body(content: Content) -> some View {
        content
            .swipeActions(edge: .leading, allowsFullSwipe: true) {
                Button { Task { await toggleRead() } } label: {
                    Label(chat.needsReading ? "Lu" : "Non lu", systemImage: chat.needsReading ? "envelope.open" : "envelope.badge")
                }
                .tint(ChatNeon.lavB)
                if !chat.archived && !chat.incomingRequest {
                    Button { Task { await store.setState(chat, pinned: !chat.pinned) } } label: {
                        Label(chat.pinned ? "Désépingler" : "Épingler", systemImage: chat.pinned ? "pin.slash" : "pin")
                    }
                    .tint(PronoTheme.pinkFill)
                }
            }
            .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                Button { Task { await store.setState(chat, archived: !chat.archived) } } label: {
                    Label(chat.archived ? "Désarchiver" : "Archiver", systemImage: chat.archived ? "tray.and.arrow.up" : "archivebox")
                }
                .tint(Color(hex: 0x5B5480))
                Button { if muted { Task { await store.mute(chat, nil) } } else { askMute(chat) } } label: {
                    Label(muted ? "Réactiver" : "Sourdine", systemImage: muted ? "bell" : "bell.slash")
                }
                .tint(Color(hex: 0xB25E00))
            }
            .contextMenu {
                menu
            } preview: {
                ChatPreviewCard(chat: chat)
            }
    }

    @ViewBuilder private var menu: some View {
        Button { Task { await toggleRead() } } label: {
            Label(chat.needsReading ? "Marquer comme lu" : "Marquer comme non lu",
                  systemImage: chat.needsReading ? "envelope.open" : "envelope.badge")
        }
        if !chat.archived && !chat.incomingRequest {
            Button { Task { await store.setState(chat, pinned: !chat.pinned) } } label: {
                Label(chat.pinned ? "Désépingler" : "Épingler", systemImage: chat.pinned ? "pin.slash" : "pin")
            }
            if chat.pinned, let reorderPins {
                Button { reorderPins() } label: { Label("Réorganiser les épinglées", systemImage: "arrow.left.arrow.right") }
            }
        }
        Menu {
            if muted {
                Button { Task { await store.mute(chat, nil) } } label: { Label("Réactiver", systemImage: "bell") }
            }
            ForEach(ChatMuteSpan.allCases) { span in
                Button(span.label) { Task { await store.mute(chat, span) } }
            }
        } label: {
            Label(muted ? "Sourdine (active)" : "Sourdine", systemImage: "bell.slash")
        }
        Button { Task { await store.setState(chat, archived: !chat.archived) } } label: {
            Label(chat.archived ? "Désarchiver" : "Archiver", systemImage: chat.archived ? "tray.and.arrow.up" : "archivebox")
        }
        if chat.direct, let user = chat.userID {
            if let showProfile {
                Button { showProfile(user) } label: { Label("Voir le profil", systemImage: "person.crop.circle") }
            }
            if !chat.blocked {
                Button(role: .destructive) { askBlock(chat) } label: { Label("Bloquer", systemImage: "hand.raised") }
            }
        }
    }

    private func toggleRead() async {
        Haptics.tap()
        if chat.needsReading { await store.markRead(chat) } else { await store.setState(chat, unread: true) }
    }
}

extension View {
    func chatRowActions(_ chat: ChatSummary, store: ChatsStore, askMute: @escaping (ChatSummary) -> Void,
                        askBlock: @escaping (ChatSummary) -> Void, showProfile: ((String) -> Void)?,
                        reorderPins: (() -> Void)? = nil) -> some View {
        modifier(ChatRowActions(chat: chat, store: store, askMute: askMute, askBlock: askBlock, showProfile: showProfile,
                                reorderPins: reorderPins))
    }
}

/// Aperçu de l'appui long : la discussion en grand, son dernier message en entier.
struct ChatPreviewCard: View {
    let chat: ChatSummary

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 12) {
                ChatAvatar(chat: chat, size: 56)
                VStack(alignment: .leading, spacing: 2) {
                    Text(chat.name).font(.headline).foregroundStyle(ChatNeon.t1).lineLimit(2)
                    Text(kindLine).font(.footnote).foregroundStyle(ChatNeon.t3)
                }
            }
            Text(ChatListText.subtitle(chat))
                .font(.body)
                .foregroundStyle(ChatNeon.t1)
                .lineLimit(6)
                .padding(12)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(ChatNeon.theirs, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).strokeBorder(ChatNeon.lavA.opacity(0.10), lineWidth: 1))
        }
        .padding(18)
        .frame(width: 320, alignment: .leading)
        .background(NeonGlow())
    }

    private var kindLine: String {
        let time = ChatListText.time(chat.lastAt)
        let kind: String
        switch chat.kind {
        case .direct: kind = "Message direct"
        case .group: kind = chat.members.map { $0 == 1 ? "Groupe · 1 membre" : "Groupe · \($0) membres" } ?? "Groupe"
        case .event: kind = chat.eventPast ? "Soirée passée" : "Discussion de la soirée"
        }
        return time.isEmpty ? kind : "\(kind) · \(time)"
    }
}

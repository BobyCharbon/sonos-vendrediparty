import PhotosUI
import SwiftUI

/// Conversation d'un groupe : bulles, réponses, photos, réactions ; les admins épinglent et suppriment.
/// Appui long sur une bulle : réagir, répondre, épingler, supprimer.
struct ConversationView: View {
    @ObservedObject var store: ChatsStore
    let group: String

    @State private var text = ""
    @State private var replyTo: Conversation.Message?
    @State private var picked: PhotosPickerItem?
    @State private var showInfo = false
    @FocusState private var writing: Bool

    private var chat: Conversation? { store.conversation?.id == group ? store.conversation : nil }

    var body: some View {
        VStack(spacing: 0) {
            if let chat {
                if let pinned = chat.pinned { pinnedBanner(pinned) }
                messages(chat)
                if chat.member { composer(chat) }
            } else if let error = store.error {
                Text(error).foregroundStyle(.secondary).padding().frame(maxHeight: .infinity)
            } else {
                ProgressView().frame(maxHeight: .infinity)
            }
        }
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle(chat?.name ?? "Discussion")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button { showInfo = true } label: { Image(systemName: "info.circle") }
                    .accessibilityLabel("Infos du groupe")
                    .disabled(chat == nil)
            }
        }
        .sheet(isPresented: $showInfo) { ChatInfoView(store: store) }
        .overlay(alignment: .bottom) { notice }
        .task(id: group) {
            while !Task.isCancelled {
                await store.open(group)
                try? await Task.sleep(for: ChatsStore.conversationEvery)
            }
        }
        .onDisappear { store.close() }
        .onChange(of: picked) { item in Task { await sendPhoto(item) } }
    }

    private func pinnedBanner(_ m: Conversation.Message) -> some View {
        HStack(spacing: 8) {
            Image(systemName: "pin.fill").foregroundStyle(Color(uiColor: AppConfig.uiAccent))
            Text("\(m.authorName) : \(m.preview)").font(.footnote).lineLimit(2)
            Spacer()
        }
        .padding(12)
        .background(.ultraThinMaterial)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Épinglé : \(m.authorName), \(m.preview)")
    }

    private func messages(_ chat: Conversation) -> some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 12) {
                    if chat.messages.isEmpty {
                        Text("Aucun message pour l'instant. Lance la discussion !").foregroundStyle(.secondary).padding(.top, 40)
                    }
                    ForEach(chat.messages) { m in
                        ChatBubble(message: m, reactions: chat.reactions, canWrite: chat.member, isAdmin: chat.admin,
                                   onReact: { emoji in Task { await store.react(m, emoji) } },
                                   onReply: { replyTo = m; writing = true },
                                   onPin: { Task { await store.pin(m) } },
                                   onDelete: { Task { await store.delete(m) } })
                            .id(m.id)
                    }
                }
                .padding(16)
            }
            .scrollDismissesKeyboard(.interactively)
            .onAppear { proxy.scrollTo(chat.messages.last?.id, anchor: .bottom) }
            .onChange(of: chat.messages.last?.id) { last in
                withAnimation { proxy.scrollTo(last, anchor: .bottom) }
            }
        }
    }

    private func composer(_ chat: Conversation) -> some View {
        VStack(spacing: 6) {
            if let replyTo {
                HStack {
                    Text("↪ Réponse à \(replyTo.authorName) : \(replyTo.preview)").font(.caption).foregroundStyle(.secondary).lineLimit(1)
                    Spacer()
                    Button { self.replyTo = nil } label: { Image(systemName: "xmark.circle.fill") }
                        .accessibilityLabel("Annuler la réponse")
                }
            }
            HStack(alignment: .bottom, spacing: 8) {
                PhotosPicker(selection: $picked, matching: .images) {
                    Image(systemName: "photo").font(.title3).frame(width: 36, height: 36)
                }
                .accessibilityLabel("Envoyer une photo")
                .disabled(store.sending)
                TextField(chat.admin ? "Message… (@surnom, @tout)" : "Message… (@surnom pour citer)", text: $text, axis: .vertical)
                    .lineLimit(1...5)
                    .focused($writing)
                    .padding(.horizontal, 12).padding(.vertical, 8)
                    .background(Color.white.opacity(0.08), in: RoundedRectangle(cornerRadius: 18))
                    .accessibilityLabel("Message")
                    .accessibilityIdentifier("chat-message")
                Button {
                    Task {
                        if await store.send(text, replyTo: replyTo?.id) {
                            text = ""
                            replyTo = nil
                        }
                    }
                } label: {
                    if store.sending { ProgressView().frame(width: 36, height: 36) } else {
                        Image(systemName: "arrow.up.circle.fill").font(.system(size: 32))
                    }
                }
                .accessibilityLabel("Envoyer")
                .accessibilityIdentifier("chat-send")
                .disabled(text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || store.sending)
            }
        }
        .padding(.horizontal, 12).padding(.vertical, 8)
        .background(.bar)
    }

    @ViewBuilder private var notice: some View {
        if let notice = store.notice {
            Text(notice).font(.footnote).padding(10).background(.ultraThinMaterial, in: Capsule()).padding(.bottom, 80)
                .onTapGesture { store.notice = nil }
                .task { try? await Task.sleep(for: .seconds(4)); store.notice = nil }
        }
    }

    private func sendPhoto(_ item: PhotosPickerItem?) async {
        guard let item else { return }
        picked = nil
        guard let data = try? await item.loadTransferable(type: Data.self), let image = UIImage(data: data),
              let jpeg = ChatPhoto.jpeg(from: image) else {
            store.notice = "Cette photo n'a pas pu être lue. Choisis-en une autre."
            return
        }
        if await store.send(text, replyTo: replyTo?.id, photo: jpeg) {
            text = ""
            replyTo = nil
        }
    }
}

/// Une bulle façon WhatsApp : mes messages à droite (rose), les autres à gauche avec nom et photo.
private struct ChatBubble: View {
    let message: Conversation.Message
    let reactions: [String]
    let canWrite: Bool
    let isAdmin: Bool
    let onReact: (String) -> Void
    let onReply: () -> Void
    let onPin: () -> Void
    let onDelete: () -> Void

    private var accent: Color { Color(uiColor: AppConfig.uiAccent) }
    private var actions: Bool { canWrite && !message.deleted }

    var body: some View {
        HStack(alignment: .bottom, spacing: 8) {
            if message.mine { Spacer(minLength: 48) } else { Initials(name: message.authorName, photo: message.authorPhoto) }
            VStack(alignment: message.mine ? .trailing : .leading, spacing: 4) {
                if !message.mine {
                    Text(message.authorName).font(.caption.weight(.bold)).foregroundStyle(Color(red: 0.73, green: 0.65, blue: 1))
                }
                bubble
                    .contextMenu { if actions { menu } }
                if !message.reactions.isEmpty { reactionChips }
                Text(time).font(.caption2).foregroundStyle(.secondary)
            }
            if !message.mine { Spacer(minLength: 48) }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(message.mine ? "Toi" : message.authorName) : \(message.deleted ? message.body : message.preview)")
        .accessibilityHint(actions ? "Appui long pour réagir, répondre\(isAdmin ? ", épingler" : "") ou supprimer" : "")
    }

    private var time: String {
        let t = message.date?.formatted(date: .omitted, time: .shortened) ?? ""
        return message.edited ? "\(t) · modifié" : t
    }

    private var bubble: some View {
        VStack(alignment: .leading, spacing: 6) {
            if message.pinned { Label("Épinglé", systemImage: "pin.fill").font(.caption2.weight(.bold)) }
            if let reply = message.reply {
                Text("↪ \(reply.name) : \(reply.text)").font(.caption).lineLimit(2).padding(6)
                    .background(Color.black.opacity(0.15), in: RoundedRectangle(cornerRadius: 8))
            }
            if let photo = message.photo.flatMap(URL.init(string:)) {
                AsyncImage(url: photo) { image in image.resizable().scaledToFill() } placeholder: { ProgressView() }
                    .frame(width: 230, height: 230).clipShape(RoundedRectangle(cornerRadius: 12))
                    .accessibilityLabel("Photo de \(message.authorName)")
            }
            if message.deleted {
                Label(message.body, systemImage: "nosign").font(.subheadline.italic()).foregroundStyle(.secondary)
            } else if !message.body.isEmpty {
                Text(message.body).font(.body)
            }
        }
        .foregroundStyle(message.mine && !message.deleted ? Color.black : Color.white)
        .padding(message.photo == nil ? 10 : 4)
        .background(message.deleted ? Color.white.opacity(0.06) : message.mine ? accent : Color(red: 0.13, green: 0.10, blue: 0.24),
                    in: RoundedRectangle(cornerRadius: 16))
    }

    @ViewBuilder private var menu: some View {
        ControlGroup {
            ForEach(reactions, id: \.self) { emoji in Button(emoji) { onReact(emoji) } }
        }
        Button { onReply() } label: { Label("Répondre", systemImage: "arrowshape.turn.up.left") }
        Button { UIPasteboard.general.string = message.body } label: { Label("Copier", systemImage: "doc.on.doc") }
        if isAdmin {
            Button { onPin() } label: { Label(message.pinned ? "Désépingler" : "Épingler", systemImage: message.pinned ? "pin.slash" : "pin") }
        }
        if message.mine || isAdmin {
            Button(role: .destructive) { onDelete() } label: { Label("Supprimer", systemImage: "trash") }
        }
    }

    private var reactionChips: some View {
        HStack(spacing: 4) {
            ForEach(message.reactions, id: \.emoji) { r in
                Button { onReact(r.emoji) } label: {
                    Text("\(r.emoji) \(r.count)").font(.caption)
                        .padding(.horizontal, 7).padding(.vertical, 3)
                        .background(r.mine ? accent.opacity(0.25) : Color.white.opacity(0.08), in: Capsule())
                        .overlay(Capsule().stroke(r.mine ? accent : .clear))
                }
                .buttonStyle(.plain)
                .disabled(!canWrite)
                .accessibilityLabel("\(r.emoji) \(r.count)\(r.mine ? ", retirer ma réaction" : "")")
            }
        }
    }
}

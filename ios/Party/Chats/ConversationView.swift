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
    @StateObject private var recorder = VoiceRecorder()
    @StateObject private var player = VoicePlayer()
    /// Pendant l'appui sur le micro : doigt glissé assez à gauche pour annuler.
    @State private var holdingMic = false
    @State private var cancelVoice = false

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
        .onDisappear { store.close(); player.stop(); _ = recorder.stop(send: false) }
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
                        ChatBubble(message: m, reactions: chat.reactions, canWrite: chat.member, isAdmin: chat.admin, player: player,
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
                if recorder.recording {
                    recordingBar
                } else {
                    PhotosPicker(selection: $picked, matching: .images) {
                        Image(systemName: "photo").font(.title3).frame(width: 36, height: 36)
                    }
                    .accessibilityLabel("Envoyer une photo")
                    .disabled(store.sending)
                    field(chat)
                }
                if text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !store.sending {
                    micButton
                } else {
                    sendButton
                }
            }
            if let problem = recorder.problem {
                Text(problem).font(.caption).foregroundStyle(.red)
            }
        }
        .padding(.horizontal, 12).padding(.vertical, 8)
        .background(.bar)
        .task { recorder.warmUp() }  // micro prêt avant le premier appui
    }

    private func field(_ chat: Conversation) -> some View {
                TextField(chat.admin ? "Message… (@surnom, @tout)" : "Message… (@surnom pour citer)", text: $text, axis: .vertical)
                    .lineLimit(1...5)
                    .focused($writing)
                    .padding(.horizontal, 12).padding(.vertical, 8)
                    .background(Color.white.opacity(0.08), in: RoundedRectangle(cornerRadius: 18))
                    .accessibilityLabel("Message")
                    .accessibilityIdentifier("chat-message")
    }

    private var sendButton: some View {
                Button {
                    // Champ vidé tout de suite, message affiché aussitôt ; en cas d'échec, le texte revient.
                    let typed = text, quoted = replyTo
                    text = ""
                    replyTo = nil
                    Task {
                        if !(await store.send(typed, replyTo: quoted?.id)) {
                            text = typed
                            replyTo = quoted
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

    /// Appui long : enregistre ; relâcher : envoie ; glisser vers la gauche : annule (comme WhatsApp).
    private var micButton: some View {
        Image(systemName: recorder.recording ? "mic.circle.fill" : "mic.circle")
            .font(.system(size: recorder.recording ? 44 : 32))
            .foregroundStyle(recorder.recording ? (cancelVoice ? Color.secondary : Color.red) : Color(uiColor: AppConfig.uiAccent))
            .frame(width: 44, height: 44)
            .contentShape(Rectangle())
            .gesture(DragGesture(minimumDistance: 0)
                .onChanged { value in
                    if !holdingMic {
                        holdingMic = true
                        cancelVoice = false
                        Task { await recorder.start() }
                    }
                    cancelVoice = value.translation.width < -90
                }
                .onEnded { _ in
                    holdingMic = false
                    if let (file, seconds) = recorder.stop(send: !cancelVoice) {
                        let quoted = replyTo
                        replyTo = nil
                        Task { await store.sendVoice(file, seconds: seconds, replyTo: quoted?.id) }
                    }
                    cancelVoice = false
                })
            .accessibilityLabel("Message vocal")
            .accessibilityHint("Maintiens pour enregistrer, relâche pour envoyer, glisse à gauche pour annuler")
            .accessibilityIdentifier("chat-mic")
    }

    private var recordingBar: some View {
        HStack(spacing: 10) {
            Circle().fill(.red).frame(width: 10, height: 10)
            Text(VoiceRecorder.clock(recorder.elapsed)).font(.body.monospacedDigit())
            Spacer()
            Text(cancelVoice ? "Relâche pour annuler" : "‹ Glisse pour annuler").font(.subheadline)
                .foregroundStyle(cancelVoice ? .red : .secondary)
        }
        .padding(.horizontal, 12).frame(height: 40)
        .background(Color.white.opacity(0.08), in: RoundedRectangle(cornerRadius: 18))
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Enregistrement \(VoiceRecorder.clock(recorder.elapsed))")
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
    @ObservedObject var player: VoicePlayer
    let onReact: (String) -> Void
    let onReply: () -> Void
    let onPin: () -> Void
    let onDelete: () -> Void

    /// Distance à glisser vers la droite pour répondre (comme WhatsApp) ; au-delà, l'élan est freiné.
    static let replySwipe: CGFloat = 64

    private var accent: Color { Color(uiColor: AppConfig.uiAccent) }
    private var actions: Bool { canWrite && !message.deleted && !message.pending }
    @State private var swipe: CGFloat = 0
    @State private var armed = false

    var body: some View {
        ZStack(alignment: .leading) {
            // Flèche de réponse qui apparaît sous le doigt pendant le glissement.
            Image(systemName: "arrowshape.turn.up.left.circle.fill")
                .font(.title2)
                .foregroundStyle(armed ? accent : .secondary)
                .opacity(Double(min(1, swipe / Self.replySwipe)))
                .scaleEffect(armed ? 1.15 : 0.8)
                .padding(.leading, 4)
                .accessibilityHidden(true)
            row.offset(x: swipe)
        }
        .simultaneousGesture(actions ? replyGesture : nil)
        .accessibilityAction(named: "Répondre") { if actions { onReply() } }
    }

    /// Glisser de gauche à droite : répondre à ce message (la personne est citée et notifiée).
    private var replyGesture: some Gesture {
        DragGesture(minimumDistance: 18)
            .onChanged { value in
                let dx = value.translation.width, dy = value.translation.height
                guard dx > 0, abs(dx) > abs(dy) * 1.5 else { return }
                swipe = dx < Self.replySwipe ? dx : Self.replySwipe + (dx - Self.replySwipe) * 0.25
                let reached = dx >= Self.replySwipe
                if reached != armed {
                    armed = reached
                    if reached { UIImpactFeedbackGenerator(style: .medium).impactOccurred() }
                }
            }
            .onEnded { _ in
                if armed { onReply() }
                armed = false
                withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) { swipe = 0 }
            }
    }

    private var row: some View {
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
        .accessibilityHint(actions ? "Glisse vers la droite pour répondre ; appui long pour réagir\(isAdmin ? ", épingler" : "") ou supprimer" : "")
    }

    private var time: String {
        if message.pending { return "Envoi…" }
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
            if let seconds = message.audioSeconds, !message.deleted {
                VoiceBubble(player: player, id: message.id, url: message.audio.flatMap(URL.init(string:)), seconds: seconds, mine: message.mine)
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
                    HStack(spacing: 3) {
                        Text(verbatim: r.emoji).font(.system(size: 14))
                        Text("\(r.count)").font(.caption).foregroundStyle(.secondary)
                    }
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

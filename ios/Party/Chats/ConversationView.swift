import PhotosUI
import SwiftUI

/// Conversation d'un groupe : bulles, réponses, photos, réactions, @citations (suggestions des membres en tapant @,
/// @tout), @annonce en surbrillance en haut ; les admins épinglent, retirent les annonces et suppriment.
/// Appui long sur une bulle : réagir, répondre, épingler, supprimer ; sur le bandeau (admins) : retirer l'annonce.
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
    /// Micro touché (pas maintenu) : l'enregistrement continue jusqu'au prochain toucher, qui l'envoie.
    @State private var micLocked = false
    @State private var pressedAt = Date()

    private var chat: Conversation? { store.conversation?.id == group ? store.conversation : nil }

    /// Titre : message direct, « Nom du contact · pseudo » de l'autre personne ; groupe, son nom.
    private var title: String {
        guard let chat else { return "Discussion" }
        return chat.isDirect ? ContactNames.shared.label(for: chat.userID, pseudo: chat.name).text : chat.name
    }

    var body: some View {
        VStack(spacing: 0) {
            if let chat {
                if let banner = chat.banner {
                    pinnedBanner(banner.item, others: banner.others, canRemove: chat.admin || chat.isDirect || (chat.isStaff && banner.item.announcement))
                        .motionTransition(.unfold)
                }
                messages(chat).transition(.opacity)
                if chat.blocked == true {
                    // Message direct : j'ai bloqué cette personne ; l'historique reste, l'écriture revient en la débloquant.
                    Text("Tu as bloqué \(title). Débloque-le dans les infos (ⓘ) pour lui écrire.")
                        .font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.center)
                        .padding().frame(maxWidth: .infinity).background(.bar)
                } else if chat.member {
                    composer(chat)
                }
            } else if let error = store.error {
                Text(error).foregroundStyle(.secondary).padding().frame(maxHeight: .infinity).transition(.opacity)
            } else {
                ProgressView().frame(maxHeight: .infinity).transition(.opacity)
            }
        }
        // Chargement → conversation : fondu ; message épinglé ou désépinglé : le bandeau se déplie.
        .motion(Motion.smooth, value: chat == nil)
        .motion(Motion.snappy, value: chat?.banner?.item.id)
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle(title)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button { showInfo = true } label: { Image(systemName: "info.circle") }
                    .accessibilityLabel(chat?.isDirect == true ? "Infos de la conversation" : "Infos du groupe")
                    .disabled(chat == nil)
            }
        }
        .sheet(isPresented: $showInfo) {
            if store.conversation?.isDirect == true { DirectChatInfoView(store: store) } else { ChatInfoView(store: store) }
        }
        .overlay(alignment: .bottom) { notice }
        .task(id: group) {
            while !Task.isCancelled {
                await store.open(group)
                try? await Task.sleep(for: ChatsStore.conversationEvery)
            }
        }
        .onDisappear { store.close(); player.stop(); micLocked = false; _ = recorder.stop(send: false) }
        .onChange(of: picked) { item in Task { await sendPhoto(item) } }
    }

    /// Descend au dernier message, après la mise en page de la liste (sinon la liste ne descend pas toujours).
    private func bottom(_ proxy: ScrollViewProxy, _ id: String?, animated: Bool = true, delay: Double = 0.05) {
        guard let id else { return }
        DispatchQueue.main.asyncAfter(deadline: .now() + delay) {
            if animated { Motion.animate(Motion.snappy) { proxy.scrollTo(id, anchor: .bottom) } } else { proxy.scrollTo(id, anchor: .bottom) }
        }
    }

    private func reply(to m: Conversation.Message) {
        Haptics.press()
        Motion.animate { replyTo = m }
        writing = true
    }

    /// Bandeau du haut : la dernière annonce en surbrillance (sinon le dernier épinglé) ; appui long (admins, et
    /// organisateurs pour une annonce) : la retirer.
    private func pinnedBanner(_ h: Conversation.Highlight, others: Int, canRemove admin: Bool) -> some View {
        let accent = Color(uiColor: AppConfig.uiAccent)
        return HStack(alignment: .top, spacing: 8) {
            Image(systemName: h.announcement ? "megaphone.fill" : "pin.fill").foregroundStyle(accent)
            VStack(alignment: .leading, spacing: 2) {
                Text(h.announcement ? "Annonce" : "Épinglé").font(.caption.weight(.bold)).foregroundColor(accent)
                    + Text(others > 0 ? " · +\(others)" : "").font(.caption).foregroundColor(.secondary)
                Text("\(h.authorName) : \(h.text)").font(h.announcement ? .subheadline.weight(.semibold) : .footnote).lineLimit(3)
            }
            Spacer()
        }
        .padding(12)
        .background(h.announcement ? AnyShapeStyle(accent.opacity(0.18)) : AnyShapeStyle(.ultraThinMaterial))
        .overlay(alignment: .bottom) { if h.announcement { accent.frame(height: 1) } }
        .contentShape(Rectangle())
        .contextMenu {
            if admin {
                Button(role: .destructive) { Task { await store.unpin(h.id) } } label: {
                    Label(h.announcement ? "Retirer l'annonce" : "Désépingler", systemImage: "pin.slash")
                }
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(h.announcement ? "Annonce" : "Épinglé") : \(h.authorName), \(h.text)")
        .accessibilityAction(named: h.announcement ? "Retirer l'annonce" : "Désépingler") { if admin { Task { await store.unpin(h.id) } } }
        .accessibilityIdentifier("chat-banner")
    }

    private func messages(_ chat: Conversation) -> some View {
        ScrollViewReader { proxy in
            // Liste native : glisser une bulle vers la droite = « Répondre » (glissement complet = réponse directe),
            // le geste d'iOS lui-même (Mail, Messages), qui ne se bat pas avec le défilement.
            List {
                if chat.messages.isEmpty {
                    VStack(spacing: 12) {
                        Text("Aucun message pour l'instant. Lance la discussion !").foregroundStyle(.secondary)
                        // Groupe tout neuf (créé depuis Discussions) : y ajouter du monde.
                        if chat.member && !chat.isDirect && chat.members.count <= 1 {
                            Button("Ajouter des membres") { showInfo = true }.buttonStyle(.borderedProminent)
                        }
                    }
                    .padding(.top, 40)
                    .frame(maxWidth: .infinity).listRowBackground(Color.clear).listRowSeparator(.hidden)
                }
                ForEach(chat.messages) { m in
                    ChatBubble(message: m, reactions: chat.reactions, canWrite: chat.member, isAdmin: chat.admin, isStaff: chat.isStaff,
                               canPin: chat.admin || chat.isDirect, player: player,
                               onReact: { emoji in Haptics.tap(); Task { await store.react(m, emoji) } },
                               onReply: { reply(to: m) },
                               onPin: { Task { await store.pin(m) } },
                               onDelete: { Task { await store.delete(m) } })
                        .id(m.id)
                        .listRowBackground(Color.clear)
                        .listRowSeparator(.hidden)
                        .listRowInsets(EdgeInsets(top: 6, leading: 16, bottom: 6, trailing: 16))
                        .swipeActions(edge: .leading, allowsFullSwipe: true) {
                            if chat.member && !m.deleted && !m.pending {
                                Button { reply(to: m) } label: { Label("Répondre", systemImage: "arrowshape.turn.up.left.fill") }
                                    .tint(Color(uiColor: AppConfig.uiAccent))
                            }
                        }
                }
            }
            .listStyle(.plain)
            .scrollContentBackground(.hidden)
            .scrollDismissesKeyboard(.interactively)
            // Bulle qui arrive (envoyée, reçue en direct) ou supprimée : la liste s'écarte en douceur
            // au lieu de sauter. Les relectures régulières sans nouveauté ne changent pas les identifiants : rien ne bouge.
            .motion(Motion.snappy, value: chat.messages.map(\.id))
            .onAppear { bottom(proxy, chat.messages.last?.id, animated: false) }
            // Nouveau message, ou dernier message qui grandit (réaction, envoi confirmé) : on reste en bas.
            .onChange(of: chat.messages.last) { last in bottom(proxy, last?.id) }
            // Clavier qui s'ouvre : le dernier message reste visible au-dessus du champ.
            .onChange(of: writing) { on in if on { bottom(proxy, chat.messages.last?.id, delay: 0.35) } }
        }
    }

    private func composer(_ chat: Conversation) -> some View {
        VStack(spacing: 6) {
            mentionBar(chat)
            if let replyTo {
                HStack {
                    Text("↪ Réponse à \(replyTo.authorName) : \(replyTo.preview)").font(.caption).foregroundStyle(.secondary).lineLimit(1)
                    Spacer()
                    Button { Motion.animate { self.replyTo = nil } } label: { Image(systemName: "xmark.circle.fill") }
                        .accessibilityLabel("Annuler la réponse")
                }
                .motionTransition(.opacity.combined(with: .move(edge: .bottom)))
            }
            HStack(alignment: .bottom, spacing: 8) {
                if recorder.recording {
                    recordingBar.motionTransition(.opacity.combined(with: .move(edge: .trailing)))
                } else {
                    PhotosPicker(selection: $picked, matching: .images) {
                        Image(systemName: "photo").font(.title3).frame(width: 36, height: 36)
                    }
                    .accessibilityLabel("Envoyer une photo")
                    .disabled(store.sending)
                    .transition(.opacity)
                    field(chat).transition(.opacity)
                }
                // Micro ↔ flèche d'envoi : l'un rétrécit pendant que l'autre grandit, comme dans Messages.
                if text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !store.sending {
                    micButton.motionTransition(.scale(scale: 0.5).combined(with: .opacity))
                } else {
                    sendButton.motionTransition(.scale(scale: 0.5).combined(with: .opacity))
                }
            }
            if let problem = recorder.problem {
                Text(problem).font(.caption).foregroundStyle(.red).motionTransition(.unfold)
            }
        }
        .motion(Motion.snappy, value: text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
        .motion(Motion.snappy, value: store.sending)
        .motion(Motion.snappy, value: recorder.recording)
        .motion(Motion.snappy, value: replyTo?.id)
        .motion(Motion.snappy, value: Mentions.query(in: text) == nil)
        .motion(Motion.snappy, value: recorder.problem)
        .padding(.horizontal, 12).padding(.vertical, 8)
        .background(.bar)
        .task { recorder.warmUp() }  // micro prêt avant le premier appui
    }

    /// Suggestions de l'@ en cours de frappe : membres filtrés en direct, puis @tout et @annonce ; un toucher insère.
    @ViewBuilder private func mentionBar(_ chat: Conversation) -> some View {
        let found: [Mentions.Suggestion] = chat.isDirect ? [] : Mentions.query(in: text).map {
            Mentions.suggestions(for: $0, members: chat.members, me: chat.me, everyone: chat.canEveryone, announce: chat.isStaff,
                                 contacts: ContactNames.shared.names)
        } ?? []
        if let note = chat.tagNote(for: text) {
            Label(note, systemImage: "info.circle").font(.caption).foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .motionTransition(.opacity)
        }
        if !found.isEmpty {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(found) { s in
                        Button {
                            Haptics.selection()
                            text = Mentions.insert(s.label, into: text)
                        } label: {
                            HStack(spacing: 6) {
                                if let m = s.member {
                                    Initials(name: m.name, photo: m.photo, size: 24)
                                } else {
                                    Image(systemName: s.label == "tout" ? "person.3.fill" : "megaphone.fill").font(.caption)
                                }
                                Text("@" + s.label).font(.subheadline.weight(.semibold)).lineLimit(1)
                                // Nom de mon répertoire à côté du pseudo inséré (le @ reste le pseudo Party).
                                if s.member != nil && !s.hint.isEmpty {
                                    Text(s.hint).font(.caption).foregroundStyle(.secondary).lineLimit(1)
                                }
                            }
                            .padding(.horizontal, 10).padding(.vertical, 6)
                            .background(Color.white.opacity(0.1), in: Capsule())
                        }
                        .buttonStyle(PressableStyle(scale: 0.94))
                        .accessibilityLabel(s.member != nil ? "Citer \(s.label)" : "@\(s.label) : \(s.hint)")
                    }
                }
            }
            .accessibilityIdentifier("chat-mentions")
            .motionTransition(.opacity.combined(with: .move(edge: .bottom)))
        }
    }

    private func field(_ chat: Conversation) -> some View {
                TextField(chat.isDirect ? "Message…" : "Message… (@ pour citer, @tout, @annonce)", text: $text, axis: .vertical)
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
                    Haptics.tap()
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
    /// Simple toucher : l'enregistrement reste actif ; un second toucher l'envoie, sans jamais en relancer un autre.
    private var micButton: some View {
        Image(systemName: recorder.recording ? "mic.circle.fill" : "mic.circle")
            .font(.system(size: 32))
            // Enregistrement : le micro grossit sous le doigt (échelle animée, plus un saut de taille de police).
            .scaleEffect(recorder.recording ? 1.35 : 1)
            .foregroundStyle(recorder.recording ? (cancelVoice ? Color.secondary : Color.red) : Color(uiColor: AppConfig.uiAccent))
            .frame(width: 44, height: 44)
            .contentShape(Rectangle())
            .gesture(DragGesture(minimumDistance: 0)
                .onChanged { value in
                    if !holdingMic {
                        holdingMic = true
                        pressedAt = Date()
                        if micLocked && !recorder.recording { micLocked = false }  // micro refusé ou jamais ouvert
                        cancelVoice = false
                        if !micLocked { Task { await recorder.start() } }  // verrouillé : ce toucher-ci envoie
                    }
                    let cancelling = value.translation.width < -90
                    if cancelling != cancelVoice {
                        Haptics.selection()  // seuil d'annulation franchi, dans un sens ou dans l'autre
                        Motion.animate { cancelVoice = cancelling }
                    }
                }
                .onEnded { _ in
                    holdingMic = false
                    defer { cancelVoice = false }
                    if !micLocked && !cancelVoice && Date().timeIntervalSince(pressedAt) < Self.tapSeconds {
                        micLocked = true  // simple toucher : on continue d'enregistrer
                        return
                    }
                    micLocked = false
                    sendVoice(recorder.stop(send: !cancelVoice))
                })
            .accessibilityLabel("Message vocal")
            .accessibilityHint("Maintiens pour enregistrer et relâche pour envoyer, ou touche une fois pour enregistrer et encore une fois pour envoyer")
            .accessibilityIdentifier("chat-mic")
    }

    /// Plus court qu'un appui : un toucher, qui verrouille l'enregistrement.
    static let tapSeconds: TimeInterval = 0.35

    private func sendVoice(_ recorded: (URL, TimeInterval)?) {
        guard let (file, seconds) = recorded else { return }
        let quoted = replyTo
        replyTo = nil
        Task { await store.sendVoice(file, seconds: seconds, replyTo: quoted?.id) }
    }

    private var recordingBar: some View {
        HStack(spacing: 10) {
            RecordingDot()
            Text(VoiceRecorder.clock(recorder.elapsed)).font(.body.monospacedDigit())
                .contentTransition(.numericText())
                .motion(Motion.snappy, value: Int(recorder.elapsed.rounded()))
            Spacer()
            if micLocked {
                Button("Annuler") { micLocked = false; _ = recorder.stop(send: false) }.font(.subheadline)
                Text("Touche le micro pour envoyer").font(.subheadline).foregroundStyle(.secondary)
            } else {
                Text(cancelVoice ? "Relâche pour annuler" : "‹ Glisse pour annuler").font(.subheadline)
                    .foregroundStyle(cancelVoice ? .red : .secondary)
            }
        }
        .padding(.horizontal, 12).frame(height: 40)
        .background(Color.white.opacity(0.08), in: RoundedRectangle(cornerRadius: 18))
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Enregistrement \(VoiceRecorder.clock(recorder.elapsed))")
    }

    private var notice: some View {
        NoticeBanner(notice: store.notice.map { NoticeBanner.Notice(text: $0, tone: .error) }, seconds: 4, material: true) {
            store.notice = nil
        }
        .padding(.bottom, 68)
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
    /// Admin ou organisateur : retire les annonces.
    let isStaff: Bool
    /// Épingle : admins d'un groupe, les deux personnes d'un message direct.
    let canPin: Bool
    @ObservedObject var player: VoicePlayer
    let onReact: (String) -> Void
    let onReply: () -> Void
    let onPin: () -> Void
    let onDelete: () -> Void

    private var accent: Color { Color(uiColor: AppConfig.uiAccent) }
    private var actions: Bool { canWrite && !message.deleted && !message.pending }

    var body: some View {
        row.accessibilityAction(named: "Répondre") { if actions { onReply() } }
    }

    private var row: some View {
        HStack(alignment: .bottom, spacing: 8) {
            if message.mine { Spacer(minLength: 48) } else { Initials(name: message.authorName, photo: message.authorPhoto) }
            VStack(alignment: message.mine ? .trailing : .leading, spacing: 4) {
                if !message.mine {
                    PersonName(id: message.author, pseudo: message.authorName, pseudoFont: .caption2)
                        .font(.caption.weight(.bold)).foregroundStyle(Color(red: 0.73, green: 0.65, blue: 1))
                }
                bubble
                    // En cours d'envoi : bulle légèrement estompée, qui s'affirme une fois le message reçu.
                    .opacity(message.pending ? 0.65 : 1)
                    .contextMenu { if actions { menu } }
                if !message.reactions.isEmpty { reactionChips.motionTransition(.scale(scale: 0.6, anchor: message.mine ? .trailing : .leading).combined(with: .opacity)) }
                Text(time).font(.caption2).foregroundStyle(.secondary)
                    .id(time).transition(.opacity)
            }
            if !message.mine { Spacer(minLength: 48) }
        }
        .motion(Motion.smooth, value: message.pending)
        .motion(Motion.bouncy, value: message.reactions.map { "\($0.emoji)\($0.count)\($0.mine)" })
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(message.mine ? "Toi" : ContactNames.shared.label(for: message.author, pseudo: message.authorName).text) : \(message.deleted ? message.body : message.preview)")
        .accessibilityHint(actions ? "Glisse vers la droite pour répondre ; appui long pour réagir\(isAdmin ? ", épingler" : "") ou supprimer" : "")
    }

    private var time: String {
        if message.pending { return "Envoi…" }
        let t = message.date?.formatted(date: .omitted, time: .shortened) ?? ""
        return message.edited ? "\(t) · modifié" : t
    }

    private var bubble: some View {
        VStack(alignment: .leading, spacing: 6) {
            if message.pinned {
                Label(message.isAnnouncement ? "Annonce" : "Épinglé", systemImage: message.isAnnouncement ? "megaphone.fill" : "pin.fill")
                    .font(.caption2.weight(.bold))
            }
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
        .overlay {
            if message.isAnnouncement {
                RoundedRectangle(cornerRadius: 16).stroke(message.mine ? Color.white : accent, lineWidth: 2)
            }
        }
    }

    @ViewBuilder private var menu: some View {
        ControlGroup {
            ForEach(reactions, id: \.self) { emoji in Button(emoji) { onReact(emoji) } }
        }
        Button { onReply() } label: { Label("Répondre", systemImage: "arrowshape.turn.up.left") }
        Button { UIPasteboard.general.string = message.body } label: { Label("Copier", systemImage: "doc.on.doc") }
        if message.isAnnouncement {
            if isStaff { Button { onPin() } label: { Label("Retirer l'annonce", systemImage: "pin.slash") } }
        } else if canPin {
            Button { onPin() } label: {
                Label(message.pinned ? "Désépingler" : "Épingler", systemImage: message.pinned ? "pin.slash" : "pin")
            }
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
                            .contentTransition(.numericText())
                    }
                        .padding(.horizontal, 7).padding(.vertical, 3)
                        .background(r.mine ? accent.opacity(0.25) : Color.white.opacity(0.08), in: Capsule())
                        .overlay(Capsule().stroke(r.mine ? accent : .clear))
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
private struct RecordingDot: View {
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


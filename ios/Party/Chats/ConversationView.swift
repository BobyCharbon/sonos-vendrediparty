import PhotosUI
import SwiftUI

/// Conversation (groupe, message direct, discussion d'un événement), façon WhatsApp (16.11.2026) : séparateurs de jours,
/// messages d'une même personne regroupés (nom en tête, photo en bas), heure dans la bulle, @citations en couleur,
/// citation qui remonte au message d'origine, bouton ↓ avec les nouveaux messages, bandeau des annonces et épinglés
/// qui passe de l'un à l'autre, annonces en carte. Glisser une bulle vers la droite : répondre ; appui long : réagir,
/// répondre, copier, épingler, supprimer, signaler.
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
    /// Modération commune : « Signaler » un message ; conditions d'utilisation avant le premier message.
    @State private var reporting: ReportTarget?
    @State private var askTerms = false
    /// Organisation d'un événement : le prochain message part en annonce (📣).
    @State private var announcing = false
    /// Bas du fil visible ; sinon le bouton ↓ apparaît avec le nombre de messages arrivés entre-temps.
    @State private var atBottom = true
    @State private var unseen = 0
    /// Message à montrer (citation, bandeau) puis à faire clignoter.
    @State private var jumpTo: String?
    @State private var flashing: String?
    @State private var pinIndex = 0
    /// Entré avec sa réponse à un événement (17.11) : bandeau gardé tant que l'écran est ouvert (la base ne le rend qu'une fois).
    @State private var joinNote: Conversation.JoinNote?
    @State private var confirmLeave = false

    private var chat: Conversation? { store.conversation?.id == group ? store.conversation : nil }
    private var accent: Color { Color(uiColor: AppConfig.uiAccent) }
    private static let end = "chat-end"

    /// Titre : message direct, « Nom du contact · pseudo » de l'autre personne ; groupe ou événement, son nom.
    private var title: String {
        guard let chat else { return "Discussion" }
        return chat.isDirect ? ContactNames.shared.label(for: chat.userID, pseudo: chat.name).text : chat.name
    }

    private var subtitle: String? {
        guard let chat, !chat.isDirect else { return nil }
        let n = chat.members.count
        if chat.isEvent { return n > 1 ? "Discussion · \(n) personnes" : "Discussion de l'événement" }
        return n == 1 ? "1 membre" : "\(n) membres"
    }

    var body: some View {
        VStack(spacing: 0) {
            if let note = joinNote {
                joinBanner(note).motionTransition(.unfold)
            }
            if let chat {
                let pins = chat.pins
                if !pins.isEmpty {
                    pinnedBanner(pins, chat: chat).motionTransition(.unfold)
                }
                messages(chat).transition(.opacity)
                if chat.blocked == true {
                    // Message direct : j'ai bloqué cette personne ; l'historique reste, l'écriture revient en la débloquant.
                    Text("Tu as bloqué \(title). Débloque-le dans les infos (ⓘ) pour lui écrire.")
                        .font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.center)
                        .padding().frame(maxWidth: .infinity).background(.bar)
                } else if chat.member {
                    composer(chat)
                } else if chat.isEvent {
                    Text("Tu peux lire la discussion ; tu pourras écrire une fois l'événement publié et ta place confirmée.")
                        .font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.center)
                        .padding().frame(maxWidth: .infinity).background(.bar)
                }
            } else if let error = store.error {
                Text(error).foregroundStyle(.secondary).padding().frame(maxHeight: .infinity).transition(.opacity)
            } else {
                ProgressView().frame(maxHeight: .infinity).transition(.opacity)
            }
        }
        // Chargement → conversation : fondu ; message épinglé ou désépinglé : le bandeau se déplie.
        .motion(Motion.smooth, value: chat == nil)
        .motion(Motion.snappy, value: chat?.pins.map(\.id))
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle(title)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .principal) {
                // Titre et sous-titre, comme WhatsApp : un toucher ouvre les infos.
                Button { showInfo = true } label: {
                    VStack(spacing: 0) {
                        Text(title).font(.headline).lineLimit(1)
                        if let subtitle { Text(subtitle).font(.caption2).foregroundStyle(.secondary).lineLimit(1) }
                    }
                }
                .buttonStyle(.plain)
                .disabled(chat == nil)
                .accessibilityHint("Ouvre les infos")
            }
            ToolbarItem(placement: .navigationBarTrailing) {
                Button { showInfo = true } label: { Image(systemName: "info.circle") }
                    .accessibilityLabel(chat?.isDirect == true ? "Infos de la conversation" : chat?.isEvent == true ? "Participants et notifications" : "Infos du groupe")
                    .disabled(chat == nil)
            }
        }
        .sheet(isPresented: $showInfo) {
            if store.conversation?.isEvent == true { EventChatInfoView(store: store) }
            else if store.conversation?.isDirect == true { DirectChatInfoView(store: store) } else { ChatInfoView(store: store) }
        }
        .sheet(item: $reporting) { ReportSheet(store: store.moderation, target: $0) }
        .sheet(isPresented: $askTerms) { TermsAcceptSheet(store: store.moderation) }
        .overlay(alignment: .bottom) { notice }
        .task(id: group) {
            while !Task.isCancelled {
                await store.open(group)
                try? await Task.sleep(for: ChatsStore.conversationEvery)
            }
        }
        .onDisappear { store.close(); player.stop(); micLocked = false; _ = recorder.stop(send: false) }
        .onChange(of: picked) { item in Task { await sendPhoto(item) } }
        .onChange(of: chat?.joinNote) { note in if joinNote == nil, let note { Motion.animate(Motion.snappy) { joinNote = note } } }
    }

    // MARK: Bandeau « Tu es dans le groupe » (entrée par une réponse à un événement, 17.11)

    private func joinBanner(_ note: Conversation.JoinNote) -> some View {
        HStack(alignment: .center, spacing: 10) {
            Image(systemName: "person.2.fill").foregroundStyle(Color(red: 0.725, green: 0.655, blue: 1))
            VStack(alignment: .leading, spacing: 2) {
                Text("Tu es dans le groupe « \(note.groupName) »").font(.subheadline.weight(.semibold)).lineLimit(2)
                Text(Self.joinLine(note)).font(.caption).foregroundStyle(.secondary).lineLimit(2)
            }
            Spacer(minLength: 0)
            if note.creator != true {
                Button("Quitter", role: .destructive) { confirmLeave = true }
                    .buttonStyle(.bordered).controlSize(.small)
                    .accessibilityIdentifier("group-join-leave")
            }
            Button { Motion.animate(Motion.snappy) { joinNote = nil } } label: {
                Image(systemName: "xmark").font(.caption.weight(.bold)).frame(width: 30, height: 30)
            }
            .buttonStyle(.plain).foregroundStyle(.secondary).accessibilityLabel("Fermer")
        }
        .padding(.horizontal, 14).padding(.vertical, 10)
        .background(.ultraThinMaterial)
        .overlay(alignment: .bottom) { Color.white.opacity(0.08).frame(height: 1) }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("group-join-note")
        .confirmationDialog("Quitter « \(note.groupName) » ?", isPresented: $confirmLeave, titleVisibility: .visible) {
            Button("Quitter le groupe", role: .destructive) {
                Task { if await store.leaveGroup() { Motion.animate(Motion.snappy) { joinNote = nil } } }
            }
        } message: {
            Text("Personne n'est prévenu. Tu ne seras plus remis dans ce groupe sans ton propre geste.")
        }
    }

    /// « Ajouté avec ta réponse à « Raclette » de Ludo ».
    static func joinLine(_ note: Conversation.JoinNote) -> String {
        "Ajouté avec ta réponse à « \(note.eventTitle) »" + (note.owner.map { " de \($0)" } ?? "")
    }

    /// Descend en bas du fil, après la mise en page de la liste (sinon la liste ne descend pas toujours).
    private func bottom(_ proxy: ScrollViewProxy, animated: Bool = true, delay: Double = 0.05) {
        DispatchQueue.main.asyncAfter(deadline: .now() + delay) {
            if animated { Motion.animate(Motion.snappy) { proxy.scrollTo(Self.end, anchor: .bottom) } } else { proxy.scrollTo(Self.end, anchor: .bottom) }
        }
    }

    /// Montre un message au milieu de l'écran puis le fait clignoter (citation touchée, bandeau).
    private func show(_ id: String, _ proxy: ScrollViewProxy) {
        Motion.animate(Motion.smooth) { proxy.scrollTo(id, anchor: .center) }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
            Motion.animate(Motion.snappy) { flashing = id }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.9) { Motion.animate(Motion.smooth) { if flashing == id { flashing = nil } } }
        }
    }

    private func reply(to m: Conversation.Message) {
        Haptics.press()
        Motion.animate { replyTo = m }
        writing = true
    }

    // MARK: Bandeau des annonces et épinglés

    /// Annonces puis épinglés : un toucher montre le message et passe au suivant ; traits à gauche = combien il y en a.
    private func pinnedBanner(_ pins: [Conversation.Highlight], chat: Conversation) -> some View {
        let index = pinIndex % pins.count
        let h = pins[index]
        let canRemove = chat.admin || chat.isDirect || (chat.isStaff && h.announcement)
        return HStack(alignment: .center, spacing: 10) {
            if pins.count > 1 {
                VStack(spacing: 2) {
                    ForEach(0..<min(pins.count, 5), id: \.self) { i in
                        Capsule().fill(i == min(index, 4) ? accent : Color.secondary.opacity(0.35)).frame(width: 3)
                    }
                }
                .frame(height: 34)
            }
            Image(systemName: h.announcement ? "megaphone.fill" : "pin.fill").foregroundStyle(accent)
            VStack(alignment: .leading, spacing: 2) {
                Text(h.announcement ? "Annonce" : "Message épinglé").font(.caption.weight(.bold)).foregroundColor(accent)
                    + Text(pins.count > 1 ? "  \(index + 1)/\(pins.count)" : "").font(.caption.monospacedDigit()).foregroundColor(.secondary)
                Text("\(h.authorName) : \(Self.clean(h.text))")
                    .font(h.announcement ? .subheadline.weight(.semibold) : .subheadline).lineLimit(h.announcement ? 2 : 1)
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 14).padding(.vertical, 10)
        .background(h.announcement ? AnyShapeStyle(accent.opacity(0.16)) : AnyShapeStyle(.ultraThinMaterial))
        .overlay(alignment: .bottom) { (h.announcement ? accent.opacity(0.6) : Color.white.opacity(0.08)).frame(height: 1) }
        .contentShape(Rectangle())
        .onTapGesture {
            Haptics.selection()
            jumpTo = h.id
            if pins.count > 1 { Motion.animate(Motion.snappy) { pinIndex = index + 1 } }
        }
        .contextMenu {
            Button { jumpTo = h.id } label: { Label("Voir le message", systemImage: "text.bubble") }
            if canRemove {
                Button(role: .destructive) { Task { await store.unpin(h.id) } } label: {
                    Label(h.announcement ? "Retirer l'annonce" : "Désépingler", systemImage: "pin.slash")
                }
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(h.announcement ? "Annonce" : "Épinglé") \(pins.count > 1 ? "\(index + 1) sur \(pins.count)" : "") : \(h.authorName), \(Self.clean(h.text))")
        .accessibilityHint("Touche pour voir le message")
        .accessibilityAction(named: h.announcement ? "Retirer l'annonce" : "Désépingler") { if canRemove { Task { await store.unpin(h.id) } } }
        .accessibilityIdentifier("chat-banner")
    }

    /// « @annonce » ne s'affiche pas dans le texte d'une annonce (la carte le dit déjà).
    static func clean(_ text: String) -> String {
        let stripped = text.replacingOccurrences(of: "(^|\\s)@annonce(?=$|[^\\p{L}\\p{N}_])", with: "$1",
                                                 options: [.regularExpression, .caseInsensitive])
        return stripped.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    // MARK: Fil

    private func messages(_ chat: Conversation) -> some View {
        let names = chat.members.map(\.name)
        let rows = ChatTimeline.rows(chat.messages)
        return ScrollViewReader { proxy in
            // Liste native : glisser une bulle vers la droite = « Répondre » (glissement complet = réponse directe),
            // le geste d'iOS lui-même (Mail, Messages), qui ne se bat pas avec le défilement.
            List {
                if chat.messages.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "bubble.left.and.bubble.right").font(.largeTitle).foregroundStyle(.secondary)
                        Text(chat.isEvent ? "Aucun message pour l'instant. Lance la discussion avec les invités !"
                                          : "Aucun message pour l'instant. Lance la discussion !")
                            .foregroundStyle(.secondary).multilineTextAlignment(.center)
                        // Groupe tout neuf (créé depuis Discussions) : y ajouter du monde.
                        if chat.member && !chat.isDirect && !chat.isEvent && chat.members.count <= 1 {
                            Button("Ajouter des membres") { showInfo = true }.buttonStyle(.borderedProminent)
                        }
                    }
                    .padding(.top, 60)
                    .frame(maxWidth: .infinity).listRowBackground(Color.clear).listRowSeparator(.hidden)
                }
                ForEach(rows) { row in
                    switch row.kind {
                    case .day(let label):
                        DayPill(label: label)
                            .frame(maxWidth: .infinity)
                            .listRowBackground(Color.clear).listRowSeparator(.hidden)
                            .listRowInsets(EdgeInsets(top: 10, leading: 16, bottom: 6, trailing: 16))
                    case .message(let m, let first, let last):
                        messageRow(m, first: first, last: last, chat: chat, names: names, proxy: proxy)
                    }
                }
                // Bas du fil : visible = on suit les nouveaux messages ; caché = bouton ↓.
                Color.clear.frame(height: 1).id(Self.end)
                    .listRowBackground(Color.clear).listRowSeparator(.hidden).listRowInsets(EdgeInsets())
                    .onAppear { atBottom = true; unseen = 0 }
                    .onDisappear { atBottom = false }
            }
            .listStyle(.plain)
            .scrollContentBackground(.hidden)
            .scrollDismissesKeyboard(.interactively)
            // Bulle qui arrive (envoyée, reçue en direct) ou supprimée : la liste s'écarte en douceur
            // au lieu de sauter. Les relectures régulières sans nouveauté ne changent pas les identifiants : rien ne bouge.
            .motion(Motion.snappy, value: chat.messages.map(\.id))
            .overlay(alignment: .bottomTrailing) { jumpButton(proxy) }
            .onAppear { bottom(proxy, animated: false) }
            // Nouveau message : on suit s'il est à moi ou si l'on était en bas ; sinon le bouton ↓ le compte.
            .onChange(of: chat.messages.last?.id) { _ in
                guard let last = chat.messages.last else { return }
                if last.mine || atBottom { bottom(proxy) } else { Motion.animate(Motion.bouncy) { unseen += 1 } }
            }
            // Réaction, envoi confirmé sur le dernier message : on reste en bas si on y était.
            .onChange(of: chat.messages.last) { _ in if atBottom { bottom(proxy) } }
            // Clavier qui s'ouvre : le dernier message reste visible au-dessus du champ.
            .onChange(of: writing) { on in if on { bottom(proxy, delay: 0.35) } }
            .onChange(of: jumpTo) { id in
                guard let id else { return }
                jumpTo = nil
                if chat.messages.contains(where: { $0.id == id }) { show(id, proxy) } else { store.notice = "Ce message est plus ancien que ceux affichés." }
            }
        }
    }

    @ViewBuilder
    private func messageRow(_ m: Conversation.Message, first: Bool, last: Bool, chat: Conversation, names: [String],
                            proxy: ScrollViewProxy) -> some View {
        let report = {
            reporting = ReportTarget(kind: chat.isEvent ? .eventMessage : chat.isDirect ? .directMessage : .groupMessage, id: m.id,
                                     label: "le message de \(m.authorName)")
        }
        Group {
            if m.isAnnouncement {
                AnnouncementCard(message: m, names: names, reactions: chat.reactions, canWrite: chat.member, isStaff: chat.isStaff,
                                 isAdmin: chat.admin, player: player,
                                 onReact: { emoji in Haptics.tap(); Task { await store.react(m, emoji) } },
                                 onReply: { reply(to: m) }, onPin: { Task { await store.pin(m) } },
                                 onDelete: { Task { await store.delete(m) } }, onReport: report)
            } else {
                ChatBubble(message: m, first: first, last: last, showAuthor: !chat.isDirect, names: names,
                           reactions: chat.reactions, canWrite: chat.member, isAdmin: chat.admin, isStaff: chat.isStaff,
                           canPin: chat.admin || chat.isDirect, player: player,
                           onReact: { emoji in Haptics.tap(); Task { await store.react(m, emoji) } },
                           onReply: { reply(to: m) },
                           onQuote: { if let id = m.reply?.id { jumpTo = id } },
                           onPin: { Task { await store.pin(m) } },
                           onDelete: { Task { await store.delete(m) } },
                           onReport: report)
            }
        }
        .background(RoundedRectangle(cornerRadius: 14).fill(accent.opacity(flashing == m.id ? 0.22 : 0)).padding(-4))
        .id(m.id)
        .listRowBackground(Color.clear)
        .listRowSeparator(.hidden)
        .listRowInsets(EdgeInsets(top: first ? 5 : 1, leading: 10, bottom: last ? 5 : 1, trailing: 12))
        .swipeActions(edge: .leading, allowsFullSwipe: true) {
            if chat.member && !m.deleted && !m.pending {
                Button { reply(to: m) } label: { Label("Répondre", systemImage: "arrowshape.turn.up.left.fill") }
                    .tint(accent)
            }
        }
    }

    /// Bouton ↓ (en bas à droite) : revient au dernier message ; pastille = messages arrivés pendant qu'on lisait plus haut.
    @ViewBuilder private func jumpButton(_ proxy: ScrollViewProxy) -> some View {
        if !atBottom, chat?.messages.isEmpty == false {
            Button {
                Haptics.tap()
                unseen = 0
                bottom(proxy, delay: 0)
            } label: {
                Image(systemName: "chevron.down").font(.body.weight(.semibold)).foregroundStyle(.white)
                    .frame(width: 40, height: 40)
                    .background(.regularMaterial, in: Circle())
                    .overlay(Circle().stroke(Color.white.opacity(0.12)))
                    .overlay(alignment: .topTrailing) {
                        if unseen > 0 {
                            Text("\(min(unseen, 99))").font(.caption2.weight(.bold).monospacedDigit()).foregroundStyle(.black)
                                .padding(.horizontal, 5).frame(minWidth: 18, minHeight: 18)
                                .background(accent, in: Capsule()).offset(x: 4, y: -4)
                                .contentTransition(.numericText())
                        }
                    }
            }
            .buttonStyle(PressableStyle(scale: 0.9))
            .padding(.trailing, 12).padding(.bottom, 10)
            .accessibilityLabel(unseen > 0 ? "\(unseen) nouveaux messages, descendre" : "Descendre au dernier message")
            .accessibilityIdentifier("chat-jump-bottom")
            .motionTransition(.scale(scale: 0.6).combined(with: .opacity))
        }
    }

    // MARK: Saisie

    private func composer(_ chat: Conversation) -> some View {
        VStack(spacing: 6) {
            mentionBar(chat)
            if announcing {
                Label("Annonce : épinglée en haut et envoyée à tous les invités", systemImage: "megaphone.fill")
                    .font(.caption.weight(.semibold)).foregroundStyle(accent)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .motionTransition(.opacity.combined(with: .move(edge: .bottom)))
            }
            if let replyTo {
                HStack(spacing: 8) {
                    RoundedRectangle(cornerRadius: 2).fill(ChatTimeline.nameColor(for: replyTo.author)).frame(width: 3)
                    VStack(alignment: .leading, spacing: 1) {
                        Text("Réponse à \(replyTo.mine ? "toi" : replyTo.authorName)").font(.caption.weight(.semibold))
                            .foregroundStyle(ChatTimeline.nameColor(for: replyTo.author))
                        Text(replyTo.preview).font(.caption).foregroundStyle(.secondary).lineLimit(1)
                    }
                    Spacer()
                    Button { Motion.animate { self.replyTo = nil } } label: { Image(systemName: "xmark.circle.fill").foregroundStyle(.secondary) }
                        .accessibilityLabel("Annuler la réponse")
                }
                .padding(8)
                .background(Color.white.opacity(0.06), in: RoundedRectangle(cornerRadius: 10))
                .frame(maxHeight: 54)
                .motionTransition(.opacity.combined(with: .move(edge: .bottom)))
            }
            HStack(alignment: .bottom, spacing: 8) {
                if recorder.recording {
                    recordingBar.motionTransition(.opacity.combined(with: .move(edge: .trailing)))
                } else {
                    if chat.isEvent && chat.isStaff {
                        Button {
                            Haptics.selection()
                            Motion.animate(Motion.snappy) { announcing.toggle() }
                        } label: {
                            Image(systemName: announcing ? "megaphone.fill" : "megaphone").font(.title3)
                                .foregroundStyle(announcing ? accent : .secondary).frame(width: 36, height: 36)
                        }
                        .accessibilityLabel(announcing ? "Annonce activée" : "Faire une annonce")
                        .accessibilityHint("Épinglée en haut de la discussion et envoyée à tous les invités")
                        .accessibilityIdentifier("chat-announce")
                        .transition(.opacity)
                    }
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
        .padding(.horizontal, 10).padding(.vertical, 8)
        .background(.bar)
        .task { recorder.warmUp() }  // micro prêt avant le premier appui
    }

    /// Suggestions de l'@ en cours de frappe : membres filtrés en direct, puis les citations spéciales permises
    /// (@tout et @annonce d'un groupe ; @toutlemonde, @present et @annonce de l'organisation d'un événement).
    @ViewBuilder private func mentionBar(_ chat: Conversation) -> some View {
        let found: [Mentions.Suggestion] = chat.isDirect ? [] : Mentions.query(in: text).map {
            Mentions.suggestions(for: $0, members: chat.members, me: chat.me, everyone: chat.canEveryone, announce: chat.isStaff,
                                 contacts: ContactNames.shared.names, tags: chat.isEvent ? (chat.tags ?? []) : nil)
        } ?? []
        if let note = chat.tagNote(for: text) {
            Label(note, systemImage: "info.circle").font(.caption).foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .motionTransition(.opacity)
        }
        if !found.isEmpty {
            // Liste verticale au-dessus du champ, comme WhatsApp : photo, surnom, nom du contact ou explication.
            VStack(spacing: 0) {
                ForEach(found) { s in
                    Button {
                        Haptics.selection()
                        text = Mentions.insert(s.label, into: text)
                    } label: {
                        HStack(spacing: 10) {
                            if let m = s.member {
                                Initials(name: m.name, photo: m.photo, size: 30)
                            } else {
                                Image(systemName: Self.tagIcon(s.label)).font(.subheadline.weight(.semibold)).foregroundStyle(accent)
                                    .frame(width: 30, height: 30).background(accent.opacity(0.18), in: Circle())
                            }
                            VStack(alignment: .leading, spacing: 1) {
                                Text("@" + s.label).font(.subheadline.weight(.semibold)).lineLimit(1)
                                if !s.hint.isEmpty {
                                    Text(s.hint).font(.caption).foregroundStyle(.secondary).lineLimit(1)
                                }
                            }
                            Spacer(minLength: 0)
                        }
                        .padding(.horizontal, 10).padding(.vertical, 6)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(s.member != nil ? "Citer \(s.label)" : "@\(s.label) : \(s.hint)")
                    if s.id != found.last?.id { Divider().padding(.leading, 50) }
                }
            }
            .background(Color.white.opacity(0.06), in: RoundedRectangle(cornerRadius: 14))
            .accessibilityIdentifier("chat-mentions")
            .motionTransition(.opacity.combined(with: .move(edge: .bottom)))
        }
    }

    static func tagIcon(_ tag: String) -> String {
        switch tag {
        case "annonce": return "megaphone.fill"
        case "present": return "checkmark.circle.fill"
        default: return "person.3.fill"
        }
    }

    private func field(_ chat: Conversation) -> some View {
        TextField(announcing ? "Écris ton annonce…" : chat.isDirect ? "Message" : "Message (@ pour citer)", text: $text, axis: .vertical)
            .lineLimit(1...6)
            .focused($writing)
            .padding(.horizontal, 14).padding(.vertical, 9)
            .background(announcing ? accent.opacity(0.14) : Color.white.opacity(0.08), in: RoundedRectangle(cornerRadius: 20))
            .overlay(RoundedRectangle(cornerRadius: 20).stroke(announcing ? accent.opacity(0.8) : Color.clear, lineWidth: 1))
            .accessibilityLabel(announcing ? "Annonce" : "Message")
            .accessibilityIdentifier("chat-message")
    }

    private var sendButton: some View {
        Button {
            // Champ vidé tout de suite, message affiché aussitôt ; en cas d'échec, le texte revient.
            Haptics.tap()
            let typed = text, quoted = replyTo, announce = announcing
            text = ""
            replyTo = nil
            announcing = false
            Task {
                if !(await termsAccepted()) {
                    text = typed
                    replyTo = quoted
                    announcing = announce
                    return
                }
                if !(await store.send(typed, replyTo: quoted?.id, announce: announce)) {
                    text = typed
                    replyTo = quoted
                    announcing = announce
                }
            }
        } label: {
            if store.sending { ProgressView().frame(width: 36, height: 36) } else {
                // Même flèche en annonce (le champ et la ligne 📣 au-dessus disent déjà que c'est une annonce).
                Image(systemName: "arrow.up.circle.fill").font(.system(size: 34))
                    .foregroundStyle(accent)
            }
        }
        .accessibilityLabel(announcing ? "Publier l'annonce" : "Envoyer")
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
            .foregroundStyle(recorder.recording ? (cancelVoice ? Color.secondary : Color.red) : accent)
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
        Task {
            guard await termsAccepted() else {
                try? FileManager.default.removeItem(at: file)
                return
            }
            await store.sendVoice(file, seconds: seconds, replyTo: quoted?.id)
        }
    }

    /// Conditions d'utilisation acceptées avant le premier message (Google UGC) ; sinon la feuille s'ouvre.
    private func termsAccepted() async -> Bool {
        if await store.moderation.termsAccepted() { return true }
        askTerms = true
        return false
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
        .background(Color.white.opacity(0.08), in: RoundedRectangle(cornerRadius: 20))
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
        guard await termsAccepted() else { return }
        if await store.send(text, replyTo: replyTo?.id, photo: jpeg, announce: announcing) {
            text = ""
            replyTo = nil
            announcing = false
        }
    }
}

/// Séparateur de jour, centré : « Aujourd'hui », « Hier », « Lundi », « 12 novembre ».
private struct DayPill: View {
    let label: String

    var body: some View {
        Text(label).font(.caption.weight(.semibold)).foregroundStyle(.secondary)
            .padding(.horizontal, 12).padding(.vertical, 5)
            .background(.ultraThinMaterial, in: Capsule())
            .accessibilityAddTraits(.isHeader)
    }
}

/// Heure (et « modifié », horloge pendant l'envoi, coche une fois reçu) en bas à droite de la bulle.
private struct MessageMeta: View {
    let message: Conversation.Message
    var onPhoto = false

    var body: some View {
        HStack(spacing: 3) {
            if message.edited && !message.deleted { Text("modifié") }
            Text(message.date?.formatted(date: .omitted, time: .shortened) ?? "")
            if message.mine && !message.deleted {
                Image(systemName: message.pending ? "clock" : "checkmark").font(.system(size: 9, weight: .bold))
            }
        }
        .font(.caption2.monospacedDigit())
        .foregroundStyle(onPhoto ? Color.white : message.mine ? Color.black.opacity(0.55) : Color.secondary)
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
private struct QuoteBlock: View {
    let reply: Conversation.Reply
    let mine: Bool
    let onTap: () -> Void

    var body: some View {
        let color = mine ? Color.black.opacity(0.7) : ChatTimeline.nameColor(for: reply.author ?? reply.name)
        Button(action: onTap) {
            HStack(spacing: 8) {
                RoundedRectangle(cornerRadius: 2).fill(color).frame(width: 3)
                VStack(alignment: .leading, spacing: 1) {
                    Text(reply.name).font(.caption.weight(.semibold)).foregroundStyle(color).lineLimit(1)
                    Text(reply.text).font(.caption).foregroundStyle(mine ? Color.black.opacity(0.65) : Color.secondary).lineLimit(2)
                }
                Spacer(minLength: 0)
            }
            .padding(6)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.black.opacity(mine ? 0.1 : 0.22), in: RoundedRectangle(cornerRadius: 8))
        }
        .buttonStyle(.plain)
        .disabled(reply.id == nil)
        .accessibilityLabel("Réponse à \(reply.name) : \(reply.text)")
        .accessibilityHint(reply.id == nil ? "" : "Touche pour voir le message d'origine")
    }
}

/// Une bulle façon WhatsApp : mes messages à droite (couleur de l'app), les autres à gauche ; dans un groupe, le nom en
/// couleur en tête de la série et la photo en bas ; heure dans la bulle ; @citations en gras et en couleur.
private struct ChatBubble: View {
    let message: Conversation.Message
    let first: Bool
    let last: Bool
    /// Groupe ou événement : nom et photo des autres (pas à deux).
    let showAuthor: Bool
    let names: [String]
    let reactions: [String]
    let canWrite: Bool
    let isAdmin: Bool
    /// Admin ou organisateur : retire les annonces.
    let isStaff: Bool
    /// Épingle : admins d'un groupe, organisation d'un événement, les deux personnes d'un message direct.
    let canPin: Bool
    @ObservedObject var player: VoicePlayer
    let onReact: (String) -> Void
    let onReply: () -> Void
    let onQuote: () -> Void
    let onPin: () -> Void
    let onDelete: () -> Void
    /// « Signaler » (modération commune) : sur le message d'un autre, même sans pouvoir écrire.
    var onReport: (() -> Void)?

    private var accent: Color { Color(uiColor: AppConfig.uiAccent) }
    private var actions: Bool { (canWrite || (!message.mine && onReport != nil)) && !message.deleted && !message.pending }
    private var avatar: CGFloat { 28 }

    var body: some View {
        HStack(alignment: .bottom, spacing: 6) {
            if message.mine {
                Spacer(minLength: 56)
            } else if showAuthor {
                if last { Initials(name: message.authorName, photo: message.authorPhoto, size: avatar) } else { Color.clear.frame(width: avatar, height: 1) }
            }
            VStack(alignment: message.mine ? .trailing : .leading, spacing: 0) {
                bubble
                    // En cours d'envoi : bulle légèrement estompée, qui s'affirme une fois le message reçu.
                    .opacity(message.pending ? 0.7 : 1)
                    .contextMenu { if actions { ChatMenu(message: message, reactions: reactions, canWrite: canWrite, isAdmin: isAdmin,
                                                         isStaff: isStaff, canPin: canPin, onReact: onReact, onReply: onReply,
                                                         onPin: onPin, onDelete: onDelete, onReport: onReport) } }
                if !message.reactions.isEmpty {
                    ReactionChips(message: message, canWrite: canWrite, onReact: onReact)
                        .offset(y: -5).padding(.horizontal, 8).padding(.bottom, -5)
                        .motionTransition(.scale(scale: 0.6, anchor: message.mine ? .trailing : .leading).combined(with: .opacity))
                }
            }
            if !message.mine { Spacer(minLength: 56) }
        }
        .motion(Motion.smooth, value: message.pending)
        .motion(Motion.bouncy, value: message.reactions.map { "\($0.emoji)\($0.count)\($0.mine)" })
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibility)
        .accessibilityHint(actions ? "Glisse vers la droite pour répondre ; appui long pour réagir\(canPin ? ", épingler" : "") ou supprimer" : "")
        .accessibilityAction(named: "Répondre") { if actions && canWrite { onReply() } }
    }

    private var accessibility: String {
        let who = message.mine ? "Toi" : ContactNames.shared.label(for: message.author, pseudo: message.authorName).text
        let time = message.pending ? "envoi en cours" : message.date?.formatted(date: .omitted, time: .shortened) ?? ""
        return "\(who), \(time) : \(message.deleted ? message.body : message.preview)"
    }

    /// Coin côté auteur plus serré en tête de série (la « queue » des messageries).
    private var shape: UnevenRoundedRectangle {
        let tight: CGFloat = first ? 5 : 18
        return UnevenRoundedRectangle(cornerRadii: .init(topLeading: message.mine ? 18 : tight, bottomLeading: 18,
                                                         bottomTrailing: 18, topTrailing: message.mine ? tight : 18))
    }

    private var bubble: some View {
        let photoOnly = message.photo != nil && message.body.isEmpty && !message.deleted
        return VStack(alignment: .leading, spacing: 5) {
            if showAuthor && first && !message.mine {
                PersonName(id: message.author, pseudo: message.authorName, pseudoFont: .caption2)
                    .font(.subheadline.weight(.semibold)).foregroundStyle(ChatTimeline.nameColor(for: message.author))
                    .padding(.horizontal, message.photo == nil ? 0 : 6).padding(.top, message.photo == nil ? 0 : 4)
            }
            if message.pinned && !message.deleted {
                (Text(Image(systemName: "pin.fill")) + Text(" Épinglé")).font(.caption2.weight(.bold))
                    .foregroundStyle(message.mine ? Color.black.opacity(0.6) : accent)
                    .padding(.horizontal, message.photo == nil ? 0 : 6)
            }
            if let reply = message.reply, !message.deleted {
                QuoteBlock(reply: reply, mine: message.mine, onTap: onQuote)
            }
            if let photo = message.photo.flatMap(URL.init(string:)), !message.deleted {
                AsyncImage(url: photo) { image in image.resizable().scaledToFill() } placeholder: {
                    ZStack { Color.white.opacity(0.06); ProgressView() }
                }
                .frame(width: 240, height: 240).clipShape(RoundedRectangle(cornerRadius: 14))
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
                    .padding(.horizontal, message.photo == nil ? 0 : 6)
                    .overlay(alignment: .bottomTrailing) { MessageMeta(message: message).offset(y: 2) }
                    .fixedSize(horizontal: false, vertical: true)
            } else if message.photo == nil && message.audioSeconds == nil {
                MessageMeta(message: message)
            }
        }
        .foregroundStyle(message.mine && !message.deleted ? Color.black : Color.white)
        .padding(.horizontal, message.photo == nil ? 12 : 4).padding(.vertical, message.photo == nil ? 8 : 4)
        .background(message.deleted ? Color.white.opacity(0.06) : message.mine ? accent : Color(red: 0.15, green: 0.12, blue: 0.27), in: shape)
    }
}

/// Annonce de l'organisation : une carte pleine largeur, distincte des bulles (en-tête 📣, bord de couleur).
private struct AnnouncementCard: View {
    let message: Conversation.Message
    let names: [String]
    let reactions: [String]
    let canWrite: Bool
    let isStaff: Bool
    let isAdmin: Bool
    @ObservedObject var player: VoicePlayer
    let onReact: (String) -> Void
    let onReply: () -> Void
    let onPin: () -> Void
    let onDelete: () -> Void
    let onReport: () -> Void

    private var accent: Color { Color(uiColor: AppConfig.uiAccent) }
    private var actions: Bool { (canWrite || !message.mine) && !message.pending }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
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
                        .frame(maxWidth: .infinity).frame(height: 200).clipShape(RoundedRectangle(cornerRadius: 12))
                }
                if let seconds = message.audioSeconds {
                    VoiceBubble(player: player, id: message.id, url: message.audio.flatMap(URL.init(string:)), seconds: seconds, mine: false)
                }
                let text = ConversationView.clean(message.body)
                if !text.isEmpty {
                    Text(Mentions.highlighted(text, names: names, color: accent)).font(.body.weight(.medium))
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(accent.opacity(0.13), in: RoundedRectangle(cornerRadius: 18))
            .overlay(RoundedRectangle(cornerRadius: 18).stroke(accent.opacity(0.85), lineWidth: 1.5))
            .opacity(message.pending ? 0.7 : 1)
            .contextMenu { if actions { ChatMenu(message: message, reactions: reactions, canWrite: canWrite, isAdmin: isAdmin,
                                                 isStaff: isStaff, canPin: false, onReact: onReact, onReply: onReply,
                                                 onPin: onPin, onDelete: onDelete, onReport: onReport) } }
            if !message.reactions.isEmpty {
                ReactionChips(message: message, canWrite: canWrite, onReact: onReact).offset(y: -5).padding(.horizontal, 12).padding(.bottom, -5)
            }
        }
        .padding(.vertical, 6)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Annonce de \(message.mine ? "toi" : message.authorName) : \(ConversationView.clean(message.preview))")
        .accessibilityAction(named: "Répondre") { if canWrite && !message.pending { onReply() } }
        .accessibilityIdentifier("chat-announcement")
    }
}

/// Appui long : réactions en tête, puis Répondre, Copier, Épingler / Retirer l'annonce, Supprimer, Signaler.
private struct ChatMenu: View {
    let message: Conversation.Message
    let reactions: [String]
    let canWrite: Bool
    let isAdmin: Bool
    let isStaff: Bool
    let canPin: Bool
    let onReact: (String) -> Void
    let onReply: () -> Void
    let onPin: () -> Void
    let onDelete: () -> Void
    var onReport: (() -> Void)?

    var body: some View {
        if canWrite {
            ControlGroup {
                ForEach(reactions, id: \.self) { emoji in Button(emoji) { onReact(emoji) } }
            }
            Button { onReply() } label: { Label("Répondre", systemImage: "arrowshape.turn.up.left") }
        }
        if !message.body.isEmpty {
            Button { UIPasteboard.general.string = ConversationView.clean(message.body) } label: { Label("Copier", systemImage: "doc.on.doc") }
        }
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
        if !message.mine, let onReport {
            Button(role: .destructive) { onReport() } label: { Label("Signaler", systemImage: "exclamationmark.bubble") }
        }
    }
}

/// Réactions sous la bulle (à cheval sur son bord) : un toucher ajoute ou retire la mienne.
private struct ReactionChips: View {
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

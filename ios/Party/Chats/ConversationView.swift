import PhotosUI
import SwiftUI

/// Conversation (groupe, message direct, discussion d'un événement), façon WhatsApp (16.11, revue le 17.11.2026) : fond à
/// motif, bulles à queue, nom de l'auteur en couleur, heure et ✓ dans la bulle, pastilles de jour, « Nouveaux messages »
/// au premier non-lu, citation qui remonte au message d'origine, bouton ↓ avec les messages arrivés, bandeau des
/// annonces et épinglés, anciens messages chargés en remontant. Glisser une bulle vers la droite : répondre ; appui long :
/// la bulle se soulève avec la barre de réactions et le menu (Répondre, Copier, Épingler, Signaler, Supprimer).
/// Barre de saisie : ＋, champ arrondi, appareil photo, micro qui devient ➤ dès qu'on écrit.
/// embedded : posée dans un écran qui a son propre en-tête (EventChatScreen) ; ni titre ni boutons de barre.
struct ConversationView: View {
    @ObservedObject var store: ChatsStore
    let group: String
    var embedded = false

    @State private var text = ""
    @State private var replyTo: Conversation.Message?
    @State private var picked: PhotosPickerItem?
    @State private var showPhotos = false
    @State private var showCamera = false
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
    /// Bulle soulevée par un appui long.
    @State private var focus: BubbleFocus?
    /// « Nouveaux messages » : premier message non lu à l'ouverture, et leur nombre.
    @State private var newFrom: String?
    @State private var newCount = 0
    /// Premières secondes : la liste se place (bas du fil ou premier non-lu) avant que le doigt ne la prenne.
    @State private var settling = true
    /// Anciens messages : chargement en remontant, arrêté quand il n'y a plus rien.
    @State private var loadingOlder = false
    @State private var olderDone = false
    /// Dernier message signalé comme lu (pas deux fois le même appel).
    @State private var lastRead: String?

    private var chat: Conversation? { store.conversation?.id == group ? store.conversation : nil }
    private var accent: Color { Color(uiColor: AppConfig.uiAccent) }
    private static let end = "chat-end"
    private static let unreadID = "chat-unread-divider"

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
        chrome(content)
            .sheet(isPresented: $showInfo) {
                if store.conversation?.isEvent == true { EventChatInfoView(store: store) }
                else if store.conversation?.isDirect == true { DirectChatInfoView(store: store) } else { ChatInfoView(store: store) }
            }
            .sheet(item: $reporting) { ReportSheet(store: store.moderation, target: $0) }
            .sheet(isPresented: $askTerms) { TermsAcceptSheet(store: store.moderation) }
            .photosPicker(isPresented: $showPhotos, selection: $picked, matching: .images)
            .fullScreenCover(isPresented: $showCamera) {
                BubbleCamera { image in Task { await sendImage(image) } }.ignoresSafeArea()
            }
            .task(id: group) {
                while !Task.isCancelled {
                    await store.open(group)
                    try? await Task.sleep(for: ChatsStore.conversationEvery)
                }
            }
            .onDisappear { store.close(); player.stop(); micLocked = false; _ = recorder.stop(send: false) }
            .onChange(of: picked) { item in Task { await sendPhoto(item) } }
    }

    private var content: some View {
        VStack(spacing: 0) {
            if let chat {
                let pins = chat.pins
                if !pins.isEmpty {
                    pinnedBanner(pins, chat: chat).motionTransition(.unfold)
                }
                messages(chat).transition(.opacity)
                footer(chat)
            } else if let error = store.error {
                Text(error).foregroundStyle(.secondary).padding().frame(maxWidth: .infinity, maxHeight: .infinity).transition(.opacity)
            } else {
                ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity).transition(.opacity)
            }
        }
        // Chargement → conversation : fondu ; message épinglé ou désépinglé : le bandeau se déplie.
        .motion(Motion.smooth, value: chat == nil)
        .motion(Motion.snappy, value: chat?.pins.map(\.id))
        .background(ChatWallpaper())
        .overlay { focusOverlay }
        .overlay(alignment: .bottom) { notice }
    }

    /// Hors d'un écran qui a son propre en-tête : titre et sous-titre (toucher = infos), bouton ⓘ.
    @ViewBuilder private func chrome<V: View>(_ view: V) -> some View {
        if embedded {
            view
        } else {
            view
                .navigationTitle(title)
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .principal) {
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
        }
    }

    // MARK: Droits

    /// Peut écrire et répondre : membre, pas bloqué, discussion ouverte à tous (ou je fais partie de l'organisation).
    private func canReply(_ chat: Conversation) -> Bool {
        chat.member && chat.blocked != true && chat.canWrite != false
    }

    private func canPin(_ chat: Conversation) -> Bool { chat.admin || chat.isDirect }

    /// Le menu de l'appui long (et les actions de VoiceOver) pour ce message.
    private func actions(for m: Conversation.Message, in chat: Conversation) -> [BubbleAction] {
        guard !m.pending, !m.deleted else { return [] }
        var list: [BubbleAction] = []
        if canReply(chat) {
            list.append(BubbleAction(id: "reply", title: "Répondre", icon: "arrowshape.turn.up.left") { reply(to: m) })
        }
        if !m.body.isEmpty {
            list.append(BubbleAction(id: "copy", title: "Copier", icon: "doc.on.doc") {
                UIPasteboard.general.string = ConversationView.clean(m.body)
                Haptics.success()
            })
        }
        if m.isAnnouncement {
            if chat.isStaff {
                list.append(BubbleAction(id: "pin", title: "Retirer l'annonce", icon: "pin.slash") { Task { await store.pin(m) } })
            }
        } else if canPin(chat) {
            list.append(BubbleAction(id: "pin", title: m.pinned ? "Désépingler" : "Épingler", icon: m.pinned ? "pin.slash" : "pin") {
                Task { await store.pin(m) }
            })
        }
        if !m.mine {
            list.append(BubbleAction(id: "report", title: "Signaler", icon: "exclamationmark.bubble", destructive: true) {
                reporting = ReportTarget(kind: chat.isEvent ? .eventMessage : chat.isDirect ? .directMessage : .groupMessage, id: m.id,
                                         label: "le message de \(m.authorName)")
            })
        }
        if m.mine || chat.admin {
            list.append(BubbleAction(id: "delete", title: "Supprimer", icon: "trash", destructive: true) { Task { await store.delete(m) } })
        }
        return list
    }

    // MARK: Défilement

    /// Descend en bas du fil, après la mise en page de la liste (sinon la liste ne descend pas toujours).
    private func bottom(_ proxy: ScrollViewProxy, animated: Bool = true, delay: Double = 0.05) {
        DispatchQueue.main.asyncAfter(deadline: .now() + delay) {
            if animated { Motion.animate(Motion.snappy) { proxy.scrollTo(Self.end, anchor: .bottom) } } else { proxy.scrollTo(Self.end, anchor: .bottom) }
        }
    }

    /// Montre un message au milieu de l'écran puis le fait clignoter (citation touchée, bandeau, recherche).
    private func show(_ id: String, _ proxy: ScrollViewProxy) {
        Motion.animate(Motion.smooth) { proxy.scrollTo(id, anchor: .center) }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
            Motion.animate(Motion.snappy) { flashing = id }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.9) { Motion.animate(Motion.smooth) { if flashing == id { flashing = nil } } }
        }
    }

    private func loaded(_ id: String) -> Bool { store.conversation?.messages.contains { $0.id == id } == true }

    /// Message demandé (citation, bandeau, recherche) : s'il est plus ancien que ceux affichés, on remonte page par page.
    private func reveal(_ id: String, _ proxy: ScrollViewProxy) {
        if loaded(id) { show(id, proxy); return }
        Task {
            for _ in 0..<10 where !loaded(id) {
                let before = store.conversation?.messages.count ?? 0
                await store.loadOlder()
                if (store.conversation?.messages.count ?? 0) <= before { break }
            }
            if loaded(id) {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) { show(id, proxy) }
            } else {
                store.notice = "Ce message n'est plus dans la discussion."
            }
        }
    }

    /// Haut du fil atteint : la page précédente arrive au-dessus, et la lecture reste sur le même message.
    private func loadOlder(_ proxy: ScrollViewProxy) {
        guard !loadingOlder, !olderDone, !settling, let anchor = store.conversation?.messages.first?.id else { return }
        let before = store.conversation?.messages.count ?? 0
        loadingOlder = true
        Task {
            await store.loadOlder()
            let now = store.conversation?.messages.count ?? 0
            if now <= before { olderDone = true } else { DispatchQueue.main.async { proxy.scrollTo(anchor, anchor: .top) } }
            loadingOlder = false
        }
    }

    /// Marque la discussion comme lue (ouverture, arrivée en bas, nouveau message vu) ; une fois par dernier message.
    private func markRead(_ chat: Conversation) {
        guard chat.member, let last = chat.messages.last(where: { !$0.pending })?.id, last != lastRead else { return }
        lastRead = last
        Task { await store.markRead() }
    }

    /// À l'ouverture : premier message non lu (d'après le serveur) ; la bande « Nouveaux messages » se pose avant lui.
    private func placeUnread(_ chat: Conversation, _ proxy: ScrollViewProxy) {
        guard newFrom == nil, settling, let unread = chat.unread, unread > 0 else { return }
        let others = chat.messages.filter { !$0.pending }
        guard unread <= others.count else { return }
        let first = others[others.count - unread]
        guard !first.mine else { return }
        newFrom = first.id
        newCount = unread
        unseen = unread
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.08) { proxy.scrollTo(Self.unreadID, anchor: .top) }
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
                .frame(width: 30, height: 30)
                .background(accent.opacity(0.16), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
            VStack(alignment: .leading, spacing: 2) {
                Text(h.announcement ? "Annonce" : "Message épinglé").font(.caption.weight(.bold)).foregroundColor(accent)
                    + Text(pins.count > 1 ? "  \(index + 1)/\(pins.count)" : "").font(.caption.monospacedDigit()).foregroundColor(.secondary)
                Text("\(h.authorName) : \(Self.clean(h.text))")
                    .font(h.announcement ? .subheadline.weight(.semibold) : .subheadline).lineLimit(h.announcement ? 2 : 1)
                    .id(h.id)
                    .transition(.opacity)
            }
            Spacer(minLength: 0)
            if pins.count > 1 {
                Image(systemName: "chevron.down").font(.caption.weight(.bold)).foregroundStyle(.secondary)
            }
        }
        .padding(.horizontal, 14).padding(.vertical, 9)
        .background(h.announcement ? AnyShapeStyle(accent.opacity(0.16)) : AnyShapeStyle(.ultraThinMaterial))
        .background(.ultraThinMaterial)
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

    private struct Line: Identifiable {
        enum Kind {
            case day(String)
            case unread(Int)
            case message(Conversation.Message, first: Bool, last: Bool)
        }

        let id: String
        let kind: Kind
    }

    /// Jours, messages et la bande « Nouveaux messages » (le message qui la suit ouvre une nouvelle série).
    private func lines(_ chat: Conversation) -> [Line] {
        var out: [Line] = []
        var afterDivider = false
        for row in ChatTimeline.rows(chat.messages) {
            switch row.kind {
            case .day(let label):
                out.append(Line(id: row.id, kind: .day(label)))
            case .message(let m, let first, let last):
                if m.id == newFrom {
                    out.append(Line(id: Self.unreadID, kind: .unread(newCount)))
                    afterDivider = true
                }
                out.append(Line(id: row.id, kind: .message(m, first: first || afterDivider, last: last)))
                afterDivider = false
            }
        }
        return out
    }

    private func messages(_ chat: Conversation) -> some View {
        let names = chat.members.map(\.name)
        return ScrollViewReader { proxy in
            List {
                if chat.messages.isEmpty {
                    emptyState(chat)
                } else if !olderDone {
                    // Haut du fil : la page précédente se charge en remontant.
                    HStack { if loadingOlder { ProgressView() } }
                        .frame(maxWidth: .infinity, minHeight: loadingOlder ? 36 : 1)
                        .listRowBackground(Color.clear).listRowSeparator(.hidden).listRowInsets(EdgeInsets())
                        .onAppear { loadOlder(proxy) }
                }
                ForEach(lines(chat)) { line in
                    switch line.kind {
                    case .day(let label):
                        DayPill(label: label)
                            .frame(maxWidth: .infinity)
                            .listRowBackground(Color.clear).listRowSeparator(.hidden)
                            .listRowInsets(EdgeInsets(top: 10, leading: 16, bottom: 6, trailing: 16))
                    case .unread(let count):
                        UnreadDivider(count: count)
                            .id(Self.unreadID)
                            .listRowBackground(Color.clear).listRowSeparator(.hidden)
                            .listRowInsets(EdgeInsets(top: 8, leading: 0, bottom: 8, trailing: 0))
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
            .environment(\.defaultMinListRowHeight, 1)
            // Bulle qui arrive (envoyée, reçue en direct) ou supprimée : la liste s'écarte en douceur
            // au lieu de sauter. Les relectures régulières sans nouveauté ne changent pas les identifiants : rien ne bouge.
            .motion(Motion.snappy, value: chat.messages.last?.id)
            .overlay(alignment: .bottomTrailing) { jumpButton(proxy) }
            .onAppear {
                if let id = store.jumpTo {
                    store.jumpTo = nil
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) { reveal(id, proxy) }
                } else {
                    bottom(proxy, animated: false)
                    placeUnread(chat, proxy)
                }
                // Lue après la mise en place : la bande « Nouveaux messages » a eu le temps de lire le compte du serveur.
                DispatchQueue.main.asyncAfter(deadline: .now() + 1.2) {
                    settling = false
                    if let now = self.chat { markRead(now) }
                }
            }
            // Le serveur dit combien de messages n'ont pas été lus (souvent juste après la version gardée sur le téléphone).
            .onChange(of: chat.unread ?? 0) { _ in
                placeUnread(chat, proxy)
                markRead(chat)
            }
            // Nouveau message : on suit s'il est à moi ou si l'on était en bas ; sinon le bouton ↓ le compte.
            .onChange(of: chat.messages.last?.id) { _ in
                guard let last = chat.messages.last else { return }
                if last.mine || atBottom {
                    bottom(proxy)
                    if !last.mine { markRead(chat) }
                } else {
                    Motion.animate(Motion.bouncy) { unseen += 1 }
                }
            }
            // Réaction, envoi confirmé sur le dernier message : on reste en bas si on y était.
            .onChange(of: chat.messages.last) { _ in if atBottom { bottom(proxy) } }
            .onChange(of: atBottom) { bottomNow in if bottomNow { markRead(chat) } }
            // Clavier qui s'ouvre : le dernier message reste visible au-dessus du champ.
            .onChange(of: writing) { on in if on { bottom(proxy, delay: 0.35) } }
            .onChange(of: jumpTo) { id in
                guard let id else { return }
                jumpTo = nil
                reveal(id, proxy)
            }
            // Recherche, épinglés de l'écran d'infos : le message à montrer.
            .onChange(of: store.jumpTo) { id in
                guard let id else { return }
                store.jumpTo = nil
                reveal(id, proxy)
            }
        }
    }

    private func emptyState(_ chat: Conversation) -> some View {
        VStack(spacing: 12) {
            Image(systemName: "bubble.left.and.bubble.right").font(.largeTitle).foregroundStyle(.secondary)
            Text(chat.isEvent ? "Aucun message pour l'instant. Lance la discussion avec les invités !"
                              : "Aucun message pour l'instant. Lance la discussion !")
                .foregroundStyle(.secondary).multilineTextAlignment(.center)
            // Groupe tout neuf (créé depuis Discussions) : y ajouter du monde.
            if chat.member && !chat.isDirect && !chat.isEvent && chat.members.count <= 1 && !embedded {
                Button("Ajouter des membres") { showInfo = true }.buttonStyle(.borderedProminent)
            }
        }
        .padding(20)
        .background(Color(red: 0.13, green: 0.11, blue: 0.21).opacity(0.9), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .padding(.top, 60).padding(.horizontal, 24)
        .frame(maxWidth: .infinity).listRowBackground(Color.clear).listRowSeparator(.hidden)
    }

    @ViewBuilder
    private func messageRow(_ m: Conversation.Message, first: Bool, last: Bool, chat: Conversation, names: [String],
                            proxy: ScrollViewProxy) -> some View {
        let actions = actions(for: m, in: chat)
        let react: (String) -> Void = { emoji in Haptics.tap(); Task { await store.react(m, emoji) } }
        let lift: (CGRect, AnyView) -> Void = { frame, preview in
            Motion.animate(Motion.snappy) { focus = BubbleFocus(message: m, frame: frame, preview: preview) }
        }
        Group {
            if m.isAnnouncement {
                AnnouncementCard(message: m, names: names, canReact: chat.member, canReply: canReply(chat), actions: actions,
                                 lifted: focus?.id == m.id, player: player, onReact: react, onReply: { reply(to: m) }, onFocus: lift)
            } else {
                ChatBubble(message: m, first: first, showAuthor: !chat.isDirect, names: names, canReact: chat.member,
                           canReply: canReply(chat), actions: actions, lifted: focus?.id == m.id, player: player,
                           onReact: react, onReply: { reply(to: m) },
                           onQuote: { if let id = m.reply?.id { jumpTo = id } }, onFocus: lift)
            }
        }
        .background(RoundedRectangle(cornerRadius: 14).fill(accent.opacity(flashing == m.id ? 0.22 : 0)).padding(-4))
        .id(m.id)
        .listRowBackground(Color.clear)
        .listRowSeparator(.hidden)
        .listRowInsets(EdgeInsets(top: first ? 5 : 1, leading: 6, bottom: last ? 5 : 1, trailing: 8))
    }

    /// Bulle soulevée : voile, barre de réactions et menu, par-dessus le fil.
    @ViewBuilder private var focusOverlay: some View {
        if let focus, let chat {
            let current = chat.messages.first { $0.id == focus.id } ?? focus.message
            BubbleFocusOverlay(focus: focus,
                               reactions: chat.member && !current.deleted ? chat.reactions : [],
                               actions: actions(for: current, in: chat),
                               onReact: { emoji in Task { await store.react(current, emoji) } },
                               onClose: { self.focus = nil })
                .transition(.identity)
                .zIndex(2)
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
                    .background(Color(red: 0.16, green: 0.13, blue: 0.27), in: Circle())
                    .overlay(Circle().stroke(Color.white.opacity(0.12)))
                    .shadow(color: .black.opacity(0.3), radius: 6, y: 2)
                    .overlay(alignment: .topTrailing) {
                        if unseen > 0 {
                            Text("\(min(unseen, 99))").font(.caption2.weight(.bold).monospacedDigit()).foregroundStyle(.black)
                                .padding(.horizontal, 5).frame(minWidth: 18, minHeight: 18)
                                .background(accent, in: Capsule()).offset(x: 4, y: -6)
                                .contentTransition(.numericText())
                                .motionTransition(.scale(scale: 0.4).combined(with: .opacity))
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

    @ViewBuilder private func footer(_ chat: Conversation) -> some View {
        if chat.blocked == true {
            // Message direct : j'ai bloqué cette personne ; l'historique reste, l'écriture revient en la débloquant.
            readOnly("Tu as bloqué \(title). Débloque-le dans les infos (ⓘ) pour lui écrire.", icon: "hand.raised.fill")
        } else if chat.member && chat.canWrite == false {
            // « Qui peut écrire : Organisation seulement » (réglage de l'organisation de l'événement).
            readOnly("Seule l'organisation peut écrire dans cette discussion", icon: "lock.fill")
        } else if chat.member {
            composer(chat)
        } else if chat.isEvent {
            readOnly("Tu peux lire la discussion ; tu pourras écrire une fois l'événement publié et ta place confirmée.", icon: "eye")
        }
    }

    private func readOnly(_ text: String, icon: String) -> some View {
        Label(text, systemImage: icon)
            .font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.center)
            .padding(.horizontal, 16).padding(.vertical, 14).frame(maxWidth: .infinity)
            .background(.bar)
            .accessibilityIdentifier("chat-read-only")
    }

    private var typed: Bool { !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }

    private func composer(_ chat: Conversation) -> some View {
        VStack(spacing: 6) {
            mentionBar(chat)
            if announcing {
                Label("Annonce : épinglée en haut et envoyée à tous les invités", systemImage: "megaphone.fill")
                    .font(.caption.weight(.semibold)).foregroundStyle(accent)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 6)
                    .motionTransition(.opacity.combined(with: .move(edge: .bottom)))
            }
            if let replyTo {
                HStack(spacing: 8) {
                    RoundedRectangle(cornerRadius: 2).fill(ChatTimeline.nameColor(for: replyTo.author)).frame(width: 4)
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
                .background(Color.white.opacity(0.07), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                .frame(maxHeight: 56)
                .motionTransition(.opacity.combined(with: .move(edge: .bottom)))
            }
            HStack(alignment: .bottom, spacing: 6) {
                if recorder.recording {
                    recordingBar.motionTransition(.opacity.combined(with: .move(edge: .trailing)))
                } else {
                    attachMenu(chat).transition(.opacity)
                    if chat.isEvent && chat.isStaff {
                        Button {
                            Haptics.selection()
                            Motion.animate(Motion.snappy) { announcing.toggle() }
                        } label: {
                            Image(systemName: announcing ? "megaphone.fill" : "megaphone").font(.system(size: 19))
                                .foregroundStyle(announcing ? accent : .secondary).frame(width: 34, height: 40)
                        }
                        .accessibilityLabel(announcing ? "Annonce activée" : "Faire une annonce")
                        .accessibilityHint("Épinglée en haut de la discussion et envoyée à tous les invités")
                        .accessibilityIdentifier("chat-announce")
                        .transition(.opacity)
                    }
                    field(chat).transition(.opacity)
                    // Appareil photo à côté du champ tant qu'on n'écrit pas, comme WhatsApp.
                    if !typed && BubbleCamera.available {
                        Button { Haptics.tap(); showCamera = true } label: {
                            Image(systemName: "camera").font(.system(size: 20)).foregroundStyle(accent).frame(width: 36, height: 40)
                        }
                        .disabled(store.sending)
                        .accessibilityLabel("Prendre une photo")
                        .accessibilityIdentifier("chat-camera")
                        .motionTransition(.scale(scale: 0.5).combined(with: .opacity))
                    }
                }
                // Micro ↔ flèche d'envoi : l'un rétrécit pendant que l'autre grandit.
                if !typed && !store.sending {
                    micButton.motionTransition(.scale(scale: 0.5).combined(with: .opacity))
                } else {
                    sendButton.motionTransition(.scale(scale: 0.5).combined(with: .opacity))
                }
            }
            if let problem = recorder.problem {
                Text(problem).font(.caption).foregroundStyle(.red).motionTransition(.unfold)
            }
        }
        .motion(Motion.snappy, value: typed)
        .motion(Motion.snappy, value: store.sending)
        .motion(Motion.snappy, value: recorder.recording)
        .motion(Motion.snappy, value: replyTo?.id)
        .motion(Motion.snappy, value: Mentions.query(in: text) == nil)
        .motion(Motion.snappy, value: recorder.problem)
        .padding(.horizontal, 8).padding(.vertical, 7)
        .background(.bar)
        .overlay(alignment: .top) { Color.white.opacity(0.06).frame(height: 0.5) }
        .task { recorder.warmUp() }  // micro prêt avant le premier appui
    }

    /// ＋ : pièces jointes (photo de la photothèque, appareil photo ; annonce pour l'organisation d'un événement).
    private func attachMenu(_ chat: Conversation) -> some View {
        Menu {
            Button { showPhotos = true } label: { Label("Photos", systemImage: "photo.on.rectangle") }
            if BubbleCamera.available {
                Button { showCamera = true } label: { Label("Appareil photo", systemImage: "camera") }
            }
            if chat.isEvent && chat.isStaff {
                Button { Motion.animate(Motion.snappy) { announcing.toggle() } } label: {
                    Label(announcing ? "Message normal" : "Annonce à tous", systemImage: "megaphone")
                }
            }
        } label: {
            Image(systemName: "plus").font(.system(size: 22, weight: .regular)).foregroundStyle(accent)
                .frame(width: 36, height: 40)
        }
        .disabled(store.sending)
        .accessibilityLabel("Joindre")
        .accessibilityHint("Photo ou appareil photo")
        .accessibilityIdentifier("chat-attach")
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
            .background(Color(red: 0.13, green: 0.11, blue: 0.21), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).stroke(Color.white.opacity(0.06)))
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
            .background(announcing ? accent.opacity(0.14) : Color.white.opacity(0.09), in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).stroke(announcing ? accent.opacity(0.8) : Color.white.opacity(0.05), lineWidth: 1))
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
            ZStack {
                Circle().fill(accent)
                if store.sending { ProgressView().tint(.black) } else {
                    Image(systemName: "paperplane.fill").font(.system(size: 17, weight: .semibold)).foregroundStyle(.black)
                        .offset(x: 1)
                }
            }
            .frame(width: 40, height: 40)
        }
        .buttonStyle(PressableStyle(scale: 0.88))
        .accessibilityLabel(announcing ? "Publier l'annonce" : "Envoyer")
        .accessibilityIdentifier("chat-send")
        .disabled(!typed || store.sending)
    }

    /// Appui long : enregistre ; relâcher : envoie ; glisser vers la gauche : annule (comme WhatsApp).
    /// Simple toucher : l'enregistrement reste actif ; un second toucher l'envoie, sans jamais en relancer un autre.
    private var micButton: some View {
        ZStack {
            Circle().fill(recorder.recording ? (cancelVoice ? Color.secondary : Color.red) : Color.clear)
            Image(systemName: "mic.fill").font(.system(size: 20))
                .foregroundStyle(recorder.recording ? Color.white : accent)
        }
        .frame(width: 40, height: 40)
        // Enregistrement : le micro grossit sous le doigt.
        .scaleEffect(recorder.recording ? 1.3 : 1)
        .motion(Motion.bouncy, value: recorder.recording)
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
        .background(Color.white.opacity(0.09), in: RoundedRectangle(cornerRadius: 20, style: .continuous))
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
        guard let data = try? await item.loadTransferable(type: Data.self), let image = UIImage(data: data) else {
            store.notice = "Cette photo n'a pas pu être lue. Choisis-en une autre."
            return
        }
        await sendImage(image)
    }

    /// Photo (photothèque ou appareil photo) : envoyée avec le texte en cours, la réponse et l'annonce éventuelles.
    private func sendImage(_ image: UIImage) async {
        guard let jpeg = ChatPhoto.jpeg(from: image) else {
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

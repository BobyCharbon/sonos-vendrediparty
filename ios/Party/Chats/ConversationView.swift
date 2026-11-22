import PhotosUI
import SwiftUI

/// Conversation (groupe, message direct, discussion d'un événement), façon WhatsApp (16.11.2026) : séparateurs de jours,
/// messages d'une même personne regroupés (nom en tête, photo en bas), heure dans la bulle, @citations en couleur,
/// citation qui remonte au message d'origine, bouton ↓ avec les nouveaux messages, bandeau des annonces et épinglés
/// qui passe de l'un à l'autre, annonces en carte. Glisser une bulle vers la droite : répondre ; appui long : réagir,
/// répondre, copier, modifier, répondre en privé, épingler, supprimer, signaler.
/// Discussions v2 (18.11) : graphisme Néon club (maquette 1-neon/4), en-tête photo + nom (→ mini-profil), carte de soirée,
/// citation privée, « Vu », « écrit… », demandes de message (ConversationModel).
/// Discussion d'un événement (17.11) : « Nouveaux messages » au premier non-lu, anciens messages chargés en remontant,
/// message montré depuis la recherche ou les épinglés des infos (store.jumpTo), lue en arrivant en bas,
/// « Seule l'organisation peut écrire », appareil photo à côté du champ.
/// embedded : posée dans un écran qui a son propre en-tête (EventChatScreen) ; ni titre ni boutons de barre.
struct ConversationView: View {
    @ObservedObject var store: ChatsStore
    let group: String
    var embedded = false

    @StateObject private var v2 = ConversationModel()
    @Environment(\.conversationRoutes) private var routes
    @Environment(\.writeDirect) private var writeDirect
    @Environment(\.dismiss) private var dismiss
    @State private var text = ""
    @State private var replyTo: Conversation.Message?
    /// « Modifier » : le message dont le texte est dans le champ (15 min après l'envoi au plus).
    @State private var editing: Conversation.Message?
    /// « Répondre en privé » depuis un groupe ou une soirée : la citation part avec le prochain message direct.
    @State private var privateQuote: PrivateQuote?
    @State private var person: PersonRef?
    @State private var picked: PhotosPickerItem?
    @State private var showCamera = false
    /// Photo d'une bulle touchée : plein écran, zoom, Enregistrer, Partager (avis 48a0eefd44ce).
    @State private var viewingPhoto: ChatMediaItem?
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
    @State private var confirmBlock = false
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
    /// « Nouveaux messages » : premier message non lu à l'ouverture, et leur nombre (discussion d'un événement).
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
    private var accent: Color { ConvNeon.lav }
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

    private var typingLine: String? {
        guard let chat else { return nil }
        return ConversationRules.typingLabel(v2.typing.values.sorted(), direct: chat.isDirect)
    }

    /// Clé des relectures v2 : nouvelle conversation, nouveau message, message confirmé.
    private var v2Key: String {
        guard let chat else { return "" }
        return "\(chat.id)|\(chat.messages.count)|\(chat.messages.last?.id ?? "")|\(chat.messages.last?.pending == true)"
    }

    var body: some View {
        chrome(content)
            .sheet(isPresented: $showInfo) {
                if store.conversation?.isEvent == true { EventChatInfoView(store: store) }
                else if store.conversation?.isDirect == true { DirectChatInfoView(store: store) } else { ChatInfoView(store: store) }
            }
            .sheet(item: $reporting) { target in
                if v2.canRelay { MessageReportSheet(model: v2, target: target) } else { ReportSheet(store: store.moderation, target: target) }
            }
            .sheet(isPresented: $askTerms) { TermsAcceptSheet(store: store.moderation) }
            .fullScreenCover(isPresented: $showCamera) {
                BubbleCamera { image in Task { await sendImage(image) } }.ignoresSafeArea()
            }
            .fullScreenCover(item: $viewingPhoto) { EventChatPhotoViewer(item: $0) }
            .personSheet($person, store: store, routes: routes, canWrite: chat?.isDirect != true)
            .confirmationDialog("Bloquer \(title) ?", isPresented: $confirmBlock, titleVisibility: .visible) {
                Button("Bloquer", role: .destructive) {
                    Task {
                        await store.setBlocked(true)
                        dismiss()
                    }
                }
            } message: {
                Text("Sa demande disparaît et elle ne pourra plus t'écrire. Les modérateurs sont prévenus. Tu pourras débloquer dans Réglages › Confidentialité.")
            }
            .overlay(alignment: .bottom) { notice }
            .task(id: group) {
                v2.attach(store)
                // Conditions d'utilisation lues dès l'ouverture : le premier message part sans attendre le serveur.
                Task { _ = await store.moderation.termsAccepted() }
                while !Task.isCancelled {
                    await store.open(group)
                    if let chat { await v2.refreshSeen(chat) }
                    try? await Task.sleep(for: ChatsStore.conversationEvery)
                }
            }
            .task(id: v2Key) {
                v2.attach(store)
                if let chat { await v2.update(chat) }
            }
            // « Répondre en privé » : la citation attend la conversation directe avec cette personne.
            .task(id: chat?.userID) {
                if let user = chat?.userID, chat?.isDirect == true, let quote = ConversationRules.pendingQuotes.removeValue(forKey: user) {
                    Motion.animate { privateQuote = quote }
                    writing = true
                }
            }
            .onDisappear { store.close(); v2.stop(); player.stop(); micLocked = false; _ = recorder.stop(send: false) }
            .onChange(of: picked) { item in Task { await sendPhoto(item) } }
            .onChange(of: chat?.joinNote) { note in if joinNote == nil, let note { Motion.animate(Motion.snappy) { joinNote = note } } }
            .onChange(of: text) { value in if let chat, !value.isEmpty, editing == nil { v2.typed(in: chat) } }
            .onChange(of: chat?.messages.last?.id) { _ in
                if let last = chat?.messages.last, !last.mine { v2.messageArrived(from: last.author) }
            }
    }

    private var content: some View {
        VStack(spacing: 0) {
            if let note = joinNote {
                joinBanner(note).motionTransition(.unfold)
            }
            if let chat {
                let pins = chat.pins
                if !pins.isEmpty {
                    pinnedBanner(pins, chat: chat).motionTransition(.unfold)
                }
                let request = v2.request(in: chat)
                if let request, chat.blocked != true {
                    requestBanner(request, chat: chat).motionTransition(.unfold)
                }
                messages(chat).transition(.opacity).onAppear { ChatTiming.mark("conv.shown") }
                if chat.blocked == true {
                    // Message direct : j'ai bloqué cette personne ; l'historique reste, l'écriture revient en la débloquant.
                    footNote("Tu as bloqué \(title). Débloque-le dans les infos (…) pour lui écrire.")
                } else if request == .incoming || (request == .outgoing && chat.messages.contains { $0.mine }) {
                    // Demande : le destinataire répond après avoir accepté ; l'expéditeur a envoyé son seul message.
                    EmptyView()
                } else if chat.member && chat.canWrite == false {
                    // « Qui peut écrire : Organisation seulement » (réglage de l'organisation de l'événement) : on lit,
                    // on réagit et on signale.
                    footNote("Seule l'organisation peut écrire dans cette discussion").accessibilityIdentifier("chat-read-only")
                } else if chat.member {
                    composer(chat, textOnly: request == .outgoing)
                } else if chat.isEvent {
                    footNote("Tu peux lire la discussion ; tu pourras écrire une fois l'événement publié et ta place confirmée.")
                }
            } else if let error = store.error {
                Text(error).foregroundStyle(ConvNeon.t2).padding().frame(maxHeight: .infinity).transition(.opacity)
            } else {
                ProgressView().tint(ConvNeon.lav).frame(maxHeight: .infinity).transition(.opacity)
            }
        }
        // Chargement → conversation : fondu ; message épinglé ou désépinglé : le bandeau se déplie.
        .motion(Motion.smooth, value: chat == nil)
        .motion(Motion.snappy, value: chat?.pins.map(\.id))
        .motion(Motion.snappy, value: v2.status)
        .foregroundStyle(ConvNeon.t1)
        .background(ZStack { ConvNeon.bg; ConvNeon.halo }.ignoresSafeArea())
    }

    /// Hors d'un écran qui a son propre en-tête (EventChatScreen) : en-tête photo + nom, bouton ….
    @ViewBuilder private func chrome<V: View>(_ view: V) -> some View {
        if embedded {
            view
        } else {
            view
                .navigationTitle(title)
                .navigationBarTitleDisplayMode(.inline)
                .toolbarBackground(ConvNeon.bg, for: .navigationBar)
                .toolbar {
                    ToolbarItem(placement: .principal) { header }
                    ToolbarItem(placement: .navigationBarTrailing) {
                        Button { showInfo = true } label: {
                            Image(systemName: "ellipsis").font(.body.weight(.bold)).foregroundStyle(ConvNeon.lav)
                                .frame(width: 44, height: 44)
                        }
                        .accessibilityLabel(chat?.isDirect == true ? "Infos de la conversation" : chat?.isEvent == true ? "Participants et notifications" : "Infos du groupe")
                        .disabled(chat == nil)
                    }
                }
        }
    }

    // MARK: En-tête (photo, nom → mini-profil)

    private var header: some View {
        Button {
            Haptics.tap()
            if let chat, chat.isDirect, let user = chat.userID { person = PersonRef(id: user) } else { showInfo = true }
        } label: {
            HStack(spacing: 10) {
                headerAvatar
                VStack(alignment: .leading, spacing: 0) {
                    Text(title).font(.system(.headline, design: .rounded).weight(.heavy)).foregroundStyle(ConvNeon.t1).lineLimit(1)
                    if let typingLine {
                        Text(typingLine).font(.caption.weight(.semibold)).foregroundStyle(ConvNeon.mint).lineLimit(1)
                            .transition(.opacity)
                    } else if let subtitle {
                        Text(subtitle).font(.caption).foregroundStyle(ConvNeon.t2).lineLimit(1).transition(.opacity)
                    }
                }
            }
            .frame(minHeight: 44)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .motion(Motion.snappy, value: typingLine)
        .disabled(chat == nil)
        .accessibilityLabel([title, typingLine ?? subtitle].compactMap { $0 }.joined(separator: ", "))
        .accessibilityHint(chat?.isDirect == true ? "Ouvre son profil" : "Ouvre les infos")
        .accessibilityIdentifier("chat-header")
    }

    @ViewBuilder private var headerAvatar: some View {
        if let chat {
            if chat.isDirect {
                ConvFace(id: chat.userID ?? chat.id, name: title, photo: chat.photo, size: 34)
            } else if chat.isEvent {
                Image(systemName: "party.popper.fill").font(.system(size: 15, weight: .bold)).foregroundStyle(PronoTheme.fixed(0x2A1206))
                    .frame(width: 34, height: 34)
                    .background(ConvNeon.evening, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                    .accessibilityHidden(true)
            } else {
                let s = store.chats?.first { $0.id == chat.id }
                GroupTile(emoji: s?.emoji ?? "👥", color: s?.color, photo: s?.photo, system: s?.system ?? false, size: 34)
                    .accessibilityHidden(true)
            }
        }
    }

    private func footNote(_ text: String) -> some View {
        Text(text).font(.footnote).foregroundStyle(ConvNeon.t2).multilineTextAlignment(.center)
            .padding().frame(maxWidth: .infinity)
            .background(ConvNeon.surface.ignoresSafeArea(edges: .bottom))
            .overlay(alignment: .top) { ConvNeon.line.frame(height: 1) }
    }

    // MARK: Demande de message

    private func requestBanner(_ request: MessageRequest, chat: Conversation) -> some View {
        RequestBanner(request: request, name: title, sent: chat.messages.contains { $0.mine },
                      onAccept: { Task { await v2.accept(chat) } },
                      onDelete: { Task { if await v2.decline(chat) { dismiss() } } },
                      onBlock: { confirmBlock = true },
                      onReport: {
                          if let first = chat.messages.first(where: { !$0.mine }) {
                              reporting = ReportTarget(kind: .directMessage, id: first.id, label: "la demande de \(title)")
                          } else if let user = chat.userID {
                              reporting = ReportTarget(kind: .profile, id: user, label: title)
                          }
                      })
    }

    // MARK: Bandeau « Tu es dans le groupe » (entrée par une réponse à un événement, 17.11)

    private func joinBanner(_ note: Conversation.JoinNote) -> some View {
        HStack(alignment: .center, spacing: 10) {
            Image(systemName: "person.2.fill").foregroundStyle(ConvNeon.lav)
            VStack(alignment: .leading, spacing: 2) {
                Text("Tu es dans le groupe « \(note.groupName) »").font(.subheadline.weight(.semibold)).lineLimit(2)
                Text(Self.joinLine(note)).font(.caption).foregroundStyle(ConvNeon.t2).lineLimit(2)
            }
            Spacer(minLength: 0)
            if note.creator != true {
                Button("Quitter", role: .destructive) { confirmLeave = true }
                    .buttonStyle(.bordered).controlSize(.small)
                    .accessibilityIdentifier("group-join-leave")
            }
            Button { Motion.animate(Motion.snappy) { joinNote = nil } } label: {
                Image(systemName: "xmark").font(.caption.weight(.bold)).frame(width: 44, height: 44)
            }
            .buttonStyle(.plain).foregroundStyle(ConvNeon.t2).accessibilityLabel("Fermer")
        }
        .padding(.leading, 14).padding(.trailing, 4).padding(.vertical, 4)
        .background(ConvNeon.glass)
        .overlay(alignment: .bottom) { ConvNeon.line.frame(height: 1) }
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

    private func loaded(_ id: String) -> Bool { store.conversation?.messages.contains { $0.id == id } == true }

    /// Message demandé (citation, bandeau, recherche) : s'il est plus ancien que ceux affichés, la discussion d'un
    /// événement remonte page par page.
    private func reveal(_ id: String, _ proxy: ScrollViewProxy) {
        if loaded(id) { show(id, proxy); return }
        guard store.forEvents else { store.notice = "Ce message est plus ancien que ceux affichés."; return }
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

    /// Discussion d'un événement lue (ouverture, arrivée en bas, nouveau message vu) ; une fois par dernier message.
    private func markRead(_ chat: Conversation) {
        guard store.forEvents, chat.member, let last = chat.messages.last(where: { !$0.pending })?.id, last != lastRead else { return }
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

    /// Toucher une photo (groupe, événement, à deux) : plein écran, comme dans « Médias ».
    private func showPhoto(_ m: Conversation.Message) {
        guard let photo = m.photo, !m.deleted else { return }
        Haptics.tap()
        viewingPhoto = ChatMediaItem(messageId: m.id, kind: "photo", url: photo, at: m.at, authorName: m.mine ? "Toi" : m.authorName)
    }

    private func reply(to m: Conversation.Message) {
        Haptics.press()
        Motion.animate {
            editing = nil
            replyTo = m
        }
        writing = true
    }

    /// « Modifier » : le texte revient dans le champ ; ✓ l'enregistre, ✕ annule.
    private func startEdit(_ m: Conversation.Message) {
        Haptics.press()
        Motion.animate {
            replyTo = nil
            editing = m
            text = m.body
        }
        writing = true
    }

    /// « Répondre en privé » : la conversation directe avec l'auteur s'ouvre dans Discussions, citation prête.
    private func replyPrivately(to m: Conversation.Message, in chat: Conversation) {
        guard let writeDirect else { return }
        Haptics.press()
        let quote = ConversationRules.quote(of: m, in: chat)
        Task {
            guard await v2.openPrivate(with: m.author) != nil else { return }
            ConversationRules.pendingQuotes[m.author] = quote
            if store.forEvents { dismiss() }  // discussion d'un événement : par-dessus la page, on la referme
            if await writeDirect.open(m.author) != .opened { ConversationRules.pendingQuotes[m.author] = nil }
        }
    }

    // MARK: Bandeau des annonces et épinglés

    /// Annonces puis épinglés : un toucher montre le message et passe au suivant ; traits à gauche = combien il y en a.
    private func pinnedBanner(_ pins: [Conversation.Highlight], chat: Conversation) -> some View {
        let index = pinIndex % pins.count
        let h = pins[index]
        let canRemove = chat.admin || chat.isDirect || (chat.isStaff && h.announcement)
        let tone = h.announcement ? ConvNeon.pink : accent
        return HStack(alignment: .center, spacing: 10) {
            if pins.count > 1 {
                VStack(spacing: 2) {
                    ForEach(0..<min(pins.count, 5), id: \.self) { i in
                        Capsule().fill(i == min(index, 4) ? tone : ConvNeon.t3.opacity(0.5)).frame(width: 3)
                    }
                }
                .frame(height: 34)
            }
            Image(systemName: h.announcement ? "megaphone.fill" : "pin.fill").foregroundStyle(tone)
            VStack(alignment: .leading, spacing: 2) {
                Text(h.announcement ? "Annonce" : "Message épinglé").font(.caption.weight(.bold)).foregroundColor(tone)
                    + Text(pins.count > 1 ? "  \(index + 1)/\(pins.count)" : "").font(.caption.monospacedDigit()).foregroundColor(ConvNeon.t2)
                Text("\(h.authorName) : \(Self.clean(h.text))")
                    .font(h.announcement ? .subheadline.weight(.semibold) : .subheadline).lineLimit(h.announcement ? 2 : 1)
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 14).padding(.vertical, 10)
        .background(h.announcement ? AnyShapeStyle(ConvNeon.pink.opacity(0.14)) : AnyShapeStyle(ConvNeon.glass))
        .overlay(alignment: .bottom) { (h.announcement ? ConvNeon.pink.opacity(0.6) : ConvNeon.line).frame(height: 1) }
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
        let lastMine = chat.messages.last { $0.mine && !$0.pending }?.id
        return ScrollViewReader { proxy in
            // Liste native : glisser une bulle vers la droite = « Répondre » (glissement complet = réponse directe),
            // le geste d'iOS lui-même (Mail, Messages), qui ne se bat pas avec le défilement.
            List {
                if chat.messages.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "bubble.left.and.bubble.right.fill").font(.largeTitle).foregroundStyle(ConvNeon.lavender)
                        Text(chat.isEvent ? "Aucun message pour l'instant. Lance la discussion avec les invités !"
                                          : "Aucun message pour l'instant. Lance la discussion !")
                            .foregroundStyle(ConvNeon.t2).multilineTextAlignment(.center)
                        // Groupe tout neuf (créé depuis Discussions) : y ajouter du monde.
                        if chat.member && !chat.isDirect && !chat.isEvent && chat.members.count <= 1 {
                            Button { showInfo = true } label: {
                                Text("Ajouter des membres").font(.headline).foregroundStyle(PronoTheme.fixed(0x1F0618))
                                    .padding(.horizontal, 22).frame(minHeight: 48)
                                    .background(ConvNeon.pink, in: Capsule())
                            }
                            .buttonStyle(PressableStyle())
                        }
                    }
                    .padding(.top, 60)
                    .frame(maxWidth: .infinity).listRowBackground(Color.clear).listRowSeparator(.hidden)
                } else if store.forEvents && !olderDone {
                    // Discussion d'un événement : en haut du fil, la page précédente se charge en remontant.
                    HStack { if loadingOlder { ProgressView().tint(ConvNeon.lav) } }
                        .frame(maxWidth: .infinity, minHeight: loadingOlder ? 36 : 1)
                        .listRowBackground(Color.clear).listRowSeparator(.hidden).listRowInsets(EdgeInsets())
                        .onAppear { loadOlder(proxy) }
                }
                ForEach(rows) { row in
                    switch row.kind {
                    case .day(let label):
                        DayPill(label: label)
                            .frame(maxWidth: .infinity)
                            .listRowBackground(Color.clear).listRowSeparator(.hidden)
                            .listRowInsets(EdgeInsets(top: 10, leading: 16, bottom: 6, trailing: 16))
                    case .message(let m, let first, let last):
                        if m.id == newFrom {
                            UnreadDivider(count: newCount)
                                .id(Self.unreadID)
                                .listRowBackground(Color.clear).listRowSeparator(.hidden)
                                .listRowInsets(EdgeInsets(top: 8, leading: 0, bottom: 8, trailing: 0))
                        }
                        messageRow(m, first: first || m.id == newFrom, last: last, chat: chat, names: names, lastMine: lastMine, proxy: proxy)
                    }
                }
                if let typingLine, v2.request(in: chat) == nil {
                    HStack { TypingBubble(); Spacer() }
                        .listRowBackground(Color.clear).listRowSeparator(.hidden)
                        .listRowInsets(EdgeInsets(top: 4, leading: chat.isDirect ? 10 : 44, bottom: 4, trailing: 12))
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel(chat.isDirect ? "\(title) écrit…" : typingLine)
                        .motionTransition(.opacity.combined(with: .scale(scale: 0.8, anchor: .leading)))
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
            .motion(Motion.snappy, value: typingLine)
            .overlay(alignment: .bottomTrailing) { jumpButton(proxy) }
            .onAppear {
                if let id = store.jumpTo {
                    // Recherche, épinglés, médias des infos : le message à montrer.
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
            .onChange(of: atBottom) { bottomNow in if bottomNow { markRead(chat) } }
            // Réaction, envoi confirmé sur le dernier message : on reste en bas si on y était.
            .onChange(of: chat.messages.last) { _ in if atBottom { bottom(proxy) } }
            .onChange(of: typingLine) { _ in if atBottom { bottom(proxy) } }
            // Clavier qui s'ouvre : le dernier message reste visible au-dessus du champ.
            .onChange(of: writing) { on in if on { bottom(proxy, delay: 0.35) } }
            .onChange(of: jumpTo) { id in
                guard let id else { return }
                jumpTo = nil
                reveal(id, proxy)
            }
            // Recherche, épinglés, médias de l'écran d'infos : le message à montrer.
            .onChange(of: store.jumpTo) { id in
                guard let id else { return }
                store.jumpTo = nil
                reveal(id, proxy)
            }
        }
    }

    @ViewBuilder
    private func messageRow(_ m: Conversation.Message, first: Bool, last: Bool, chat: Conversation, names: [String],
                            lastMine: String?, proxy: ScrollViewProxy) -> some View {
        let report = {
            reporting = ReportTarget(kind: chat.isEvent ? .eventMessage : chat.isDirect ? .directMessage : .groupMessage, id: m.id,
                                     label: "le message de \(m.authorName)")
        }
        let extra = v2.extras[m.id]
        let canEdit = chat.member && chat.blocked != true && chat.canWrite != false && ConversationRules.canEdit(m, isEvent: chat.isEvent)
        // « Seule l'organisation peut écrire » : on réagit et on signale, sans répondre.
        let canReply = chat.canWrite != false
        let canPrivate = writeDirect != nil && !chat.isDirect && !m.mine && !m.deleted && !m.pending && v2.canRelay
        let seen = chat.isDirect && ConversationRules.seen(m, lastMine: lastMine, seenAt: v2.seenAt)
        let key = BubbleKey(message: m, first: first, last: last, names: names, reactions: chat.reactions, chatName: chat.name,
                            flags: [chat.member, chat.admin, chat.isStaff, chat.isDirect, chat.isEvent, v2.request(in: chat) == nil,
                                    canEdit, canPrivate, seen, canReply],
                            extra: extra, card: extra?.eventID.flatMap { v2.cards[$0] })
        SameBubble(key: key) { Group {
            if m.isAnnouncement {
                AnnouncementCard(message: m, names: names, reactions: chat.reactions, canWrite: chat.member, isStaff: chat.isStaff,
                                 isAdmin: chat.admin, canReply: canReply, player: player,
                                 onReact: { emoji in Haptics.tap(); Task { await store.react(m, emoji) } },
                                 onReply: { reply(to: m) }, onPin: { Task { await store.pin(m) } },
                                 onDelete: { Task { await store.delete(m) } }, onReport: report,
                                 onPrivateReply: canPrivate ? { replyPrivately(to: m, in: chat) } : nil,
                                 onPhoto: { showPhoto(m) })
            } else {
                ChatBubble(message: m, first: first, last: last, showAuthor: !chat.isDirect, names: names,
                           reactions: chat.reactions, canWrite: chat.member && v2.request(in: chat) == nil, isAdmin: chat.admin,
                           isStaff: chat.isStaff, canPin: chat.admin || chat.isDirect, canReply: canReply, player: player,
                           quote: extra?.quote, eventID: extra?.eventID, card: extra?.eventID.flatMap { v2.cards[$0] } ?? extra?.eventCard,
                           seen: seen,
                           onReact: { emoji in Haptics.tap(); Task { await store.react(m, emoji) } },
                           onReply: { reply(to: m) },
                           onQuote: { if let id = m.reply?.id { jumpTo = id } },
                           onPin: { Task { await store.pin(m) } },
                           onDelete: { Task { await store.delete(m) } },
                           onReport: report,
                           onEdit: canEdit ? { startEdit(m) } : nil,
                           onPrivateReply: canPrivate ? { replyPrivately(to: m, in: chat) } : nil,
                           onAuthor: { person = PersonRef(id: m.author) },
                           onPhoto: { showPhoto(m) },
                           onOpenEvent: routes.openEvent,
                           onRetry: m.failed ? { Haptics.tap(); Task { await store.retry(m) } } : nil)
            }
        } }
        .equatable()
        .background(RoundedRectangle(cornerRadius: 14).fill(accent.opacity(flashing == m.id ? 0.22 : 0)).padding(-4))
        .id(m.id)
        .listRowBackground(Color.clear)
        .listRowSeparator(.hidden)
        .listRowInsets(EdgeInsets(top: first ? 5 : 1, leading: 10, bottom: last ? 5 : 1, trailing: 12))
        .swipeActions(edge: .leading, allowsFullSwipe: true) {
            if chat.member && canReply && !m.deleted && !m.pending && v2.request(in: chat) == nil {
                Button { reply(to: m) } label: { Label("Répondre", systemImage: "arrowshape.turn.up.left.fill") }
                    .tint(ConvNeon.lavDeep)
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
                Image(systemName: "chevron.down").font(.body.weight(.semibold)).foregroundStyle(ConvNeon.lav)
                    .frame(width: 44, height: 44)
                    .background(ConvNeon.glass, in: Circle())
                    .overlay(Circle().stroke(ConvNeon.line2))
                    .overlay(alignment: .topTrailing) {
                        if unseen > 0 {
                            Text("\(min(unseen, 99))").font(.caption2.weight(.bold).monospacedDigit()).foregroundStyle(PronoTheme.fixed(0x1F0618))
                                .padding(.horizontal, 5).frame(minWidth: 18, minHeight: 18)
                                .background(ConvNeon.pink, in: Capsule()).offset(x: 4, y: -4)
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

    /// textOnly : demande de message pas encore envoyée (un seul message, texte seul : ni photo, ni vocal).
    private func composer(_ chat: Conversation, textOnly: Bool) -> some View {
        VStack(spacing: 6) {
            mentionBar(chat)
            if announcing {
                Label("Annonce : épinglée en haut et envoyée à tous les invités", systemImage: "megaphone.fill")
                    .font(.caption.weight(.semibold)).foregroundStyle(ConvNeon.pink)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .motionTransition(.opacity.combined(with: .move(edge: .bottom)))
            }
            if let editing {
                composerBanner(icon: "pencil", title: "Modifier le message", detail: editing.body, color: ConvNeon.lav,
                               cancel: "Annuler la modification") {
                    self.editing = nil
                    text = ""
                }
            } else if let replyTo {
                composerBanner(icon: "arrowshape.turn.up.left", title: "Réponse à \(replyTo.mine ? "toi" : replyTo.authorName)",
                               detail: replyTo.preview, color: ConvNeon.name(replyTo.author), cancel: "Annuler la réponse") {
                    self.replyTo = nil
                }
            } else if let privateQuote {
                HStack(spacing: 8) {
                    PrivateQuoteBlock(quote: privateQuote, mine: false)
                    Button { Motion.animate { self.privateQuote = nil } } label: {
                        Image(systemName: "xmark.circle.fill").foregroundStyle(ConvNeon.t2).frame(width: 44, height: 44)
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Retirer la citation")
                }
                .motionTransition(.opacity.combined(with: .move(edge: .bottom)))
                .accessibilityIdentifier("chat-private-quote")
            }
            HStack(alignment: .bottom, spacing: 8) {
                if recorder.recording {
                    recordingBar.motionTransition(.opacity.combined(with: .move(edge: .trailing)))
                } else {
                    if chat.isEvent && chat.isStaff && editing == nil {
                        Button {
                            Haptics.selection()
                            Motion.animate(Motion.snappy) { announcing.toggle() }
                        } label: {
                            Image(systemName: announcing ? "megaphone.fill" : "megaphone").font(.body.weight(.semibold))
                                .foregroundStyle(announcing ? ConvNeon.pink : ConvNeon.lav)
                                .frame(width: 44, height: 44)
                                .background(ConvNeon.glass, in: Circle())
                                .overlay(Circle().strokeBorder(announcing ? ConvNeon.pink : ConvNeon.line2, lineWidth: 1))
                        }
                        .accessibilityLabel(announcing ? "Annonce activée" : "Faire une annonce")
                        .accessibilityHint("Épinglée en haut de la discussion et envoyée à tous les invités")
                        .accessibilityIdentifier("chat-announce")
                        .transition(.opacity)
                    }
                    if !textOnly && editing == nil {
                        PhotosPicker(selection: $picked, matching: .images) {
                            Image(systemName: "photo").font(.body.weight(.semibold)).foregroundStyle(ConvNeon.lav)
                                .frame(width: 44, height: 44)
                                .background(ConvNeon.glass, in: Circle())
                                .overlay(Circle().strokeBorder(ConvNeon.line2, lineWidth: 1))
                        }
                        .accessibilityLabel("Envoyer une photo")
                        .disabled(store.sending)
                        .transition(.opacity)
                        // Appareil photo tant qu'on n'écrit pas, comme WhatsApp (absent sans appareil photo : simulateur).
                        if BubbleCamera.available && text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                            Button { Haptics.tap(); showCamera = true } label: {
                                Image(systemName: "camera").font(.body.weight(.semibold)).foregroundStyle(ConvNeon.lav)
                                    .frame(width: 44, height: 44)
                                    .background(ConvNeon.glass, in: Circle())
                                    .overlay(Circle().strokeBorder(ConvNeon.line2, lineWidth: 1))
                            }
                            .disabled(store.sending)
                            .accessibilityLabel("Prendre une photo")
                            .accessibilityIdentifier("chat-camera")
                            .motionTransition(.scale(scale: 0.5).combined(with: .opacity))
                        }
                    }
                    field(chat, textOnly: textOnly).transition(.opacity)
                }
                // Micro ↔ flèche d'envoi : l'un rétrécit pendant que l'autre grandit, comme dans Messages.
                if text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !store.sending && !textOnly && editing == nil {
                    micButton.motionTransition(.scale(scale: 0.5).combined(with: .opacity))
                } else {
                    sendButton(chat).motionTransition(.scale(scale: 0.5).combined(with: .opacity))
                }
            }
            if let problem = recorder.problem {
                Text(problem).font(.caption).foregroundStyle(PronoTheme.pinkInk).motionTransition(.unfold)
            }
        }
        .motion(Motion.snappy, value: text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
        .motion(Motion.snappy, value: store.sending)
        .motion(Motion.snappy, value: recorder.recording)
        .motion(Motion.snappy, value: replyTo?.id)
        .motion(Motion.snappy, value: editing?.id)
        .motion(Motion.snappy, value: privateQuote)
        .motion(Motion.snappy, value: Mentions.query(in: text) == nil)
        .motion(Motion.snappy, value: recorder.problem)
        .padding(.horizontal, 10).padding(.top, 10).padding(.bottom, 8)
        .background(
            LinearGradient(colors: [ConvNeon.bg.opacity(0), ConvNeon.bg.opacity(0.94), ConvNeon.bg],
                           startPoint: .top, endPoint: .init(x: 0.5, y: 0.3))
                .ignoresSafeArea(edges: .bottom)
        )
    }

    /// Au-dessus du champ : ce que le prochain envoi fera (répondre, modifier), avec ✕.
    private func composerBanner(icon: String, title: String, detail: String, color: Color, cancel: String,
                                onCancel: @escaping () -> Void) -> some View {
        HStack(spacing: 8) {
            RoundedRectangle(cornerRadius: 2).fill(color).frame(width: 4)
            VStack(alignment: .leading, spacing: 1) {
                Label(title, systemImage: icon).font(.caption.weight(.semibold)).foregroundStyle(color)
                Text(detail).font(.caption).foregroundStyle(ConvNeon.t2).lineLimit(1)
            }
            Spacer()
            Button { Motion.animate(Motion.snappy, onCancel) } label: {
                Image(systemName: "xmark.circle.fill").foregroundStyle(ConvNeon.t2).frame(width: 44, height: 44)
            }
            .buttonStyle(.plain)
            .accessibilityLabel(cancel)
        }
        .padding(.leading, 8)
        .background(ConvNeon.surface, in: RoundedRectangle(cornerRadius: 14))
        .frame(maxHeight: 54)
        .motionTransition(.opacity.combined(with: .move(edge: .bottom)))
    }

    /// Suggestions de l'@ en cours de frappe : membres filtrés en direct, puis les citations spéciales permises
    /// (@tout et @annonce d'un groupe ; @toutlemonde, @present et @annonce de l'organisation d'un événement).
    @ViewBuilder private func mentionBar(_ chat: Conversation) -> some View {
        let found: [Mentions.Suggestion] = chat.isDirect ? [] : Mentions.query(in: text).map {
            Mentions.suggestions(for: $0, members: chat.citable, me: chat.me, everyone: chat.canEveryone, announce: chat.isStaff,
                                 contacts: ContactNames.shared.names, tags: chat.isEvent ? (chat.tags ?? []) : nil)
        } ?? []
        if let note = chat.tagNote(for: text) {
            Label(note, systemImage: "info.circle").font(.caption).foregroundStyle(ConvNeon.t2)
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
                                ConvFace(id: m.id, name: m.name, photo: m.photo, size: 30)
                            } else {
                                Image(systemName: Self.tagIcon(s.label)).font(.subheadline.weight(.semibold)).foregroundStyle(accent)
                                    .frame(width: 30, height: 30).background(accent.opacity(0.18), in: Circle())
                            }
                            VStack(alignment: .leading, spacing: 1) {
                                Text("@" + s.label).font(.subheadline.weight(.semibold)).foregroundStyle(ConvNeon.t1).lineLimit(1)
                                if !s.hint.isEmpty {
                                    Text(s.hint).font(.caption).foregroundStyle(ConvNeon.t2).lineLimit(1)
                                }
                            }
                            Spacer(minLength: 0)
                        }
                        .padding(.horizontal, 10).frame(minHeight: 44)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(s.member != nil ? "Citer \(s.label)" : "@\(s.label) : \(s.hint)")
                    if s.id != found.last?.id { ConvNeon.line.frame(height: 1).padding(.leading, 50) }
                }
            }
            .background(ConvNeon.surface, in: RoundedRectangle(cornerRadius: 16))
            .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(ConvNeon.line2, lineWidth: 1))
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

    private func field(_ chat: Conversation, textOnly: Bool) -> some View {
        let prompt = announcing ? "Écris ton annonce…" : textOnly ? "Ta demande de message" : chat.isDirect ? "Message" : "Message (@ pour citer)"
        return TextField("", text: $text, prompt: Text(prompt).foregroundColor(ConvNeon.t3), axis: .vertical)
            .lineLimit(1...6)
            .focused($writing)
            .foregroundStyle(ConvNeon.t1)
            .padding(.horizontal, 16).padding(.vertical, 11)
            .frame(minHeight: 44)
            .background(announcing ? ConvNeon.pink.opacity(0.12) : ConvNeon.surface, in: RoundedRectangle(cornerRadius: 22))
            .overlay(RoundedRectangle(cornerRadius: 22).strokeBorder(announcing ? ConvNeon.pink.opacity(0.8) : ConvNeon.line2, lineWidth: 1))
            .accessibilityLabel(announcing ? "Annonce" : editing != nil ? "Message modifié" : "Message")
            .accessibilityIdentifier("chat-message")
    }

    private func sendButton(_ chat: Conversation) -> some View {
        Button {
            // Champ vidé tout de suite, message affiché aussitôt ; en cas d'échec, le texte revient.
            ChatTiming.mark("send.tap")
            Haptics.tap()
            let typed = text, quoted = replyTo, announce = announcing, edited = editing, privateQuoted = privateQuote
            text = ""
            replyTo = nil
            announcing = false
            editing = nil
            privateQuote = nil
            // CGU déjà acceptées (lues à l'ouverture) : la bulle s'affiche dans ce même geste, sans attendre.
            if edited == nil, privateQuoted == nil || !chat.isDirect, store.moderation.terms?.accepted == true,
               let sending = store.sendNow(typed, replyTo: quoted?.id, announce: announce) {
                Task {
                    guard !(await sending.value) else { return }
                    // Refusé : le texte revient (sans écraser ce qui a été écrit entre-temps).
                    if text.isEmpty { text = typed }
                    if replyTo == nil { replyTo = quoted }
                    announcing = announce
                }
                return
            }
            Task {
                if let edited {
                    if !(await v2.edit(edited, to: typed, in: chat)) { text = typed; editing = edited }
                    return
                }
                if !(await termsAccepted()) {
                    text = typed
                    replyTo = quoted
                    announcing = announce
                    privateQuote = privateQuoted
                    return
                }
                if let privateQuoted, chat.isDirect {
                    if !(await v2.send(typed, quote: privateQuoted, in: chat)) { text = typed; privateQuote = privateQuoted }
                } else if !(await store.send(typed, replyTo: quoted?.id, announce: announce)) {
                    // Refusé : le texte revient (sans écraser ce qui a été écrit entre-temps).
                    if text.isEmpty { text = typed }
                    if replyTo == nil { replyTo = quoted }
                    announcing = announce
                }
            }
        } label: {
            if store.sending { ProgressView().tint(ConvNeon.lav).frame(width: 44, height: 44) } else {
                // Même flèche en annonce (le champ et la ligne 📣 au-dessus disent déjà que c'est une annonce).
                Image(systemName: editing != nil ? "checkmark" : "arrow.up").font(.body.weight(.heavy))
                    .foregroundStyle(PronoTheme.fixed(0x120B26))
                    .frame(width: 44, height: 44)
                    .background(announcing ? AnyShapeStyle(ConvNeon.pink) : AnyShapeStyle(ConvNeon.lavender), in: Circle())
                    .shadow(color: ConvNeon.lavDeep.opacity(0.6), radius: 9)
            }
        }
        .buttonStyle(PressableStyle(scale: 0.9))
        .accessibilityLabel(editing != nil ? "Enregistrer la modification" : announcing ? "Publier l'annonce" : "Envoyer")
        .accessibilityIdentifier("chat-send")
        .disabled(text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || store.sending)
    }

    /// Appui long : enregistre ; relâcher : envoie ; glisser vers la gauche : annule (comme WhatsApp).
    /// Simple toucher : l'enregistrement reste actif ; un second toucher l'envoie, sans jamais en relancer un autre.
    private var micButton: some View {
        Image(systemName: "mic.fill")
            .font(.body.weight(.bold))
            .foregroundStyle(PronoTheme.fixed(0x120B26))
            .frame(width: 44, height: 44)
            .background(recorder.recording ? (cancelVoice ? AnyShapeStyle(ConvNeon.t3) : AnyShapeStyle(ConvNeon.pink))
                                           : AnyShapeStyle(ConvNeon.lavender), in: Circle())
            .shadow(color: ConvNeon.lavDeep.opacity(0.6), radius: 9)
            // Enregistrement : le micro grossit sous le doigt.
            .scaleEffect(recorder.recording ? 1.3 : 1)
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
                Button("Annuler") { micLocked = false; _ = recorder.stop(send: false) }.font(.subheadline).foregroundStyle(ConvNeon.lav)
                Text("Touche le micro pour envoyer").font(.subheadline).foregroundStyle(ConvNeon.t2)
            } else {
                Text(cancelVoice ? "Relâche pour annuler" : "‹ Glisse pour annuler").font(.subheadline)
                    .foregroundStyle(cancelVoice ? PronoTheme.pinkInk : ConvNeon.t2)
            }
        }
        .padding(.horizontal, 14).frame(height: 44)
        .background(ConvNeon.surface, in: RoundedRectangle(cornerRadius: 22))
        .overlay(RoundedRectangle(cornerRadius: 22).strokeBorder(ConvNeon.line2, lineWidth: 1))
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

/// Ce qu'une bulle montre : si rien n'a changé, elle n'est pas redessinée quand le reste de l'écran l'est (chaque
/// lettre tapée, vitesse 18.11 : la frappe ne refait plus tout le fil). Ses actions suivent le même message.
private struct BubbleKey: Equatable {
    let message: Conversation.Message
    let first: Bool
    let last: Bool
    let names: [String]
    let reactions: [String]
    let chatName: String
    let flags: [Bool]
    let extra: MessageExtra?
    let card: ChatEventCard?
}

private struct SameBubble<Content: View>: View, Equatable {
    let key: BubbleKey
    @ViewBuilder let content: () -> Content

    static func == (a: Self, b: Self) -> Bool { a.key == b.key }

    var body: some View { content() }
}

/// Séparateur de jour, centré, en capitales : « AUJOURD'HUI », « HIER », « LUNDI », « 12 NOVEMBRE ».
private struct DayPill: View {
    let label: String

    var body: some View {
        Text(label).font(.caption.weight(.bold)).tracking(0.8).textCase(.uppercase).foregroundStyle(ConvNeon.t2)
            .padding(.horizontal, 12).frame(minHeight: 26)
            .background(ConvNeon.surface.opacity(0.8), in: Capsule())
            .overlay(Capsule().strokeBorder(ConvNeon.line, lineWidth: 1))
            .accessibilityLabel(label)
            .accessibilityAddTraits(.isHeader)
    }
}

/// Heure (et « modifié », horloge pendant l'envoi, coche une fois reçu, « Vu ») en bas à droite de la bulle.
/// « 3 nouveaux messages » : bande posée avant le premier message non lu, à l'ouverture (discussion d'un événement).
private struct UnreadDivider: View {
    let count: Int

    var body: some View {
        Text(count > 1 ? "\(count) nouveaux messages" : "1 nouveau message")
            .font(.caption.weight(.semibold)).foregroundStyle(ConvNeon.lav)
            .padding(.vertical, 6)
            .frame(maxWidth: .infinity)
            .background(ConvNeon.glass)
            .overlay(alignment: .top) { ConvNeon.line.frame(height: 1) }
            .overlay(alignment: .bottom) { ConvNeon.line.frame(height: 1) }
            .accessibilityAddTraits(.isHeader)
            .accessibilityIdentifier("chat-unread")
    }
}

private struct MessageMeta: View {
    let message: Conversation.Message
    var onPhoto = false
    var seen = false

    var body: some View {
        HStack(spacing: 3) {
            if message.edited && !message.deleted { Text("modifié") }
            Text(message.date?.formatted(date: .omitted, time: .shortened) ?? "")
            if seen { Text("· Vu") }
            if message.mine && !message.deleted {
                if message.failed {
                    Image(systemName: "exclamationmark.circle.fill").font(.system(size: 10, weight: .bold))
                } else if message.pending {
                    Image(systemName: "clock").font(.system(size: 9, weight: .bold))
                } else {
                    // ✓ envoyé ; ✓✓ lavande clair une fois vu.
                    HStack(spacing: -5) {
                        Image(systemName: "checkmark")
                        if seen { Image(systemName: "checkmark") }
                    }
                    .font(.system(size: 9, weight: .bold))
                    .foregroundStyle(seen ? PronoTheme.fixed(0xDCD5FF) : Color.white.opacity(0.9))
                }
            }
        }
        .font(.caption2.monospacedDigit())
        .foregroundStyle(onPhoto ? Color.white : message.mine ? Color.white.opacity(0.9) : ConvNeon.t3)
        .padding(.horizontal, onPhoto ? 6 : 0).padding(.vertical, onPhoto ? 2 : 0)
        .background(onPhoto ? AnyShapeStyle(Color.black.opacity(0.45)) : AnyShapeStyle(Color.clear), in: Capsule())
        .accessibilityHidden(true)
    }

    /// Texte invisible de même largeur : le texte du message s'arrête avant l'heure, qui se loge sur sa dernière ligne.
    static func spacer(for m: Conversation.Message, seen: Bool = false) -> String {
        let time = m.date?.formatted(date: .omitted, time: .shortened) ?? ""
        return "\u{2003}" + (m.edited ? "modifié " : "") + time + (seen ? " · Vu" : "") + (m.mine ? (seen ? " ✓✓" : " ✓") : "")
    }
}

/// Citation dans une bulle : trait de la couleur de l'auteur, son nom, l'extrait ; un toucher remonte au message.
private struct QuoteBlock: View {
    let reply: Conversation.Reply
    let mine: Bool
    let onTap: () -> Void

    var body: some View {
        let color = mine ? PronoTheme.fixed(0xE6DFFF) : ConvNeon.name(reply.author ?? reply.name)
        Button(action: onTap) {
            HStack(spacing: 8) {
                RoundedRectangle(cornerRadius: 2).fill(mine ? ConvNeon.lav : color).frame(width: 4)
                VStack(alignment: .leading, spacing: 1) {
                    Text(reply.name).font(.caption.weight(.bold)).foregroundStyle(color).lineLimit(1)
                    Text(reply.text).font(.caption).foregroundStyle(mine ? Color.white.opacity(0.82) : ConvNeon.t2).lineLimit(2)
                }
                Spacer(minLength: 0)
            }
            .padding(6)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(mine ? ConvNeon.quoteOnMine : PronoTheme.fixed(0x0E0A1F, 0.35), in: RoundedRectangle(cornerRadius: 12))
        }
        .buttonStyle(.plain)
        .disabled(reply.id == nil)
        .accessibilityLabel("Réponse à \(reply.name) : \(reply.text)")
        .accessibilityHint(reply.id == nil ? "" : "Touche pour voir le message d'origine")
    }
}

/// Une bulle Néon : mes messages à droite (dégradé violet, texte blanc), les autres à gauche (nuit, liseré lavande) ;
/// dans un groupe, le nom en couleur en tête de la série et la photo en bas (un toucher : son mini-profil) ; heure dans
/// la bulle ; @citations en gras et en couleur ; carte de soirée et citation privée (Discussions v2).
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
    /// false : « Seule l'organisation peut écrire » (réactions et signalement seulement).
    var canReply = true
    @ObservedObject var player: VoicePlayer
    var quote: PrivateQuote?
    var eventID: String?
    var card: ChatEventCard?
    var seen = false
    let onReact: (String) -> Void
    let onReply: () -> Void
    let onQuote: () -> Void
    let onPin: () -> Void
    let onDelete: () -> Void
    /// « Signaler » (modération commune) : sur le message d'un autre, même sans pouvoir écrire.
    var onReport: (() -> Void)?
    var onEdit: (() -> Void)?
    var onPrivateReply: (() -> Void)?
    var onAuthor: (() -> Void)?
    /// Toucher la photo : plein écran (Enregistrer, Partager).
    var onPhoto: (() -> Void)?
    var onOpenEvent: (@MainActor (String) -> Void)?
    /// Message pas parti (réseau absent) : un toucher le renvoie.
    var onRetry: (() -> Void)?

    private var actions: Bool { (canWrite || (!message.mine && onReport != nil)) && !message.deleted && !message.pending && !message.failed }
    private var avatar: CGFloat { 28 }
    /// Une carte de soirée seule (sans texte) : pas de bulle autour, l'heure dessous.
    private var cardOnly: Bool {
        eventID != nil && message.body.isEmpty && message.photo == nil && message.audioSeconds == nil && quote == nil && !message.deleted
    }

    var body: some View {
        HStack(alignment: .bottom, spacing: 6) {
            if message.mine {
                Spacer(minLength: 56)
            } else if showAuthor {
                if last {
                    Button { onAuthor?() } label: { ConvFace(id: message.author, name: message.authorName, photo: message.authorPhoto, size: avatar) }
                        .buttonStyle(.borderless)
                        .accessibilityLabel("Profil de \(message.authorName)")
                } else { Color.clear.frame(width: avatar, height: 1) }
            }
            VStack(alignment: message.mine ? .trailing : .leading, spacing: 4) {
                if let eventID, !message.deleted {
                    if let card {
                        EventCardBubble(card: card, onOpen: onOpenEvent.map { open in { open(eventID) } })
                    } else {
                        EventCardUnavailable()
                    }
                }
                Group {
                    if cardOnly {
                        MessageMeta(message: message, seen: seen).padding(.horizontal, 6)
                    } else {
                        bubble
                    }
                }
                // En cours d'envoi : bulle légèrement estompée, qui s'affirme une fois le message reçu.
                .opacity(message.pending ? 0.7 : 1)
                .contextMenu { if actions { ChatMenu(message: message, reactions: reactions, canWrite: canWrite, isAdmin: isAdmin,
                                                     isStaff: isStaff, canPin: canPin, canReply: canReply, onReact: onReact, onReply: onReply,
                                                     onPin: onPin, onDelete: onDelete, onReport: onReport, onEdit: onEdit,
                                                     onPrivateReply: onPrivateReply) } }
                if !message.reactions.isEmpty {
                    ReactionChips(message: message, canWrite: canWrite, onReact: onReact)
                        .offset(y: -9).padding(.horizontal, 10).padding(.bottom, -9)
                        .motionTransition(.scale(scale: 0.6, anchor: message.mine ? .trailing : .leading).combined(with: .opacity))
                }
                if message.failed {
                    Button { onRetry?() } label: {
                        Label("Pas envoyé · Toucher pour réessayer", systemImage: "exclamationmark.circle.fill")
                            .font(.caption.weight(.semibold)).foregroundStyle(PronoTheme.pinkInk)
                            .frame(minHeight: 30)
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("chat-retry")
                    .motionTransition(.opacity.combined(with: .move(edge: .top)))
                }
            }
            if !message.mine { Spacer(minLength: 56) }
        }
        .motion(Motion.smooth, value: message.pending)
        .motion(Motion.snappy, value: message.failed)
        .onAppear { ChatTiming.mark(message.pending ? "send.appear" : message.mine ? "mine.appear" : "recv.appear." + message.id) }
        .motion(Motion.smooth, value: seen)
        .motion(Motion.bouncy, value: message.reactions.map { "\($0.emoji)\($0.count)\($0.mine)" })
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibility)
        .accessibilityHint(actions ? "Glisse vers la droite pour répondre ; appui long pour réagir\(onEdit != nil ? ", modifier" : "")\(canPin ? ", épingler" : "") ou supprimer" : "")
        .accessibilityAction(named: "Répondre") { if actions && canWrite && canReply { onReply() } }
        .accessibilityAction(named: "Réessayer") { onRetry?() }
        .accessibilityActions { if message.photo != nil && !message.deleted { Button("Voir la photo") { onPhoto?() } } }
    }

    private var accessibility: String {
        let who = message.mine ? "Toi" : ContactNames.shared.label(for: message.author, pseudo: message.authorName).text
        let time = message.failed ? "pas envoyé, touche pour réessayer" : message.pending ? "envoi en cours"
            : message.date?.formatted(date: .omitted, time: .shortened) ?? ""
        var parts = ["\(who), \(time)"]
        if let card { parts.append("soirée \(card.title)") }
        if let quote { parts.append("réponse privée à \(quote.author) : \(quote.excerpt)") }
        parts.append(message.deleted ? message.body : cardOnly ? "" : message.preview)
        if message.edited && !message.deleted { parts.append("modifié") }
        if seen { parts.append("vu") }
        return parts.filter { !$0.isEmpty }.joined(separator: ", ")
    }

    /// Coin côté auteur plus serré dans une série (la « queue » des messageries).
    private var shape: UnevenRoundedRectangle {
        let r: CGFloat = 22, tight: CGFloat = 8
        return message.mine
            ? UnevenRoundedRectangle(cornerRadii: .init(topLeading: r, bottomLeading: r, bottomTrailing: last ? r : tight, topTrailing: first ? r : tight))
            : UnevenRoundedRectangle(cornerRadii: .init(topLeading: first ? r : tight, bottomLeading: last ? r : tight, bottomTrailing: r, topTrailing: r))
    }

    private var bubble: some View {
        let photoOnly = message.photo != nil && message.body.isEmpty && !message.deleted
        return VStack(alignment: .leading, spacing: 5) {
            if showAuthor && first && !message.mine {
                Button { onAuthor?() } label: {
                    PersonName(id: message.author, pseudo: message.authorName, pseudoFont: .caption2)
                        .font(.subheadline.weight(.bold)).foregroundStyle(ConvNeon.name(message.author))
                }
                .buttonStyle(.borderless)
                .padding(.horizontal, message.photo == nil ? 0 : 6).padding(.top, message.photo == nil ? 0 : 4)
            }
            if message.pinned && !message.deleted {
                (Text(Image(systemName: "pin.fill")) + Text(" Épinglé")).font(.caption2.weight(.bold))
                    .foregroundStyle(message.mine ? PronoTheme.fixed(0xE6DFFF) : ConvNeon.lav)
                    .padding(.horizontal, message.photo == nil ? 0 : 6)
            }
            if let quote, !message.deleted {
                PrivateQuoteBlock(quote: quote, mine: message.mine)
            }
            if let reply = message.reply, !message.deleted {
                QuoteBlock(reply: reply, mine: message.mine, onTap: onQuote)
            }
            if let photo = message.photo.flatMap(URL.init(string:)), !message.deleted {
                AsyncImage(url: photo) { image in image.resizable().scaledToFill() } placeholder: {
                    ZStack { ConvNeon.surface2; ProgressView().tint(ConvNeon.lav) }
                }
                .frame(width: 240, height: 240).clipShape(RoundedRectangle(cornerRadius: 18))
                .overlay(alignment: .bottomTrailing) { if photoOnly { MessageMeta(message: message, onPhoto: true, seen: seen).padding(8) } }
                .contentShape(RoundedRectangle(cornerRadius: 18))
                .onTapGesture { onPhoto?() }
                .accessibilityLabel("Photo de \(message.authorName)")
                .accessibilityIdentifier("chat-photo")
            }
            if let seconds = message.audioSeconds, !message.deleted {
                VoiceBubble(player: player, id: message.id, url: message.audio.flatMap(URL.init(string:)), seconds: seconds, mine: message.mine)
                HStack { Spacer(); MessageMeta(message: message, seen: seen) }
            }
            if message.deleted {
                HStack(spacing: 6) {
                    Label(message.body, systemImage: "nosign").font(.subheadline.italic())
                    MessageMeta(message: message)
                }
                .foregroundStyle(ConvNeon.t2)
            } else if !message.body.isEmpty {
                // L'heure se loge sur la dernière ligne s'il y a la place (espace invisible de sa largeur), sinon dessous.
                (Text(Mentions.highlighted(message.body, names: names, color: message.mine ? PronoTheme.fixed(0xE6DFFF) : ConvNeon.lav))
                    + Text(MessageMeta.spacer(for: message, seen: seen)).font(.caption2.monospacedDigit()).foregroundColor(.clear))
                    .font(.body)
                    .padding(.horizontal, message.photo == nil ? 0 : 6)
                    .overlay(alignment: .bottomTrailing) { MessageMeta(message: message, seen: seen).offset(y: 2) }
                    .fixedSize(horizontal: false, vertical: true)
            } else if message.photo == nil && message.audioSeconds == nil {
                MessageMeta(message: message, seen: seen)
            }
        }
        .foregroundStyle(message.mine && !message.deleted ? Color.white : ConvNeon.t1)
        .padding(.horizontal, message.photo == nil ? 13 : 4).padding(.top, message.photo == nil ? 9 : 4).padding(.bottom, message.photo == nil ? 8 : 4)
        .background {
            if message.deleted {
                shape.fill(ConvNeon.surface.opacity(0.6))
            } else if message.mine {
                shape.fill(ConvNeon.mine).shadow(color: ConvNeon.mineA.opacity(0.45), radius: 12, y: 8)
            } else {
                shape.fill(ConvNeon.theirs).overlay(shape.strokeBorder(ConvNeon.theirsLine, lineWidth: 1))
            }
        }
    }
}

/// Annonce de l'organisation : une carte pleine largeur, distincte des bulles (en-tête 📣, bord rose).
private struct AnnouncementCard: View {
    let message: Conversation.Message
    let names: [String]
    let reactions: [String]
    let canWrite: Bool
    let isStaff: Bool
    let isAdmin: Bool
    var canReply = true
    @ObservedObject var player: VoicePlayer
    let onReact: (String) -> Void
    let onReply: () -> Void
    let onPin: () -> Void
    let onDelete: () -> Void
    let onReport: () -> Void
    var onPrivateReply: (() -> Void)?
    var onPhoto: (() -> Void)?

    private var accent: Color { ConvNeon.pink }
    private var actions: Bool { (canWrite || !message.mine) && !message.pending }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 6) {
                    Image(systemName: "megaphone.fill")
                    Text("ANNONCE").font(.caption.weight(.heavy)).tracking(0.8)
                    Text("· \(message.mine ? "toi" : message.authorName)").font(.caption.weight(.semibold)).foregroundStyle(ConvNeon.t2).lineLimit(1)
                    Spacer(minLength: 0)
                    if message.pending { Image(systemName: "clock") } else {
                        Text(message.date?.formatted(date: .omitted, time: .shortened) ?? "").font(.caption2.monospacedDigit())
                            .foregroundStyle(ConvNeon.t2)
                    }
                }
                .font(.caption).foregroundStyle(PronoTheme.pinkInk)
                if let photo = message.photo.flatMap(URL.init(string:)) {
                    AsyncImage(url: photo) { image in image.resizable().scaledToFill() } placeholder: { ProgressView() }
                        .frame(maxWidth: .infinity).frame(height: 200).clipShape(RoundedRectangle(cornerRadius: 14))
                        .contentShape(RoundedRectangle(cornerRadius: 14))
                        .onTapGesture { onPhoto?() }
                        .accessibilityIdentifier("chat-photo")
                }
                if let seconds = message.audioSeconds {
                    VoiceBubble(player: player, id: message.id, url: message.audio.flatMap(URL.init(string:)), seconds: seconds, mine: false)
                }
                let text = ConversationView.clean(message.body)
                if !text.isEmpty {
                    Text(Mentions.highlighted(text, names: names, color: ConvNeon.lav)).font(.body.weight(.medium))
                        .foregroundStyle(ConvNeon.t1)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(accent.opacity(0.12), in: RoundedRectangle(cornerRadius: 22, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).strokeBorder(accent.opacity(0.85), lineWidth: 1.5))
            .opacity(message.pending ? 0.7 : 1)
            .contextMenu { if actions { ChatMenu(message: message, reactions: reactions, canWrite: canWrite, isAdmin: isAdmin,
                                                 isStaff: isStaff, canPin: false, canReply: canReply, onReact: onReact, onReply: onReply,
                                                 onPin: onPin, onDelete: onDelete, onReport: onReport,
                                                 onPrivateReply: onPrivateReply) } }
            if !message.reactions.isEmpty {
                ReactionChips(message: message, canWrite: canWrite, onReact: onReact).offset(y: -9).padding(.horizontal, 12).padding(.bottom, -9)
            }
        }
        .padding(.vertical, 6)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Annonce de \(message.mine ? "toi" : message.authorName) : \(ConversationView.clean(message.preview))")
        .accessibilityAction(named: "Répondre") { if canWrite && canReply && !message.pending { onReply() } }
        .accessibilityIdentifier("chat-announcement")
        .accessibilityActions { if message.photo != nil { Button("Voir la photo") { onPhoto?() } } }
    }
}

/// Appui long : réactions en tête, puis Répondre, Répondre en privé, Copier, Modifier, Épingler / Retirer l'annonce,
/// Supprimer, Signaler.
private struct ChatMenu: View {
    let message: Conversation.Message
    let reactions: [String]
    let canWrite: Bool
    let isAdmin: Bool
    let isStaff: Bool
    let canPin: Bool
    var canReply = true
    let onReact: (String) -> Void
    let onReply: () -> Void
    let onPin: () -> Void
    let onDelete: () -> Void
    var onReport: (() -> Void)?
    var onEdit: (() -> Void)?
    var onPrivateReply: (() -> Void)?

    var body: some View {
        if canWrite {
            ControlGroup {
                ForEach(reactions, id: \.self) { emoji in Button(emoji) { onReact(emoji) } }
            }
            if canReply {
                Button { onReply() } label: { Label("Répondre", systemImage: "arrowshape.turn.up.left") }
            }
        }
        if let onPrivateReply {
            Button { onPrivateReply() } label: { Label("Répondre en privé", systemImage: "bubble.left.and.text.bubble.right") }
        }
        if !message.body.isEmpty {
            Button { UIPasteboard.general.string = ConversationView.clean(message.body) } label: { Label("Copier", systemImage: "doc.on.doc") }
        }
        if let onEdit {
            Button { onEdit() } label: { Label("Modifier", systemImage: "pencil") }
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

    var body: some View {
        HStack(spacing: 4) {
            ForEach(message.reactions, id: \.emoji) { r in
                Button { onReact(r.emoji) } label: {
                    HStack(spacing: 4) {
                        Text(verbatim: r.emoji).font(.system(size: 15))
                        if r.count > 1 {
                            Text("\(r.count)").font(.caption.weight(.bold)).foregroundStyle(r.mine ? ConvNeon.lav : ConvNeon.t2)
                                .contentTransition(.numericText())
                        }
                    }
                    .padding(.horizontal, 8).frame(minHeight: 28)
                    .background(r.mine ? ConvNeon.reactMine : ConvNeon.surface2, in: Capsule())
                    .overlay(Capsule().strokeBorder(ConvNeon.bg, lineWidth: 2))
                    .overlay(Capsule().stroke(r.mine ? ConvNeon.lav.opacity(0.5) : ConvNeon.line2, lineWidth: 1).padding(-1))
                }
                .buttonStyle(PressableStyle(scale: 0.9))
                .disabled(!canWrite)
                .accessibilityLabel("\(r.emoji) \(r.count)\(r.mine ? ", retirer ma réaction" : "")")
                .motionTransition(.scale(scale: 0.6).combined(with: .opacity))
            }
        }
    }
}

/// Point rose de l'enregistrement : il bat doucement (immobile avec Réduire les animations).
private struct RecordingDot: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var dim = false

    var body: some View {
        Circle().fill(ConvNeon.pink).frame(width: 10, height: 10)
            .opacity(dim ? 0.3 : 1)
            .onAppear {
                guard !reduceMotion else { return }
                withAnimation(.easeInOut(duration: 0.7).repeatForever(autoreverses: true)) { dim = true }
            }
    }
}

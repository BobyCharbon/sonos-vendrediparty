import SwiftUI

/// Onglet Discussions natif : la liste des groupes et la conversation ouverte, mises à jour EN DIRECT (WebSocket
/// Supabase Realtime, ChatRealtime) ; un rafraîchissement lent reste en secours. Un message envoyé s'affiche tout de
/// suite (horloge) puis prend sa place quand le serveur l'a enregistré, comme Snapchat ou WhatsApp.
@MainActor
final class ChatsStore: ObservableObject {
    /// Secours si le temps réel est coupé (réseau capricieux) : la conversation, puis la liste.
    static let conversationEvery: Duration = .seconds(10)
    static let listEvery: Duration = .seconds(30)

    @Published private(set) var chats: [ChatSummary]?
    @Published private(set) var conversation: Conversation?
    @Published private(set) var error: String?
    @Published private(set) var sending = false
    @Published var notice: String?
    /// Conversation à ouvrir (toucher d'une notification) : la liste la pousse dès qu'elle s'affiche.
    @Published var requested: String?
    /// Message à montrer (recherche, bandeau des épinglés) : le fil y défile puis le remet à nil.
    @Published var jumpTo: String?
    /// Discussion d'un événement : page plus ancienne en cours ; false quand le début de la discussion est atteint.
    @Published private(set) var loadingOlder = false
    @Published private(set) var hasOlder = true
    /// Messages plus anciens chargés (loadOlder) : gardés au-dessus du fil à chaque relecture.
    private var older: [Conversation.Message] = []
    /// Réglage changé à l'écran, pas encore confirmé : appliqué par-dessus une relecture arrivée entre-temps.
    private var prefsOverride: ((Conversation) -> Conversation)?

    private let api: PartyAPI
    private weak var web: WebStorage?
    private var endpoint: ChatRealtime.Endpoint?
    private var listLive: ChatRealtime?
    private var chatLive: ChatRealtime?
    /// Messages envoyés pas encore confirmés : gardés en bas de la conversation jusqu'à leur retour du serveur.
    private var pending: [Conversation.Message] = []
    private var refreshing: Task<Void, Never>?

    /// Discussion d'un événement (écran natif ouvert depuis sa fiche) : mêmes écrans, routes /api/account/event-chat/*.
    let forEvents: Bool

    init(api: PartyAPI, web: WebStorage?, forEvents: Bool = false) {
        self.api = api
        self.web = web
        self.forEvents = forEvents
    }

    /// Pause des notifications de toutes les Discussions (bouton en haut de la liste) ; même réglage que
    /// Réglages › Notifications.
    private(set) lazy var pause = PauseStore(api: api, web: web)

    /// Groupes (mêmes données et actions que Réglages › Groupes) : créer un groupe depuis Discussions, le gérer
    /// depuis les infos d'une discussion.
    private(set) lazy var groups = GroupsStore(api: api, web: web)
    private(set) lazy var privacy = PrivacyStore(api: api, web: web)
    /// « Signaler » un message, conditions d'utilisation avant le premier message (modération commune).
    private(set) lazy var moderation = ModerationStore(api: api, web: web)

    /// Nouveau groupe depuis Discussions : même création que Réglages › Groupes, le créateur dedans d'office ;
    /// la liste est relue et la discussion du groupe s'ouvre (requested).
    func createGroup(_ name: String) async -> Bool {
        guard let id = await groups.create(name, join: true) else {
            if let problem = groups.notice ?? groups.error { notice = problem; groups.notice = nil }
            return false
        }
        await loadList()
        requested = id
        return true
    }

    var unread: Int { chats?.reduce(0) { $0 + $1.unread } ?? 0 }

    /// Conversation privée à deux (d'après la liste ou la conversation ouverte) ; inconnue : le serveur la reconnaît.
    func isDirect(_ id: String) -> Bool {
        conversation?.id == id ? conversation?.isDirect == true : chats?.first { $0.id == id }?.direct == true
    }

    /// « Écrire » (Mes amis, fiche d'un membre) : LA conversation privée avec cette personne, ouverte dans Discussions.
    /// Rend false (et un message dans notice) si on ne peut pas lui écrire.
    func write(to user: String, contactHash: String? = nil) async -> Bool {
        var chat: String?
        await run { token in chat = try await api.startDirectChat(token: token, user: user, contactHash: contactHash) }
        guard let chat else { return false }
        requested = chat
        return true
    }

    /// Bloquer / débloquer l'autre personne d'un message direct (elle n'en est pas prévenue).
    func setBlocked(_ on: Bool) async {
        guard let user = conversation?.userID, conversation?.isDirect == true else { return }
        await act { token in try await api.blockDirect(token: token, user: user, on: on) }
    }

    func loadList() async {
        #if DEBUG
        if demo { return }
        #endif
        if chats == nil, let account = await account() {
            chats = ChatsCache.load([ChatSummary].self, account: account, name: "list")  // tout de suite, puis à jour
        }
        await run(loading: chats == nil) { token in
            let (list, endpoint) = try await api.chats(token: token)
            if list != chats { chats = list }
            if let endpoint { self.endpoint = endpoint }
            if let account = ChatsCache.account(of: token) { ChatsCache.save(list, account: account, name: "list") }
        }
    }

    /// Au lancement de l'app : la liste est prête avant même d'ouvrir l'onglet (sans compte, rien).
    func preload() async {
        guard await web?.accountToken() != nil else { return }
        await loadList()
    }

    private func account() async -> String? {
        guard let token = await web?.accountToken() else { return nil }
        return ChatsCache.account(of: token)
    }

    /// Liste à l'écran : temps réel sur tous mes groupes (nouveau message → liste relue).
    func startListLive() async {
        guard listLive == nil, let endpoint, let token = await web?.accountToken() else { return }
        let live = ChatRealtime(endpoint: endpoint, token: token, group: nil) { [weak self] in self?.refreshSoon(nil) }
        listLive = live
        live.start()
    }

    func stopListLive() {
        listLive?.stop()
        listLive = nil
    }

    #if DEBUG
    /// Simulateur : PARTY_DEBUG_MOTION=chat rejoue une conversation figée (MotionDemo) pour regarder les animations.
    private(set) var demo = false

    func showDemo(list: [ChatSummary]? = nil, conversation: Conversation? = nil) {
        demo = true
        error = nil
        if let list { chats = list }
        if let conversation { self.conversation = conversation }
    }
    #endif

    /// Ouvre (ou relit) une conversation ; la marque comme lue si de nouveaux messages sont arrivés.
    func open(_ group: String) async {
        #if DEBUG
        if demo { return }
        #endif
        if conversation?.id != group {
            pending = []
            older = []
            hasOlder = true
            jumpTo = nil
            // Dernière version gardée sur le téléphone : la conversation s'affiche sans attendre le serveur.
            conversation = await account().flatMap { ChatsCache.load(Conversation.self, account: $0, name: "chat-" + group) }
        }
        await run(loading: conversation == nil) { token in
            let fresh = forEvents ? try await api.openEventChat(token: token, event: group)
                                  : try await api.openChat(token: token, group: group, direct: isDirect(group))
            if let live = fresh.realtime { endpoint = live }
            if let account = ChatsCache.account(of: token) { ChatsCache.save(fresh, account: account, name: "chat-" + group) }
            let changed = fresh.messages.last?.id != conversation?.messages.filter { !$0.pending }.last?.id || conversation == nil
            pending.removeAll { p in fresh.messages.contains { $0.id == p.id } }
            var shown = pending.isEmpty && older.isEmpty ? fresh
                : fresh.with(messages: Conversation.merge(older: older, into: fresh.messages) + pending)
            if let prefsOverride { shown = prefsOverride(shown) }
            if shown != conversation { conversation = shown }
            if changed && fresh.member && !forEvents { try? await api.readChat(token: token, group: group, direct: fresh.isDirect) }
        }
        if chatLive == nil, conversation?.id == group { await startChatLive(group) }
    }

    private func startChatLive(_ group: String) async {
        if endpoint == nil && !forEvents { await loadList() }
        guard let endpoint, let token = await web?.accountToken() else { return }
        let live = forEvents
            ? ChatRealtime(endpoint: endpoint, token: token, event: group) { [weak self] in self?.refreshSoon(group) }
            : ChatRealtime(endpoint: endpoint, token: token, group: group, direct: isDirect(group)) { [weak self] in self?.refreshSoon(group) }
        chatLive = live
        live.start()
    }

    /// Plusieurs changements dans la même seconde (message + réaction…) : une seule relecture.
    private func refreshSoon(_ group: String?) {
        refreshing?.cancel()
        refreshing = Task { [weak self] in
            try? await Task.sleep(for: .milliseconds(120))
            guard let self, !Task.isCancelled else { return }
            if let group, self.conversation?.id == group { await self.open(group) } else if group == nil { await self.loadList() }
        }
    }

    func close() {
        chatLive?.stop()
        chatLive = nil
        conversation = nil
        pending = []
        older = []
        hasOlder = true
        jumpTo = nil
    }

    /// Texte : affiché tout de suite, envoyé en un seul appel (citations calculées ici). Photo : envoyée d'abord.
    /// announce : interrupteur 📣 de l'organisation d'un événement (vaut « @annonce »).
    func send(_ text: String, replyTo: String?, photo: Data? = nil, announce: Bool = false) async -> Bool {
        guard let chat = conversation else { return false }
        let body = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !body.isEmpty || photo != nil else { return false }
        let id = UUID().uuidString.lowercased()
        if photo == nil { show(Self.draft(id: id, body: body, replyTo: replyTo, in: chat, announce: announce)) } else { sending = true }
        defer { sending = false }
        var sent = false
        await run { token in
            if forEvents {
                let path = try await photo.asyncMap { try await api.uploadEventChatFile(token: token, event: chat.id, data: $0, audio: false) }
                try await api.sendEventChat(token: token, event: chat.id, body: body, replyTo: replyTo, photoPath: path,
                                            mentions: chat.mentions(in: body, me: chat.me), id: id, announcement: announce)
            } else {
                let path = try await photo.asyncMap { try await api.uploadChatPhoto(token: token, group: chat.id, jpeg: $0) }
                try await api.sendChat(token: token, group: chat.id, body: body, replyTo: replyTo, photoPath: path,
                                       mentions: chat.mentions(in: body, me: chat.me), id: id, direct: chat.isDirect)
            }
            sent = true
        }
        if !sent { drop(id) }
        await open(chat.id)
        return sent
    }

    /// Vocal : bulle affichée tout de suite (« Envoi… »), fichier envoyé puis message ; le fichier local est effacé.
    func sendVoice(_ file: URL, seconds: TimeInterval, replyTo: String?) async {
        guard let chat = conversation, let data = try? Data(contentsOf: file) else { return }
        defer { try? FileManager.default.removeItem(at: file) }
        let id = UUID().uuidString.lowercased()
        var draft = Self.draft(id: id, body: "", replyTo: replyTo, in: chat)
        draft.audioSeconds = seconds
        show(draft)
        var sent = false
        await run { token in
            if forEvents {
                let path = try await api.uploadEventChatFile(token: token, event: chat.id, data: data, audio: true)
                try await api.sendEventChat(token: token, event: chat.id, body: "", replyTo: replyTo, photoPath: nil, mentions: [],
                                            id: id, audioPath: path, audioSeconds: seconds)
            } else {
                let path = try await api.uploadChatAudio(token: token, group: chat.id, audio: data)
                try await api.sendChat(token: token, group: chat.id, body: "", replyTo: replyTo, photoPath: nil, mentions: [],
                                       id: id, audioPath: path, audioSeconds: seconds, direct: chat.isDirect)
            }
            sent = true
        }
        if !sent { drop(id) }
        await open(chat.id)
    }

    private func show(_ message: Conversation.Message) {
        pending.append(message)
        if let chat = conversation { conversation = chat.with(messages: chat.messages + [message]) }
    }

    private func drop(_ id: String) {
        pending.removeAll { $0.id == id }
        if let chat = conversation { conversation = chat.with(messages: chat.messages.filter { $0.id != id }) }
    }

    nonisolated static func draft(id: String, body: String, replyTo: String?, in chat: Conversation,
                                  announce: Bool = false) -> Conversation.Message {
        let quoted = replyTo.flatMap { r in chat.messages.first { $0.id == r } }
        let me = chat.members.first { $0.id == chat.me }
        let announced = chat.isStaff && (announce || Mentions.isAnnouncement(body))  // d'un simple membre : message normal
        return Conversation.Message(
            id: id, author: chat.me ?? "", authorName: me?.name ?? "Moi", authorPhoto: me?.photo, mine: true,
            at: ISO8601DateFormatter().string(from: Date()), edited: false, body: body, deleted: false, photo: nil,
            pinned: announced, reply: quoted.map { Conversation.Reply(name: $0.authorName, text: $0.preview) }, reactions: [],
            announcement: announced ? true : nil, pending: true)
    }

    func react(_ message: Conversation.Message, _ emoji: String) async {
        let on = !message.reactions.contains { $0.emoji == emoji && $0.mine }
        let direct = conversation?.isDirect == true
        await act { token in
            if forEvents { try await api.reactEventChat(token: token, message: message.id, emoji: emoji, on: on) }
            else { try await api.reactChat(token: token, message: message.id, emoji: emoji, on: on, direct: direct) }
        }
    }

    func pin(_ message: Conversation.Message) async {
        await setPinned(message.id, !message.pinned)
    }

    /// Retire une annonce (ou un épinglé) du bandeau : admins du groupe, d'un appui long sur le bandeau.
    func unpin(_ id: String) async {
        await setPinned(id, false)
    }

    private func setPinned(_ id: String, _ pin: Bool) async {
        let direct = conversation?.isDirect == true
        await act { token in
            if forEvents { try await api.pinEventChat(token: token, message: id, pin: pin) }
            else { try await api.pinChat(token: token, message: id, pin: pin, direct: direct) }
        }
    }

    func delete(_ message: Conversation.Message) async {
        let direct = conversation?.isDirect == true
        await act { token in
            if forEvents { try await api.deleteEventChat(token: token, message: message.id) }
            else { try await api.deleteChat(token: token, message: message.id, direct: direct) }
        }
    }

    func setNotify(_ level: ChatNotify) async {
        if forEvents { return await setLevel(ChatNotifyLevel(rawValue: level.rawValue) ?? .mentions) }
        guard let group = conversation?.id else { return }
        let direct = conversation?.isDirect == true
        await act { token in
            if forEvents { try await api.notifyEventChat(token: token, event: group, level: level) }
            else { try await api.notifyChat(token: token, group: group, level: level, direct: direct) }
        }
    }

    func setOrganizer(_ member: Conversation.Member, _ on: Bool) async {
        guard let group = conversation?.id else { return }
        await act { token in try await api.setChatOrganizer(token: token, group: group, member: member.id, on: on) }
    }

    func setEveryone(_ who: String) async {
        guard let group = conversation?.id else { return }
        await act { token in try await api.setChatEveryone(token: token, group: group, who: who) }
    }

    func setAdmin(_ member: Conversation.Member, _ on: Bool) async {
        guard let group = conversation?.id else { return }
        await act { token in try await api.setChatAdmin(token: token, group: group, member: member.id, on: on) }
    }

    // MARK: Discussion d'un événement : réglages, lecture, médias, recherche (17.11). Rien pour une discussion de groupe.

    /// Sourdine en cours (date à venir ou « toujours »).
    var isMuted: Bool { conversation?.isMuted() ?? false }
    /// Ce qui me prévient vraiment : rien en sourdine, sinon mon niveau (Mentions seulement par défaut).
    var effectiveLevel: ChatNotifyLevel { conversation?.effectiveLevel() ?? .mentions }

    /// Serveur à jour (17.11) : il donne le niveau ou les non-lus. Sinon ses routes read / older n'existent pas.
    private var modern: Bool { conversation.map { $0.level != nil || $0.unread != nil } ?? false }

    /// Tout / Mentions seulement / Rien : changé tout de suite à l'écran, remis comme avant si le serveur refuse.
    func setLevel(_ level: ChatNotifyLevel) async {
        await changePrefs({ $0.level = level }) { token, event in
            try await self.api.setEventChatLevel(token: token, event: event, level: level)
        }
    }

    /// Sourdine jusqu'à `until` ; nil = réactiver ; `.distantFuture` (ou plus de 50 ans) = toujours.
    func mute(until: Date?) async {
        let always = until.map { $0.timeIntervalSinceNow > 50 * 365 * 86_400 } ?? false
        let iso = until.map { ISO8601DateFormatter().string(from: $0) }
        await changePrefs({ $0.mutedUntil = always ? "infinity" : iso }) { token, event in
            try await self.api.muteEventChat(token: token, event: event, until: always ? "always" : iso)
        }
    }

    private func changePrefs(_ change: @escaping (inout Conversation) -> Void,
                             _ work: (String, String) async throws -> Void) async {
        guard forEvents, let chat = conversation else { return }
        let apply: (Conversation) -> Conversation = { var c = $0; change(&c); return c }
        prefsOverride = apply
        conversation = apply(chat)
        var done = false
        await run { token in
            try await work(token, chat.id)
            done = true
        }
        prefsOverride = nil
        guard conversation?.id == chat.id, var now = conversation else { return }
        if done {
            if let account = await account() { ChatsCache.save(now, account: account, name: "chat-" + chat.id) }
        } else {
            now.level = chat.level
            now.mutedUntil = chat.mutedUntil
            conversation = now
        }
    }

    /// Discussion lue : les non-lus passent à 0 tout de suite ; l'écran l'appelle quand le fil est affiché.
    func markRead() async {
        guard forEvents, modern, let chat = conversation, (chat.unread ?? 0) > 0,
              let token = await web?.accountToken() else { return }
        conversation?.unread = 0
        try? await api.readEventChat(token: token, event: chat.id)
    }

    /// Organisation de l'événement : qui peut écrire ("all" | "staff") et description ; nil = inchangé.
    func saveSettings(write: String?, description: String?) async -> Bool {
        guard forEvents, let chat = conversation else { return false }
        var saved = false
        await run { token in
            try await api.eventChatSettings(token: token, event: chat.id, write: write, description: description)
            saved = true
        }
        guard saved else { return false }
        if conversation?.id == chat.id {
            if let write { conversation?.writeMode = write }
            if let description { conversation?.description = description }
        }
        await open(chat.id)
        return true
    }

    /// Photos, vocaux et liens, les plus récents d'abord ; `before` : page suivante (date du dernier élément reçu).
    func media(before: String? = nil) async -> [ChatMediaItem] {
        guard forEvents, let event = conversation?.id else { return [] }
        var items: [ChatMediaItem] = []
        await run { token in items = try await api.eventChatMedia(token: token, event: event, before: before) }
        return items
    }

    func search(_ q: String) async -> [ChatSearchResult] {
        let query = q.trimmingCharacters(in: .whitespacesAndNewlines)
        guard forEvents, !query.isEmpty, let event = conversation?.id else { return [] }
        var results: [ChatSearchResult] = []
        await run { token in results = try await api.searchEventChat(token: token, event: event, query: query) }
        return results
    }

    /// Page précédente, ajoutée au-dessus sans doublon (l'écran garde son message de référence à l'écran).
    func loadOlder() async {
        guard forEvents, modern, hasOlder, !loadingOlder, let chat = conversation,
              let first = chat.messages.first(where: { !$0.pending }) else { return }
        loadingOlder = true
        defer { loadingOlder = false }
        var page: [Conversation.Message]?
        await run { token in page = try await api.olderEventChat(token: token, event: chat.id, before: first.id) }
        guard let page, conversation?.id == chat.id, let current = conversation else { return }
        let added = Conversation.merge(older: page, into: current.messages)
        if added.count == current.messages.count { hasOlder = false; return }
        older = Conversation.merge(older: page, into: older)
        conversation = current.with(messages: added)
    }

    /// Montre un message (résultat de recherche, épinglé) : charge les pages plus anciennes s'il le faut, puis jumpTo.
    func reveal(_ id: String) async {
        for _ in 0..<20 {
            if conversation?.messages.contains(where: { $0.id == id }) == true { break }
            let count = conversation?.messages.count
            await loadOlder()
            if !hasOlder || conversation?.messages.count == count { break }
        }
        if conversation?.messages.contains(where: { $0.id == id }) == true { jumpTo = id }
        else { notice = "Ce message n'est plus dans la discussion." }
    }

    private func act(_ work: (String) async throws -> Void) async {
        guard let group = conversation?.id else { return }
        var done = false
        await run { token in
            try await work(token)
            done = true
        }
        if done { await open(group) }
    }

    /// loading : premier chargement, l'erreur prend la place de l'écran ; sinon bandeau.
    private func run(loading: Bool = false, _ work: (String) async throws -> Void) async {
        guard let token = await web?.accountToken() else {
            error = forEvents ? "Connecte-toi pour discuter avec les invités" : "Connecte-toi pour discuter avec tes groupes"
            return
        }
        do {
            try await work(token)
            if loading { error = nil }
        } catch PartyAPIError.needsCode {
            error = "Ta connexion a expiré : reconnecte-toi dans Réglages"
        } catch is CancellationError {
            return
        } catch {
            if loading { self.error = error.localizedDescription } else { notice = error.localizedDescription }
        }
    }
}

private extension Optional {
    func asyncMap<T>(_ transform: (Wrapped) async throws -> T) async rethrows -> T? {
        guard let value = self else { return nil }
        return try await transform(value)
    }
}

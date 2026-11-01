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

    private let api: PartyAPI
    private weak var web: WebStorage?
    private var endpoint: ChatRealtime.Endpoint?
    private var listLive: ChatRealtime?
    private var chatLive: ChatRealtime?
    /// Messages envoyés pas encore confirmés : gardés en bas de la conversation jusqu'à leur retour du serveur.
    private var pending: [Conversation.Message] = []
    private var refreshing: Task<Void, Never>?

    init(api: PartyAPI, web: WebStorage?) {
        self.api = api
        self.web = web
    }

    var unread: Int { chats?.reduce(0) { $0 + $1.unread } ?? 0 }

    func loadList() async {
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

    /// Ouvre (ou relit) une conversation ; la marque comme lue si de nouveaux messages sont arrivés.
    func open(_ group: String) async {
        if conversation?.id != group {
            pending = []
            // Dernière version gardée sur le téléphone : la conversation s'affiche sans attendre le serveur.
            conversation = await account().flatMap { ChatsCache.load(Conversation.self, account: $0, name: "chat-" + group) }
        }
        await run(loading: conversation == nil) { token in
            let fresh = try await api.openChat(token: token, group: group)
            if let account = ChatsCache.account(of: token) { ChatsCache.save(fresh, account: account, name: "chat-" + group) }
            let changed = fresh.messages.last?.id != conversation?.messages.filter { !$0.pending }.last?.id || conversation == nil
            pending.removeAll { p in fresh.messages.contains { $0.id == p.id } }
            let shown = pending.isEmpty ? fresh : fresh.with(messages: fresh.messages + pending)
            if shown != conversation { conversation = shown }
            if changed && fresh.member { try? await api.readChat(token: token, group: group) }
        }
        if chatLive == nil, conversation?.id == group { await startChatLive(group) }
    }

    private func startChatLive(_ group: String) async {
        if endpoint == nil { await loadList() }
        guard let endpoint, let token = await web?.accountToken() else { return }
        let live = ChatRealtime(endpoint: endpoint, token: token, group: group) { [weak self] in self?.refreshSoon(group) }
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
    }

    /// Texte : affiché tout de suite, envoyé en un seul appel (citations calculées ici). Photo : envoyée d'abord.
    func send(_ text: String, replyTo: String?, photo: Data? = nil) async -> Bool {
        guard let chat = conversation else { return false }
        let body = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !body.isEmpty || photo != nil else { return false }
        let id = UUID().uuidString.lowercased()
        if photo == nil { show(Self.draft(id: id, body: body, replyTo: replyTo, in: chat)) } else { sending = true }
        defer { sending = false }
        var sent = false
        await run { token in
            let path = try await photo.asyncMap { try await api.uploadChatPhoto(token: token, group: chat.id, jpeg: $0) }
            try await api.sendChat(token: token, group: chat.id, body: body, replyTo: replyTo, photoPath: path,
                                   mentions: chat.mentions(in: body, me: chat.me), id: id)
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
            let path = try await api.uploadChatAudio(token: token, group: chat.id, audio: data)
            try await api.sendChat(token: token, group: chat.id, body: "", replyTo: replyTo, photoPath: nil, mentions: [],
                                   id: id, audioPath: path, audioSeconds: seconds)
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

    nonisolated static func draft(id: String, body: String, replyTo: String?, in chat: Conversation) -> Conversation.Message {
        let quoted = replyTo.flatMap { r in chat.messages.first { $0.id == r } }
        let me = chat.members.first { $0.id == chat.me }
        return Conversation.Message(
            id: id, author: chat.me ?? "", authorName: me?.name ?? "Moi", authorPhoto: me?.photo, mine: true,
            at: ISO8601DateFormatter().string(from: Date()), edited: false, body: body, deleted: false, photo: nil,
            pinned: false, reply: quoted.map { Conversation.Reply(name: $0.authorName, text: $0.preview) }, reactions: [], pending: true)
    }

    func react(_ message: Conversation.Message, _ emoji: String) async {
        let on = !message.reactions.contains { $0.emoji == emoji && $0.mine }
        await act { token in try await api.reactChat(token: token, message: message.id, emoji: emoji, on: on) }
    }

    func pin(_ message: Conversation.Message) async {
        await act { token in try await api.pinChat(token: token, message: message.id, pin: !message.pinned) }
    }

    func delete(_ message: Conversation.Message) async {
        await act { token in try await api.deleteChat(token: token, message: message.id) }
    }

    func setNotify(_ level: ChatNotify) async {
        guard let group = conversation?.id else { return }
        await act { token in try await api.notifyChat(token: token, group: group, level: level) }
    }

    func setAdmin(_ member: Conversation.Member, _ on: Bool) async {
        guard let group = conversation?.id else { return }
        await act { token in try await api.setChatAdmin(token: token, group: group, member: member.id, on: on) }
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
            error = "Connecte-toi pour discuter avec tes groupes"
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

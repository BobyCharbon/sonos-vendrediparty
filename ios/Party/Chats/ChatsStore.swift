import SwiftUI

/// Onglet Discussions natif : la liste des groupes et la conversation ouverte, rafraîchie toutes les 3 s tant
/// qu'elle est à l'écran (la liste toutes les 15 s). Chaque action relit la conversation.
@MainActor
final class ChatsStore: ObservableObject {
    static let conversationEvery: Duration = .seconds(3)
    static let listEvery: Duration = .seconds(15)

    @Published private(set) var chats: [ChatSummary]?
    @Published private(set) var conversation: Conversation?
    @Published private(set) var error: String?
    @Published private(set) var sending = false
    @Published var notice: String?
    /// Conversation à ouvrir (toucher d'une notification) : la liste la pousse dès qu'elle s'affiche.
    @Published var requested: String?

    private let api: PartyAPI
    private weak var web: WebStorage?

    init(api: PartyAPI, web: WebStorage?) {
        self.api = api
        self.web = web
    }

    var unread: Int { chats?.reduce(0) { $0 + $1.unread } ?? 0 }

    func loadList() async {
        await run(loading: chats == nil) { token in chats = try await api.chats(token: token) }
    }

    /// Ouvre (ou relit) une conversation ; la marque comme lue si de nouveaux messages sont arrivés.
    func open(_ group: String) async {
        if conversation?.id != group { conversation = nil }
        await run(loading: conversation == nil) { token in
            let fresh = try await api.openChat(token: token, group: group)
            let changed = fresh.messages.last?.id != conversation?.messages.last?.id || conversation == nil
            if fresh != conversation { conversation = fresh }
            if changed && fresh.member { try? await api.readChat(token: token, group: group) }
        }
    }

    func close() {
        conversation = nil
    }

    func send(_ text: String, replyTo: String?, photo: Data? = nil) async -> Bool {
        guard let group = conversation?.id, !sending else { return false }
        let body = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !body.isEmpty || photo != nil else { return false }
        sending = true
        defer { sending = false }
        var sent = false
        await run { token in
            let path = try await photo.asyncMap { try await api.uploadChatPhoto(token: token, group: group, jpeg: $0) }
            try await api.sendChat(token: token, group: group, body: body, replyTo: replyTo, photoPath: path)
            sent = true
        }
        if sent { await open(group) }
        return sent
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

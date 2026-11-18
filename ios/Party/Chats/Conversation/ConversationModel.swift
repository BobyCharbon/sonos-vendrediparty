import SwiftUI

/// État v2 d'une conversation ouverte, à côté de ChatsStore : demande de message, « Vu », champs ajoutés aux messages
/// (citation privée, carte de soirée), cartes des soirées, personnes en train d'écrire.
@MainActor
final class ConversationModel: ObservableObject {
    /// Statut de la conversation directe (`open_direct_chat`) : "active", "request" ou "none".
    @Published private(set) var status: String?
    @Published private(set) var seenAt: Date?
    @Published private(set) var extras: [String: MessageExtra] = [:]
    @Published private(set) var cards: [String: ChatEventCard] = [:]
    /// Personnes en train d'écrire : identifiant → surnom.
    @Published private(set) var typing: [String: String] = [:]

    private weak var store: ChatsStore?
    private var relay: ConversationRelay?
    private var chatID: String?
    private var readIDs: [String] = []
    private var needsStatus = false
    /// Dernier message d'événement marqué lu (`mark_event_chat_read`).
    private var markedRead: String??
    private var typingFor: String?
    private var typingLive: ChatRealtime?
    private var typingUntil: [String: Date] = [:]
    private var lastTyped = Date.distantPast

    static let typingShown: TimeInterval = 6
    static let typingEvery: TimeInterval = 3

    func attach(_ store: ChatsStore) {
        guard self.store == nil else { return }
        self.store = store
        relay = ConversationRelay.of(store)
    }

    var canRelay: Bool { relay != nil }

    func request(in chat: Conversation) -> MessageRequest? {
        chat.isDirect ? ConversationRules.request(status: status, messages: chat.messages) : nil
    }

    /// À chaque nouvelle version de la conversation : statut (à l'ouverture), champs v2 des nouveaux messages, « Vu ».
    func update(_ chat: Conversation) async {
        guard let relay else { return }
        if chatID != chat.id {
            stop()
            chatID = chat.id
            status = nil
            seenAt = nil
            extras = [:]
            readIDs = []
            markedRead = nil
            needsStatus = chat.isDirect
        }
        // Relecture annulée (nouvelle version arrivée entre-temps) : on reprend à la suivante.
        if needsStatus, let user = chat.userID {
            guard let opening = try? await relay.openDirect(user), chatID == chat.id else { return }
            status = opening.status
            needsStatus = false
        }
        startTyping(chat)
        let ids = chat.messages.filter { !$0.pending }.map(\.id)
        // Discussion d'un événement : « lu » dans chat_list_state (liste v2), à l'ouverture et à chaque nouveau message.
        if chat.isEvent, ids.last != markedRead {
            if (try? await relay.run("mark_event_chat_read", ["e": chat.id])) != nil, chatID == chat.id { markedRead = ids.last }
        }
        if !chat.isEvent, !ids.isEmpty, ids != readIDs {
            // Champs v2 lus avec la conversation (même réponse) ; serveur d'avant : une lecture à part.
            let fromChat = chat.extras
            let fetched = fromChat == nil ? try? await relay.extras(chat: chat.id, direct: chat.isDirect) : nil
            if let list = fromChat ?? fetched, chatID == chat.id {
                readIDs = ids
                extras = Dictionary(list.map { ($0.id, $0) }, uniquingKeysWith: { a, _ in a })
                let missing = Set(list.compactMap(\.eventID)).subtracting(cards.keys)
                if !missing.isEmpty, let found = try? await relay.eventCards(missing.sorted()) {
                    for card in found { cards[card.id] = card }
                }
            }
        }
        await refreshSeen(chat)
    }

    /// « Vu » : seulement à deux, hors demande et blocage, quand mon message est le dernier.
    func refreshSeen(_ chat: Conversation) async {
        guard let relay, chat.isDirect, request(in: chat) == nil, chat.blocked != true,
              chat.messages.last(where: { !$0.pending })?.mine == true else { return }
        let seen = try? await relay.seen(chat.id)
        if seen != seenAt { Motion.animate(Motion.smooth) { seenAt = seen } }
    }

    // MARK: Demande de message

    func accept(_ chat: Conversation) async {
        guard await perform({ try await $0.run("accept_message_request", ["chat": chat.id]) }) else { return }
        Haptics.success()
        Motion.animate(Motion.snappy) { status = "active" }
        startTyping(chat)
        await store?.open(chat.id)
    }

    func decline(_ chat: Conversation) async -> Bool {
        await perform { try await $0.run("decline_message_request", ["chat": chat.id]) }
    }

    // MARK: Messages

    func edit(_ m: Conversation.Message, to body: String, in chat: Conversation) async -> Bool {
        let text = body.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, text != m.body else { return text == m.body }
        guard let relay else { return false }
        do {
            try await relay.edit(m.id, body: text, direct: chat.isDirect)
        } catch {
            store?.notice = ConversationRules.editRefusal(error)
            return false
        }
        await store?.open(chat.id)
        return true
    }

    /// Message direct qui porte la citation d'un groupe ou d'une soirée (« Répondre en privé »).
    func send(_ text: String, quote: PrivateQuote, in chat: Conversation) async -> Bool {
        let body = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !body.isEmpty else { return false }
        let id = UUID().uuidString.lowercased()
        guard await perform({ try await $0.send(chat: chat.id, direct: true, body: body, id: id, quote: quote) }) else { return false }
        await store?.open(chat.id)
        return true
    }

    /// « Répondre en privé » : ouvre (ou crée) la conversation directe ; nil et un message si c'est impossible.
    func openPrivate(with user: String) async -> DirectOpening? {
        guard let relay else { return nil }
        do {
            let opening = try await relay.openDirect(user)
            if opening.chat == nil || opening.status == "none" {
                store?.notice = ConversationRules.refusal(opening.reason)
                return nil
            }
            return opening
        } catch {
            store?.notice = error.localizedDescription
            return nil
        }
    }

    func report(_ target: ReportTarget, reason: ReportReason, comment: String, context: Bool) async throws {
        guard let relay else { throw PartyAPIError.offline }
        try await relay.report(target, reason: reason, comment: comment, context: context)
    }

    private func perform(_ work: (ConversationRelay) async throws -> Void) async -> Bool {
        guard let relay else { return false }
        do {
            try await work(relay)
            return true
        } catch is CancellationError {
            return false
        } catch {
            store?.notice = error.localizedDescription
            return false
        }
    }

    // MARK: « écrit… »

    /// Canal « écrit… » ouvert une fois par conversation, hors demande et blocage (adresse du temps réel connue).
    private func startTyping(_ chat: Conversation) {
        guard typingFor != chat.id, let store, chat.blocked != true, request(in: chat) == nil,
              let endpoint = chat.realtime ?? ConversationRelay.endpoint(of: store) else { return }
        typingFor = chat.id
        let me = chat.me
        Task {
            guard let token = try? await relay?.token(), chatID == chat.id, typingFor == chat.id else { return }
            let live = ChatRealtime(endpoint: endpoint, token: token, typing: ConversationRules.typingChannel(chat)) { [weak self] who in
                guard let self, let user = who["user"], user != me else { return }
                self.someoneTyped(user, name: who["name"] ?? "")
            }
            typingLive = live
            live.start()
        }
    }

    private func someoneTyped(_ user: String, name: String) {
        typingUntil[user] = Date().addingTimeInterval(Self.typingShown)
        if typing[user] != name { Motion.animate(Motion.snappy) { typing[user] = name } }
        Task { [weak self] in
            try? await Task.sleep(for: .seconds(Self.typingShown + 0.1))
            guard let self, let until = self.typingUntil[user], until <= Date() else { return }
            Motion.animate(Motion.snappy) { _ = self.typing.removeValue(forKey: user) }
        }
    }

    /// J'écris : un signal toutes les 3 s au plus, jamais dans une demande ni envers une personne bloquée.
    func typed(in chat: Conversation) {
        guard let typingLive, request(in: chat) == nil, chat.blocked != true,
              Date().timeIntervalSince(lastTyped) >= Self.typingEvery, let me = chat.me else { return }
        lastTyped = Date()
        let name = chat.members.first { $0.id == me }?.name ?? ""
        typingLive.sendTyping(["user": me, "name": name])
    }

    /// Message reçu de quelqu'un : son « écrit… » s'efface aussitôt.
    func messageArrived(from user: String) {
        guard typing[user] != nil else { return }
        typingUntil[user] = nil
        Motion.animate(Motion.snappy) { _ = typing.removeValue(forKey: user) }
    }

    /// Écran fermé : plus de canal ; une réouverture relit tout.
    func stop() {
        typingLive?.stop()
        typingLive = nil
        typing = [:]
        typingUntil = [:]
        typingFor = nil
        chatID = nil
    }
}

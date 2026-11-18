import SwiftUI

/// Discussions v2 (18.11.2026) — ce que la conversation ajoute : modifier (15 min), carte de soirée, répondre en privé,
/// « Vu », « écrit… », demandes de message, signalement avec les 10 messages précédents. Tout passe par le relais du
/// serveur `POST /api/account/chats/rpc` (app/chat_rpc.py, liste blanche) et `/chats/send` étendu (event_id, quote).

// MARK: - Routes données par l'app

/// Mini-profil (I2 : `MiniProfileSheet(userID:)`) et fiche d'un événement (page web). Branchées par l'app
/// (`.environment(\.conversationRoutes, …)` dans PartyApp) ; absentes : la fiche native du membre, et pas de « Voir ».
struct ConversationRoutes {
    var miniProfile: (@MainActor (_ userID: String) -> AnyView)?
    var openEvent: (@MainActor (_ eventID: String) -> Void)?
}

private struct ConversationRoutesKey: EnvironmentKey {
    static let defaultValue = ConversationRoutes()
}

extension EnvironmentValues {
    var conversationRoutes: ConversationRoutes {
        get { self[ConversationRoutesKey.self] }
        set { self[ConversationRoutesKey.self] = newValue }
    }
}

/// Identifiant de personne présentable en feuille (`.sheet(item:)`).
struct PersonRef: Identifiable, Equatable {
    let id: String
}

// MARK: - Données

/// Citation d'un message de groupe ou d'événement jointe à un message direct (« Répondre en privé »).
struct PrivateQuote: Codable, Equatable {
    let from: String
    let title: String
    let author: String
    let excerpt: String

    var json: [String: Any] { ["from": from, "title": title, "author": author, "excerpt": excerpt] }
}

/// Carte d'une soirée dans un message (`chat_event_cards`, seulement les événements que je peux voir).
struct ChatEventCard: Codable, Equatable, Identifiable {
    let id: String
    let title: String
    let start: String?
    let place: String?
    let cover: String?
    let going: Int?
    let mine: String?

    var date: Date? { ChatDates.parse(start) }
}

/// Réponse de `open_direct_chat` : la conversation et son statut d'après `chat_link`.
struct DirectOpening: Decodable, Equatable {
    let chat: String?
    let status: String
    let reason: String?
}

/// Ce que `/chats/open` renvoie en plus par message (event_id, quote) : lu à part tant que le modèle commun ne l'a pas.
struct MessageExtra: Codable, Equatable {
    let id: String
    let eventID: String?
    let quote: PrivateQuote?
    /// Copie de la carte gardée avec le message (`event_card`) : montrée si `chat_event_cards` ne la rend pas.
    let eventCard: ChatEventCard?

    enum CodingKeys: String, CodingKey { case id, quote, eventID = "event_id", eventCard = "event_card" }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        eventID = try? c.decodeIfPresent(String.self, forKey: .eventID)
        quote = try? c.decodeIfPresent(PrivateQuote.self, forKey: .quote)
        eventCard = try? c.decodeIfPresent(ChatEventCard.self, forKey: .eventCard)
    }

    init(id: String, eventID: String?, quote: PrivateQuote?, eventCard: ChatEventCard? = nil) {
        self.id = id
        self.eventID = eventID
        self.quote = quote
        self.eventCard = eventCard
    }
}

/// Demande de message (conversation directe en statut « request ») vue de mon côté.
enum MessageRequest: Equatable {
    /// On m'écrit : Accepter / Supprimer / Bloquer / Signaler ; je ne peux pas écrire avant d'accepter.
    case incoming
    /// J'écris : un seul message, texte seul ; puis « Demande envoyée », saisie fermée.
    case outgoing
}

// MARK: - Règles (testées dans ConversationV2Tests)

enum ConversationRules {
    /// Modifier un message : 15 minutes après l'envoi au plus (la base refuse au-delà : `edit_window`).
    static let editWindow: TimeInterval = 15 * 60
    static let excerptMax = 140

    /// « Modifier » : mon message texte, envoyé, pas supprimé, dans les 15 minutes ; message direct ou de groupe
    /// (pas d'une discussion d'événement), jamais une annonce.
    static func canEdit(_ m: Conversation.Message, isEvent: Bool, now: Date = Date()) -> Bool {
        guard m.mine, !m.deleted, !m.pending, !m.body.isEmpty, !isEvent, !m.isAnnouncement, let at = m.date else { return false }
        return now.timeIntervalSince(at) <= editWindow
    }

    /// Citation de « Répondre en privé » : d'où (groupe / soirée), son nom, l'auteur, un extrait de 140 caractères au plus.
    static func quote(of m: Conversation.Message, in chat: Conversation) -> PrivateQuote {
        let text = m.preview.trimmingCharacters(in: .whitespacesAndNewlines)
        let excerpt = text.count > excerptMax ? String(text.prefix(excerptMax - 1)) + "…" : text
        return PrivateQuote(from: chat.isEvent ? "event" : "group", title: chat.name, author: m.authorName, excerpt: excerpt)
    }

    /// Statut « request » → de quel côté je suis : j'ai écrit le premier message (ou rien encore) = je demande.
    static func request(status: String?, messages: [Conversation.Message]) -> MessageRequest? {
        guard status == "request" else { return nil }
        return messages.first(where: { !$0.pending })?.mine == false ? .incoming : .outgoing
    }

    /// « Vu » sous mon dernier message seulement, quand l'autre l'a lu (direct_seen ≥ son heure).
    static func seen(_ m: Conversation.Message, lastMine: String?, seenAt: Date?) -> Bool {
        guard m.mine, !m.pending, m.id == lastMine, let seenAt, let at = m.date else { return false }
        return seenAt >= at
    }

    /// Bandeau « écrit… » : « Léa écrit… », « Léa et Tom écrivent… », « 3 personnes écrivent… ».
    static func typingLabel(_ names: [String], direct: Bool) -> String? {
        let names = names.filter { !$0.isEmpty }
        if names.isEmpty { return nil }
        if direct { return "écrit…" }
        switch names.count {
        case 1: return "\(names[0]) écrit…"
        case 2: return "\(names[0]) et \(names[1]) écrivent…"
        default: return "\(names.count) personnes écrivent…"
        }
    }

    /// Pourquoi on ne peut pas écrire (raison d'`open_direct_chat`).
    static func refusal(_ reason: String?) -> String {
        switch reason {
        case "blocked": return "Tu ne peux pas écrire à cette personne."
        case "inactive": return "Ce compte n'est plus actif."
        case "profile_required": return "Complète ton profil (Réglages › Mon profil) pour écrire."
        case "terms_required": return "Accepte les conditions d'utilisation de Party pour écrire."
        case "limit": return "Tu as envoyé beaucoup de demandes : réessaie demain."
        default: return "Cette personne ne reçoit pas de demandes de message."
        }
    }

    /// Refus de la base traduit pour l'écran (`edit_window:` après 15 minutes).
    static func editRefusal(_ error: Error) -> String {
        let text = error.localizedDescription
        return text.contains("edit_window") ? "Ce message ne peut plus être modifié : 15 minutes après l'envoi au plus." : text
    }

    /// Canal « écrit… » partagé avec la page web.
    static func typingChannel(_ chat: Conversation) -> String {
        "typing:\(chat.isEvent ? "event" : chat.isDirect ? "direct" : "group"):\(chat.id)"
    }

    /// « Répondre en privé » attend que la conversation directe s'ouvre : la citation est gardée pour la personne visée.
    @MainActor static var pendingQuotes: [String: PrivateQuote] = [:]
}

// MARK: - Relais

/// Appels de la conversation v2 avec la session du compte (celle de ChatsStore).
@MainActor
final class ConversationRelay {
    let api: PartyAPI
    private weak var web: WebStorage?

    init(api: PartyAPI, web: WebStorage?) {
        self.api = api
        self.web = web
    }

    /// La session et le temps réel de la liste viennent de ChatsStore, qui les garde pour lui (fichier d'I1) : lus par
    /// réflexion en attendant qu'il les expose (intégration : remplacer par `store.api` / `store.web`).
    static func of(_ store: ChatsStore) -> ConversationRelay? {
        var api: PartyAPI?
        var web: WebStorage?
        for child in Mirror(reflecting: store).children {
            if child.label == "api" { api = child.value as? PartyAPI }
            if child.label == "web" { web = unwrap(child.value) as? WebStorage }
        }
        return api.map { ConversationRelay(api: $0, web: web) }
    }

    /// Adresse du temps réel connue de ChatsStore (liste ouverte au moins une fois).
    static func endpoint(of store: ChatsStore) -> ChatRealtime.Endpoint? {
        Mirror(reflecting: store).children.first { $0.label == "endpoint" }.flatMap { unwrap($0.value) as? ChatRealtime.Endpoint }
    }

    private static func unwrap(_ value: Any) -> Any? {
        let m = Mirror(reflecting: value)
        guard m.displayStyle == .optional else { return value }
        return m.children.first?.value
    }

    func token() async throws -> String {
        guard let token = await web?.accountToken() else { throw PartyAPIError.server("Connecte-toi pour discuter.") }
        return token
    }

    private struct Reply<T: Decodable>: Decodable { let result: T }

    /// Fonction de la base via le relais ; la réponse (« result ») décodée en T.
    func call<T: Decodable>(_ fn: String, _ args: [String: Any] = [:], as: T.Type = T.self) async throws -> T {
        let reply: Reply<T> = try await api.postDecoding("/api/account/chats/rpc", body: ["token": try await token(), "fn": fn, "args": args])
        return reply.result
    }

    /// Fonction sans réponse utile (accepter, modifier…).
    func run(_ fn: String, _ args: [String: Any] = [:]) async throws {
        try await api.post("/api/account/chats/rpc", body: ["token": try await token(), "fn": fn, "args": args])
    }

    func openDirect(_ target: String) async throws -> DirectOpening {
        try await call("open_direct_chat", ["target": target])
    }

    /// Heure où l'autre a lu, ou nil (confirmations coupées d'un côté, rien lu, demande, blocage).
    func seen(_ chat: String) async throws -> Date? {
        struct Seen: Decodable { let result: String? }
        let reply: Seen = try await api.postDecoding("/api/account/chats/rpc",
                                                     body: ["token": try await token(), "fn": "direct_seen", "args": ["chat": chat]])
        return ChatDates.parse(reply.result)
    }

    func eventCards(_ ids: [String]) async throws -> [ChatEventCard] {
        try await call("chat_event_cards", ["ids": ids])
    }

    func edit(_ message: String, body: String, direct: Bool) async throws {
        try await run(direct ? "edit_direct_message" : "edit_group_message", ["msg": message, "new_body": body])
    }

    /// Message avec une citation privée ou une carte de soirée (`/chats/send` étendu).
    func send(chat: String, direct: Bool, body: String, id: String, quote: PrivateQuote?, eventID: String? = nil) async throws {
        var payload: [String: Any] = ["token": try await token(), "group_id": chat, "body": body, "mentions": [String](),
                                      "id": id, "direct": direct]
        if let quote { payload["quote"] = quote.json }
        if let eventID { payload["event_id"] = eventID }
        try await api.post("/api/account/chats/send", body: payload)
    }

    /// Champs ajoutés par message (event_id, quote) : la même lecture que ChatsStore, décodée à part.
    func extras(chat: String, direct: Bool) async throws -> [MessageExtra] {
        struct Open: Decodable { let messages: [MessageExtra] }
        let open: Open = try await api.postDecoding("/api/account/chats/open",
                                                    body: ["token": try await token(), "group_id": chat, "direct": direct])
        return open.messages
    }

    /// Signaler un message ; context : copie des 10 messages précédents jointe au signalement (case décochée par défaut).
    func report(_ target: ReportTarget, reason: ReportReason, comment: String, context: Bool) async throws {
        try await api.post("/api/account/moderation/report", body: [
            "token": try await token(), "kind": target.kind.rawValue, "target": target.id,
            "reason": reason.rawValue, "comment": comment, "context": context,
        ])
    }
}

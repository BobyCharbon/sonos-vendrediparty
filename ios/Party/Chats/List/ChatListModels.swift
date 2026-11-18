import Foundation

// MARK: - Discussions v2 : liste (chat_list), filtres, textes, personnes, recherche, relais iPhone

/// Filtres de la liste (puces sous la recherche).
enum ChatFilter: String, CaseIterable, Identifiable {
    case all, unread, people, groups, events

    var id: String { rawValue }

    var label: String {
        switch self {
        case .all: return "Tout"
        case .unread: return "Non lus"
        case .people: return "Personnes"
        case .groups: return "Groupes"
        case .events: return "Soirées"
        }
    }

    func matches(_ chat: ChatSummary) -> Bool {
        switch self {
        case .all: return true
        case .unread: return chat.needsReading
        case .people: return chat.kind == .direct
        case .groups: return chat.kind == .group
        case .events: return chat.kind == .event
        }
    }
}

/// Règles de la liste, sans écran (testées dans ChatsListTests).
enum ChatListLogic {
    /// Épinglées (la plus récemment épinglée d'abord), puis le dernier message le plus récent.
    static func sorted(_ chats: [ChatSummary]) -> [ChatSummary] {
        chats.enumerated().sorted { a, b in
            let (x, y) = (a.element, b.element)
            if x.pinned != y.pinned { return x.pinned }
            if x.pinned, let px = ChatDates.parse(x.pinnedAt), let py = ChatDates.parse(y.pinnedAt), px != py { return px > py }
            let lx = ChatDates.parse(x.lastAt), ly = ChatDates.parse(y.lastAt)
            if lx != ly { return (lx ?? .distantPast) > (ly ?? .distantPast) }
            return a.offset < b.offset  // stable : l'ordre du serveur
        }.map(\.element)
    }

    /// La liste principale : ni archivées, ni demandes reçues (écrans à part).
    static func main(_ chats: [ChatSummary]) -> [ChatSummary] {
        sorted(chats.filter { !$0.archived && !$0.incomingRequest })
    }

    static func pinned(_ chats: [ChatSummary], filter: ChatFilter) -> [ChatSummary] {
        main(chats).filter { $0.pinned && filter.matches($0) }
    }

    static func rows(_ chats: [ChatSummary], filter: ChatFilter) -> [ChatSummary] {
        main(chats).filter { !$0.pinned && filter.matches($0) }
    }

    /// Demandes de message reçues, la plus récente en haut.
    static func requests(_ chats: [ChatSummary]) -> [ChatSummary] {
        sorted(chats.filter(\.incomingRequest))
    }

    static func archived(_ chats: [ChatSummary]) -> [ChatSummary] {
        sorted(chats.filter { $0.archived && !$0.incomingRequest })
    }

    /// Puce « Non lus » : nombre de discussions à lire (pas de messages).
    static func unreadChats(_ chats: [ChatSummary]) -> Int {
        main(chats).filter(\.needsReading).count
    }

    /// Pastille de l'onglet (même règle que `chat_badge`) : non lus hors archivées et hors sourdine, plus 1 par
    /// demande reçue.
    static func badge(_ chats: [ChatSummary], now: Date = Date()) -> Int {
        chats.reduce(0) { total, chat in
            if chat.incomingRequest { return total + 1 }
            if chat.archived || chat.isMuted(now: now) { return total }
            return total + chat.unread
        }
    }

    /// Recherche « Discussions » : titre, sans accents ni majuscules.
    static func matching(_ chats: [ChatSummary], query: String) -> [ChatSummary] {
        let q = Mentions.fold(query.trimmingCharacters(in: .whitespaces))
        guard !q.isEmpty else { return [] }
        return sorted(chats.filter { !$0.incomingRequest && Mentions.fold($0.name).contains(q) })
    }

    /// Sourdine « Toujours » (set_chat_state muted_until = 'infinity').
    static let muteForever = "infinity"

    /// Fin d'une sourdine limitée (ISO), à partir de maintenant ; nil pour « Toujours ».
    static func muteEnd(_ span: ChatMuteSpan, now: Date = Date()) -> String? {
        guard let seconds = span.seconds else { return nil }
        return ISO8601DateFormatter().string(from: now.addingTimeInterval(seconds))
    }
}

/// Sourdine d'une discussion depuis la liste (glisser, appui long).
enum ChatMuteSpan: String, CaseIterable, Identifiable {
    case hour, eightHours, week, always

    var id: String { rawValue }

    var label: String {
        switch self {
        case .hour: return "1 heure"
        case .eightHours: return "8 heures"
        case .week: return "1 semaine"
        case .always: return "Toujours"
        }
    }

    /// nil : toujours (muted_until = 'infinity').
    var seconds: TimeInterval? {
        switch self {
        case .hour: return 3600
        case .eightHours: return 8 * 3600
        case .week: return 7 * 24 * 3600
        case .always: return nil
        }
    }
}

/// Textes de la liste.
enum ChatListText {
    private static let locale = Locale(identifier: "fr_CH")

    private static func formatter(_ format: String, _ calendar: Calendar) -> DateFormatter {
        let f = DateFormatter()
        f.locale = locale
        f.calendar = calendar
        f.timeZone = calendar.timeZone
        f.dateFormat = format
        return f
    }

    /// Aperçu du dernier message : « Toi : … », « Léa : … » (groupe, soirée), photo, vocal, carte de soirée, supprimé.
    static func preview(of last: ChatLast, kind: ChatKind) -> String {
        let text = (last.text ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let body: String
        switch last.type {
        case "deleted": return "Message supprimé"
        case "photo": body = text.isEmpty ? "📷 Photo" : "📷 " + text
        case "audio": body = "🎤 Message vocal"
        case "event": body = "📅 " + (text.isEmpty ? "Une soirée" : text)
        default: body = text
        }
        if last.fromMe { return "Toi : " + body }
        if kind != .direct, let author = last.author?.trimmingCharacters(in: .whitespaces), !author.isEmpty {
            return author + " : " + body
        }
        return body
    }

    /// Deuxième ligne d'une ligne de la liste.
    static func subtitle(_ chat: ChatSummary) -> String {
        if chat.outgoingRequest { return "Demande envoyée" }
        if chat.blocked { return "Tu as bloqué cette personne" }
        return chat.last ?? "Aucun message pour l'instant"
    }

    /// « 21:48 » aujourd'hui, « Hier », le jour de la semaine (« Lun. ») cette semaine, sinon « 28.10 » (« 28.10.25 »
    /// une autre année), comme Messages et WhatsApp.
    static func time(_ value: String?, now: Date = Date(), calendar: Calendar = .current) -> String {
        guard let date = ChatDates.parse(value) else { return "" }
        if calendar.isDate(date, inSameDayAs: now) { return formatter("HH:mm", calendar).string(from: date) }
        let today = calendar.startOfDay(for: now)
        let day = calendar.startOfDay(for: date)
        let days = calendar.dateComponents([.day], from: day, to: today).day ?? 0
        if days == 1 { return "Hier" }
        if days > 1 && days < 7 {
            let name = formatter("EEE", calendar).string(from: date)
            return name.prefix(1).uppercased() + name.dropFirst()
        }
        let sameYear = calendar.component(.year, from: date) == calendar.component(.year, from: now)
        return formatter(sameYear ? "dd.MM" : "dd.MM.yy", calendar).string(from: date)
    }

    /// Tuile de soirée : « VEN. » et « 21 ».
    static func weekdayShort(_ date: Date) -> String { formatter("EEE", .current).string(from: date).uppercased() }
    static func dayNumber(_ date: Date) -> String { formatter("d", .current).string(from: date) }

    /// Lecture VoiceOver d'une ligne : sorte, nom, état, dernier message.
    static func accessibility(_ chat: ChatSummary, now: Date = Date()) -> String {
        var parts: [String] = []
        switch chat.kind {
        case .direct: parts.append("Message direct, \(chat.name)")
        case .group: parts.append("Groupe, \(chat.name)")
        case .event: parts.append("Soirée, \(chat.name)")
        }
        if chat.pinned { parts.append("épinglée") }
        if chat.unread > 0 { parts.append(chat.unread == 1 ? "1 non lu" : "\(chat.unread) non lus") }
        else if chat.markedUnread { parts.append("marquée non lue") }
        if chat.mention { parts.append("on te cite") }
        if chat.isMuted(now: now) { parts.append("en sourdine") }
        if chat.seenByOther == true { parts.append("vu") }
        parts.append(subtitle(chat))
        let time = time(chat.lastAt, now: now)
        if !time.isEmpty { parts.append(time) }
        return parts.joined(separator: ", ")
    }
}

// MARK: - Personnes, recherche, demandes (contrat §4, §8)

/// La personne (ChatPerson) et les suggestions (PeopleSuggestions) sont dans People/PeopleAPI.swift.
typealias ChatPeopleSuggestions = PeopleSuggestions

extension ChatPerson {
    var firstName: String { name.split(separator: " ").first.map(String.init) ?? name }

    /// Sous-titre : la soirée ou le groupe en commun, sinon « Déjà vu 3 fois ».
    var detail: String? {
        if let sub, !sub.isEmpty { return sub }
        return ChatPerson.metText(metCount ?? 0)
    }

    static func metText(_ n: Int) -> String? {
        n <= 0 ? nil : n == 1 ? "Déjà vu 1 fois" : "Déjà vu \(n) fois"
    }
}

/// Un message trouvé (chat_search) : seulement dans mes conversations.
struct ChatMessageHit: Decodable, Equatable, Identifiable {
    let kind: ChatKind
    let chatID: String
    let title: String
    let messageID: String
    let excerpt: String
    let at: String?

    var id: String { messageID }

    enum CodingKeys: String, CodingKey { case kind, title, excerpt, at, chatID = "id", messageID = "message_id" }
}

/// open_direct_chat : la conversation (créée au besoin), active ou demande ; none + raison si on ne peut pas écrire.
struct ChatOpenResult: Decodable, Equatable {
    let chat: String?
    let status: String
    var reason: String?

    /// Raison du refus, dite simplement.
    var refusal: String {
        switch reason {
        case "blocked": return "Tu ne peux pas écrire à cette personne."
        case "inactive": return "Ce compte n'est plus actif."
        case "profile_required": return "Complète ton profil (prénom, nom, surnom) pour écrire."
        case "terms_required": return "Accepte les conditions d'utilisation de Party pour écrire."
        case "closed": return "Cette personne ne reçoit pas de demandes de message."
        case "limit": return "Trop de demandes envoyées : réessaie demain."
        default: return "Tu ne peux pas écrire à cette personne pour l'instant."
        }
    }
}

/// Mini-profil d'une demande (member_mini, sous-ensemble) : qui veut t'écrire.
struct ChatRequester: Decodable, Equatable {
    let id: String
    let name: String
    var nickname: String?
    var photo: String?
    var since: String?
    var metCount = 0
    var groupsCount = 0
    var eventsCount = 0

    enum CodingKeys: String, CodingKey {
        case id, name, nickname, photo, since
        case metCount = "met_count", groupsCount = "groups_count", eventsCount = "events_count"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        name = (try? c.decodeIfPresent(String.self, forKey: .name)) ?? nil ?? ""
        nickname = try? c.decodeIfPresent(String.self, forKey: .nickname)
        photo = try? c.decodeIfPresent(String.self, forKey: .photo)
        since = try? c.decodeIfPresent(String.self, forKey: .since)
        metCount = ((try? c.decodeIfPresent(Int.self, forKey: .metCount)) ?? nil) ?? 0
        groupsCount = ((try? c.decodeIfPresent(Int.self, forKey: .groupsCount)) ?? nil) ?? 0
        eventsCount = ((try? c.decodeIfPresent(Int.self, forKey: .eventsCount)) ?? nil) ?? 0
    }

    /// « Jamais rencontré · 2 groupes en commun · Sur Party depuis nov. 2026 ».
    var facts: [String] {
        var out = [ChatPerson.metText(metCount) ?? "Jamais rencontré"]
        if groupsCount > 0 { out.append(groupsCount == 1 ? "1 groupe en commun" : "\(groupsCount) groupes en commun") }
        if eventsCount > 0 { out.append(eventsCount == 1 ? "1 soirée à venir ensemble" : "\(eventsCount) soirées à venir ensemble") }
        if let date = ChatDates.parse(since) {
            let f = DateFormatter()
            f.locale = Locale(identifier: "fr_CH")
            f.dateFormat = "MMMM yyyy"
            out.append("Sur Party depuis " + f.string(from: date))
        }
        return out
    }
}

// MARK: - Relais iPhone : POST /api/account/chats/rpc {"fn", "args"} (app/chat_rpc.py, contrat §6)

private struct ChatRPCReply<T: Decodable>: Decodable { let result: T }

extension PartyAPI {
    /// Fonction de la base relayée par le serveur (liste blanche) ; la réponse (« result ») décodée en T.
    func chatsRPC<T: Decodable>(token: String, fn: String, args: [String: Any] = [:]) async throws -> T {
        let reply: ChatRPCReply<T> = try await postDecoding("/api/account/chats/rpc", body: ["token": token, "fn": fn, "args": args])
        return reply.result
    }

    /// Appel sans réponse utile (épingler, archiver, accepter…).
    func chatsRPCRun(token: String, fn: String, args: [String: Any] = [:]) async throws {
        try await post("/api/account/chats/rpc", body: ["token": token, "fn": fn, "args": args])
    }
}

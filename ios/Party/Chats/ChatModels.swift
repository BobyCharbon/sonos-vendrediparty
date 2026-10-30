import UIKit

/// Discussions de groupe (avis n°10), relayées par le serveur (app/group_chats.py) avec la session du compte.
enum ChatNotify: String, Codable, CaseIterable, Identifiable {
    case all, mentions, none
    var id: String { rawValue }
    var label: String { self == .all ? "Tout" : self == .mentions ? "Mentions" : "Rien" }
    var hint: String {
        switch self {
        case .all: return "Une notification pour chaque message du groupe."
        case .mentions: return "Seulement quand on te cite (@surnom), qu'on te répond ou qu'un admin écrit @tout."
        case .none: return "Aucune notification de ce groupe, même citée."
        }
    }
}

/// Une ligne de la liste (POST /api/account/chats) : la plus récente en haut, comme WhatsApp.
struct ChatSummary: Decodable, Equatable, Identifiable {
    let id: String
    let name: String
    let member: Bool
    let notify: ChatNotify
    let last: String?
    let lastAt: String?
    let unread: Int

    enum CodingKeys: String, CodingKey { case id, name, member, notify, last, unread, lastAt = "last_at" }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        name = try c.decode(String.self, forKey: .name)
        member = try c.decodeIfPresent(Bool.self, forKey: .member) ?? false
        notify = (try? c.decode(ChatNotify.self, forKey: .notify)) ?? .mentions
        last = try c.decodeIfPresent(String.self, forKey: .last)
        lastAt = try c.decodeIfPresent(String.self, forKey: .lastAt)
        unread = try c.decodeIfPresent(Int.self, forKey: .unread) ?? 0
    }
}

/// Une conversation (POST /api/account/chats/open) : messages du plus ancien au plus récent.
struct Conversation: Decodable, Equatable {
    struct Reaction: Decodable, Equatable, Hashable {
        let emoji: String
        let count: Int
        let mine: Bool
    }

    struct Reply: Decodable, Equatable {
        let name: String
        let text: String
    }

    struct Message: Decodable, Equatable, Identifiable {
        let id: String
        let author: String
        let authorName: String
        let authorPhoto: String?
        let mine: Bool
        let at: String
        let edited: Bool
        let body: String
        let deleted: Bool
        let photo: String?
        let pinned: Bool
        let reply: Reply?
        let reactions: [Reaction]

        enum CodingKeys: String, CodingKey {
            case id, author, mine, at, edited, body, deleted, photo, pinned, reply, reactions
            case authorName = "author_name", authorPhoto = "author_photo"
        }

        var preview: String { body.isEmpty ? "📷 Photo" : body }
        var date: Date? { ChatDates.parse(at) }
    }

    struct Member: Decodable, Equatable, Identifiable {
        let id: String
        let name: String
        let photo: String?
        let admin: Bool
        let creator: Bool
        /// Numéro montré dans ce groupe (« +41790000001 ») : un toucher appelle.
        var phone: String? = nil

        /// Lien d'appel, seulement pour un numéro valide (chiffres, avec ou sans +).
        var call: URL? {
            guard let phone, phone.range(of: "^\\+?[0-9]{6,15}$", options: .regularExpression) != nil else { return nil }
            return URL(string: "tel:\(phone)")
        }
    }

    let id: String
    let name: String
    let member: Bool
    let admin: Bool
    let notify: ChatNotify
    let canNameAdmins: Bool
    let reactions: [String]
    let members: [Member]
    let messages: [Message]

    enum CodingKeys: String, CodingKey {
        case id, name, member, admin, notify, reactions, members, messages
        case canNameAdmins = "can_name_admins"
    }

    /// Dernier message épinglé : affiché en bandeau en haut de la conversation.
    var pinned: Message? { messages.last { $0.pinned } }
}

enum ChatDates {
    private static let iso: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()
    private static let plain = ISO8601DateFormatter()

    static func parse(_ value: String?) -> Date? {
        guard let value else { return nil }
        return iso.date(from: value) ?? plain.date(from: value)
    }

    /// « 14:05 » aujourd'hui, « hier », sinon « 28.10 », comme la liste de WhatsApp.
    static func short(_ value: String?, now: Date = Date()) -> String {
        guard let date = parse(value) else { return "" }
        let calendar = Calendar.current
        if calendar.isDate(date, inSameDayAs: now) { return date.formatted(date: .omitted, time: .shortened) }
        if let yesterday = calendar.date(byAdding: .day, value: -1, to: now), calendar.isDate(date, inSameDayAs: yesterday) { return "hier" }
        return date.formatted(.dateTime.day(.twoDigits).month(.twoDigits))
    }
}

/// Photo envoyée : 1600 px au plus, JPEG, comme la version web (lib/chats.ts).
enum ChatPhoto {
    static let maxSide: CGFloat = 1600

    static func jpeg(from image: UIImage) -> Data? {
        let scale = min(1, maxSide / max(image.size.width, image.size.height))
        let size = CGSize(width: (image.size.width * scale).rounded(), height: (image.size.height * scale).rounded())
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        let rendered = UIGraphicsImageRenderer(size: size, format: format).image { _ in image.draw(in: CGRect(origin: .zero, size: size)) }
        return rendered.jpegData(compressionQuality: 0.82)
    }
}

private struct ChatList: Decodable { let chats: [ChatSummary] }
private struct PhotoPath: Decodable { let path: String }

extension PartyAPI {
    func chats(token: String) async throws -> [ChatSummary] {
        let list: ChatList = try await postDecoding("/api/account/chats", body: ["token": token])
        return list.chats
    }

    func openChat(token: String, group: String) async throws -> Conversation {
        try await postDecoding("/api/account/chats/open", body: ["token": token, "group_id": group])
    }

    func sendChat(token: String, group: String, body: String, replyTo: String?, photoPath: String?) async throws {
        var payload: [String: Any] = ["token": token, "group_id": group, "body": body]
        if let replyTo { payload["reply_to"] = replyTo }
        if let photoPath { payload["photo_path"] = photoPath }
        try await post("/api/account/chats/send", body: payload)
    }

    func uploadChatPhoto(token: String, group: String, jpeg: Data) async throws -> String {
        let r: PhotoPath = try await postDecoding("/api/account/chats/photo",
                                                  body: ["token": token, "group_id": group, "photo": jpeg.base64EncodedString()])
        return r.path
    }

    func reactChat(token: String, message: String, emoji: String, on: Bool) async throws {
        try await post("/api/account/chats/react", body: ["token": token, "id": message, "emoji": emoji, "on": on])
    }

    func pinChat(token: String, message: String, pin: Bool) async throws {
        try await post("/api/account/chats/pin", body: ["token": token, "id": message, "pin": pin])
    }

    func deleteChat(token: String, message: String) async throws {
        try await post("/api/account/chats/delete", body: ["token": token, "id": message])
    }

    func notifyChat(token: String, group: String, level: ChatNotify) async throws {
        try await post("/api/account/chats/notify", body: ["token": token, "group_id": group, "level": level.rawValue])
    }

    func setChatAdmin(token: String, group: String, member: String, on: Bool) async throws {
        try await post("/api/account/chats/admin", body: ["token": token, "group_id": group, "user_id": member, "on": on])
    }

    func readChat(token: String, group: String) async throws {
        try await post("/api/account/chats/read", body: ["token": token, "group_id": group])
    }
}

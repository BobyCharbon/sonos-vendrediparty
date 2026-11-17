import SwiftUI
import UIKit

/// Discussions de groupe (avis n°10), relayées par le serveur (app/group_chats.py) avec la session du compte.
enum ChatNotify: String, Codable, CaseIterable, Identifiable {
    case all, mentions, none
    var id: String { rawValue }
    var label: String { self == .all ? "Tout" : self == .mentions ? "Mentions" : "Rien" }
    var hint: String {
        switch self {
        case .all: return "Une notification pour chaque message du groupe."
        case .mentions: return "Seulement quand on te cite (@surnom), qu'on te répond ou que quelqu'un écrit @tout."
        case .none: return "Aucune notification de ce groupe, même citée."
        }
    }
}

/// Une ligne de la liste (POST /api/account/chats) : la plus récente en haut, comme WhatsApp.
struct ChatSummary: Codable, Equatable, Identifiable {
    let id: String
    let name: String
    let member: Bool
    let notify: ChatNotify
    let last: String?
    let lastAt: String?
    let unread: Int
    /// Message direct (conversation privée à deux, 4.11) : l'autre personne, sa photo (lien signé), bloquée par moi.
    var direct = false
    var userID: String?
    var photo: String?
    var blocked = false
    /// Groupe : son emoji et sa couleur (nouveau graphisme du 17.11, my_chats) ; absents d'un serveur plus ancien.
    var emoji: String?
    var color: String?

    enum CodingKeys: String, CodingKey {
        case id, name, member, notify, last, unread, kind, photo, blocked, emoji, color, lastAt = "last_at", userID = "user_id"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        name = try c.decode(String.self, forKey: .name)
        member = try c.decodeIfPresent(Bool.self, forKey: .member) ?? false
        notify = (try? c.decode(ChatNotify.self, forKey: .notify)) ?? .mentions
        last = try c.decodeIfPresent(String.self, forKey: .last)
        lastAt = try c.decodeIfPresent(String.self, forKey: .lastAt)
        unread = try c.decodeIfPresent(Int.self, forKey: .unread) ?? 0
        direct = (try? c.decodeIfPresent(String.self, forKey: .kind)) == "direct"
        userID = try c.decodeIfPresent(String.self, forKey: .userID)
        photo = try c.decodeIfPresent(String.self, forKey: .photo)
        blocked = try c.decodeIfPresent(Bool.self, forKey: .blocked) ?? false
        emoji = try? c.decodeIfPresent(String.self, forKey: .emoji)
        color = try? c.decodeIfPresent(String.self, forKey: .color)
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(id, forKey: .id)
        try c.encode(name, forKey: .name)
        try c.encode(member, forKey: .member)
        try c.encode(notify, forKey: .notify)
        try c.encodeIfPresent(last, forKey: .last)
        try c.encodeIfPresent(lastAt, forKey: .lastAt)
        try c.encode(unread, forKey: .unread)
        try c.encode(direct ? "direct" : "group", forKey: .kind)
        try c.encodeIfPresent(userID, forKey: .userID)
        try c.encodeIfPresent(photo, forKey: .photo)
        try c.encode(blocked, forKey: .blocked)
        try c.encodeIfPresent(emoji, forKey: .emoji)
        try c.encodeIfPresent(color, forKey: .color)
    }
}

/// Une conversation (POST /api/account/chats/open) : messages du plus ancien au plus récent.
struct Conversation: Codable, Equatable {
    struct Reaction: Codable, Equatable, Hashable {
        let emoji: String
        let count: Int
        let mine: Bool
    }

    struct Reply: Codable, Equatable {
        let name: String
        let text: String
        /// Message cité : un toucher sur la citation y remonte (absent d'un ancien serveur ou du cache) ; son auteur
        /// (couleur de son nom).
        var id: String? = nil
        var author: String? = nil
    }

    struct Message: Codable, Equatable, Identifiable {
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
            case id, author, mine, at, edited, body, deleted, photo, pinned, reply, reactions, audio, announcement
            case authorName = "author_name", authorPhoto = "author_photo", audioSeconds = "audio_seconds"
        }

        /// « @annonce » : épinglé d'office par la base, en surbrillance (absent d'un ancien serveur ou du cache : non).
        var announcement: Bool? = nil
        var isAnnouncement: Bool { announcement == true && pinned && !deleted }

        /// Message vocal : lien d'écoute (signé) et durée.
        var audio: String? = nil
        var audioSeconds: Double? = nil
        /// Affiché tout de suite à l'envoi, avant la réponse du serveur (horloge à la place de l'heure).
        var pending = false

        var preview: String { !body.isEmpty ? body : audioSeconds != nil ? "🎤 Message vocal" : "📷 Photo" }
        var date: Date? { ChatDates.parse(at) }
    }

    /// Annonce ou message épinglé du bandeau du haut (lu à part : gardé même au-delà des derniers messages).
    struct Highlight: Codable, Equatable, Identifiable {
        let id: String
        let authorName: String
        let at: String
        let text: String
        let announcement: Bool

        enum CodingKeys: String, CodingKey { case id, at, text, announcement, authorName = "author_name" }
    }

    struct Member: Codable, Equatable, Identifiable {
        let id: String
        let name: String
        let photo: String?
        let admin: Bool
        let creator: Bool
        /// Organisateur du groupe : fait des annonces et les retire (absent d'un ancien serveur : non).
        var organizer: Bool? = nil
        /// Numéro montré dans ce groupe (« +41790000001 ») : un toucher appelle.
        var phone: String? = nil
        /// Discussion d'un événement : sa réponse (yes, maybe, no ; nil sans réponse) ; invité sans réponse (vu par
        /// l'organisation seulement).
        var rsvp: String? = nil
        var invited: Bool? = nil

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
    /// Mon identifiant de compte (messages « à moi » affichés tout de suite).
    var me: String? = nil
    let reactions: [String]
    let members: [Member]
    let messages: [Message]
    /// Annonces et messages épinglés, du plus ancien au plus récent (absent d'un ancien serveur).
    var highlights: [Highlight]? = nil
    /// Je suis organisateur (ou admin) du groupe : annonces.
    var organizer: Bool? = nil
    /// Qui peut écrire @tout : "all" (tous les membres) ou "staff" (admins et organisateurs).
    var everyone: String? = nil
    /// Citation spéciale (discussion d'un événement, organisation seulement) : @toutlemonde, @present, @annonce.
    struct Tag: Codable, Equatable {
        let tag: String
        let hint: String
    }

    /// Message direct (conversation privée à deux) : l'autre personne, sa photo, bloquée par moi (absent : un groupe).
    var direct: Bool? = nil
    var userID: String? = nil
    var photo: String? = nil
    var blocked: Bool? = nil
    /// Discussion d'un événement (app/event_chats.py) : citations spéciales permises (vide : aucune).
    var event: Bool? = nil
    var tags: [Tag]? = nil
    /// Temps réel de l'événement (adresse et clé publiques de Supabase), donné avec la discussion d'un événement.
    var realtime: ChatRealtime.Endpoint? = nil

    enum CodingKeys: String, CodingKey {
        case id, name, member, admin, notify, reactions, members, messages, me, highlights, organizer, everyone, direct, photo, blocked
        case event, tags, realtime
        case canNameAdmins = "can_name_admins", userID = "user_id"
    }

    var isDirect: Bool { direct == true }
    var isEvent: Bool { event == true }

    /// Admin ou organisateur : fait des annonces (@annonce) et les retire.
    var isStaff: Bool { admin || (member && organizer == true) }
    /// Peut écrire @tout dans ce groupe (choix des admins du groupe).
    var canEveryone: Bool { everyone != "staff" || isStaff }
    /// Prévenu avant l'envoi : @annonce d'un simple membre (message normal), @tout réservé par le groupe.
    func tagNote(for text: String) -> String? {
        if isDirect { return nil }  // à deux : ni @tout ni @annonce
        if isEvent {
            guard !isStaff, Mentions.eventTag(in: text) != nil else { return nil }
            return "@toutlemonde, @present et les annonces sont réservés à l'organisation de l'événement : ton message partira sans prévenir personne."
        }
        if Mentions.isAnnouncement(text) && !isStaff {
            return "Seuls les admins et organisateurs du groupe font des annonces : ton message partira comme un message normal."
        }
        if text.range(of: "(^|\\s)@tout(\\s|$|[!?.,])", options: [.regularExpression, .caseInsensitive]) != nil && !canEveryone {
            return "Dans ce groupe, seuls les admins et organisateurs peuvent écrire @tout : personne ne sera prévenu."
        }
        return nil
    }

    /// Bandeau du haut, façon WhatsApp : annonces puis messages épinglés, les plus récents d'abord ; un toucher montre
    /// le message et passe au suivant. Message envoyé en annonce pas encore confirmé : montré aussitôt.
    var pins: [Highlight] {
        let pendingAnnouncement = messages.filter { $0.pending && $0.isAnnouncement }.map {
            Highlight(id: $0.id, authorName: $0.authorName, at: $0.at, text: $0.preview, announcement: true)
        }
        let list = (highlights ?? messages.filter { $0.pinned && !$0.deleted }.map {
            Highlight(id: $0.id, authorName: $0.authorName, at: $0.at, text: $0.preview, announcement: $0.isAnnouncement)
        }) + pendingAnnouncement
        let newest = Array(list.reversed())
        return newest.filter(\.announcement) + newest.filter { !$0.announcement }
    }

    /// Dernier message épinglé : affiché en bandeau en haut de la conversation.
    var pinned: Message? { messages.last { $0.pinned } }

    /// Bandeau du haut : la dernière annonce (en surbrillance), sinon le dernier message épinglé ; « autres » = combien
    /// d'annonces (ou d'épinglés) en plus. Message envoyé en annonce pas encore confirmé : montré aussitôt.
    var banner: (item: Highlight, others: Int)? {
        let pendingAnnouncement = messages.last { $0.pending && $0.isAnnouncement }.map {
            Highlight(id: $0.id, authorName: $0.authorName, at: $0.at, text: $0.preview, announcement: true)
        }
        let list = (highlights ?? messages.filter { $0.pinned && !$0.deleted }.map {
            Highlight(id: $0.id, authorName: $0.authorName, at: $0.at, text: $0.preview, announcement: $0.isAnnouncement)
        }) + (pendingAnnouncement.map { [$0] } ?? [])
        let announcements = list.filter(\.announcement)
        if let last = announcements.last { return (last, announcements.count - 1) }
        return list.last.map { ($0, list.count - 1) }
    }

    /// Même conversation avec d'autres messages (message affiché tout de suite à l'envoi).
    func with(messages: [Message]) -> Conversation {
        Conversation(id: id, name: name, member: member, admin: admin, notify: notify, canNameAdmins: canNameAdmins,
                     me: me, reactions: reactions, members: members, messages: messages, highlights: highlights,
                     organizer: organizer, everyone: everyone, direct: direct, userID: userID, photo: photo, blocked: blocked,
                     event: event, tags: tags, realtime: realtime)
    }

    /// Membres cités par « @surnom » (sans accents ni casse) dans le texte (sauf moi) : envoyés avec le message,
    /// la base ne garde que les membres.
    func mentions(in body: String, me: String?) -> [String] {
        if isDirect { return [] }
        let folded = Mentions.fold(body)
        return members.filter { $0.id != me && !$0.name.isEmpty && folded.contains("@" + Mentions.fold($0.name)) }.map(\.id)
    }
}

/// Suggestions de l'@ (avis du 3.11) : en tapant « @lé », les membres du groupe dont le surnom (ou un de ses mots)
/// commence par ces lettres, sans accents ni casse ; puis @tout (tout le groupe) et @annonce (épinglée en haut).
enum Mentions {
    struct Suggestion: Equatable, Identifiable {
        let id: String
        let label: String
        let hint: String
        /// Membre cité (nil : @tout ou @annonce).
        let member: Conversation.Member?
    }

    static let maxShown = 6
    private static let specials = [Suggestion(id: "@tout", label: "tout", hint: "Tout le groupe", member: nil),
                                   Suggestion(id: "@annonce", label: "annonce", hint: "Annonce épinglée en haut du groupe", member: nil)]

    static func fold(_ text: String) -> String {
        text.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: Locale(identifier: "fr_CH")).lowercased()
    }

    /// Lettres tapées après l'@ en fin de texte ; nil quand on n'est pas en train de citer.
    static func query(in text: String) -> String? {
        guard let at = text.lastIndex(of: "@") else { return nil }
        let typed = text[text.index(after: at)...]
        guard !typed.contains(where: { $0.isWhitespace || $0 == "@" }) else { return nil }
        if at > text.startIndex, !text[text.index(before: at)].isWhitespace { return nil }  // une adresse mail, pas une citation
        return String(typed)
    }

    /// everyone : je peux écrire @tout ; announce : je peux faire une annonce (admins et organisateurs).
    /// contacts : noms du répertoire (app iPhone) ; « @mar » trouve aussi le membre enregistré « Marie » dans mes contacts.
    static func suggestions(for query: String, members: [Conversation.Member], me: String?,
                            everyone: Bool = true, announce: Bool = true, contacts: [String: String] = [:],
                            tags: [Conversation.Tag]? = nil) -> [Suggestion] {
        let q = fold(query)
        func starts(_ name: String) -> Bool {
            let n = fold(name)
            return n.hasPrefix(q) || n.split(whereSeparator: { " .-_".contains($0) }).contains { $0.hasPrefix(q) }
        }
        let found = members.filter { $0.id != me && !$0.name.isEmpty && (starts($0.name) || contacts[$0.id].map(starts) == true) }
            .sorted { a, b in
                let (pa, pb) = (fold(a.name).hasPrefix(q), fold(b.name).hasPrefix(q))
                return pa != pb ? pa : a.name.localizedCompare(b.name) == .orderedAscending
            }
            .map { Suggestion(id: $0.id, label: $0.name, hint: contacts[$0.id] ?? "", member: $0) }
        // Événement : les citations de l'organisation (@toutlemonde, @present, @annonce) ; groupe : @tout et @annonce.
        let special = tags.map { $0.map { Suggestion(id: "@" + $0.tag, label: $0.tag, hint: $0.hint, member: nil) } }
            ?? specials.filter { $0.label == "tout" ? everyone : announce }
        let shownTags = special.filter { fold($0.label).hasPrefix(q) }
        return Array(found.prefix(maxShown - shownTags.count)) + shownTags
    }

    /// Remplace l'@ en cours par « @Surnom » suivi d'une espace.
    static func insert(_ label: String, into text: String) -> String {
        guard let at = text.lastIndex(of: "@") else { return text }
        return String(text[..<at]) + "@" + label + " "
    }

    /// Citation de l'organisation d'un événement dans le texte (@toutlemonde, @present, @annonce), même règle que la
    /// base (guard_message_change) ; nil s'il n'y en a pas.
    static func eventTag(in body: String) -> String? {
        for tag in ["toutlemonde", "pr[eé]sents?", "annonce"] {
            if body.range(of: "(^|[^\\p{L}\\p{N}_])@\(tag)($|[^\\p{L}\\p{N}_])", options: [.regularExpression, .caseInsensitive]) != nil {
                return tag
            }
        }
        return nil
    }

    /// Texte d'une bulle : chaque « @surnom » d'un membre (et @tout, @toutlemonde, @present, @annonce) en gras et en
    /// couleur, comme WhatsApp ; le reste tel quel (liens détectés par Text).
    static func highlighted(_ body: String, names: [String], color: Color) -> AttributedString {
        let words = Array(Set((names + ["toutlemonde", "tout", "presents", "present", "annonce"]).filter { !$0.isEmpty }.map(fold)))
            .sorted { $0.count > $1.count }
        func wordChar(_ c: Character) -> Bool { c.isLetter || c.isNumber || c == "_" }
        var out = AttributedString()
        var plain = ""
        var i = body.startIndex
        while i < body.endIndex {
            if body[i] == "@", i == body.startIndex || !wordChar(body[body.index(before: i)]) {
                let rest = body[body.index(after: i)...]
                let hit = words.lazy.compactMap { w -> String.Index? in
                    guard let end = rest.index(rest.startIndex, offsetBy: w.count, limitedBy: rest.endIndex),
                          fold(String(rest[..<end])) == w, end == rest.endIndex || !wordChar(rest[end]) else { return nil }
                    return end
                }.first
                if let end = hit {
                    out += AttributedString(plain)
                    plain = ""
                    var tagged = AttributedString(String(body[i..<end]))
                    tagged.foregroundColor = color
                    tagged.inlinePresentationIntent = .stronglyEmphasized
                    out += tagged
                    i = end
                    continue
                }
            }
            plain.append(body[i])
            i = body.index(after: i)
        }
        out += AttributedString(plain)
        return linked(out)
    }

    /// Adresses web, e-mails et numéros du message : des liens touchables (comme la version web, LinkedText).
    static func linked(_ text: AttributedString) -> AttributedString {
        let plain = String(text.characters)
        guard plain.contains(where: { $0 == "." || $0 == "@" || $0.isNumber }),
              let detector = try? NSDataDetector(types: NSTextCheckingResult.CheckingType.link.rawValue
                                                 | NSTextCheckingResult.CheckingType.phoneNumber.rawValue) else { return text }
        let matches = detector.matches(in: plain, range: NSRange(plain.startIndex..., in: plain))
        guard !matches.isEmpty else { return text }
        let ns = NSMutableAttributedString(text)
        for match in matches {
            let url = match.url ?? match.phoneNumber.flatMap { URL(string: "tel:" + $0.filter { $0.isNumber || $0 == "+" }) }
            guard let url, ["http", "https", "mailto", "tel"].contains(url.scheme?.lowercased() ?? "") else { continue }
            ns.addAttribute(.link, value: url, range: match.range)
            ns.addAttribute(.underlineStyle, value: NSUnderlineStyle.single.rawValue, range: match.range)
        }
        return (try? AttributedString(ns, including: \.swiftUI)) ?? text
    }

    /// « @annonce » en mot entier, sans casse (même règle que la base, guard_group_message).
    static func isAnnouncement(_ body: String) -> Bool {
        body.range(of: "(^|[^\\p{L}\\p{N}_])@annonce($|[^\\p{L}\\p{N}_])", options: [.regularExpression, .caseInsensitive]) != nil
    }
}

/// Fil de la discussion, façon WhatsApp : un séparateur par jour (« Aujourd'hui », « Hier », « lundi », « 12 novembre »)
/// et les messages d'une même personne regroupés (moins de 5 min d'écart, même jour) : nom en tête de la série,
/// photo en bas, bulles rapprochées.
enum ChatTimeline {
    struct Row: Identifiable, Equatable {
        enum Kind: Equatable {
            case day(String)
            case message(Conversation.Message, first: Bool, last: Bool)
        }

        let id: String
        let kind: Kind
    }

    static let series: TimeInterval = 5 * 60

    static func rows(_ messages: [Conversation.Message], now: Date = Date(), calendar: Calendar = .current) -> [Row] {
        var rows: [Row] = []
        var day: Date?
        for (i, m) in messages.enumerated() {
            let date = m.date ?? now
            if day.map({ !calendar.isDate($0, inSameDayAs: date) }) ?? true {
                day = date
                rows.append(Row(id: "day-" + m.id, kind: .day(label(for: date, now: now, calendar: calendar))))
            }
            let previous = i > 0 ? messages[i - 1] : nil
            let next = i + 1 < messages.count ? messages[i + 1] : nil
            rows.append(Row(id: m.id, kind: .message(m, first: !joins(previous, m, calendar), last: !joins(m, next, calendar))))
        }
        return rows
    }

    /// Deux messages de la même série : même auteur, même jour, moins de 5 min, ni l'un ni l'autre une annonce.
    static func joins(_ a: Conversation.Message?, _ b: Conversation.Message?, _ calendar: Calendar = .current) -> Bool {
        guard let a, let b, a.author == b.author, !a.isAnnouncement, !b.isAnnouncement else { return false }
        guard let da = a.date, let db = b.date else { return true }
        return calendar.isDate(da, inSameDayAs: db) && abs(db.timeIntervalSince(da)) < series
    }

    static func label(for date: Date, now: Date = Date(), calendar: Calendar = .current) -> String {
        if calendar.isDate(date, inSameDayAs: now) { return "Aujourd'hui" }
        if let yesterday = calendar.date(byAdding: .day, value: -1, to: now), calendar.isDate(date, inSameDayAs: yesterday) { return "Hier" }
        let fr = Locale(identifier: "fr_CH")
        if let week = calendar.date(byAdding: .day, value: -6, to: calendar.startOfDay(for: now)), date >= week, date <= now {
            return date.formatted(.dateTime.weekday(.wide).locale(fr)).capitalized(with: fr)
        }
        let sameYear = calendar.component(.year, from: date) == calendar.component(.year, from: now)
        return sameYear ? date.formatted(.dateTime.day().month(.wide).locale(fr))
                        : date.formatted(.dateTime.day().month(.wide).year().locale(fr))
    }

    /// Couleur du nom d'un auteur dans un groupe : stable d'un lancement à l'autre, lisible sur fond sombre.
    static func nameColor(for id: String) -> Color {
        let palette: [Color] = [Color(red: 0.73, green: 0.65, blue: 1), Color(red: 0.45, green: 0.85, blue: 0.95),
                                Color(red: 1, green: 0.62, blue: 0.45), Color(red: 0.55, green: 0.9, blue: 0.55),
                                Color(red: 1, green: 0.55, blue: 0.75), Color(red: 1, green: 0.82, blue: 0.4),
                                Color(red: 0.5, green: 0.7, blue: 1), Color(red: 0.85, green: 0.6, blue: 0.95)]
        let sum = id.unicodeScalars.reduce(UInt32(5381)) { ($0 &* 33) &+ $1.value }
        return palette[Int(sum % UInt32(palette.count))]
    }
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

private struct ChatList: Decodable {
    let chats: [ChatSummary]
    let realtime: ChatRealtime.Endpoint?
}
private struct PhotoPath: Decodable { let path: String }
private struct DirectChatID: Decodable { let id: String }

extension PartyAPI {
    func chats(token: String) async throws -> ([ChatSummary], ChatRealtime.Endpoint?) {
        let list: ChatList = try await postDecoding("/api/account/chats", body: ["token": token])
        return (list.chats, list.realtime)
    }

    func openChat(token: String, group: String, direct: Bool = false) async throws -> Conversation {
        try await postDecoding("/api/account/chats/open", body: ["token": token, "group_id": group, "direct": direct])
    }

    /// « Écrire » : LA conversation privée avec cette personne (créée au besoin). contactHash : empreinte de son numéro
    /// (contacts de l'iPhone), preuve qu'on la connaît quand on n'a ni groupe ni événement en commun.
    func startDirectChat(token: String, user: String, contactHash: String? = nil) async throws -> String {
        var body: [String: Any] = ["token": token, "user_id": user]
        if let contactHash { body["contact_hash"] = contactHash }
        let r: DirectChatID = try await postDecoding("/api/account/chats/direct", body: body)
        return r.id
    }

    func blockDirect(token: String, user: String, on: Bool) async throws {
        try await post("/api/account/chats/block", body: ["token": token, "user_id": user, "on": on])
    }

    func sendChat(token: String, group: String, body: String, replyTo: String?, photoPath: String?,
                  mentions: [String], id: String, audioPath: String? = nil, audioSeconds: Double? = nil, direct: Bool = false) async throws {
        var payload: [String: Any] = ["token": token, "group_id": group, "body": body, "mentions": mentions, "id": id, "direct": direct]
        if let audioPath { payload["audio_path"] = audioPath }
        if let audioSeconds { payload["audio_seconds"] = (audioSeconds * 10).rounded() / 10 }
        if let replyTo { payload["reply_to"] = replyTo }
        if let photoPath { payload["photo_path"] = photoPath }
        try await post("/api/account/chats/send", body: payload)
    }

    func uploadChatPhoto(token: String, group: String, jpeg: Data) async throws -> String {
        let r: PhotoPath = try await postDecoding("/api/account/chats/photo",
                                                  body: ["token": token, "group_id": group, "photo": jpeg.base64EncodedString()])
        return r.path
    }

    func uploadChatAudio(token: String, group: String, audio: Data) async throws -> String {
        let r: PhotoPath = try await postDecoding("/api/account/chats/audio",
                                                  body: ["token": token, "group_id": group, "photo": audio.base64EncodedString()])
        return r.path
    }

    func reactChat(token: String, message: String, emoji: String, on: Bool, direct: Bool = false) async throws {
        try await post("/api/account/chats/react", body: ["token": token, "id": message, "emoji": emoji, "on": on, "direct": direct])
    }

    func pinChat(token: String, message: String, pin: Bool, direct: Bool = false) async throws {
        try await post("/api/account/chats/pin", body: ["token": token, "id": message, "pin": pin, "direct": direct])
    }

    func deleteChat(token: String, message: String, direct: Bool = false) async throws {
        try await post("/api/account/chats/delete", body: ["token": token, "id": message, "direct": direct])
    }

    func notifyChat(token: String, group: String, level: ChatNotify, direct: Bool = false) async throws {
        try await post("/api/account/chats/notify", body: ["token": token, "group_id": group, "level": level.rawValue, "direct": direct])
    }

    func setChatAdmin(token: String, group: String, member: String, on: Bool) async throws {
        try await post("/api/account/chats/admin", body: ["token": token, "group_id": group, "user_id": member, "on": on])
    }

    func setChatOrganizer(token: String, group: String, member: String, on: Bool) async throws {
        try await post("/api/account/chats/organizer", body: ["token": token, "group_id": group, "user_id": member, "on": on])
    }

    func setChatEveryone(token: String, group: String, who: String) async throws {
        try await post("/api/account/chats/everyone", body: ["token": token, "group_id": group, "who": who])
    }

    // Discussion d'un événement (/api/account/event-chat/*, app/event_chats.py) : mêmes gestes, autres routes.
    func openEventChat(token: String, event: String) async throws -> Conversation {
        try await postDecoding("/api/account/event-chat/open", body: ["token": token, "event_id": event])
    }

    func sendEventChat(token: String, event: String, body: String, replyTo: String?, photoPath: String?, mentions: [String],
                       id: String, audioPath: String? = nil, audioSeconds: Double? = nil, announcement: Bool = false) async throws {
        var payload: [String: Any] = ["token": token, "event_id": event, "body": body, "mentions": mentions, "id": id,
                                      "announcement": announcement]
        if let audioPath { payload["audio_path"] = audioPath }
        if let audioSeconds { payload["audio_seconds"] = (audioSeconds * 10).rounded() / 10 }
        if let replyTo { payload["reply_to"] = replyTo }
        if let photoPath { payload["photo_path"] = photoPath }
        try await post("/api/account/event-chat/send", body: payload)
    }

    func uploadEventChatFile(token: String, event: String, data: Data, audio: Bool) async throws -> String {
        let r: PhotoPath = try await postDecoding(audio ? "/api/account/event-chat/audio" : "/api/account/event-chat/photo",
                                                  body: ["token": token, "event_id": event, "photo": data.base64EncodedString()])
        return r.path
    }

    func reactEventChat(token: String, message: String, emoji: String, on: Bool) async throws {
        try await post("/api/account/event-chat/react", body: ["token": token, "id": message, "emoji": emoji, "on": on])
    }

    func pinEventChat(token: String, message: String, pin: Bool) async throws {
        try await post("/api/account/event-chat/pin", body: ["token": token, "id": message, "pin": pin])
    }

    func deleteEventChat(token: String, message: String) async throws {
        try await post("/api/account/event-chat/delete", body: ["token": token, "id": message])
    }

    func notifyEventChat(token: String, event: String, level: ChatNotify) async throws {
        try await post("/api/account/event-chat/notify", body: ["token": token, "event_id": event, "level": level == .none ? "none" : "all"])
    }

    func readChat(token: String, group: String, direct: Bool = false) async throws {
        try await post("/api/account/chats/read", body: ["token": token, "group_id": group, "direct": direct])
    }
}

import SwiftUI

// Discussions v2 (18.11.2026), personnes : « Nouveau message », mini-profil, groupe à plusieurs. La base décide de qui
// peut écrire à qui (`chat_link`, `open_direct_chat`) ; l'app ne fait que proposer. Tous les appels passent par le relais
// POST /api/account/chats/rpc (app/chat_rpc.py, même forme que /api/account/pronos/rpc : {"result": …}, photos signées).

// MARK: - Modèles

/// Une personne proposée (P du contrat) : suggestions, recherche, contacts.
struct ChatPerson: Codable, Hashable, Identifiable {
    let id: String
    var name: String
    var nickname: String?
    /// Lien signé de la photo (ajouté par le serveur).
    var photo: String?
    /// Soirée croisée, groupe en commun, « Dans tes contacts »… ; vide : « Déjà vu N fois ».
    var sub: String?
    /// "direct" (dans la boîte) ou "request" (demande de message) ; jamais "none" à l'écran.
    var link: String
    var metCount: Int?

    var isRequest: Bool { link == "request" }

    /// Prénom court des puces « À : » et du bouton « Écrire à Léa ».
    var short: String {
        if let nick = nickname?.trimmingCharacters(in: .whitespaces), !nick.isEmpty { return nick }
        return name.split(separator: " ").first.map(String.init) ?? name
    }

    var face: PronoFace { PronoFace(id: id, name: name.isEmpty ? (nickname ?? "") : name, photo: photo) }

    init(id: String, name: String, nickname: String?, photo: String?, sub: String?, link: String, metCount: Int?) {
        self.id = id
        self.name = name
        self.nickname = nickname
        self.photo = photo
        self.sub = sub
        self.link = link
        self.metCount = metCount
    }

    /// Lu par deux décodeurs (avec et sans convertFromSnakeCase) : « met_count » et « metCount » acceptés.
    private enum Keys: String, CodingKey { case id, name, nickname, photo, sub, link, metCount, metCountSnake = "met_count" }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: Keys.self)
        id = try c.decode(String.self, forKey: .id)
        name = try c.decodeIfPresent(String.self, forKey: .name) ?? ""
        nickname = try c.decodeIfPresent(String.self, forKey: .nickname)
        photo = try c.decodeIfPresent(String.self, forKey: .photo)
        sub = try c.decodeIfPresent(String.self, forKey: .sub)
        link = try c.decodeIfPresent(String.self, forKey: .link) ?? "request"
        metCount = try c.decodeIfPresent(Int.self, forKey: .metCount) ?? c.decodeIfPresent(Int.self, forKey: .metCountSnake)
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: Keys.self)
        try c.encode(id, forKey: .id)
        try c.encode(name, forKey: .name)
        try c.encodeIfPresent(nickname, forKey: .nickname)
        try c.encodeIfPresent(photo, forKey: .photo)
        try c.encodeIfPresent(sub, forKey: .sub)
        try c.encode(link, forKey: .link)
        try c.encodeIfPresent(metCount, forKey: .metCountSnake)
    }
}

struct PeopleSuggestions: Codable, Equatable {
    var recent: [ChatPerson] = []
    var crossed: [ChatPerson] = []
    var groups: [ChatPerson] = []

    init(recent: [ChatPerson] = [], crossed: [ChatPerson] = [], groups: [ChatPerson] = []) {
        self.recent = recent
        self.crossed = crossed
        self.groups = groups
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        recent = try c.decodeIfPresent([ChatPerson].self, forKey: .recent) ?? []
        crossed = try c.decodeIfPresent([ChatPerson].self, forKey: .crossed) ?? []
        groups = try c.decodeIfPresent([ChatPerson].self, forKey: .groups) ?? []
    }

    /// « Croisés récemment » : conversations récentes puis soirées en commun, sans doublon.
    var row: [ChatPerson] {
        var seen = Set<String>()
        return (recent + crossed).filter { seen.insert($0.id).inserted }
    }

    var isEmpty: Bool { recent.isEmpty && crossed.isEmpty && groups.isEmpty }
}

/// Mini-profil (`member_mini`) ; restreint si l'autre m'a bloqué : nom + photo seulement, link "none".
struct MemberMini: Codable, Equatable, Identifiable {
    struct Met: Codable, Equatable, Identifiable {
        let id: String
        let title: String
        var start: String?
    }

    struct Upcoming: Codable, Equatable, Identifiable {
        let id: String
        let title: String
        var start: String?
        /// Ma réponse / la sienne : yes, maybe, no, invited, organizer (ou null).
        var mine: String?
        var theirs: String?
    }

    struct Group: Codable, Equatable, Identifiable {
        let id: String
        let name: String
        var emoji: String?
        var color: String?
        var photo: String?
    }

    let id: String
    var name: String
    var nickname: String?
    var photo: String?
    var since: String?
    var link: String
    var blocked: Bool
    var blockedMe: Bool
    var chat: String?
    var metCount: Int
    var met: [Met]
    var events: [Upcoming]
    var groups: [Group]
    var eventsCount: Int
    var groupsCount: Int

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        name = try c.decodeIfPresent(String.self, forKey: .name) ?? ""
        nickname = try c.decodeIfPresent(String.self, forKey: .nickname)
        photo = try c.decodeIfPresent(String.self, forKey: .photo)
        since = try c.decodeIfPresent(String.self, forKey: .since)
        link = try c.decodeIfPresent(String.self, forKey: .link) ?? "none"
        blocked = try c.decodeIfPresent(Bool.self, forKey: .blocked) ?? false
        blockedMe = try c.decodeIfPresent(Bool.self, forKey: .blockedMe) ?? false
        chat = try c.decodeIfPresent(String.self, forKey: .chat)
        metCount = try c.decodeIfPresent(Int.self, forKey: .metCount) ?? 0
        met = Array((try c.decodeIfPresent([Met].self, forKey: .met) ?? []).prefix(3))
        events = try c.decodeIfPresent([Upcoming].self, forKey: .events) ?? []
        groups = try c.decodeIfPresent([Group].self, forKey: .groups) ?? []
        eventsCount = try c.decodeIfPresent(Int.self, forKey: .eventsCount) ?? events.count
        groupsCount = try c.decodeIfPresent(Int.self, forKey: .groupsCount) ?? groups.count
    }

    var canWrite: Bool { link == "direct" || link == "request" }
    /// L'autre m'a bloqué : on ne montre que son nom et sa photo (on ne dit jamais qui a bloqué).
    var restricted: Bool { blockedMe }

    var person: ChatPerson {
        ChatPerson(id: id, name: name, nickname: nickname, photo: photo, sub: nil, link: link, metCount: metCount)
    }
}

/// Réponse de `open_direct_chat`.
struct DirectOpen: Codable, Equatable {
    var chat: String?
    var status: String
    var reason: String?

    enum Outcome: Equatable {
        case chat(String)
        case terms
        case refused(String)
    }

    /// Une conversation qui existe s'ouvre toujours (l'historique reste lisible) ; sinon la raison, dite sans jamais
    /// révéler qui a bloqué qui.
    var outcome: Outcome {
        if let chat, !chat.isEmpty { return .chat(chat) }
        if reason == "terms_required" { return .terms }
        return .refused(PeopleText.refusal(reason))
    }
}

/// Réponse de `create_chat_group`.
struct ChatGroupCreated: Codable, Equatable {
    let group: String
    var invited: Int
    var refused: [String]

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        group = try c.decode(String.self, forKey: .group)
        invited = try c.decodeIfPresent(Int.self, forKey: .invited) ?? 0
        refused = try c.decodeIfPresent([String].self, forKey: .refused) ?? []
    }
}

// Carte d'une soirée (`chat_event_cards`) : ChatEventCard, dans Conversation/ConversationRelay.swift.

// MARK: - Textes et choix (testés : ChatsPeopleTests)

enum PeopleText {
    /// « Jamais rencontré », « Déjà vu 1 fois », « Déjà vu 3 fois » (soirées passées vécues ensemble).
    static func met(_ count: Int) -> String {
        count <= 0 ? "Jamais rencontré" : "Déjà vu \(count) fois"
    }

    /// Sous-titre d'une personne dans « Nouveau message » : sa soirée / son groupe, sinon « Déjà vu N fois ».
    static func sub(_ p: ChatPerson) -> String? {
        if let sub = p.sub?.trimmingCharacters(in: .whitespaces), !sub.isEmpty { return sub }
        if let n = p.metCount, n > 0 { return met(n) }
        return nil
    }

    /// Raison d'un refus de `open_direct_chat` (jamais « elle t'a bloqué »).
    static func refusal(_ reason: String?) -> String {
        switch reason {
        case "inactive": return "Ce compte n'est plus actif."
        case "profile_required": return "Complète ton profil (prénom, nom et surnom) pour écrire."
        case "terms_required": return "Accepte les règles de Party pour écrire."
        case "limit": return "Tu as envoyé beaucoup de demandes de message : réessaie demain."
        case "closed": return "Cette personne ne reçoit pas de nouveaux messages pour l'instant."
        default: return "Tu ne peux pas écrire à cette personne pour l'instant."
        }
    }

    /// « Léa », « Léa et Noé », « Léa, Noé et Chloé », « Léa, Noé et 3 autres ».
    static func names(_ people: [ChatPerson]) -> String {
        let n = people.map(\.short)
        switch n.count {
        case 0: return ""
        case 1: return n[0]
        case 2: return "\(n[0]) et \(n[1])"
        case 3: return "\(n[0]), \(n[1]) et \(n[2])"
        default: return "\(n[0]), \(n[1]) et \(n.count - 2) autres"
        }
    }

    /// Réponse à un événement, à la 3e personne (« Noé vient ») ou pour moi (« toi : peut-être »).
    static func answer(_ value: String?, me: Bool) -> String? {
        switch value {
        case "yes": return me ? "tu viens" : "vient"
        case "maybe": return "peut-être"
        case "no": return me ? "tu ne viens pas" : "ne vient pas"
        case "invited": return "invité·e"
        case "organizer": return me ? "tu organises" : "organise"
        default: return nil
        }
    }

    /// « Vous venez tous les deux », « Noé vient · toi : peut-être », « Noé organise ».
    static func together(_ e: MemberMini.Upcoming, them: String) -> String {
        let going: Set<String> = ["yes", "organizer"]
        if let m = e.mine, let t = e.theirs, going.contains(m), going.contains(t) { return "Vous venez tous les deux" }
        var parts: [String] = []
        if let t = answer(e.theirs, me: false) { parts.append("\(them) \(t)") }
        if let m = e.mine {
            if m == "maybe" || m == "invited" { parts.append("toi : \(answer(m, me: true) ?? "")") }
            else if let a = answer(m, me: true) { parts.append(a) }
        }
        return parts.isEmpty ? "Soirée en commun" : parts.joined(separator: " · ")
    }
}

/// Ce que fait le bouton de « Nouveau message » selon les personnes choisies.
enum NewMessagePlan: Equatable {
    case none
    /// Une personne : sa conversation ; `request` = ce sera une demande de message.
    case direct(ChatPerson, request: Bool)
    /// Plusieurs : le groupe qui existe déjà avec exactement elles (chat_group_with), sinon un nouveau groupe.
    case group([ChatPerson])

    static let maxPeople = 49  // 2 à 50 personnes avec moi (create_chat_group)

    init(_ selected: [ChatPerson]) {
        switch selected.count {
        case 0: self = .none
        case 1: self = .direct(selected[0], request: selected[0].isRequest)
        default: self = .group(selected)
        }
    }

    var title: String? {
        switch self {
        case .none: return nil
        case .direct(let p, _): return "Écrire à \(p.short)"
        case .group(let people): return "Créer un groupe avec \(PeopleText.names(people))"
        }
    }

    var note: String? {
        switch self {
        case .none: return nil
        case .direct(let p, let request):
            return request ? "Ce sera une demande de message : \(p.short) choisira de l'accepter." : nil
        case .group(let people): return "\(people.count) personnes : ce sera un groupe"
        }
    }
}

/// Résultat d'« Écrire » / « Envoyer un message ».
enum WriteDirectResult: Equatable {
    case opened
    /// Les règles de Party (CGU) d'abord : feuille TermsAcceptSheet, puis nouvel essai.
    case termsRequired
    case refused(String)

    var problem: String? {
        switch self {
        case .opened: return nil
        case .termsRequired: return PeopleText.refusal("terms_required")
        case .refused(let message): return message
        }
    }
}

enum PeopleDate {
    private static let iso: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()

    private static let isoPlain = ISO8601DateFormatter()

    static func parse(_ s: String?) -> Date? {
        guard let s else { return nil }
        return iso.date(from: s) ?? isoPlain.date(from: s)
    }

    private static func format(_ pattern: String) -> DateFormatter {
        let f = DateFormatter()
        f.locale = Locale(identifier: "fr_CH")
        f.timeZone = TimeZone(identifier: "Europe/Zurich") ?? .current
        f.setLocalizedDateFormatFromTemplate(pattern)
        return f
    }

    private static let weekday = format("EEE")
    private static let day = format("d")
    private static let long = format("EEEEdMMMM")

    /// Tuile date : (« VEN. », « 21 »).
    static func tile(_ s: String?) -> (weekday: String, day: String)? {
        guard let d = parse(s) else { return nil }
        let w = weekday.string(from: d).uppercased()
        return (w.hasSuffix(".") ? w : w + ".", day.string(from: d))
    }

    /// « vendredi 21 novembre » (VoiceOver, aperçu de la soirée jointe).
    static func spoken(_ s: String?) -> String? { parse(s).map { long.string(from: $0) } }
}

/// Feuilles des personnes ouvertes par la page web (pont PartyNative.chat) : mini-profil ou « Nouveau message ».
enum PeopleRoute: Identifiable, Equatable {
    case profile(String)
    case newMessage(event: String?)

    var id: String {
        switch self {
        case .profile(let user): return "profile:\(user)"
        case .newMessage(let event): return "new:\(event ?? "")"
        }
    }

    /// Messages du pont « direct:<uuid> » (ouvrir la conversation), « new », « new:<uuid de soirée> ». nil pour le reste.
    static func bridge(_ body: String) -> (direct: String?, newMessage: PeopleRoute?)? {
        func uuid(_ s: Substring) -> String? { UUID(uuidString: String(s))?.uuidString.lowercased() }
        if body == "new" { return (nil, .newMessage(event: nil)) }
        if body.hasPrefix("new:"), let e = uuid(body.dropFirst(4)) { return (nil, .newMessage(event: e)) }
        if body.hasPrefix("direct:"), let u = uuid(body.dropFirst(7)) { return (u, nil) }
        return nil
    }
}

// MARK: - Appels

extension PartyAPI {
    /// Relais des Discussions v2 (app/chat_rpc.py) : fonctions de la liste blanche, réponse {"result": …}.
    func chatsRPC(token: String, fn: String, args: [String: Any] = [:]) async throws -> [String: Any] {
        let reply: RawJSON = try await postDecoding("/api/account/chats/rpc", body: ["token": token, "fn": fn, "args": args])
        return (try JSONSerialization.jsonObject(with: reply.data) as? [String: Any]) ?? [:]
    }
}

/// Réponse JSON gardée telle quelle (le relais rend {"result": …} de forme libre).
private struct RawJSON: Decodable {
    let data: Data

    init(from decoder: Decoder) throws {
        let value = try decoder.singleValueContainer().decode(AnyJSON.self)
        data = try JSONSerialization.data(withJSONObject: value.object, options: [.fragmentsAllowed])
    }
}

private struct AnyJSON: Decodable {
    let object: Any

    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { object = NSNull() }
        else if let b = try? c.decode(Bool.self) { object = b }
        else if let i = try? c.decode(Int.self) { object = i }
        else if let d = try? c.decode(Double.self) { object = d }
        else if let s = try? c.decode(String.self) { object = s }
        else if let a = try? c.decode([AnyJSON].self) { object = a.map(\.object) }
        else { object = try c.decode([String: AnyJSON].self).mapValues(\.object) }
    }
}

/// Personnes des Discussions : appels du relais et ouverture des conversations natives. Donné par l'app (WebModel) à
/// toute la hiérarchie de vues (`\.people`) ; nil quand Discussions n'est pas disponible (« Bientôt ») : les écrans
/// retombent alors sur la fiche native et cachent « Envoyer un message ».
@MainActor
final class PeopleStore {
    private let api: PartyAPI
    private weak var web: WebStorage?
    /// Ouvre une conversation (directe ou de groupe) dans l'onglet Discussions natif.
    let openChat: @MainActor (String) -> Void
    /// Ouvre la fiche d'un événement dans l'onglet Événements.
    let openEvent: @MainActor (String) -> Void

    init(api: PartyAPI, web: WebStorage?, openChat: @escaping @MainActor (String) -> Void,
         openEvent: @escaping @MainActor (String) -> Void) {
        self.api = api
        self.web = web
        self.openChat = openChat
        self.openEvent = openEvent
    }

    private(set) lazy var moderation = ModerationStore(api: api, web: web)
    private(set) lazy var privacy = PrivacyStore(api: api, web: web)

    static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }()

    func call<T: Decodable>(_ fn: String, _ args: [String: Any] = [:], as: T.Type = T.self) async throws -> T {
        guard let token = await web?.accountToken() else { throw PartyAPIError.server("Connecte-toi à Party pour écrire.") }
        let reply = try await api.chatsRPC(token: token, fn: fn, args: args)
        let data = try JSONSerialization.data(withJSONObject: reply["result"] ?? NSNull(), options: [.fragmentsAllowed])
        return try Self.decoder.decode(T.self, from: data)
    }

    /// Photo d'un groupe (JPEG recadré) : le serveur la dépose et la pose sur le groupe (app/group_pages.py), la base
    /// vérifie le droit et les CGU.
    func uploadGroupPhoto(_ group: String, jpeg: Data) async throws {
        guard let token = await web?.accountToken() else { throw PartyAPIError.server("Connecte-toi à Party pour écrire.") }
        try await api.post("/api/account/chats/group-photo", body: ["token": token, "group_id": group, "photo": jpeg.base64EncodedString()],
                           timeout: 60)
    }

    func suggestions() async throws -> PeopleSuggestions {
        try await call("chat_people_suggestions", as: PeopleSuggestions?.self) ?? PeopleSuggestions()
    }

    /// Recherche par prénom, nom ou surnom (≥ 2 caractères, jamais par numéro) ; la base ne rend que link ≠ none.
    func search(_ q: String) async throws -> [ChatPerson] {
        let q = q.trimmingCharacters(in: .whitespacesAndNewlines)
        guard q.count >= 2 else { return [] }
        return (try await call("chat_people_search", ["q": q], as: [ChatPerson]?.self) ?? []).filter { $0.link != "none" }
    }

    /// Contact du répertoire : l'empreinte de son numéro prouve qu'on se connaît, et la base propose alors une demande de
    /// message au lieu de « none » (member_mini_contact ; recette de nuit du 28.11 : bouton grisé pour un contact).
    func mini(_ user: String) async throws -> MemberMini {
        // Serveur ou base d'avant (fonction pas encore là) : repli sur member_mini, jamais un mini-profil en erreur.
        if let hash = ContactNames.shared.contactHash(for: user),
           let m = try? await call("member_mini_contact", ["target": user, "contact_hash": hash], as: MemberMini.self) {
            return m
        }
        return try await call("member_mini", ["target": user])
    }

    /// « Tes contacts sur Party » : les membres reconnus sur cet iPhone (empreintes calculées ici, contacts_match), avec
    /// leur lien d'après la base ; jamais de « none ». 20 au plus.
    func contactPeople() async -> [ChatPerson] {
        let contacts = ContactNames.shared
        let ids = contacts.names.sorted { $0.value.localizedCaseInsensitiveCompare($1.value) == .orderedAscending }.map(\.key).prefix(20)
        let found = await withTaskGroup(of: MemberMini?.self) { group in
            for id in ids { group.addTask { try? await self.mini(id) } }
            var all: [MemberMini] = []
            for await m in group { if let m { all.append(m) } }
            return all
        }
        let byID = Dictionary(found.map { ($0.id, $0) }, uniquingKeysWith: { a, _ in a })
        return ids.compactMap { id in
            guard let m = byID[id], m.canWrite, !m.blocked, !m.restricted else { return nil }
            var p = m.person
            p.sub = "Dans tes contacts"
            return p
        }
    }

    /// La conversation à deux (créée au besoin, statut décidé par la base). L'empreinte du numéro (contacts de
    /// l'iPhone) prouve qu'on se connaît.
    func resolveDirect(_ user: String) async -> DirectOpen.Outcome {
        var args: [String: Any] = ["target": user]
        if let hash = ContactNames.shared.contactHash(for: user) { args["contact_hash"] = hash }
        do {
            let r: DirectOpen = try await call("open_direct_chat", args)
            return r.outcome
        } catch PartyAPIError.termsRequired {
            return .terms
        } catch {
            return .refused(Self.message(error))
        }
    }

    /// « Envoyer un message » : ouvre la conversation native (demande comprise).
    func openDirect(_ user: String) async -> WriteDirectResult {
        switch await resolveDirect(user) {
        case .chat(let chat):
            openChat(chat)
            return .opened
        case .terms: return .termsRequired
        case .refused(let message): return .refused(message)
        }
    }

    /// Le groupe dont je fais partie avec EXACTEMENT ces personnes, s'il existe.
    func groupWith(_ people: [String]) async throws -> String? {
        try await call("chat_group_with", ["members": people], as: String?.self)
    }

    /// Groupe à plusieurs, privé (Root ne le lit pas) ; seules les personnes en lien direct sont invitées.
    func createGroup(name: String, emoji: String, color: String, members: [String]) async throws -> ChatGroupCreated {
        try await call("create_chat_group", ["name": name.trimmingCharacters(in: .whitespacesAndNewlines),
                                             "emoji": emoji, "color": color, "members": members])
    }

    func eventCard(_ id: String) async -> ChatEventCard? {
        (try? await call("chat_event_cards", ["ids": [id]], as: [ChatEventCard].self))?.first
    }

    /// « Envoyer à un ami » : la carte de la soirée dans la conversation (route d'envoi existante, étendue d'`event_id`).
    func sendEvent(_ card: ChatEventCard, to chat: String, direct: Bool) async throws {
        guard let token = await web?.accountToken() else { throw PartyAPIError.server("Connecte-toi à Party pour écrire.") }
        try await api.post("/api/account/chats/send", body: [
            "token": token, "group_id": chat, "body": "📅 \(card.title)", "mentions": [String](),
            "id": UUID().uuidString.lowercased(), "direct": direct, "event_id": card.id,
        ])
    }

    static func message(_ error: Error) -> String {
        (error as? LocalizedError)?.errorDescription ?? "Ça n'a pas marché. Réessaie dans un instant."
    }
}

private struct PeopleStoreKey: EnvironmentKey {
    static let defaultValue: PeopleStore? = nil
}

extension EnvironmentValues {
    var people: PeopleStore? {
        get { self[PeopleStoreKey.self] }
        set { self[PeopleStoreKey.self] = newValue }
    }
}

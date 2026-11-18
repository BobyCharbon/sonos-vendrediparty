import SwiftUI

// Groupes en natif (demande de l'admin du 18.11 : « Je veux tout en natif ») : la liste, la page, les réglages, la création
// et « Inviter » d'un groupe, comme les pages web du module Événements (groups.tsx, group/[id]/index.tsx, settings.tsx,
// invite.tsx, group/new.tsx). Tout passe par le relais POST /api/account/chats/rpc (app/chat_rpc.py + app/group_pages.py) :
// la base décide de tout (droits, filtre des noms, CGU, Membres Vendredi Party jamais renommé ni quitté, jamais de photo).

// MARK: - Modèles

/// Une ligne de « Mes groupes » (`my_groups_overview`).
struct GroupOverview: Decodable, Equatable, Identifiable {
    struct Face: Decodable, Equatable {
        let id: String
        var name: String?
        var photo: String?
    }

    struct NextEvent: Decodable, Equatable {
        let id: String
        let title: String
        var startsAt: String?
        var dateMode: String?
    }

    let id: String
    var name: String
    var emoji: String
    var color: String?
    var photo: String?
    var system: Bool
    var creator: Bool
    var manage: Bool
    var member: Bool
    var createdByName: String?
    var members: Int
    var faces: [Face]
    var last: String?
    var lastBy: String?
    var lastAt: String?
    var unread: Int
    var nextEvent: NextEvent?

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        name = try c.decodeIfPresent(String.self, forKey: .name) ?? ""
        emoji = try c.decodeIfPresent(String.self, forKey: .emoji) ?? "👯"
        color = try c.decodeIfPresent(String.self, forKey: .color)
        photo = try c.decodeIfPresent(String.self, forKey: .photo)
        system = try c.decodeIfPresent(Bool.self, forKey: .system) ?? false
        creator = try c.decodeIfPresent(Bool.self, forKey: .creator) ?? false
        manage = try c.decodeIfPresent(Bool.self, forKey: .manage) ?? false
        member = try c.decodeIfPresent(Bool.self, forKey: .member) ?? false
        createdByName = try c.decodeIfPresent(String.self, forKey: .createdByName)
        members = try c.decodeIfPresent(Int.self, forKey: .members) ?? 0
        faces = try c.decodeIfPresent([Face].self, forKey: .faces) ?? []
        last = try c.decodeIfPresent(String.self, forKey: .last)
        lastBy = try c.decodeIfPresent(String.self, forKey: .lastBy)
        lastAt = try c.decodeIfPresent(String.self, forKey: .lastAt)
        unread = try c.decodeIfPresent(Int.self, forKey: .unread) ?? 0
        nextEvent = try c.decodeIfPresent(NextEvent.self, forKey: .nextEvent)
    }

    private enum CodingKeys: String, CodingKey {
        case id, name, emoji, color, photo, system, creator, manage, member, createdByName, members, faces, last, lastBy, lastAt
        case unread, nextEvent
    }

    /// « Membres Vendredi Party » pour le groupe de tout le monde (son nom en base : Vendredi Party).
    var title: String { GroupText.name(name, system: system) }
}

/// Invitation reçue (`my_group_invitations`).
struct GroupInvitationRow: Decodable, Equatable, Identifiable {
    let id: String
    let groupId: String
    var group: String
    var emoji: String?
    var color: String?
    var invitedBy: String?
}

/// Autre groupe (Admins du site seulement : la base ne les montre qu'à eux).
struct OtherGroup: Decodable, Equatable, Identifiable {
    let id: String
    var name: String
    var emoji: String
    var color: String?
    var photo: String?
    var system: Bool
    var members: Int
}

struct GroupsHome: Decodable, Equatable {
    var groups: [GroupOverview] = []
    var invitations: [GroupInvitationRow] = []
    var others: [OtherGroup] = []

    init() {}

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        groups = try c.decodeIfPresent([GroupOverview].self, forKey: .groups) ?? []
        invitations = try c.decodeIfPresent([GroupInvitationRow].self, forKey: .invitations) ?? []
        others = try c.decodeIfPresent([OtherGroup].self, forKey: .others) ?? []
    }

    private enum CodingKeys: String, CodingKey { case groups, invitations, others }
}

/// Page d'un groupe (`group_page`, app/group_pages.py) : le groupe, mes droits, ses membres et ses événements visibles.
struct GroupPage: Decodable, Equatable {
    struct Info: Decodable, Equatable {
        let id: String
        var name: String
        var emoji: String
        var color: String?
        var photo: String?
        var system: Bool
        var createdBy: String?
        var createdByName: String?
        var createdAt: String?
        var eventsNeedApproval: Bool
        var announceMode: String

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            id = try c.decode(String.self, forKey: .id)
            name = try c.decodeIfPresent(String.self, forKey: .name) ?? ""
            emoji = try c.decodeIfPresent(String.self, forKey: .emoji) ?? "👯"
            color = try c.decodeIfPresent(String.self, forKey: .color)
            photo = try c.decodeIfPresent(String.self, forKey: .photo)
            system = try c.decodeIfPresent(Bool.self, forKey: .system) ?? false
            createdBy = try c.decodeIfPresent(String.self, forKey: .createdBy)
            createdByName = try c.decodeIfPresent(String.self, forKey: .createdByName)
            createdAt = try c.decodeIfPresent(String.self, forKey: .createdAt)
            eventsNeedApproval = try c.decodeIfPresent(Bool.self, forKey: .eventsNeedApproval) ?? false
            announceMode = try c.decodeIfPresent(String.self, forKey: .announceMode) ?? "request"
        }

        private enum CodingKeys: String, CodingKey {
            case id, name, emoji, color, photo, system, createdBy, createdByName, createdAt, eventsNeedApproval, announceMode
        }

        var title: String { GroupText.name(name, system: system) }
    }

    struct Member: Decodable, Equatable, Identifiable {
        let id: String
        var name: String
        var photo: String?
        var creator: Bool
        var me: Bool

        var face: PronoFace { PronoFace(id: id, name: name, photo: photo) }
    }

    var group: Info
    var me: String
    var member: Bool
    var manage: Bool
    var creator: Bool
    var canCreateEvent: Bool
    var canSetRules: Bool
    var phoneShared: Bool
    var unread: Int
    var members: [Member]
    var upcoming: [ChatEventCard]
    var past: [ChatEventCard]

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        group = try c.decode(Info.self, forKey: .group)
        me = try c.decodeIfPresent(String.self, forKey: .me) ?? ""
        member = try c.decodeIfPresent(Bool.self, forKey: .member) ?? false
        manage = try c.decodeIfPresent(Bool.self, forKey: .manage) ?? false
        creator = try c.decodeIfPresent(Bool.self, forKey: .creator) ?? false
        canCreateEvent = try c.decodeIfPresent(Bool.self, forKey: .canCreateEvent) ?? false
        canSetRules = try c.decodeIfPresent(Bool.self, forKey: .canSetRules) ?? false
        phoneShared = try c.decodeIfPresent(Bool.self, forKey: .phoneShared) ?? false
        unread = try c.decodeIfPresent(Int.self, forKey: .unread) ?? 0
        members = try c.decodeIfPresent([Member].self, forKey: .members) ?? []
        upcoming = try c.decodeIfPresent([ChatEventCard].self, forKey: .upcoming) ?? []
        past = try c.decodeIfPresent([ChatEventCard].self, forKey: .past) ?? []
    }

    private enum CodingKeys: String, CodingKey {
        case group, me, member, manage, creator, canCreateEvent, canSetRules, phoneShared, unread, members, upcoming, past
    }

    /// Ce que la page montre, selon mes droits (mêmes règles que la page web du groupe).
    var showsSettings: Bool { member || manage }
    var showsInvite: Bool { manage && !group.system }
    var showsPronos: Bool { member && !group.system }
    var canLeave: Bool { member && !group.system && group.createdBy != me }
    var canReportPhoto: Bool { group.photo != nil && !group.system && !manage }
    var myName: String { members.first(where: \.me)?.name ?? "" }
}

/// « Déjà sur Party » : personne croisée à un événement (`group_invite_suggestions`, jamais tout le site).
struct GroupSuggestion: Decodable, Equatable, Identifiable {
    let id: String
    var displayName: String
    var photo: String?
    var together: Int
    var lastTitle: String?
    var invited: Bool

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        displayName = try c.decodeIfPresent(String.self, forKey: .displayName) ?? ""
        photo = try c.decodeIfPresent(String.self, forKey: .photo)
        together = try c.decodeIfPresent(Int.self, forKey: .together) ?? 0
        lastTitle = try c.decodeIfPresent(String.self, forKey: .lastTitle)
        invited = try c.decodeIfPresent(Bool.self, forKey: .invited) ?? false
    }

    private enum CodingKeys: String, CodingKey { case id, displayName, photo, together, lastTitle, invited }

    var face: PronoFace { PronoFace(id: id, name: displayName, photo: photo) }
}

/// Lien unique créé pour le groupe (`my_invite_links`).
struct GroupLinkRow: Decodable, Equatable, Identifiable {
    let token: String
    var createdAt: String?
    var expiresAt: String?
    var usedBy: String?
    var status: String

    var id: String { token }
}

struct GroupLinkURL: Decodable, Equatable {
    let token: String
    let url: String
}

struct GroupCreated: Decodable, Equatable { let group: String }
struct GroupFoundPerson: Decodable, Equatable { let id: String; let name: String }
private struct GroupOK: Decodable {}

// MARK: - Textes (testés : GroupsNativeTests)

enum GroupText {
    static let nameMax = 60
    /// Mêmes listes que la base (member_groups_emoji_check / _color_check) et web/events/src/lib/groups.ts.
    static let emojis = NewChatGroupView.emojis
    static let colors = NewChatGroupView.colors

    static func name(_ name: String, system: Bool) -> String { system ? "Membres Vendredi Party" : name }

    /// « 1 membre », « 12 membres ».
    static func members(_ n: Int) -> String { n == 1 ? "1 membre" : "\(n) membres" }

    /// Sous-titre de la page : « Toute la communauté · 40 membres » ou « 4 membres · créé par toi ».
    static func subtitle(_ page: GroupPage) -> String {
        if page.group.system { return "Toute la communauté · \(members(page.members.count))" }
        var out = members(page.members.count)
        if page.creator { out += " · créé par toi" } else if let who = page.group.createdByName, !who.isEmpty { out += " · créé par \(who)" }
        return out
    }

    /// Message envoyé avec le lien (WhatsApp, Autre) : le même que le web.
    static func inviteMessage(host: String, group: GroupPage.Info, url: String) -> String {
        let who = host.trimmingCharacters(in: .whitespaces).isEmpty ? "Moi" : host
        return "Hello ! \(who) t’invite dans le groupe « \(group.emoji) \(group.name) » sur Party. Rejoins-le ici : \(url)"
    }

    /// « Chloé, Malik et Inès », « Chloé, Malik et 3 autres ».
    static func names(_ names: [String]) -> String {
        switch names.count {
        case 0: return ""
        case 1: return names[0]
        case 2, 3: return names.dropLast().joined(separator: ", ") + " et " + names[names.count - 1]
        default: return "\(names[0]), \(names[1]) et \(names.count - 2) autres"
        }
    }

    /// Sous-titre d'une personne croisée : « Invitation envoyée », « 3 soirées ensemble », sa dernière soirée.
    static func suggestion(_ p: GroupSuggestion, sent: Bool) -> String {
        if p.invited || sent { return "Invitation envoyée" }
        if p.together > 1 { return "\(p.together) soirées ensemble" }
        return p.lastTitle ?? "Croisé à un événement"
    }

    /// Numéro tapé (« 079 123 45 67 », « +41 79… ») → chiffres au format international, comme le web ; nil sinon.
    static func phone(_ typed: String) -> String? {
        let t = typed.trimmingCharacters(in: .whitespaces)
        let digits = t.filter(\.isNumber)
        guard t.range(of: #"^[+0-9][0-9 .()\-]{6,}$"#, options: .regularExpression) != nil, digits.count >= 8 else { return nil }
        return digits.hasPrefix("0") && digits.count == 10 ? "41" + digits.dropFirst() : String(digits)
    }

    /// État d'un lien unique.
    static func linkStatus(_ link: GroupLinkRow) -> String {
        switch link.status {
        case "used": return "Utilisé par \(link.usedBy ?? "?")"
        case "expired": return "Expiré"
        case "revoked": return "Annulé"
        default: return "En attente"
        }
    }

    /// « Groupe créé le 17 novembre 2026 ».
    static func createdLine(_ iso: String?) -> String? {
        guard let d = PeopleDate.parse(iso) else { return nil }
        let f = DateFormatter()
        f.locale = Locale(identifier: "fr_CH")
        f.timeZone = TimeZone(identifier: "Europe/Zurich") ?? .current
        f.setLocalizedDateFormatFromTemplate("dMMMMyyyy")
        return "Groupe créé le \(f.string(from: d))"
    }

    static func shortDate(_ iso: String?) -> String {
        guard let d = PeopleDate.parse(iso) else { return "" }
        let f = DateFormatter()
        f.locale = Locale(identifier: "fr_CH")
        f.timeZone = TimeZone(identifier: "Europe/Zurich") ?? .current
        f.setLocalizedDateFormatFromTemplate("dMMM")
        return f.string(from: d)
    }
}

// MARK: - Appels

/// Appels des groupes par le relais des Discussions (PeopleStore.call : jeton, décodage, erreurs, CGU).
@MainActor
struct GroupsAPI {
    let people: PeopleStore

    func home() async throws -> GroupsHome { try await people.call("groups_home") }
    func page(_ id: String) async throws -> GroupPage { try await people.call("group_page", ["grp": id]) }

    func create(name: String, emoji: String, color: String) async throws -> String {
        let r: GroupCreated = try await people.call("group_create", ["name": name, "emoji": emoji, "color": color])
        return r.group
    }

    func update(_ id: String, name: String, emoji: String, color: String) async throws {
        let _: GroupOK = try await people.call("group_update", ["grp": id, "name": name, "emoji": emoji, "color": color])
    }

    func removeMember(_ id: String, _ member: String) async throws {
        let _: GroupOK = try await people.call("group_remove_member", ["grp": id, "member": member])
    }

    func leave(_ id: String) async throws { let _: GroupOK = try await people.call("group_leave", ["grp": id]) }
    func delete(_ id: String) async throws { let _: GroupOK = try await people.call("group_delete", ["grp": id]) }
    func removePhoto(_ id: String) async throws { let _: GroupOK? = try await people.call("group_photo_remove", ["grp": id]) }

    func setPhone(_ id: String, visible: Bool) async throws {
        let _: GroupAnyReply? = try await people.call("set_group_phone_share", ["grp": id, "visible": visible])
    }

    func setRules(_ id: String, needApproval: Bool, mode: String) async throws {
        let _: GroupAnyReply? = try await people.call("set_group_event_rules", ["grp": id, "need_approval": needApproval, "mode": mode])
    }

    func answer(_ invitation: String, accept: Bool) async throws {
        let _: GroupAnyReply? = try await people.call("answer_group_invitation", ["inv": invitation, "accept": accept])
    }

    func link(_ id: String, renew: Bool = false) async throws -> GroupLinkURL {
        try await people.call("group_link", ["grp": id, "renew": renew])
    }

    func singleLink(_ id: String) async throws -> GroupLinkURL { try await people.call("group_single_link", ["grp": id]) }
    func links(_ id: String) async throws -> [GroupLinkRow] { try await people.call("group_links", ["grp": id], as: [GroupLinkRow]?.self) ?? [] }
    func revoke(_ token: String) async throws { let _: GroupAnyReply? = try await people.call("revoke_invite_link", ["tok": token]) }

    func suggestions(_ id: String) async throws -> [GroupSuggestion] {
        try await people.call("group_invite_suggestions", ["grp": id], as: [GroupSuggestion]?.self) ?? []
    }

    func find(_ typed: String) async throws -> GroupFoundPerson? {
        try await people.call("group_find_person", ["q": typed], as: GroupFoundPerson?.self)
    }

    /// Invitation (personne ou numéro) : la base vérifie le droit, le blocage et le doublon.
    func invite(_ id: String, member: String?, phone: String?) async throws {
        let args: [String: Any] = ["grp": id, "member": member ?? NSNull(), "phone": phone ?? NSNull()]
        let _: GroupAnyReply? = try await people.call("invite_to_group", args)
    }
}

/// Réponse dont on ne lit rien (jsonb libre).
struct GroupAnyReply: Decodable {
    init(from decoder: Decoder) throws {}
}

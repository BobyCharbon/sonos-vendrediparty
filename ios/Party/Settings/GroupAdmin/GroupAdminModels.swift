import Foundation

/// Rôles du groupe, dans l'ordre de la base (private.role_rank) : Membre est au niveau de Guest.
enum MemberRole: String, CaseIterable, Decodable, Identifiable {
    case guest, guestplus, basic, member, organizer, coadmin, admin

    var id: String { rawValue }

    var rank: Int {
        switch self {
        case .guest, .guestplus, .basic: return 0
        case .member: return 1
        case .organizer: return 2
        case .coadmin: return 3
        case .admin: return 4
        }
    }

    var label: String {
        switch self {
        case .guest: return "Guest"
        case .guestplus: return "Guest+"
        case .basic: return "Membre"
        case .member: return "Membre VIP"
        case .organizer: return "Organisateur"
        case .coadmin: return "Co-admin"
        case .admin: return "Admin"
        }
    }

    /// Du plus haut au plus bas, comme les sections de la liste des membres.
    static let descending: [MemberRole] = allCases.reversed()
}

/// Mes droits (my_permissions) et mon rang (invité 0 … admin 4, root 99), renvoyés avec chaque écran.
struct AdminAccess: Equatable {
    static let fullAccessRank = 4
    static let rootRank = 99

    let me: String
    let perms: Set<String>
    let rank: Int

    func can(_ perm: String) -> Bool { perms.contains(perm) }
    /// Root et Admin : liste complète, numéros, suppression, journal.
    var full: Bool { rank >= Self.fullAccessRank }
    var seesMembers: Bool { full || can("members.roles") || can("members.ban") || can("members.view_identity") }
    var managesRoles: Bool { can("roles.manage") || rank >= Self.rootRank }
    var canRoles: Bool { full || can("members.roles") }
    var canBan: Bool { full || can("members.ban") }
    /// Rôles que je peux donner : seulement en dessous du mien.
    var assignable: [MemberRole] { MemberRole.allCases.filter { $0.rank < rank } }
}

private enum AccessKeys: String, CodingKey { case me, perms, rank }

private func decodeAccess(_ decoder: Decoder) throws -> AdminAccess {
    let c = try decoder.container(keyedBy: AccessKeys.self)
    return AdminAccess(me: try c.decode(String.self, forKey: .me),
                       perms: Set(try c.decodeIfPresent([String].self, forKey: .perms) ?? []),
                       rank: try c.decodeIfPresent(Int.self, forKey: .rank) ?? -1)
}

/// Accueil (POST /api/account/group-admin) : propositions, demandes d'adhésion, règle de validation.
struct AdminOverview: Decodable, Equatable {
    struct Proposal: Decodable, Equatable, Identifiable {
        let id: String
        let title: String
        let author: String
        let at: String?
        let summary: String
        let startsAt: String?

        enum CodingKeys: String, CodingKey { case id, title, author, at, summary, startsAt = "starts_at" }

        /// « 12 nov. 2026 à 20:00 · 12 places » ou « Date à définir · 2 créneau(x) ».
        var details: String {
            [AdminDate.text(startsAt), summary.isEmpty ? nil : summary].compactMap { $0 }.joined(separator: " · ")
        }
    }

    struct JoinRequest: Decodable, Equatable, Identifiable {
        let id: String
        let name: String
        let fullName: String
        let phone: String?
        let photo: String?
        let message: String?
        let at: String?
        /// Nom, prénom, surnom et photo renseignés : sinon la base refuse l'acceptation.
        let complete: Bool

        enum CodingKeys: String, CodingKey { case id, name, phone, photo, message, at, complete, fullName = "full_name" }
    }

    let access: AdminAccess
    let events: [Proposal]
    let requests: [JoinRequest]
    /// nil : pas le droit « Règles du groupe ».
    let requireApproval: Bool?

    enum CodingKeys: String, CodingKey { case events, requests, requireApproval = "require_approval" }

    init(from decoder: Decoder) throws {
        access = try decodeAccess(decoder)
        let c = try decoder.container(keyedBy: CodingKeys.self)
        events = try c.decodeIfPresent([Proposal].self, forKey: .events) ?? []
        requests = try c.decodeIfPresent([JoinRequest].self, forKey: .requests) ?? []
        requireApproval = try c.decodeIfPresent(Bool.self, forKey: .requireApproval)
    }
}

/// Membres (POST /api/account/group-admin/members).
struct AdminMembers: Decodable, Equatable {
    struct Person: Decodable, Equatable, Identifiable {
        let id: String
        let name: String
        let fullName: String
        let phone: String?
        let photo: String?
        let role: MemberRole
        let status: String
        let beta: Bool
        let root: Bool
        let complete: Bool
        let createdAt: String?
        let lastSignInAt: String?
        // Liste complète (Root, Admin) : écran Utilisateurs.
        let firstSignInAt: String?
        let signInCount: Int
        let lastDevice: String?
        let groups: [String]
        let rsvpCount: Int
        let messageCount: Int

        enum CodingKeys: String, CodingKey {
            case id, name, phone, photo, role, status, beta, root, complete, groups
            case fullName = "full_name", createdAt = "created_at", lastSignInAt = "last_sign_in_at"
            case firstSignInAt = "first_sign_in_at", signInCount = "sign_in_count", lastDevice = "last_device"
            case rsvpCount = "rsvp_count", messageCount = "message_count"
        }

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            id = try c.decode(String.self, forKey: .id)
            name = try c.decodeIfPresent(String.self, forKey: .name) ?? ""
            fullName = try c.decodeIfPresent(String.self, forKey: .fullName) ?? ""
            phone = try c.decodeIfPresent(String.self, forKey: .phone)
            photo = try c.decodeIfPresent(String.self, forKey: .photo)
            // Rôle inconnu de cette version de l'app : traité comme Guest (aucun droit de plus).
            role = (try? c.decode(MemberRole.self, forKey: .role)) ?? .guest
            status = try c.decodeIfPresent(String.self, forKey: .status) ?? "pending"
            beta = try c.decodeIfPresent(Bool.self, forKey: .beta) ?? false
            root = try c.decodeIfPresent(Bool.self, forKey: .root) ?? false
            complete = try c.decodeIfPresent(Bool.self, forKey: .complete) ?? false
            createdAt = try c.decodeIfPresent(String.self, forKey: .createdAt)
            lastSignInAt = try c.decodeIfPresent(String.self, forKey: .lastSignInAt)
            firstSignInAt = try c.decodeIfPresent(String.self, forKey: .firstSignInAt)
            signInCount = try c.decodeIfPresent(Int.self, forKey: .signInCount) ?? 0
            lastDevice = try c.decodeIfPresent(String.self, forKey: .lastDevice)
            groups = try c.decodeIfPresent([String].self, forKey: .groups) ?? []
            rsvpCount = try c.decodeIfPresent(Int.self, forKey: .rsvpCount) ?? 0
            messageCount = try c.decodeIfPresent(Int.self, forKey: .messageCount) ?? 0
        }

        var displayName: String { name.isEmpty ? "Profil à compléter" : name }
        var active: Bool { status == "active" }
        var banned: Bool { status == "banned" }
        var roleText: String { root ? "Root" : role.label }

        func matches(_ query: String) -> Bool {
            let q = query.trimmingCharacters(in: .whitespaces)
            guard !q.isEmpty else { return true }
            return [name, fullName, phone ?? ""].contains { $0.localizedCaseInsensitiveContains(q) }
        }
    }

    struct Section: Identifiable, Equatable {
        let title: String
        let people: [Person]
        var id: String { title }
    }

    let access: AdminAccess
    /// Liste complète (Root, Admin) : numéros, connexions, suppression, journal.
    let full: Bool
    let people: [Person]

    enum CodingKeys: String, CodingKey { case full, people }

    init(from decoder: Decoder) throws {
        access = try decodeAccess(decoder)
        let c = try decoder.container(keyedBy: CodingKeys.self)
        full = try c.decodeIfPresent(Bool.self, forKey: .full) ?? false
        people = try c.decodeIfPresent([Person].self, forKey: .people) ?? []
    }

    /// Sections : actifs par rôle (du plus haut au plus bas), puis en attente, puis accès retiré.
    func sections(matching query: String) -> [Section] {
        let rows = people.filter { $0.matches(query) }
        let byRole = MemberRole.descending.map { role in (role.label, rows.filter { $0.active && $0.role == role }) }
        let others = [("En attente", rows.filter { !$0.active && !$0.banned }), ("Accès retiré", rows.filter(\.banned))]
        return (byRole + others).filter { !$0.1.isEmpty }.map { Section(title: "\($0.0) (\($0.1.count))", people: $0.1) }
    }
}

/// Ce que je peux faire sur un membre : on ne touche qu'aux comptes d'un rôle inférieur au sien (comme la base).
struct MemberRules {
    let access: AdminAccess
    let person: AdminMembers.Person

    /// Ni root, ni moi, et un rôle en dessous du mien.
    var below: Bool { !person.root && person.id != access.me && person.role.rank < access.rank }
    var changesRole: Bool { below && access.canRoles && person.active }
    var bans: Bool { below && access.canBan }
    var setsBeta: Bool { access.canRoles && person.active }
    var deletes: Bool { below && access.full }
    /// Au-dessus de Guest, il faut une identité complète (guard_profile).
    func allows(_ role: MemberRole) -> Bool { role.rank == 0 || person.complete }
}

/// Rôles et droits (POST /api/account/group-admin/roles).
struct AdminRoles: Decodable, Equatable {
    struct Permission: Decodable, Equatable, Identifiable {
        let key: String
        let grp: String
        let label: String
        let hint: String?
        var id: String { key }
    }

    struct Group: Identifiable, Equatable {
        let name: String
        let perms: [Permission]
        var id: String { name }
    }

    let access: AdminAccess
    let editable: [MemberRole]
    let catalog: [Permission]
    let grants: [String: [String]]

    enum CodingKeys: String, CodingKey { case editable, catalog, grants }

    init(from decoder: Decoder) throws {
        access = try decodeAccess(decoder)
        let c = try decoder.container(keyedBy: CodingKeys.self)
        editable = (try c.decodeIfPresent([String].self, forKey: .editable) ?? []).compactMap(MemberRole.init(rawValue:))
        catalog = try c.decodeIfPresent([Permission].self, forKey: .catalog) ?? []
        grants = try c.decodeIfPresent([String: [String]].self, forKey: .grants) ?? [:]
    }

    func granted(_ perm: String, to role: MemberRole) -> Bool { grants[role.rawValue]?.contains(perm) == true }
    /// On ne donne que les droits qu'on a soi-même (sauf root) ; on peut toujours retirer.
    func canToggle(_ perm: String, for role: MemberRole) -> Bool {
        granted(perm, to: role) || access.rank >= AdminAccess.rootRank || access.can(perm)
    }

    /// Droits par rubrique, dans l'ordre du catalogue.
    var groups: [Group] {
        var order: [String] = []
        for p in catalog where !order.contains(p.grp) { order.append(p.grp) }
        return order.map { name in Group(name: name, perms: catalog.filter { $0.grp == name }) }
    }
}

/// Journal des membres (POST /api/account/group-admin/journal) : phrases déjà rédigées par le serveur.
struct AdminJournal: Decodable, Equatable {
    struct Entry: Decodable, Equatable, Identifiable {
        let id: Int
        let at: String?
        let text: String
    }

    let entries: [Entry]
    let more: Bool
}

/// Dates de la base (ISO 8601, avec ou sans fractions de seconde) → texte court, format du téléphone.
enum AdminDate {
    private static let french = Locale(identifier: "fr_CH")
    private static let plain = ISO8601DateFormatter()
    private static let fractional: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()

    static func date(_ text: String?) -> Date? {
        guard let text else { return nil }
        return fractional.date(from: text) ?? plain.date(from: text)
    }

    static func text(_ iso: String?) -> String? {
        date(iso).map { $0.formatted(.dateTime.day().month(.abbreviated).year().hour().minute().locale(french)) }
    }
}

extension PartyAPI {
    func groupAdmin(token: String) async throws -> AdminOverview {
        try await postDecoding("/api/account/group-admin", body: ["token": token])
    }

    func decideProposal(token: String, id: String, approve: Bool, reason: String?) async throws -> AdminOverview {
        var body: [String: Any] = ["token": token, "id": id, "yes": approve]
        if let reason { body["reason"] = reason }
        return try await postDecoding("/api/account/group-admin/event", body: body)
    }

    func decideJoin(token: String, id: String, accept: Bool) async throws -> AdminOverview {
        try await postDecoding("/api/account/group-admin/request", body: ["token": token, "id": id, "yes": accept])
    }

    func setRequireApproval(token: String, on: Bool) async throws -> AdminOverview {
        try await postDecoding("/api/account/group-admin/approval", body: ["token": token, "on": on])
    }

    func adminMembers(token: String) async throws -> AdminMembers {
        try await postDecoding("/api/account/group-admin/members", body: ["token": token])
    }

    func updateMember(token: String, id: String, role: MemberRole? = nil, status: String? = nil, beta: Bool? = nil) async throws -> AdminMembers {
        var body: [String: Any] = ["token": token, "id": id]
        if let role { body["role"] = role.rawValue }
        if let status { body["status"] = status }
        if let beta { body["beta"] = beta }
        return try await postDecoding("/api/account/group-admin/member", body: body)
    }

    func deleteMember(token: String, id: String, confirmName: String) async throws -> AdminMembers {
        try await postDecoding("/api/account/group-admin/member/delete", body: ["token": token, "id": id, "confirm_name": confirmName])
    }

    func adminRoles(token: String) async throws -> AdminRoles {
        try await postDecoding("/api/account/group-admin/roles", body: ["token": token])
    }

    func setPermission(token: String, role: MemberRole, perm: String, on: Bool) async throws -> AdminRoles {
        try await postDecoding("/api/account/group-admin/permission", body: ["token": token, "role": role.rawValue, "perm": perm, "on": on])
    }

    func adminJournal(token: String, member: String?, before: Int?) async throws -> AdminJournal {
        var body: [String: Any] = ["token": token]
        if let member { body["member"] = member }
        if let before { body["before"] = before }
        return try await postDecoding("/api/account/group-admin/journal", body: body)
    }
}

/// Utilisateurs (Root, Admin) : tris et filtres de l'écran, comme le module web (lib/users.ts).
enum UserList {
    enum Sort: String, CaseIterable, Identifiable {
        case lastSignIn, firstSignIn, signedUp, name, signIns, activity, role
        var id: String { rawValue }
        var label: String {
            switch self {
            case .lastSignIn: return "Dernière connexion"
            case .firstSignIn: return "Première connexion"
            case .signedUp: return "Inscription"
            case .name: return "Nom"
            case .signIns: return "Nb de connexions"
            case .activity: return "Activité"
            case .role: return "Rôle"
            }
        }
        /// Le plus récent / le plus actif d'abord ; les noms de A à Z.
        var descendingByDefault: Bool { self != .name }
    }

    enum Filter: String, CaseIterable, Identifiable {
        case all, guest, guestplus, basic, vip, team, beta, incomplete, never, banned
        var id: String { rawValue }
        var label: String {
            switch self {
            case .all: return "Tous"
            case .guest: return "Guest"
            case .guestplus: return "Guest+"
            case .basic: return "Membre"
            case .vip: return "Membre VIP"
            case .team: return "Orga et admins"
            case .beta: return "Bêta"
            case .incomplete: return "Profil incomplet"
            case .never: return "Pas revenu (30 j)"
            case .banned: return "Accès retiré"
            }
        }
    }

    private static let month: TimeInterval = 30 * 86_400

    static func matches(_ p: AdminMembers.Person, _ filter: Filter, now: Date = Date()) -> Bool {
        switch filter {
        case .all: return true
        case .guest: return p.active && p.role == .guest
        case .guestplus: return p.active && p.role == .guestplus
        case .basic: return p.active && p.role == .basic
        case .vip: return p.active && p.role == .member
        case .team: return p.active && p.role.rank > MemberRole.member.rank
        case .beta: return p.beta
        case .incomplete: return !p.complete
        case .never: return now.timeIntervalSince(AdminDate.date(p.lastSignInAt) ?? .distantPast) > month
        case .banned: return p.banned
        }
    }

    static func arrange(_ people: [AdminMembers.Person], search: String, filter: Filter, sort: Sort, descending: Bool,
                        now: Date = Date()) -> [AdminMembers.Person] {
        let rows = people.filter { $0.matches(search) && matches($0, filter, now: now) }
        return rows.sorted { a, b in
            let order: Bool
            switch sort {
            case .name:
                let x = sortName(a), y = sortName(b)
                if x == y { return a.id < b.id }
                order = x < y
            default:
                let x = value(a, sort), y = value(b, sort)
                if x == y { return a.displayName.lowercased() < b.displayName.lowercased() }
                order = x < y
            }
            return descending ? !order : order
        }
    }

    /// Surnom, sinon prénom et nom ; un profil sans nom va en fin de liste (comme le module web).
    private static func sortName(_ p: AdminMembers.Person) -> String {
        let name = p.name.isEmpty ? p.fullName : p.name
        return name.isEmpty ? "\u{10FFFF}" : name.folding(options: [.caseInsensitive, .diacriticInsensitive], locale: Locale(identifier: "fr"))
    }

    private static func value(_ p: AdminMembers.Person, _ sort: Sort) -> Double {
        switch sort {
        case .lastSignIn: return AdminDate.date(p.lastSignInAt)?.timeIntervalSince1970 ?? 0
        case .firstSignIn: return AdminDate.date(p.firstSignInAt)?.timeIntervalSince1970 ?? 0
        case .signedUp: return AdminDate.date(p.createdAt)?.timeIntervalSince1970 ?? 0
        case .signIns: return Double(p.signInCount)
        case .activity: return Double(p.rsvpCount + p.messageCount)
        case .role: return Double(p.role.rank)
        case .name: return 0
        }
    }
}

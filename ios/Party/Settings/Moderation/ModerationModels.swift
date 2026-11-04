import Foundation

/// Modération commune à toute l'app (4.11, Apple 1.2 / Google UGC) : Signaler, Personnes bloquées, conditions
/// d'utilisation, écran admin « Signalements ». Le serveur Party relaie (app/moderation_api.py) ; la base décide.

/// Ce qu'on signale : un message, un profil, une photo de profil (et bientôt les contenus du Compagnon).
struct ReportTarget: Identifiable, Equatable {
    enum Kind: String {
        case groupMessage = "group_message", directMessage = "direct_message", eventMessage = "event_message"
        case profile, profilePhoto = "profile_photo"
        case petName = "pet_name", petItem = "pet_item", petOffer = "pet_offer", petShowcase = "pet_showcase", petWord = "pet_word"
    }

    let kind: Kind
    let id: String
    /// « le message de Léa », « Léa », « la photo de profil ».
    let label: String
}

enum ReportReason: String, CaseIterable, Identifiable {
    case harassment, shocking, spam, scam, other

    var id: String { rawValue }

    var label: String {
        switch self {
        case .harassment: return "Harcèlement"
        case .shocking: return "Contenu choquant"
        case .spam: return "Spam"
        case .scam: return "Arnaque ou vente"
        case .other: return "Autre"
        }
    }

    var hint: String {
        switch self {
        case .harassment: return "Insultes, menaces, moqueries répétées"
        case .shocking: return "Haine, violence, contenu sexuel"
        case .spam: return "Messages en masse, publicité"
        case .scam: return "Demande d'argent, vente d'objets du jeu"
        case .other: return "Explique en quelques mots"
        }
    }
}

struct BlockedPerson: Decodable, Equatable, Identifiable {
    let id: String
    let name: String
    let photo: String?
}

struct TermsStatus: Decodable, Equatable {
    let version: String
    let accepted: Bool
    let acceptedAt: String?
    let contactEmail: String?
    let enforced: Bool

    enum CodingKeys: String, CodingKey {
        case version, accepted, enforced, acceptedAt = "accepted_at", contactEmail = "contact_email"
    }

    init(version: String, accepted: Bool, acceptedAt: String? = nil, contactEmail: String? = nil, enforced: Bool = false) {
        self.version = version
        self.accepted = accepted
        self.acceptedAt = acceptedAt
        self.contactEmail = contactEmail
        self.enforced = enforced
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        version = try c.decodeIfPresent(String.self, forKey: .version) ?? ""
        accepted = try c.decodeIfPresent(Bool.self, forKey: .accepted) ?? false
        acceptedAt = try c.decodeIfPresent(String.self, forKey: .acceptedAt)
        contactEmail = try c.decodeIfPresent(String.self, forKey: .contactEmail)
        enforced = try c.decodeIfPresent(Bool.self, forKey: .enforced) ?? false
    }
}

/// Un signalement dans la file des modérateurs (copie du contenu au moment du signalement).
struct ModerationReport: Decodable, Equatable, Identifiable {
    struct Person: Decodable, Equatable {
        let id: String?
        let name: String
        let photo: String?
        let status: String?
    }

    struct Sanction: Decodable, Equatable {
        let kind: String
        let endsAt: String?
        let liftedAt: String?
        let at: String?

        enum CodingKeys: String, CodingKey { case kind, at, endsAt = "ends_at", liftedAt = "lifted_at" }
    }

    let id: String
    let kind: String
    let reason: String
    let reasonLabel: String
    let comment: String?
    let status: String
    let resolution: String?
    let note: String?
    let createdAt: String?
    let handledAt: String?
    let handledBy: String?
    let reporter: String
    let text: String
    let place: String
    let photo: String?
    let user: Person?
    let sameTarget: Int
    let userReports: Int
    let sanctions: [Sanction]

    enum CodingKeys: String, CodingKey {
        case id, kind, reason, comment, status, resolution, note, reporter, text, place, photo, user, sanctions
        case reasonLabel = "reason_label", createdAt = "created_at", handledAt = "handled_at", handledBy = "handled_by"
        case sameTarget = "same_target", userReports = "user_reports"
    }

    var kindLabel: String { Self.kinds[kind] ?? kind }
    var banned: Bool { user?.status == "banned" }

    static let kinds = [
        "group_message": "Message de groupe", "direct_message": "Message direct", "event_message": "Discussion d'événement",
        "profile": "Profil", "profile_photo": "Photo de profil", "pet_name": "Nom du Zicou", "pet_item": "Objet de Zicou",
        "pet_offer": "Offre d'échange", "pet_showcase": "Vitrine", "pet_word": "Mot de Zicou",
    ]
    static let resolutions = ["hide": "Contenu masqué", "warn": "Averti", "suspend": "Suspendu", "ban": "Banni",
                              "dismiss": "Classé sans suite"]
}

struct ModerationQueue: Decodable, Equatable {
    struct Settings: Decodable, Equatable {
        let contactEmail: String?
        let termsEnforced: Bool

        enum CodingKeys: String, CodingKey { case contactEmail = "contact_email", termsEnforced = "terms_enforced" }

        init(contactEmail: String?, termsEnforced: Bool) {
            self.contactEmail = contactEmail
            self.termsEnforced = termsEnforced
        }

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            contactEmail = try c.decodeIfPresent(String.self, forKey: .contactEmail)
            termsEnforced = try c.decodeIfPresent(Bool.self, forKey: .termsEnforced) ?? false
        }
    }

    let reports: [ModerationReport]
    let settings: Settings
}

enum ModerationAction: String {
    case hide, warn, suspend, ban, dismiss
}

private struct BlockList: Decodable { let blocks: [BlockedPerson] }

extension PartyAPI {
    func report(token: String, target: ReportTarget, reason: ReportReason, comment: String) async throws {
        try await post("/api/account/moderation/report", body: ["token": token, "kind": target.kind.rawValue, "target": target.id,
                                                                "reason": reason.rawValue, "comment": comment])
    }

    func blockedPeople(token: String) async throws -> [BlockedPerson] {
        let list: BlockList = try await postDecoding("/api/account/moderation/blocks", body: ["token": token])
        return list.blocks
    }

    func setBlock(token: String, user: String, on: Bool) async throws -> [BlockedPerson] {
        let list: BlockList = try await postDecoding("/api/account/moderation/block", body: ["token": token, "user_id": user, "on": on])
        return list.blocks
    }

    func terms(token: String) async throws -> TermsStatus {
        try await postDecoding("/api/account/moderation/terms", body: ["token": token])
    }

    func acceptTerms(token: String, version: String) async throws -> TermsStatus {
        try await postDecoding("/api/account/moderation/terms/accept", body: ["token": token, "version": version])
    }

    func moderationQueue(token: String, status: String) async throws -> ModerationQueue {
        try await postDecoding("/api/account/moderation/queue", body: ["token": token, "status": status])
    }

    func moderate(token: String, report: String, action: ModerationAction, note: String, days: Int?, status: String) async throws -> ModerationQueue {
        var body: [String: Any] = ["token": token, "report_id": report, "action": action.rawValue, "note": note]
        if let days { body["days"] = days }
        return try await postDecoding("/api/account/moderation/act?status=\(status)", body: body)
    }

    func liftSanction(token: String, user: String) async throws -> ModerationQueue {
        try await postDecoding("/api/account/moderation/lift", body: ["token": token, "user_id": user])
    }

    func moderationSettings(token: String, contactEmail: String?, termsEnforced: Bool?) async throws -> ModerationQueue {
        var body: [String: Any] = ["token": token]
        if let contactEmail { body["contact_email"] = contactEmail }
        if let termsEnforced { body["terms_enforced"] = termsEnforced }
        return try await postDecoding("/api/account/moderation/settings", body: body)
    }
}

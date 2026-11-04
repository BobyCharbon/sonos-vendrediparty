import Foundation

/// Ce qu'un invité reçoit du serveur Party (GET /api/notify) : un oui/non par type, et si un de ses
/// appareils est abonné. Types : GUEST_NOTIFY_DEFAULTS dans app/party.py.
struct GuestNotifyState: Decodable, Equatable {
    var prefs: [String: Bool]
    var subscribed: Bool
}

/// Ce que l'hôte reçoit (GET /api/admin/notify) : ADMIN_NOTIFY_DEFAULTS dans app/party.py.
struct AdminNotifyState: Decodable, Equatable {
    var prefs: [String: Bool]

    enum CodingKeys: String, CodingKey { case prefs = "admin_notify" }
}

/// Préférences du compte pour les événements (table Supabase notification_prefs, via /api/account/notifications).
struct EventNotificationPrefs: Codable, Equatable {
    var pushEnabled: Bool
    var quietStart: String?
    var quietEnd: String?
    var newEvent: String
    var eventChanged: Bool
    var pollNew: Bool
    var dateFixed: Bool
    var pollNudge: Bool
    var waitlist: Bool
    var reminders: [String]
    var chat: String
    var rsvpMine: Bool
    var proposals: Bool
    /// Lune des Réglages : tout arrive sans son jusqu'à cette date (texte Postgres) ; absente avant la migration.
    var mutedUntil: String?
    /// Sourdine des Discussions des groupes jusqu'à cette date.
    var chatsMutedUntil: String?
    /// Sourdine des discussions des événements jusqu'à cette date.
    var eventChatsMutedUntil: String?
    /// Un réglage par type de notification (migration 20261103120000) ; absent avant la migration : reçu.
    var announcements: Bool?
    var rsvpSet: Bool?
    var invites: Bool?
    var proposalResult: Bool?
    var linkJoin: Bool?
    var groupMessages: Bool?
    var groupInvites: Bool?
    var groupJoins: Bool?
    /// Annonces et @tout des groupes de Discussions (absent avant la migration : reçues).
    var groupBroadcasts: Bool?
    /// Billets payants (migration 20261103130000 ; absents avant : reçues) : quelqu'un dit avoir payé ma place /
    /// l'organisateur confirme mon paiement.
    var ticketPayDeclared: Bool?
    var ticketPayConfirmed: Bool?
    /// Billets QR (migration 20261104233000 ; absent avant : reçue) : « Ton billet est prêt », remis par l'organisateur.
    var ticketIssued: Bool?
    /// Mes amis dans Party (migration 20261104090000 ; absents avant : reçues) : quelqu'un rejoint Party grâce à mon
    /// lien (envoyée par Party) ; un contact arrive sur Party (notification locale calculée par l'iPhone).
    var referralJoins: Bool?
    var contactJoins: Bool?
    /// Messages directs (migration 20261104100000 ; absent avant : reçus) : « Nouveau message de X ».
    var directMessages: Bool?
    /// Compagnon (migration 20261104130000 ; absents avant : reçus) : rappel doux du jour, alertes avant son envol.
    var petDaily: Bool?
    var petAlerts: Bool?
    /// Compagnon, lot 1 (migration 20261104150000 ; absents avant : reçus) : cadeau d'un ami, paliers de série.
    var petGifts: Bool?
    var petStreaks: Bool?
    /// Modération (migration 20261104200000 ; absents avant : reçus) : nouveau signalement (modérateurs), message de la modération.
    var moderationReports: Bool?
    var moderationNotices: Bool?

    enum CodingKeys: String, CodingKey {
        case pushEnabled = "push_enabled", quietStart = "quiet_start", quietEnd = "quiet_end", newEvent = "new_event"
        case eventChanged = "event_changed", pollNew = "poll_new", dateFixed = "date_fixed", pollNudge = "poll_nudge"
        case waitlist, reminders, chat, rsvpMine = "rsvp_mine", proposals
        case mutedUntil = "muted_until", chatsMutedUntil = "chats_muted_until", groupBroadcasts = "group_broadcasts"
        case eventChatsMutedUntil = "event_chats_muted_until", announcements, rsvpSet = "rsvp_set", invites
        case proposalResult = "proposal_result", linkJoin = "link_join", groupMessages = "group_messages"
        case groupInvites = "group_invites", groupJoins = "group_joins"
        case ticketPayDeclared = "ticket_pay_declared", ticketPayConfirmed = "ticket_pay_confirmed"
        case ticketIssued = "ticket_issued"
        case referralJoins = "referral_joins", contactJoins = "contact_joins", directMessages = "direct_messages"
        case petDaily = "pet_daily", petAlerts = "pet_alerts", petGifts = "pet_gifts", petStreaks = "pet_streaks"
        case moderationReports = "moderation_reports", moderationNotices = "moderation_notices"
    }

    var hasQuietHours: Bool { quietStart != nil && quietEnd != nil }
}

struct EventNotifyState: Decodable, Equatable {
    var prefs: EventNotificationPrefs
    /// Valide les propositions d'événements (droit events.approve) : réglage « Proposition à valider ».
    var approver: Bool
    /// Droit « Modérer les signalements » : réglage « Nouveau signalement » (absent d'un ancien serveur : non).
    var moderator: Bool? = nil
}

/// Choix proposés, mêmes libellés que le module Événements (web/events/src/app/settings/notifications.tsx).
enum EventChoices {
    struct Choice {
        let key: String
        let label: String
        let hint: String
    }

    static let newEvent = [
        Choice(key: "all", label: "Toujours", hint: "Chaque nouvel événement visible pour toi."),
        Choice(key: "subscribed", label: "Si abonné", hint: "Seulement les événements d'une catégorie ou d'un tag que tu suis."),
        Choice(key: "none", label: "Jamais", hint: "Aucune alerte de nouvel événement. Les annonces admin restent actives."),
    ]
    static let chat = [
        Choice(key: "all", label: "Tous", hint: "Chaque message des discussions des événements auxquels tu participes."),
        Choice(key: "mentions", label: "Si on me cite", hint: "Seulement quand quelqu'un écrit @ton prénom ou répond à ton message."),
        Choice(key: "none", label: "Aucun", hint: "Aucune notification. Les messages restent lisibles dans l'app."),
    ]
    /// Dans l'ordre du temps : le plus tôt d'abord.
    static let reminders = [
        Choice(key: "7d", label: "7 jours avant", hint: ""),
        Choice(key: "1d", label: "La veille", hint: ""),
        Choice(key: "2h", label: "2 heures avant", hint: ""),
        Choice(key: "0h", label: "Au début", hint: ""),
    ]

    static func hint(_ choices: [Choice], for key: String) -> String {
        choices.first { $0.key == key }?.hint ?? ""
    }

    /// Rappel coché ou décoché, dans l'ordre de la liste (jamais de doublon).
    static func reminders(_ current: [String], toggling key: String, on: Bool) -> [String] {
        let chosen = Set(current).subtracting([key]).union(on ? [key] : [])
        return reminders.map(\.key).filter(chosen.contains)
    }
}

/// Heures de silence : « 23:00 » ou « 23:00:00 » (Postgres) ↔ heure du jour.
enum QuietTime {
    static let defaultStart = "23:00"
    static let defaultEnd = "08:00"

    static func date(_ text: String?, on day: Date = Date(), calendar: Calendar = .current) -> Date {
        let parts = (text ?? "").split(separator: ":").compactMap { Int($0) }
        guard parts.count >= 2, (0..<24).contains(parts[0]), (0..<60).contains(parts[1]) else { return day }
        return calendar.date(bySettingHour: parts[0], minute: parts[1], second: 0, of: day) ?? day
    }

    static func text(_ date: Date, calendar: Calendar = .current) -> String {
        let c = calendar.dateComponents([.hour, .minute], from: date)
        return String(format: "%02d:%02d", c.hour ?? 0, c.minute ?? 0)
    }

    /// Mêmes heures (début = fin) : refusé, la plage serait vide.
    static func same(_ a: String?, _ b: String?) -> Bool {
        guard let a, let b else { return false }
        return a.prefix(5) == b.prefix(5)
    }
}

/// Live Activity « Ton titre arrive » (Dynamic Island, écran verrouillé) : réglage de cet iPhone.
enum LiveActivitySetting {
    static let key = "liveActivitiesEnabled"

    static var isEnabled: Bool {
        get { UserDefaults.standard.object(forKey: key) as? Bool ?? true }
        set { UserDefaults.standard.set(newValue, forKey: key) }
    }
}

/// Compte Party relié (vp_account dans la page, écrit par index.html linkAccount).
struct AccountSummary: Decodable, Equatable {
    let name: String
    let photo: String?
    let admin: Bool
    /// Au moins un droit d'administration du groupe (valider, membres, rôles…) : Réglages › Administration du groupe.
    let groupAdmin: Bool
    /// Droit « Écrire un avis » (Guest+ et au-dessus) : « Ton avis » s'affiche.
    let feedback: Bool

    enum CodingKeys: String, CodingKey { case name, photo, admin, feedback, groupAdmin = "group_admin" }

    init(name: String, photo: String?, admin: Bool, groupAdmin: Bool = false, feedback: Bool = false) {
        self.name = name
        self.photo = photo
        self.admin = admin
        self.groupAdmin = groupAdmin
        self.feedback = feedback
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        name = try c.decodeIfPresent(String.self, forKey: .name) ?? ""
        photo = try c.decodeIfPresent(String.self, forKey: .photo)
        admin = try c.decodeIfPresent(Bool.self, forKey: .admin) ?? false
        // Compte relié avant cette version : la page n'a pas encore noté le droit, les admins l'ont d'office.
        groupAdmin = try c.decodeIfPresent(Bool.self, forKey: .groupAdmin) ?? admin
        feedback = try c.decodeIfPresent(Bool.self, forKey: .feedback) ?? admin
    }

    static func parse(_ json: String?) -> AccountSummary? {
        guard let data = json?.data(using: .utf8), !data.isEmpty else { return nil }
        return try? JSONDecoder().decode(AccountSummary.self, from: data)
    }
}

/// Mon profil (POST /api/account/profile) : ligne profiles du membre ; photo = lien signé, valable quelques jours.
struct MemberProfile: Decodable, Equatable {
    let id: String
    var displayName: String
    var firstName: String
    var lastName: String
    let phone: String?
    let role: String
    /// Nom du rôle donné par le serveur (rôles personnalisés) ; nil avec un ancien serveur.
    let roleName: String?
    let status: String
    let photo: String?

    enum CodingKeys: String, CodingKey {
        case id, phone, role, status, photo
        case roleName = "role_label"
        case displayName = "display_name", firstName = "first_name", lastName = "last_name"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        displayName = try c.decodeIfPresent(String.self, forKey: .displayName) ?? ""
        firstName = try c.decodeIfPresent(String.self, forKey: .firstName) ?? ""
        lastName = try c.decodeIfPresent(String.self, forKey: .lastName) ?? ""
        phone = try c.decodeIfPresent(String.self, forKey: .phone)
        role = try c.decodeIfPresent(String.self, forKey: .role) ?? "guest"
        roleName = try c.decodeIfPresent(String.self, forKey: .roleName)
        status = try c.decodeIfPresent(String.self, forKey: .status) ?? "active"
        photo = try c.decodeIfPresent(String.self, forKey: .photo)
    }

    /// Libellés du module Événements (roleLabel dans web/events/src/lib/types.ts).
    var roleLabel: String {
        if status == "banned" { return "Accès retiré" }
        if let roleName { return roleName }
        return ["guest": "Guest", "guestplus": "Guest+", "basic": "Membre", "member": "Membre VIP", "organizer": "Organisateur", "coadmin": "Co-admin", "admin": "Admin"][role] ?? role
    }
}

/// Règles de Mon profil, les mêmes que la base (trigger guard_profile) : tout est obligatoire, surnom ≤ 40.
enum ProfileRules {
    static let nicknameLength = 40
    static let nameLength = 100

    static func clean(_ text: String) -> String {
        text.split(whereSeparator: \.isWhitespace).joined(separator: " ")
    }

    static func isComplete(first: String, last: String, nickname: String, hasPhoto: Bool) -> Bool {
        !clean(first).isEmpty && !clean(last).isEmpty && !clean(nickname).isEmpty && hasPhoto
            && clean(nickname).count <= nicknameLength
    }
}

/// Abonnements (POST /api/account/subscriptions) : catégories et tags actifs, et ceux que le membre suit.
struct Subscriptions: Decodable, Equatable {
    struct Topic: Decodable, Equatable, Identifiable {
        let id: String
        let name: String
        let color: String?
        let icon: String?
    }

    var categories: [Topic]
    var tags: [Topic]
    var categoryIDs: Set<String>
    var tagIDs: Set<String>

    enum CodingKeys: String, CodingKey {
        case categories, tags, categoryIDs = "category_ids", tagIDs = "tag_ids"
    }

    var count: Int { categoryIDs.count + tagIDs.count }

    func follows(_ kind: String, _ id: String) -> Bool {
        (kind == "category" ? categoryIDs : tagIDs).contains(id)
    }

    /// Choix appliqué tout de suite à l'écran (remis comme avant si l'enregistrement échoue).
    func setting(_ kind: String, _ id: String, _ on: Bool) -> Subscriptions {
        var copy = self
        if kind == "category" {
            copy.categoryIDs = on ? categoryIDs.union([id]) : categoryIDs.subtracting([id])
        } else {
            copy.tagIDs = on ? tagIDs.union([id]) : tagIDs.subtracting([id])
        }
        return copy
    }
}

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

    enum CodingKeys: String, CodingKey {
        case pushEnabled = "push_enabled", quietStart = "quiet_start", quietEnd = "quiet_end", newEvent = "new_event"
        case eventChanged = "event_changed", pollNew = "poll_new", dateFixed = "date_fixed", pollNudge = "poll_nudge"
        case waitlist, reminders, chat, rsvpMine = "rsvp_mine", proposals
    }

    var hasQuietHours: Bool { quietStart != nil && quietEnd != nil }
}

struct EventNotifyState: Decodable, Equatable {
    var prefs: EventNotificationPrefs
    /// Valide les propositions d'événements (droit events.approve) : réglage « Proposition à valider ».
    var approver: Bool
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

    enum CodingKeys: String, CodingKey { case name, photo, admin }

    init(name: String, photo: String?, admin: Bool) {
        self.name = name
        self.photo = photo
        self.admin = admin
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        name = try c.decodeIfPresent(String.self, forKey: .name) ?? ""
        photo = try c.decodeIfPresent(String.self, forKey: .photo)
        admin = try c.decodeIfPresent(Bool.self, forKey: .admin) ?? false
    }

    static func parse(_ json: String?) -> AccountSummary? {
        guard let data = json?.data(using: .utf8), !data.isEmpty else { return nil }
        return try? JSONDecoder().decode(AccountSummary.self, from: data)
    }
}

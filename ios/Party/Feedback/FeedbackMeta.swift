import Foundation

/// Statuts, zones, plateformes, efforts et vues des retours : envoyés par le serveur (`meta` de
/// GET /api/admin/feedback, STATUSES de app/feedback.py). `fallback` reprend les mêmes valeurs pour un serveur
/// qui ne les envoie pas encore.
struct FeedbackMeta: Decodable, Equatable {
    struct Status: Decodable, Equatable, Identifiable {
        let key: String
        let label: String
        let icon: String
        /// SF Symbol (le web montre `icon`).
        let symbol: String
        /// Couleur « #rrggbb ».
        let color: String
        /// Ce que l'invité en voit : new (Envoyé), progress (En cours), done, declined.
        let guest: String
        /// Posé par le serveur seul (issue claude-fix ouverte) : jamais proposé à la main.
        let technical: Bool
        let adminOnly: Bool
        let mine: Bool

        var id: String { key }
        var title: String { "\(icon) \(label)" }

        enum CodingKeys: String, CodingKey { case key, label, icon, symbol, color, guest, technical, mine, adminOnly = "admin_only" }

        init(key: String, label: String, icon: String, symbol: String, color: String, guest: String,
             technical: Bool = false, adminOnly: Bool = false, mine: Bool = false) {
            (self.key, self.label, self.icon, self.symbol, self.color, self.guest) = (key, label, icon, symbol, color, guest)
            (self.technical, self.adminOnly, self.mine) = (technical, adminOnly, mine)
        }

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            key = try c.decode(String.self, forKey: .key)
            label = try c.decodeIfPresent(String.self, forKey: .label) ?? key
            icon = try c.decodeIfPresent(String.self, forKey: .icon) ?? ""
            symbol = try c.decodeIfPresent(String.self, forKey: .symbol) ?? "circle"
            color = try c.decodeIfPresent(String.self, forKey: .color) ?? "#ffffff"
            guest = try c.decodeIfPresent(String.self, forKey: .guest) ?? "new"
            technical = try c.decodeIfPresent(Bool.self, forKey: .technical) ?? false
            adminOnly = try c.decodeIfPresent(Bool.self, forKey: .adminOnly) ?? false
            mine = try c.decodeIfPresent(Bool.self, forKey: .mine) ?? false
        }
    }

    /// Une valeur au choix (zone, plateforme, effort, priorité).
    struct Choice: Decodable, Equatable, Identifiable {
        let key: String
        let label: String
        var id: String { key }
    }

    struct View: Decodable, Equatable, Identifiable {
        let key: String
        let label: String
        let statuses: [String]
        var id: String { key }
    }

    let statuses: [Status]
    let priorities: [Choice]
    let areas: [Choice]
    let platforms: [Choice]
    let efforts: [Choice]
    let views: [View]
    let mine: [String]
    let maxTags: Int

    enum CodingKeys: String, CodingKey { case statuses, priorities, areas, platforms, efforts, views, mine, maxTags = "max_tags" }

    init(statuses: [Status], priorities: [Choice], areas: [Choice], platforms: [Choice], efforts: [Choice], views: [View],
         mine: [String], maxTags: Int) {
        (self.statuses, self.priorities, self.areas, self.platforms, self.efforts) = (statuses, priorities, areas, platforms, efforts)
        (self.views, self.mine, self.maxTags) = (views, mine, maxTags)
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        let fb = Self.fallback
        statuses = (try? c.decode([Status].self, forKey: .statuses)) ?? fb.statuses
        priorities = (try? c.decode([Choice].self, forKey: .priorities)) ?? fb.priorities
        // Objets JSON : l'ordre n'est pas garanti au décodage, on reprend celui du secours (inconnues à la fin).
        areas = Self.ordered((try? c.decode([String: String].self, forKey: .areas)), like: fb.areas)
        platforms = Self.ordered((try? c.decode([String: String].self, forKey: .platforms)), like: fb.platforms)
        efforts = Self.ordered((try? c.decode([String: String].self, forKey: .efforts)), like: fb.efforts)
        views = (try? c.decode([View].self, forKey: .views)) ?? fb.views
        mine = (try? c.decode([String].self, forKey: .mine)) ?? statuses.filter(\.mine).map(\.key)
        maxTags = (try? c.decode(Int.self, forKey: .maxTags)) ?? fb.maxTags
    }

    private static func ordered(_ dict: [String: String]?, like order: [Choice]) -> [Choice] {
        guard let dict else { return order }
        let known = order.compactMap { c in dict[c.key].map { Choice(key: c.key, label: $0) } }
        let extra = dict.keys.filter { k in !order.contains { $0.key == k } }.sorted().map { Choice(key: $0, label: dict[$0] ?? $0) }
        return known + extra
    }

    func status(_ key: String) -> Status {
        statuses.first { $0.key == key } ?? Status(key: key, label: key, icon: "", symbol: "circle", color: "#ffffff", guest: "new")
    }
    func statusRank(_ key: String) -> Int { statuses.firstIndex { $0.key == key } ?? statuses.count }
    /// Statuts proposés à la main (sans « chez Claude », posé par le serveur).
    var manualStatuses: [Status] { statuses.filter { !$0.technical } }
    func label(_ list: [Choice], _ key: String) -> String { list.first { $0.key == key }?.label ?? key }
    func inView(_ status: String, _ view: String) -> Bool {
        view == "all" || (views.first { $0.key == view }?.statuses.contains(status) ?? false)
    }

    static func priorityRank(_ key: String) -> Int { ["high": 0, "medium": 1, "low": 2][key] ?? 3 }

    /// Onglet de l'app d'où vient l'avis → zone par défaut (TAB_AREAS de app/feedback.py).
    static func tabArea(_ tab: String?) -> String {
        ["music": "music", "games": "games", "stats": "games", "events": "events", "chats": "chats", "account": "account",
         "host": "admin", "feedback": "admin"][tab ?? ""] ?? "general"
    }

    static let fallback = FeedbackMeta(
        statuses: [
            Status(key: "new", label: "À trier", icon: "📥", symbol: "tray", color: "#8fb4ff", guest: "new", mine: true),
            Status(key: "think", label: "Idée à mûrir", icon: "💭", symbol: "lightbulb", color: "#c9a8ff", guest: "new"),
            Status(key: "questions", label: "Questions à poser", icon: "❓", symbol: "questionmark.bubble", color: "#ffb46b",
                   guest: "new", mine: true),
            Status(key: "ready", label: "Prêt à faire", icon: "🟢", symbol: "flag.checkered", color: "#7be0a6", guest: "new"),
            Status(key: "blocked", label: "Bloqué / en attente", icon: "⏸️", symbol: "pause.circle", color: "#ff8a8a", guest: "progress"),
            Status(key: "progress", label: "En cours", icon: "🔧", symbol: "wrench.and.screwdriver", color: "#ffd27a", guest: "progress"),
            Status(key: "sent", label: "Chez Claude (CI)", icon: "🤖", symbol: "cpu", color: "#ffd27a", guest: "progress", technical: true),
            Status(key: "verify", label: "À vérifier", icon: "🧪", symbol: "checklist", color: "#ffd27a", guest: "progress", mine: true),
            Status(key: "done", label: "Terminé", icon: "✅", symbol: "checkmark.circle", color: "#7be0a6", guest: "done", adminOnly: true),
            Status(key: "declined", label: "Pas retenu", icon: "🚫", symbol: "xmark.circle", color: "#c9c3dc", guest: "declined", adminOnly: true),
            Status(key: "later", label: "Plus tard", icon: "💤", symbol: "moon.zzz", color: "#9aa0b4", guest: "new"),
        ],
        priorities: [Choice(key: "high", label: "🔴 Haute"), Choice(key: "medium", label: "🟠 Moyenne"), Choice(key: "low", label: "🟢 Basse")],
        areas: [Choice(key: "music", label: "🎵 Musique"), Choice(key: "games", label: "🎲 Jeux"), Choice(key: "events", label: "📅 Événements"),
                Choice(key: "chats", label: "💬 Discussions"), Choice(key: "account", label: "⚙️ Compte / Réglages"),
                Choice(key: "admin", label: "🛠️ Admin / Retours"), Choice(key: "tv", label: "📺 Apple TV / écran soirée"),
                Choice(key: "general", label: "🌐 Général")],
        platforms: [Choice(key: "web", label: "🌐 Web"), Choice(key: "iphone", label: "📱 iPhone"), Choice(key: "tv", label: "📺 Apple TV"),
                    Choice(key: "android", label: "🤖 Android")],
        efforts: [Choice(key: "xs", label: "⚡ 5 min"), Choice(key: "s", label: "🟢 Petit"), Choice(key: "m", label: "🟠 Moyen"),
                  Choice(key: "l", label: "🏗️ Gros chantier")],
        views: [View(key: "mine", label: "À moi", statuses: ["new", "questions", "verify"]),
                View(key: "claude", label: "Pour Claude", statuses: ["ready", "progress", "sent"]),
                View(key: "thinking", label: "En réflexion", statuses: ["think", "blocked", "later"]),
                View(key: "finished", label: "Terminés", statuses: ["done", "declined"]),
                View(key: "all", label: "Tout", statuses: [])],
        mine: ["new", "questions", "verify"], maxTags: 8)
}

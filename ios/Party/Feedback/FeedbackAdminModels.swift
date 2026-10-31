import Foundation

/// Retours reçus, côté hôte (GET/POST /api/admin/feedback) : mêmes états et mêmes mots que feedback-admin.js.
struct AdminFeedback: Decodable, Equatable {
    struct Claude: Decodable, Equatable {
        let state: String
        let number: Int?
        let url: String?
        let error: String?
        let migrations: [String]

        enum CodingKeys: String, CodingKey { case state, number, url, error, migrations }

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            state = try c.decodeIfPresent(String.self, forKey: .state) ?? ""
            number = try c.decodeIfPresent(Int.self, forKey: .number)
            url = try c.decodeIfPresent(String.self, forKey: .url)
            error = try c.decodeIfPresent(String.self, forKey: .error)
            migrations = try c.decodeIfPresent([String].self, forKey: .migrations) ?? []
        }

        var label: String {
            switch state {
            case "pending": return "🤖 Claude corrige"
            case "fixed": return "🧪 Corrigé sur develop"
            case "failed": return "⚠️ Échec de Claude"
            default: return ""
            }
        }
    }

    struct Item: Decodable, Equatable, Identifiable {
        let id: String
        let at: Double
        let kind: String
        let name: String
        let text: String
        let status: String
        let note: String
        let reply: String
        let game: String?
        let tab: String?
        let claude: Claude?
        /// Priorité posée par l'hôte : high, medium, low, ou "" (sans).
        let priority: String

        enum CodingKeys: String, CodingKey { case id, at, kind, name, text, status, note, reply, context, claude, priority }
        enum ContextKeys: String, CodingKey { case game, tab }

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            id = try c.decode(String.self, forKey: .id)
            at = try c.decodeIfPresent(Double.self, forKey: .at) ?? 0
            kind = try c.decodeIfPresent(String.self, forKey: .kind) ?? "other"
            name = try c.decodeIfPresent(String.self, forKey: .name) ?? "Invité"
            text = try c.decodeIfPresent(String.self, forKey: .text) ?? ""
            status = try c.decodeIfPresent(String.self, forKey: .status) ?? "new"
            note = try c.decodeIfPresent(String.self, forKey: .note) ?? ""
            reply = try c.decodeIfPresent(String.self, forKey: .reply) ?? ""
            claude = try c.decodeIfPresent(Claude.self, forKey: .claude)
            priority = try c.decodeIfPresent(String.self, forKey: .priority) ?? ""
            let context = try? c.nestedContainer(keyedBy: ContextKeys.self, forKey: .context)
            game = try context?.decodeIfPresent(String.self, forKey: .game)
            tab = try context?.decodeIfPresent(String.self, forKey: .tab)
        }

        var statusLabel: String { AdminFeedback.statusLabels[status] ?? "" }
        var priorityLabel: String { AdminFeedback.priorities.first { $0.id == priority }?.label ?? "" }
        /// Rang du tri « Priorité » : haute, moyenne, basse, puis sans.
        var priorityRank: Int { AdminFeedback.priorities.firstIndex { $0.id == priority } ?? AdminFeedback.priorities.count }
        var claudePending: Bool { claude?.state == "pending" }
        /// Boutons rapides proposés selon l'état, comme la page.
        var canStart: Bool { ["new", "done", "declined"].contains(status) }
        var canVerify: Bool { ["new", "progress", "sent"].contains(status) }
        var canFinish: Bool { ["new", "progress"].contains(status) }
        var canReopen: Bool { ["done", "declined"].contains(status) }
    }

    enum Filter: String, CaseIterable, Identifiable {
        case new, progress, verify, finished, all
        var id: String { rawValue }
        var label: String {
            switch self {
            case .new: return "À traiter"
            case .progress: return "En cours"
            case .verify: return "À vérifier"
            case .finished: return "Terminés"
            case .all: return "Tout"
            }
        }
        var statuses: Set<String> {
            switch self {
            case .new: return ["new"]
            case .progress: return ["progress", "sent"]
            case .verify: return ["verify"]
            case .finished: return ["done", "declined"]
            case .all: return []
            }
        }
        var empty: String {
            switch self {
            case .new: return "Rien à traiter pour l'instant 🎉"
            case .verify: return "Rien à vérifier."
            default: return "Aucun retour."
            }
        }
    }

    /// Priorités, de la plus haute à la plus basse (mêmes mots que feedback-admin.js).
    static let priorities: [(id: String, label: String)] = [("high", "🔴 Haute"), ("medium", "🟠 Moyenne"), ("low", "🟢 Basse")]

    enum Sort: String, CaseIterable, Identifiable {
        case recent, priority
        var id: String { rawValue }
        var label: String { self == .recent ? "🕒 Récents" : "🔥 Priorité" }
    }

    static let statusLabels = ["new": "À traiter", "progress": "🔧 En cours", "sent": "🤖 Chez Claude",
                               "verify": "🧪 À vérifier", "done": "✅ Terminé", "declined": "🚫 Pas retenu"]
    static let tabs = ["music": "Musique", "games": "Jeux", "events": "Événements"]
    static let minimumNote = 10  // MIN_CLAUDE_NOTE côté serveur

    let items: [Item]
    let kinds: [String: String]
    let claudeReady: Bool
    let games: [String: String]

    enum CodingKeys: String, CodingKey { case items, kinds, games, claudeReady = "claude_ready" }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        items = try c.decodeIfPresent([Item].self, forKey: .items) ?? []
        kinds = try c.decodeIfPresent([String: String].self, forKey: .kinds) ?? [:]
        claudeReady = try c.decodeIfPresent(Bool.self, forKey: .claudeReady) ?? false
        games = try c.decodeIfPresent([String: String].self, forKey: .games) ?? [:]
    }

    func shown(_ filter: Filter, sort: Sort = .recent) -> [Item] {
        let list = filter == .all ? items : items.filter { filter.statuses.contains($0.status) }
        guard sort == .priority else { return list }
        return list.enumerated().sorted { ($0.element.priorityRank, $0.offset) < ($1.element.priorityRank, $1.offset) }.map(\.element)
    }

    func count(_ filter: Filter) -> Int { filter == .all ? items.count : shown(filter).count }

    /// Pastille de l'onglet : à traiter + à vérifier.
    var pending: Int { items.filter { ["new", "verify"].contains($0.status) }.count }

    /// « 💡 Idée · Léa · 29 oct. 21:14 · jeu : Undercover »
    func meta(_ item: Item) -> String {
        var parts = [kinds[item.kind] ?? item.kind, item.name,
                     Date(timeIntervalSince1970: item.at).formatted(.dateTime.day().month(.abbreviated).hour().minute()
                        .locale(Locale(identifier: "fr_CH")))]
        if let game = item.game { parts.append("jeu : \(games[game] ?? game)") }
        else if let tab = item.tab { parts.append("depuis \(Self.tabs[tab] ?? tab)") }
        return parts.joined(separator: " · ")
    }
}

struct FeedbackPrompt: Decodable { let prompt: String }

extension PartyAPI {
    func adminFeedback() async throws -> AdminFeedback { try await get("/api/admin/feedback", query: [:]) }

    func adminFeedbackAction(_ id: String, _ action: String, note: String = "", reply: String = "") async throws -> AdminFeedback {
        try await postDecoding("/api/admin/feedback", body: ["ids": [id], "action": action, "note": note, "reply": reply])
    }

    func adminFeedbackPriority(_ id: String, _ priority: String) async throws -> AdminFeedback {
        try await postDecoding("/api/admin/feedback", body: ["ids": [id], "action": "priority", "priority": priority])
    }

    func adminFeedbackPrompt(_ id: String) async throws -> String {
        let encoded = id.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? id
        let result: FeedbackPrompt = try await get("/api/admin/feedback/\(encoded)/prompt", query: [:])
        return result.prompt
    }

    func adminFeedbackToClaude(_ id: String) async throws -> AdminFeedback {
        let encoded = id.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? id
        return try await postDecoding("/api/admin/feedback/\(encoded)/claude", body: [:])
    }
}

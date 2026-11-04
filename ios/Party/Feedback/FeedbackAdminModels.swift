import Foundation

/// Retours reçus, côté hôte (GET/POST /api/admin/feedback) : mêmes états et mêmes mots que feedback-admin.js.
/// Statuts, zones, plateformes, efforts et vues viennent du serveur (`meta`, STATUSES de app/feedback.py) ;
/// `FeedbackMeta.fallback` sert de secours si un serveur plus ancien ne les envoie pas.
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

    /// Message du fil admin ↔ Claude.
    struct Comment: Decodable, Equatable, Identifiable {
        let id: String
        let at: Double
        let by: String
        let text: String

        enum CodingKeys: String, CodingKey { case id, at, by, text }

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            at = try c.decodeIfPresent(Double.self, forKey: .at) ?? 0
            id = try c.decodeIfPresent(String.self, forKey: .id) ?? "\(at)"
            by = try c.decodeIfPresent(String.self, forKey: .by) ?? "admin"
            text = try c.decodeIfPresent(String.self, forKey: .text) ?? ""
        }

        var author: String { by == "claude" ? "Claude 🤖" : "Toi" }
    }

    /// Qui a changé quoi (from / to : texte ou liste ; absents pour la note et le mot, non recopiés).
    struct Change: Decodable, Equatable {
        let at: Double
        let by: String
        let field: String
        let from: String?
        let to: String?

        enum CodingKeys: String, CodingKey { case at, by, field, from, to }

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            at = try c.decodeIfPresent(Double.self, forKey: .at) ?? 0
            by = try c.decodeIfPresent(String.self, forKey: .by) ?? "admin"
            field = try c.decodeIfPresent(String.self, forKey: .field) ?? ""
            from = Self.text(c, .from)
            to = Self.text(c, .to)
        }

        private static func text(_ c: KeyedDecodingContainer<CodingKeys>, _ key: CodingKeys) -> String? {
            if let s = try? c.decodeIfPresent(String.self, forKey: key) { return s }
            if let list = try? c.decodeIfPresent([String].self, forKey: key) { return list.joined(separator: ", ") }
            return nil
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
        /// « Test » : envoyé depuis le site de test (une seule liste pour les deux sites).
        let site: String?
        let claude: Claude?
        /// Priorité posée par l'hôte : high, medium, low, ou "" (sans).
        let priority: String
        /// Classement de l'hôte (absent des anciens avis : valeurs par défaut).
        let area: String
        let platforms: [String]
        let effort: String
        let tags: [String]
        let related: [String]
        let duplicateOf: String
        let blockedBy: String
        let comments: [Comment]
        let history: [Change]
        /// Version structurée par l'IA (context.ai, app/ai_feedback.py), sous le texte d'origine ; nil sans titre.
        let ai: FeedbackAI.Draft?

        enum CodingKeys: String, CodingKey {
            case id, at, kind, name, text, status, note, reply, context, claude, priority, area, platforms, effort, tags,
                 related, comments, history, duplicateOf = "duplicate_of", blockedBy = "blocked_by"
        }
        enum ContextKeys: String, CodingKey { case game, tab, site, ai }

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
            site = try context?.decodeIfPresent(String.self, forKey: .site)
            ai = (try? context?.decodeIfPresent(StoredAI.self, forKey: .ai))?.draft
            area = (try? c.decodeIfPresent(String.self, forKey: .area)) ?? nil ?? (game != nil ? "games" : FeedbackMeta.tabArea(tab))
            platforms = (try? c.decodeIfPresent([String].self, forKey: .platforms)) ?? nil ?? []
            effort = (try? c.decodeIfPresent(String.self, forKey: .effort)) ?? nil ?? ""
            tags = (try? c.decodeIfPresent([String].self, forKey: .tags)) ?? nil ?? []
            related = (try? c.decodeIfPresent([String].self, forKey: .related)) ?? nil ?? []
            duplicateOf = (try? c.decodeIfPresent(String.self, forKey: .duplicateOf)) ?? nil ?? ""
            blockedBy = (try? c.decodeIfPresent(String.self, forKey: .blockedBy)) ?? nil ?? ""
            comments = (try? c.decodeIfPresent([Comment].self, forKey: .comments)) ?? nil ?? []
            history = (try? c.decodeIfPresent([Change].self, forKey: .history)) ?? nil ?? []
        }

        var claudePending: Bool { claude?.state == "pending" }
        var finished: Bool { ["done", "declined"].contains(status) }
    }

    /// Tris de la liste (mêmes que la page).
    enum Sort: String, CaseIterable, Identifiable {
        case recent, priority, status, area, effort, oldest
        var id: String { rawValue }
        var label: String {
            switch self {
            case .recent: return "🕒 Récents"
            case .priority: return "🔥 Priorité"
            case .status: return "🏷️ Statut"
            case .area: return "🧭 Zone"
            case .effort: return "⏱️ Effort"
            case .oldest: return "⌛ Plus ancien en attente"
            }
        }
    }

    /// Filtres fins, en plus de la vue : "" = tous ; "none" = sans effort / sans priorité.
    struct Filters: Equatable {
        var status = ""
        var area = ""
        var platform = ""
        var effort = ""
        var priority = ""
        var tag = ""
        var search = ""

        var isEmpty: Bool { self == Filters() }
    }

    static let tabs = ["music": "Musique", "games": "Jeux", "events": "Événements"]
    static let minimumNote = 10  // MIN_CLAUDE_NOTE côté serveur

    let items: [Item]
    let kinds: [String: String]
    let claudeReady: Bool
    let games: [String: String]
    let meta: FeedbackMeta

    enum CodingKeys: String, CodingKey { case items, kinds, games, meta, claudeReady = "claude_ready" }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        items = try c.decodeIfPresent([Item].self, forKey: .items) ?? []
        kinds = try c.decodeIfPresent([String: String].self, forKey: .kinds) ?? [:]
        claudeReady = try c.decodeIfPresent(Bool.self, forKey: .claudeReady) ?? false
        games = try c.decodeIfPresent([String: String].self, forKey: .games) ?? [:]
        meta = (try? c.decodeIfPresent(FeedbackMeta.self, forKey: .meta)) ?? nil ?? .fallback
    }

    func shown(view: String, filters: Filters = Filters(), sort: Sort = .recent) -> [Item] {
        let list = items.filter { meta.inView($0.status, view) && matches($0, filters) }
        return sorted(list, by: sort)
    }

    func count(view: String) -> Int { items.filter { meta.inView($0.status, view) }.count }

    /// Pastille de l'onglet : ce qui attend une action de l'hôte (à trier, questions à poser, à vérifier).
    var pending: Int { items.filter { meta.mine.contains($0.status) }.count }

    var allTags: [String] { Array(Set(items.flatMap(\.tags))).sorted() }

    private func matches(_ i: Item, _ f: Filters) -> Bool {
        let q = f.search.trimmingCharacters(in: .whitespaces).lowercased()
        return (f.status.isEmpty || i.status == f.status) && (f.area.isEmpty || i.area == f.area)
            && (f.platform.isEmpty || i.platforms.contains(f.platform))
            && (f.effort.isEmpty || (i.effort.isEmpty ? "none" : i.effort) == f.effort)
            && (f.priority.isEmpty || (i.priority.isEmpty ? "none" : i.priority) == f.priority)
            && (f.tag.isEmpty || i.tags.contains { $0.lowercased() == f.tag.lowercased() })
            && (q.isEmpty || ([i.text, i.ai?.title ?? "", i.note, i.name, i.id, i.reply] + i.tags).contains { $0.lowercased().contains(q) })
    }

    private func sorted(_ list: [Item], by sort: Sort) -> [Item] {
        let prio = { (i: Item) in FeedbackMeta.priorityRank(i.priority) }
        let rank: (Item) -> [Double]
        switch sort {
        case .recent: rank = { [-$0.at] }
        case .priority: rank = { [Double(prio($0)), -$0.at] }
        case .status: rank = { [Double(meta.statusRank($0.status)), -$0.at] }
        case .area: rank = { i in [Double(meta.areas.firstIndex { $0.key == i.area } ?? 99), -i.at] }
        case .effort: rank = { i in [Double(meta.efforts.firstIndex { $0.key == i.effort } ?? 9), Double(prio(i))] }
        case .oldest: rank = { [$0.finished ? 1 : 0, $0.at] }
        }
        return list.sorted { rank($0).lexicographicallyPrecedes(rank($1)) }
    }

    /// « 💡 Idée · Léa · 29 oct. 21:14 · jeu : Undercover »
    func meta(_ item: Item) -> String {
        var parts = [kinds[item.kind] ?? item.kind, item.name,
                     Date(timeIntervalSince1970: item.at).formatted(.dateTime.day().month(.abbreviated).hour().minute()
                        .locale(Locale(identifier: "fr_CH")))]
        if let game = item.game { parts.append("jeu : \(games[game] ?? game)") }
        else if let tab = item.tab { parts.append("depuis \(Self.tabs[tab] ?? tab)") }
        if item.site == "Test" { parts.append("🧪 site de test") }
        return parts.joined(separator: " · ")
    }
}

/// Champs d'un avis à créer ou à classer (formulaire natif) → corps JSON de « edit » / « new ».
struct FeedbackDraft: Equatable {
    var status = "new"
    var priority = ""
    var area = ""  // "" à la création : la zone est déduite de l'onglet par le serveur
    var platforms: Set<String> = []
    var effort = ""
    var tags = ""
    var note = ""
    var reply = ""
    var related = ""
    var duplicateOf = ""
    var blockedBy = ""

    init() {}

    init(_ item: AdminFeedback.Item) {
        status = item.status
        priority = item.priority
        area = item.area
        platforms = Set(item.platforms)
        effort = item.effort
        tags = item.tags.joined(separator: ", ")
        note = item.note
        reply = item.reply
        related = item.related.joined(separator: ", ")
        duplicateOf = item.duplicateOf
        blockedBy = item.blockedBy
    }

    static func list(_ text: String) -> [String] {
        text.split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces).trimmingCharacters(in: CharacterSet(charactersIn: "#")) }
            .filter { !$0.isEmpty }
    }

    /// Champs de classement, plateformes dans l'ordre de `meta`.
    func fields(_ meta: FeedbackMeta, creating: Bool = false) -> [String: Any] {
        var out: [String: Any] = ["status": status, "priority": priority, "effort": effort,
                                  "platforms": meta.platforms.map(\.key).filter(platforms.contains), "tags": Self.list(tags)]
        if !area.isEmpty { out["area"] = area }
        if !note.isEmpty || !creating { out["note"] = note }
        if !creating {
            out["reply"] = reply
            out["related"] = Self.list(related)
            out["duplicate_of"] = Self.list(duplicateOf).first ?? ""
            out["blocked_by"] = Self.list(blockedBy).first ?? ""
        }
        return out
    }

    /// Seulement ce qui a changé par rapport à l'avis (le serveur garde l'historique de chaque changement).
    func changes(from item: AdminFeedback.Item, _ meta: FeedbackMeta) -> [String: Any] {
        let before = FeedbackDraft(item).fields(meta)
        return fields(meta).filter { key, value in
            !NSDictionary(dictionary: [key: value]).isEqual(to: [key: before[key] ?? ""])
        }
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

    /// Action générique « edit » : statut, priorité, zone, plateformes, effort, étiquettes, liens, note, mot.
    func adminFeedbackEdit(_ ids: [String], fields: [String: Any]) async throws -> AdminFeedback {
        try await postDecoding("/api/admin/feedback", body: ["ids": ids, "action": "edit", "fields": fields])
    }

    func adminFeedbackComment(_ id: String, text: String) async throws -> AdminFeedback {
        try await postDecoding("/api/admin/feedback", body: ["ids": [id], "action": "comment", "text": text])
    }

    /// Avis écrit par l'hôte, classé dès la création ; renvoie la liste à jour (avec l'avis créé).
    func adminFeedbackNew(kind: String, text: String, name: String, guestID: String, tab: String?,
                          fields: [String: Any]) async throws -> AdminFeedback {
        var context: [String: Any] = [:]
        if let tab { context["tab"] = tab }
        return try await postDecoding("/api/admin/feedback/new", body: ["kind": kind, "text": text, "name": name,
                                                                          "guest_id": guestID, "context": context, "fields": fields])
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

/// context.ai tel que gardé par le serveur : champs absents ou d'un autre type → vides (avis anciens, autre version).
struct StoredAI: Decodable {
    let draft: FeedbackAI.Draft?

    private enum Keys: String, CodingKey {
        case kind, area, game, title, description, steps, expected, actual, need, proposal, device
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: Keys.self)
        let text = { (key: Keys) in ((try? c.decodeIfPresent(String.self, forKey: key)) ?? nil) ?? "" }
        let title = text(.title)
        guard !title.isEmpty else {
            draft = nil
            return
        }
        let device = text(.device)
        draft = FeedbackAI.Draft(kind: text(.kind), area: text(.area), game: text(.game), title: title,
                                 description: text(.description),
                                 steps: ((try? c.decodeIfPresent([String].self, forKey: .steps)) ?? nil) ?? [],
                                 expected: text(.expected), actual: text(.actual), need: text(.need),
                                 proposal: text(.proposal), device: device.isEmpty ? nil : device)
    }
}

extension FeedbackAI.Draft {
    /// « 💡 Idée · 🎵 Musique » : type et zone proposés par l'IA (comme la page des retours).
    var kindAndArea: String {
        [FeedbackAI.kinds[kind], FeedbackAI.areas[area]].compactMap { $0 }.joined(separator: " · ")
    }
}

import Foundation

/// Profil Méninges du compte (POST /api/brain/me), pour son seul titulaire. Décodage tolérant : un champ absent ou
/// null (percentile, progrès du mois, ancien serveur) donne une valeur neutre au lieu de faire échouer tout l'écran.
struct BrainStats: Decodable, Equatable {
    struct Domain: Decodable, Equatable {
        let index: Int
        let played: Int

        enum CodingKeys: String, CodingKey { case index, played }

        init(index: Int, played: Int) {
            self.index = index
            self.played = played
        }

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            index = c.flexibleInt(.index) ?? 0
            played = c.flexibleInt(.played) ?? 0
        }
    }

    struct Game: Decodable, Equatable {
        let index: Int
        let best: Int
        let plays: Int
        let lastLevel: Int

        enum CodingKeys: String, CodingKey { case index, best, plays, lastLevel = "last_level" }

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            index = c.flexibleInt(.index) ?? 0
            best = c.flexibleInt(.best) ?? 0
            plays = c.flexibleInt(.plays) ?? 0
            lastLevel = c.flexibleInt(.lastLevel) ?? 0
        }
    }

    struct Streak: Decodable, Equatable {
        let current: Int
        let best: Int

        enum CodingKeys: String, CodingKey { case current, best }

        init(current: Int = 0, best: Int = 0) {
            self.current = current
            self.best = best
        }

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            current = c.flexibleInt(.current) ?? 0
            best = c.flexibleInt(.best) ?? 0
        }
    }

    struct Day: Decodable, Equatable, Identifiable {
        let day: String
        let temperature: Int

        var id: String { day }
        /// « 2026-11-02 » → minuit à Zurich (le serveur compte les jours en Europe/Zurich).
        var date: Date? { Self.parser.date(from: day) }

        enum CodingKeys: String, CodingKey { case day, temperature }

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            day = (try? c.decodeIfPresent(String.self, forKey: .day)) ?? ""
            temperature = c.flexibleInt(.temperature) ?? 0
        }

        private static let parser: DateFormatter = {
            let f = DateFormatter()
            f.calendar = Calendar(identifier: .gregorian)
            f.locale = Locale(identifier: "en_US_POSIX")
            f.timeZone = TimeZone(identifier: "Europe/Zurich")
            f.dateFormat = "yyyy-MM-dd"
            return f
        }()
    }

    struct Balance: Decodable, Equatable {
        let speed: Int
        let accuracy: Int

        enum CodingKeys: String, CodingKey { case speed, accuracy }

        init(speed: Int = 0, accuracy: Int = 0) {
            self.speed = speed
            self.accuracy = accuracy
        }

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            speed = c.flexibleInt(.speed) ?? 0
            accuracy = c.flexibleInt(.accuracy) ?? 0
        }
    }

    let name: String
    let temperature: Int
    let domains: [String: Domain]
    let games: [String: Game]
    let streak: Streak
    let history: [Day]
    let strengths: [String]
    let weaknesses: [String]
    let insight: String
    let percentile: Int?
    let speedVsAccuracy: Balance
    let monthProgress: Int?

    enum CodingKeys: String, CodingKey {
        case name, temperature, domains, games, streak, history, strengths, weaknesses, insight, percentile
        case speedVsAccuracy = "speed_vs_accuracy", monthProgress = "month_progress"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        name = (try? c.decodeIfPresent(String.self, forKey: .name)) ?? "Méninges"
        temperature = c.flexibleInt(.temperature) ?? 0
        domains = (try? c.decodeIfPresent([String: Domain].self, forKey: .domains)) ?? [:]
        games = (try? c.decodeIfPresent([String: Game].self, forKey: .games)) ?? [:]
        streak = (try? c.decodeIfPresent(Streak.self, forKey: .streak)) ?? Streak()
        history = (try? c.decodeIfPresent([Day].self, forKey: .history)) ?? []
        strengths = (try? c.decodeIfPresent([String].self, forKey: .strengths)) ?? []
        weaknesses = (try? c.decodeIfPresent([String].self, forKey: .weaknesses)) ?? []
        insight = (try? c.decodeIfPresent(String.self, forKey: .insight)) ?? ""
        percentile = c.flexibleInt(.percentile)
        speedVsAccuracy = (try? c.decodeIfPresent(Balance.self, forKey: .speedVsAccuracy)) ?? Balance()
        monthProgress = c.flexibleInt(.monthProgress)
    }

    /// Parties jouées, tous jeux confondus (0 : écran « jamais joué »).
    var plays: Int { games.values.reduce(0) { $0 + $1.plays } }

    /// Jours de l'évolution qui ont une date lisible, dans l'ordre.
    var curve: [Day] { history.filter { $0.date != nil } }

    /// Jeux déjà joués, du meilleur indice au plus faible.
    var playedGames: [(id: String, game: Game)] {
        games.filter { $0.value.plays > 0 }
            .map { (id: $0.key, game: $0.value) }
            .sorted { $0.game.index != $1.game.index ? $0.game.index > $1.game.index : $0.id < $1.id }
    }

    /// 1234 → « 1 234 °M », comme la page (séparateur de milliers : espace).
    static func degrees(_ value: Int) -> String {
        let digits = String(abs(value))
        var out = ""
        for (i, ch) in digits.enumerated() {
            if i > 0, (digits.count - i) % 3 == 0 { out += "\u{202F}" }
            out.append(ch)
        }
        return (value < 0 ? "−" : "") + out + " °M"
    }
}

/// Classement Méninges entre membres (POST /api/brain/compare).
struct BrainBoard: Decodable, Equatable {
    struct Player: Decodable, Equatable, Identifiable {
        let id: String
        let name: String
        let temperature: Int
        let me: Bool

        enum CodingKeys: String, CodingKey { case id, name, temperature, me }

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            name = (try? c.decodeIfPresent(String.self, forKey: .name)) ?? "?"
            id = (try? c.decodeIfPresent(String.self, forKey: .id)) ?? name
            temperature = c.flexibleInt(.temperature) ?? 0
            me = (try? c.decodeIfPresent(Bool.self, forKey: .me)) ?? false
        }
    }

    let board: [Player]
    let rank: Int?
    let players: Int
    let percentile: Int?

    enum CodingKeys: String, CodingKey { case board, rank, players, percentile }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        board = (try? c.decodeIfPresent([Player].self, forKey: .board)) ?? []
        rank = c.flexibleInt(.rank)
        players = c.flexibleInt(.players) ?? board.count
        percentile = c.flexibleInt(.percentile)
    }

    /// Rang affiché à chaque ligne : ex aequo au même rang (même Température), comme le calcul du serveur.
    func rank(of player: Player) -> Int { board.filter { $0.temperature > player.temperature }.count + 1 }
}

/// Libellés des domaines et des jeux (GET /api/brain/catalog). Repli intégré pour les domaines si le serveur ne répond pas.
struct BrainCatalog: Decodable, Equatable {
    struct Domain: Decodable, Equatable, Identifiable {
        let id: String
        let label: String
        let icon: String
        let inTemperature: Bool

        enum CodingKeys: String, CodingKey { case id, label, icon, inTemperature = "in_temperature" }

        init(id: String, label: String, icon: String, inTemperature: Bool) {
            self.id = id
            self.label = label
            self.icon = icon
            self.inTemperature = inTemperature
        }

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            id = try c.decode(String.self, forKey: .id)
            label = (try? c.decodeIfPresent(String.self, forKey: .label)) ?? id
            icon = (try? c.decodeIfPresent(String.self, forKey: .icon)) ?? "🧠"
            inTemperature = (try? c.decodeIfPresent(Bool.self, forKey: .inTemperature)) ?? true
        }

        /// Mêmes couleurs que la page (app/static/brain/core.js, DOMAINS).
        var hex: String {
            ["vitesse": "#4f8cff", "memoire": "#b07cff", "attention": "#2ee6c5",
             "flexibilite": "#ff6fb5", "logique": "#8be36b", "calcul": "#ff7a7a"][id] ?? "#b07cff"
        }
    }

    struct Game: Decodable, Equatable, Identifiable {
        let id: String
        let name: String
        let domain: String
    }

    let domains: [Domain]
    let games: [Game]

    enum CodingKeys: String, CodingKey { case domains, games }

    init(domains: [Domain], games: [Game]) {
        self.domains = domains
        self.games = games
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        domains = (try? c.decodeIfPresent([Domain].self, forKey: .domains)) ?? Self.fallback.domains
        games = (try? c.decodeIfPresent([Game].self, forKey: .games)) ?? []
    }

    /// Les 6 domaines de app/brain.py (DOMAINS), dans le même ordre.
    static let fallback = BrainCatalog(domains: [
        Domain(id: "vitesse", label: "Vitesse", icon: "⚡", inTemperature: true),
        Domain(id: "memoire", label: "Mémoire", icon: "🧠", inTemperature: true),
        Domain(id: "attention", label: "Attention", icon: "🎯", inTemperature: true),
        Domain(id: "flexibilite", label: "Flexibilité", icon: "🔀", inTemperature: true),
        Domain(id: "logique", label: "Logique", icon: "🧩", inTemperature: true),
        Domain(id: "calcul", label: "Calcul", icon: "➗", inTemperature: false),
    ], games: [])

    func domain(_ id: String) -> Domain {
        domains.first { $0.id == id } ?? Self.fallback.domains.first { $0.id == id }
            ?? Domain(id: id, label: id.capitalized, icon: "🧠", inTemperature: false)
    }

    func game(_ id: String) -> Game? { games.first { $0.id == id } }
}

private extension KeyedDecodingContainer {
    /// Entier lu tel quel ou depuis un nombre à virgule (la base peut rendre 73.0) ; nil si absent, null ou illisible.
    func flexibleInt(_ key: Key) -> Int? {
        if let v = try? decodeIfPresent(Int.self, forKey: key) { return v }
        if let v = try? decodeIfPresent(Double.self, forKey: key), v.isFinite { return Int(v.rounded()) }
        return nil
    }
}

extension PartyAPI {
    func brainStats(token: String) async throws -> BrainStats {
        try await postDecoding("/api/brain/me", body: ["token": token])
    }

    func brainBoard(token: String) async throws -> BrainBoard {
        try await postDecoding("/api/brain/compare", body: ["token": token])
    }

    func brainCatalog() async throws -> BrainCatalog {
        try await get("/api/brain/catalog", query: [:])
    }
}

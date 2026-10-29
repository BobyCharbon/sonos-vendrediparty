import Foundation

/// Invités et messages, admin de la soirée : ce que /api/admin/state donne en plus de la musique.
struct HostPeople: Decodable, Equatable {
    struct Message: Decodable, Equatable, Identifiable {
        let id: String
        let name: String
        let text: String
        let at: Double
        let read: Bool
        let reply: String?
        let replyAt: Double?

        enum CodingKeys: String, CodingKey { case id, name, text, at, read, reply, replyAt = "reply_at" }

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            id = try c.decode(String.self, forKey: .id)
            name = try c.decodeIfPresent(String.self, forKey: .name) ?? "Invité"
            text = try c.decodeIfPresent(String.self, forKey: .text) ?? ""
            at = try c.decodeIfPresent(Double.self, forKey: .at) ?? 0
            read = try c.decodeIfPresent(Bool.self, forKey: .read) ?? false
            reply = try c.decodeIfPresent(String.self, forKey: .reply)
            replyAt = try c.decodeIfPresent(Double.self, forKey: .replyAt)
        }
    }

    /// Bloqué ou banni (soirée en cours ou précédentes) ; until 0 : banni sans limite.
    struct Ban: Decodable, Equatable, Identifiable {
        let guestID: String
        let name: String
        let until: Double
        var id: String { guestID }

        enum CodingKeys: String, CodingKey { case name, until, guestID = "guest_id" }

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            guestID = try c.decode(String.self, forKey: .guestID)
            name = try c.decodeIfPresent(String.self, forKey: .name) ?? "Invité"
            until = try c.decodeIfPresent(Double.self, forKey: .until) ?? 0
        }

        var label: String {
            until == 0 ? "⛔ banni" : "⏸ bloqué jusqu'à \(Date(timeIntervalSince1970: until).formatted(date: .omitted, time: .shortened))"
        }
    }

    struct Game: Decodable, Equatable, Identifiable {
        let code: String
        let name: String
        let phase: String
        let players: [String]
        let host: String
        let elapsed: Double
        var id: String { code }

        enum CodingKeys: String, CodingKey { case code, name, phase, players, host, elapsed }

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            code = try c.decode(String.self, forKey: .code)
            name = try c.decodeIfPresent(String.self, forKey: .name) ?? "Partie"
            phase = try c.decodeIfPresent(String.self, forKey: .phase) ?? ""
            players = try c.decodeIfPresent([String].self, forKey: .players) ?? []
            host = try c.decodeIfPresent(String.self, forKey: .host) ?? ""
            elapsed = try c.decodeIfPresent(Double.self, forKey: .elapsed) ?? 0
        }

        var summary: String {
            let minutes = max(1, Int(elapsed / 60))
            let names = players.isEmpty ? "personne" : players.joined(separator: ", ")
            return "Code \(code) · lancée par \(host.isEmpty ? "?" : host) · depuis \(minutes) min · \(names)"
        }
    }

    let messages: [Message]
    let bans: [Ban]
    let games: [Game]

    enum CodingKeys: String, CodingKey { case messages, bans, games }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        messages = try c.decodeIfPresent([Message].self, forKey: .messages) ?? []
        bans = try c.decodeIfPresent([Ban].self, forKey: .bans) ?? []
        games = try c.decodeIfPresent([Game].self, forKey: .games) ?? []
    }

    var unread: Int { messages.filter { !$0.read }.count }

    /// Bannis absents de la liste des invités de la soirée (soirées précédentes).
    func otherBans(listed guests: [AdminState.Guest], active: Bool) -> [Ban] {
        let ids = Set(active ? guests.map(\.guestID) : [])
        return bans.filter { !ids.contains($0.guestID) }
    }
}

/// Journal de la soirée (GET /api/admin/audit) : qui a fait quoi dans l'admin. Lecture seule.
struct PartyJournal: Decodable {
    struct Entry: Decodable, Identifiable, Equatable {
        struct Target: Decodable, Equatable {
            let id: String?
            let name: String?
        }

        let id: String
        let at: Double
        let actor: String
        let action: String
        let target: Target?
        let details: [String: JSONValue]?
        let ip: String?

        private static let labels = [
            "admin.login": "s'est connecté à l'admin", "admin.login_failed": "code admin incorrect",
            "admin.denied": "accès admin refusé (compte sans droits)", "admin.logout": "s'est déconnecté de l'admin",
            "admin.pin": "a changé le code de la soirée", "admin.ban": "a bloqué", "admin.unban": "a débloqué",
            "admin.rename": "a renommé", "admin.kick": "a déconnecté", "admin.purge": "a retiré les titres de",
            "admin.stop": "a arrêté la soirée", "admin.close_game": "a fermé la partie",
            "account.link": "s'est connecté à son compte",
        ]

        /// « Boby a bloqué Tom (10 min) », comme audit-admin.js.
        var text: String {
            var out = "\(actor) \(Self.labels[action] ?? action)"
            if let target, action != "account.link", !["admin.login", "admin.denied"].contains(action) {
                out += " \(target.name ?? target.id ?? "")"
            }
            switch (action, details?["to"], details?["minutes"], details?["method"]) {
            case ("admin.rename", .string(let to)?, _, _): out += " → « \(to) »"
            case ("admin.ban", _, .string(let m)?, _): out += m == "sans limite" ? " (sans limite)" : " (\(m) min)"
            case ("admin.ban", _, .number(let m)?, _): out += " (\(Int(m)) min)"
            case ("admin.login", _, _, .string(let method)?): out += " (\(method))"
            default: break
            }
            return out
        }

        var when: String {
            Date(timeIntervalSince1970: at).formatted(.dateTime.day().month(.twoDigits).hour().minute()
                .locale(Locale(identifier: "fr_CH")))
        }
    }

    let entries: [Entry]
}

extension PartyAPI {
    func adminMessages(_ action: String, ids: [String]?) async throws -> AdminState {
        try await postDecoding("/api/admin/messages", body: ["ids": ids.map { $0 as Any } ?? NSNull(), "action": action])
    }

    func adminReply(id: String, text: String) async throws -> AdminState {
        try await postDecoding("/api/admin/messages/reply", body: ["id": id, "text": text])
    }

    func adminCloseGame(code: String) async throws -> AdminState {
        try await postDecoding("/api/admin/games/close", body: ["guest_id": "admin-console", "action": "end", "target": code])
    }

    func adminJournal(before: String?, limit: Int = 50) async throws -> PartyJournal {
        var query = ["limit": "\(limit)"]
        if let before { query["before"] = before }
        return try await get("/api/admin/audit", query: query)
    }
}

import Foundation

/// Numéro saisi à la connexion → format international (+41…), comme le module web (libphonenumber) pour les cas courants :
/// Suisse et France avec ou sans le zéro initial, ou tout numéro commençant par + ou 00.
enum LoginPhone {
    enum Country: String, CaseIterable, Identifiable {
        case ch, fr, other

        var id: String { rawValue }
        var label: String {
            switch self {
            case .ch: return "Suisse +41"
            case .fr: return "France +33"
            case .other: return "Autre pays"
            }
        }
        var placeholder: String {
            switch self {
            case .ch: return "079 123 45 67"
            case .fr: return "06 12 34 56 78"
            case .other: return "+32 470 12 34 56"
            }
        }
    }

    /// nil : numéro incomplet ou invalide pour ce pays.
    static func parse(_ raw: String, country: Country) -> String? {
        var text = raw.trimmingCharacters(in: .whitespaces)
        guard !text.isEmpty, text.allSatisfy({ $0.isNumber || " +().-".contains($0) }) else { return nil }
        if text.hasPrefix("00") { text = "+" + text.dropFirst(2) }
        let digits = text.filter(\.isNumber)
        if text.hasPrefix("+") {
            return (8...15).contains(digits.count) && digits.first != "0" ? "+" + digits : nil
        }
        let local = digits.hasPrefix("0") ? String(digits.dropFirst()) : digits
        switch country {
        case .ch: return local.count == 9 && local.first != "0" ? "+41" + local : nil
        case .fr: return local.count == 9 && local.first != "0" ? "+33" + local : nil
        case .other: return nil  // indicatif obligatoire
        }
    }

    /// +41790000003 → +41 79 000 00 03 (lecture plus facile du numéro où le code est parti).
    static func pretty(_ e164: String) -> String {
        guard e164.hasPrefix("+41") || e164.hasPrefix("+33"), e164.count == 12 else { return e164 }
        let d = Array(e164.dropFirst(3))
        let groups = e164.hasPrefix("+41") ? [2, 3, 2, 2] : [1, 2, 2, 2, 2]
        var out = String(e164.prefix(3)), i = 0
        for size in groups {
            out += " " + String(d[i..<min(i + size, d.count)])
            i += size
        }
        return out
    }
}

/// Session rendue par POST /api/account/verify : rangée telle quelle là où la page (supabase-js) la lit.
struct AccountSignIn: Decodable {
    let storageKey: String
    let sessionJSON: String

    enum CodingKeys: String, CodingKey { case session, storageKey = "storage_key" }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        storageKey = try c.decode(String.self, forKey: .storageKey)
        let session = try c.decode(JSONValue.self, forKey: .session)
        sessionJSON = String(decoding: try JSONEncoder().encode(session), as: UTF8.self)
    }
}

/// Valeur JSON quelconque (la session Supabase est rendue intacte à la page).
enum JSONValue: Codable, Equatable {
    case string(String), number(Double), bool(Bool), object([String: JSONValue]), array([JSONValue]), null

    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { self = .null }
        else if let v = try? c.decode(Bool.self) { self = .bool(v) }
        else if let v = try? c.decode(Double.self) { self = .number(v) }
        else if let v = try? c.decode(String.self) { self = .string(v) }
        else if let v = try? c.decode([JSONValue].self) { self = .array(v) }
        else { self = .object(try c.decode([String: JSONValue].self)) }
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        switch self {
        case .string(let v): try c.encode(v)
        case .number(let v):
            // Entiers (expires_at…) gardés entiers : supabase-js compare des secondes.
            if v == v.rounded(), abs(v) < 1e15 { try c.encode(Int64(v)) } else { try c.encode(v) }
        case .bool(let v): try c.encode(v)
        case .object(let v): try c.encode(v)
        case .array(let v): try c.encode(v)
        case .null: try c.encodeNil()
        }
    }
}

/// Annonces admin (POST /api/account/announcements).
struct AnnouncementPage: Decodable, Equatable {
    struct Announcement: Decodable, Equatable, Identifiable {
        let id: String
        let title: String
        let body: String
        let createdAt: String

        enum CodingKeys: String, CodingKey { case id, title, body, createdAt = "created_at" }
    }

    let announcements: [Announcement]
    let more: Bool
}

/// Stats Purify Test du compte (POST /api/purity/me), pour son seul titulaire.
struct PurityStats: Decodable, Equatable {
    struct Category: Decodable, Equatable, Identifiable {
        let id: String
        let label: String
        let emoji: String
        let yes: Int
        let total: Int
        let pct: Int
    }

    let plays: Int
    let best: Int
    let last: Int
    let lastAt: Double
    let categories: [Category]

    enum CodingKeys: String, CodingKey { case plays, best, last, categories, lastAt = "last_at" }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        plays = try c.decodeIfPresent(Int.self, forKey: .plays) ?? 0
        best = try c.decodeIfPresent(Int.self, forKey: .best) ?? 0
        last = try c.decodeIfPresent(Int.self, forKey: .last) ?? 0
        lastAt = try c.decodeIfPresent(Double.self, forKey: .lastAt) ?? 0
        categories = try c.decodeIfPresent([Category].self, forKey: .categories) ?? []
    }

    /// Du plus « impur » au plus sage, comme la page.
    var ranked: [Category] { categories.sorted { $0.pct != $1.pct ? $0.pct > $1.pct : $0.label < $1.label } }

    /// Même barème que purity.js (PU_GRADES).
    static func grade(_ score: Int) -> String {
        let grades: [(Int, String)] = [
            (0, "😇 Sainte-Nitouche certifiée"), (5, "👼 Enfant de chœur"), (12, "🧸 Bisounours en liberté"),
            (22, "🍵 Tisane, plaid & Netflix"), (35, "😏 Sage… en apparence"), (48, "🍷 Bon vivant·e"),
            (60, "🌶️ Épicé·e"), (72, "😈 Sulfureux·se"), (84, "🔥 Diablotin·e de compétition"),
            (94, "🚔 Casier bien rempli"), (100, "👹 Le Diable en personne"),
        ]
        return grades.first { score <= $0.0 }?.1 ?? grades[grades.count - 1].1
    }
}

/// Catégories et tags (POST /api/account/group-admin/taxonomy).
struct Taxonomy: Decodable, Equatable {
    struct Topic: Decodable, Equatable, Identifiable {
        let id: String
        let name: String
        let color: String
        let archived: Bool

        enum CodingKeys: String, CodingKey { case id, name, color, archived }

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            id = try c.decode(String.self, forKey: .id)
            name = try c.decode(String.self, forKey: .name)
            color = try c.decodeIfPresent(String.self, forKey: .color) ?? Self.palette[0]
            archived = try c.decodeIfPresent(Bool.self, forKey: .archived) ?? false
        }

        /// Mêmes couleurs que le module web.
        static let palette = ["#FF7A59", "#D4F24A", "#F2C14A", "#7AD3C8", "#7AA7FF", "#B9A7FF", "#FF9ECF"]
        var nextColor: String { Self.palette[((Self.palette.firstIndex(of: color) ?? -1) + 1) % Self.palette.count] }
    }

    enum Kind: String, CaseIterable, Identifiable {
        case categories, tags
        var id: String { rawValue }
        var label: String { self == .categories ? "Catégories" : "Tags" }
    }

    let categories: [Topic]
    let tags: [Topic]

    func items(_ kind: Kind) -> [Topic] { kind == .categories ? categories : tags }
}

extension PartyAPI {
    func sendLoginCode(phone: String) async throws { try await post("/api/account/otp", body: ["phone": phone]) }

    func verifyLoginCode(phone: String, code: String) async throws -> AccountSignIn {
        try await postDecoding("/api/account/verify", body: ["phone": phone, "code": code])
    }

    func signOut(token: String) async throws { try await post("/api/account/logout", body: ["token": token]) }

    func deleteAccount(token: String) async throws {
        try await post("/api/account/delete", body: ["token": token, "confirm": "SUPPRIMER"])
    }

    func announcements(token: String, after last: AnnouncementPage.Announcement? = nil) async throws -> AnnouncementPage {
        var body: [String: Any] = ["token": token]
        if let last {
            body["before_at"] = last.createdAt
            body["before_id"] = last.id
        }
        return try await postDecoding("/api/account/announcements", body: body)
    }

    func publishAnnouncement(token: String, title: String, body text: String) async throws -> AnnouncementPage {
        try await postDecoding("/api/account/group-admin/announce", body: ["token": token, "title": title, "body": text])
    }

    func purityStats(token: String) async throws -> PurityStats {
        try await postDecoding("/api/purity/me", body: ["token": token])
    }

    func taxonomy(token: String) async throws -> Taxonomy {
        try await postDecoding("/api/account/group-admin/taxonomy", body: ["token": token])
    }

    func saveTopic(token: String, kind: Taxonomy.Kind, id: String?, name: String? = nil, color: String? = nil,
                   archived: Bool? = nil) async throws -> Taxonomy {
        var body: [String: Any] = ["token": token, "kind": kind.rawValue]
        if let id { body["id"] = id }
        if let name { body["name"] = name }
        if let color { body["color"] = color }
        if let archived { body["archived"] = archived }
        return try await postDecoding("/api/account/group-admin/taxonomy/save", body: body)
    }
}

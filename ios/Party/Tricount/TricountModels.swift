import Foundation

/// Tricount (Réglages › Pot commun) : ce que renvoie le serveur (/api/account/tricount/*), déjà calculé
/// (soldes, remboursements, parts de chacun). Montants en centimes.
enum TC {
    /// Pot commun d'un événement (ouvert par l'organisateur) : les présents y entrent seuls.
    struct EventRef: Decodable, Equatable { let id: String; let title: String }

    struct Overview: Decodable, Equatable {
        struct Item: Decodable, Equatable, Identifiable {
            let id: String
            let name: String
            let emoji: String
            let currency: String
            let archived: Bool
            let members: Int
            let total_cents: Int
            let my_balance_cents: Int
            var event: EventRef? = nil
        }
        struct Category: Decodable, Equatable, Identifiable { let id: String; let label: String; let emoji: String }
        let tricounts: [Item]
        let categories: [Category]
        let currencies: [String]
    }

    struct Payment: Codable, Equatable {
        var iban: String?
        var holder: String?
        var links: [String: String]
        var note: String?
        static let empty = Payment(iban: "", holder: "", links: [:], note: "")
        var isEmpty: Bool { (iban ?? "").isEmpty && links.isEmpty }
    }

    struct Member: Decodable, Equatable, Identifiable {
        let id: String
        let name: String
        let linked: Bool?
        let left: Bool?
        let me: Bool
        let balance_cents: Int
        let payment: Payment?
    }

    struct Share: Codable, Equatable { let member_id: String; let weight: Double?; let amount_cents: Int? }
    struct Part: Decodable, Equatable { let member_id: String; let name: String; let amount_cents: Int }

    struct Expense: Decodable, Equatable, Identifiable {
        let id: String
        let kind: String
        let title: String
        let amount_cents: Int
        let currency: String
        let rate: Double?
        let paid_by: String
        let paid_by_name: String
        let spent_on: String?
        let category: String
        let note: String?
        let split_mode: String
        let receipt_path: String?
        let receipt_url: String?
        let group_amount_cents: Int
        let shares: [Share]
        let parts: [Part]
        let my_part_cents: Int
        var isTransfer: Bool { kind == "transfer" }
    }

    struct Settle: Decodable, Equatable, Hashable {
        let from: String
        let to: String
        let amount_cents: Int
        let from_name: String
        let to_name: String
    }

    struct CategoryTotal: Decodable, Equatable { let category: String; let amount_cents: Int; let label: String; let emoji: String }

    struct Group: Decodable, Equatable, Identifiable {
        let id: String
        let name: String
        let emoji: String
        let currency: String
        let archived: Bool
        var event: EventRef? = nil
        let me: String?
        let link: String?
        let members: [Member]
        let expenses: [Expense]
        let total_cents: Int
        let my_balance_cents: Int
        let my_spent_cents: Int
        let by_category: [CategoryTotal]
        let settle: [Settle]

        var active: [Member] { members.filter { $0.left != true } }
        func member(_ id: String) -> Member? { members.first { $0.id == id } }
    }

    struct JoinInfo: Decodable, Equatable {
        struct Person: Decodable, Equatable, Identifiable { let id: String; let name: String; let linked: Bool }
        let id: String
        let name: String
        let emoji: String
        let currency: String
        let already: Bool
        let members: [Person]
    }

    struct Path: Decodable { let path: String }

    /// Assistant IA : le droit du compte (réglé par l'admin) et ce qu'il a utilisé ce mois-ci.
    struct AIStatus: Decodable, Equatable { let allowed: Bool; let configured: Bool; let spent_usd: Double; let budget_usd: Double }

    /// Admin : ce que l'assistant IA a coûté ce mois-ci, par personne, et les derniers appels.
    struct AIUsage: Decodable, Equatable {
        struct Person: Decodable, Equatable, Identifiable { let uid: String; let name: String; let calls: Int; let cost_usd: Double; var id: String { uid } }
        struct Call: Decodable, Equatable { let at: Double; let name: String?; let feature: String; let cost_usd: Double }
        let month_cost_usd: Double
        let people: [Person]
        let recent: [Call]
        let budget_usd: Double
        let model: String
        let configured: Bool
    }

    /// Ticket lu par l'assistant IA : de quoi remplir la dépense, et ce qui a été acheté.
    struct Receipt: Decodable, Equatable {
        struct Item: Decodable, Equatable { let label: String; let quantity: Double; let amount_cents: Int }
        let merchant: String
        let title: String
        let date: String
        let currency: String
        let amount_cents: Int
        let category: String
        let items: [Item]
        let summary: String
    }
}

/// Montants en clair, à la suisse : « 1 250.50 CHF », « −12.00 € ».
enum Money {
    static func text(_ cents: Int, _ currency: String, sign: Bool = false) -> String {
        let f = NumberFormatter()
        f.numberStyle = .currency
        f.locale = Locale(identifier: "fr_CH")
        f.currencyCode = currency
        f.maximumFractionDigits = 2
        f.minimumFractionDigits = 2
        let value = f.string(from: NSNumber(value: Double(abs(cents)) / 100)) ?? "\(Double(abs(cents)) / 100) \(currency)"
        if cents < 0 { return "−" + value }
        return sign && cents > 0 ? "+" + value : value
    }

    /// « 12,5 » / « 12.50 » / « 12 » → 1250 centimes ; nil si illisible ou nul.
    static func cents(_ typed: String) -> Int? {
        let clean = typed.replacingOccurrences(of: ",", with: ".").replacingOccurrences(of: "'", with: "")
            .replacingOccurrences(of: " ", with: "").replacingOccurrences(of: "\u{202F}", with: "")
        guard let value = Decimal(string: clean), value > 0 else { return nil }
        var rounded = value * 100
        var out = Decimal()
        NSDecimalRound(&out, &rounded, 0, .plain)
        let cents = NSDecimalNumber(decimal: out).intValue
        return cents > 0 && cents <= 100_000_000 ? cents : nil
    }

    static func typed(_ cents: Int) -> String { String(format: "%.2f", Double(cents) / 100) }
}

extension PartyAPI {
    func tricounts(token: String) async throws -> TC.Overview {
        try await postDecoding("/api/account/tricount", body: ["token": token])
    }
    func tricount(token: String, id: String) async throws -> TC.Group {
        try await postDecoding("/api/account/tricount/open", body: ["token": token, "group_id": id])
    }
    func createTricount(token: String, name: String, emoji: String, currency: String, myName: String) async throws -> TC.Group {
        try await postDecoding("/api/account/tricount/create", body: ["token": token, "name": name, "emoji": emoji, "currency": currency, "my_name": myName])
    }
    func updateTricount(token: String, id: String, name: String?, emoji: String?, currency: String?, archived: Bool?) async throws -> TC.Group {
        var body: [String: Any] = ["token": token, "group_id": id]
        if let name { body["name"] = name }
        if let emoji { body["emoji"] = emoji }
        if let currency { body["currency"] = currency }
        if let archived { body["archived"] = archived }
        return try await postDecoding("/api/account/tricount/update", body: body)
    }
    func renewTricountLink(token: String, id: String) async throws -> TC.Group {
        try await postDecoding("/api/account/tricount/link", body: ["token": token, "group_id": id])
    }
    func tricountJoinInfo(token: String, link: String) async throws -> TC.JoinInfo {
        try await postDecoding("/api/account/tricount/join/info", body: ["token": token, "link": link])
    }
    func joinTricount(token: String, link: String, myName: String, claim: String?) async throws -> TC.Group {
        var body: [String: Any] = ["token": token, "link": link, "my_name": myName]
        if let claim { body["claim"] = claim }
        return try await postDecoding("/api/account/tricount/join", body: body)
    }
    func tricountMember(token: String, id: String, member: String?, name: String) async throws -> TC.Group {
        var body: [String: Any] = ["token": token, "group_id": id, "name": name]
        if let member { body["member_id"] = member }
        return try await postDecoding("/api/account/tricount/member", body: body)
    }
    func removeTricountMember(token: String, id: String, member: String) async throws -> TC.Group {
        try await postDecoding("/api/account/tricount/member/remove", body: ["token": token, "group_id": id, "member_id": member])
    }
    func leaveTricount(token: String, id: String) async throws -> TC.Overview {
        try await postDecoding("/api/account/tricount/leave", body: ["token": token, "group_id": id])
    }
    func saveTricountExpense(token: String, id: String, expense: [String: Any]) async throws -> TC.Group {
        try await postDecoding("/api/account/tricount/expense", body: ["token": token, "group_id": id, "expense": expense])
    }
    func deleteTricountExpense(token: String, id: String, expense: String) async throws -> TC.Group {
        try await postDecoding("/api/account/tricount/expense/delete", body: ["token": token, "group_id": id, "expense_id": expense])
    }
    func settleTricount(token: String, id: String, from: String, to: String, cents: Int) async throws -> TC.Group {
        try await postDecoding("/api/account/tricount/settle", body: ["token": token, "group_id": id, "from_id": from, "to_id": to, "amount_cents": cents])
    }
    func aiStatus(token: String) async throws -> TC.AIStatus {
        try await postDecoding("/api/account/ai/status", body: ["token": token])
    }
    func aiUsage(token: String) async throws -> TC.AIUsage {
        try await postDecoding("/api/account/ai/usage", body: ["token": token])
    }
    func aiReadReceipt(token: String, jpeg: Data) async throws -> TC.Receipt {
        try await postDecoding("/api/account/ai/receipt", body: ["token": token, "photo": jpeg.base64EncodedString()])
    }
    func uploadTricountReceipt(token: String, id: String, jpeg: Data) async throws -> String {
        let r: TC.Path = try await postDecoding("/api/account/tricount/receipt", body: ["token": token, "group_id": id, "photo": jpeg.base64EncodedString()])
        return r.path
    }
    func tricountPayment(token: String) async throws -> TC.Payment {
        try await postDecoding("/api/account/tricount/payment", body: ["token": token])
    }
    func saveTricountPayment(token: String, payment: TC.Payment) async throws -> TC.Payment {
        try await postDecoding("/api/account/tricount/payment/save", body: ["token": token, "iban": payment.iban ?? "", "holder": payment.holder ?? "",
                                                                           "links": payment.links, "note": payment.note ?? ""])
    }
}

extension TC.Settle: Identifiable {
    var id: String { "\(from)-\(to)-\(amount_cents)" }
}

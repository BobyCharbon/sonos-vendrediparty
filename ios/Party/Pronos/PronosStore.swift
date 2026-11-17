import Foundation
import SwiftUI

/// Pronos entre amis (avis f071c5f46e3d, 17.11.2026, migration 20261117180000) : pour l'honneur, jamais d'argent, de
/// mise ni de lot ; des points au classement du groupe. La base garde les réponses cachées (organisateur compris)
/// jusqu'au dévoilement et décide de tout ; l'app ne fait qu'appeler le relais POST /api/account/pronos/rpc.

struct PronoFace: Codable, Hashable, Identifiable {
    let id: String
    let name: String
    /// Lien signé de la photo (ajouté par le serveur).
    var photo: String?
    var me: Bool?

    var label: String { me == true ? "Toi" : name }
}

struct PronoGroupRef: Codable, Hashable {
    let id: String
    let name: String
    let emoji: String
    let color: String?
}

struct PronoEventRef: Codable, Hashable {
    let id: String
    let title: String
}

struct PronoOption: Codable, Hashable, Identifiable {
    let id: String
    let label: String
    let count: Int?
    let correct: Bool?
}

struct PronoAnswerRef: Codable, Hashable {
    let optionId: String?
    let number: Double?
    let text: String?
    let personId: String?
    let winner: Bool?
}

struct PronoShownAnswer: Codable, Hashable, Identifiable {
    let user: PronoFace
    let optionId: String?
    let number: Double?
    let text: String?
    let hidden: Bool?
    let person: PronoFace?
    let winner: Bool

    var id: String { user.id }
}

struct PronoResult: Codable, Hashable {
    let optionId: String?
    let number: Double?
    let person: PronoFace?
}

struct PronoLink: Codable, Hashable {
    let token: String?
    let path: String?
}

struct Prono: Codable, Identifiable, Hashable {
    let id: String
    let question: String
    let kind: String
    let points: Int
    let closesAt: String
    let reveal: String
    let state: String
    let revealed: Bool
    let createdAt: String
    let mine: Bool
    let locked: Bool
    let creator: PronoFace
    let group: PronoGroupRef?
    let event: PronoEventRef?
    let options: [PronoOption]
    let candidates: [PronoFace]?
    let myAnswer: PronoAnswerRef?
    let answered: [PronoFace]
    let players: Int
    let answers: [PronoShownAnswer]?
    let result: PronoResult?
    let winners: [PronoFace]?
    let canAnswer: Bool
    let canEdit: Bool
    let canMoveEnd: Bool
    let canResult: Bool
    let canCancel: Bool
    let link: PronoLink?

    var closes: Date? { PronoFormat.date(closesAt) }

    /// Réponse lisible (ma réponse, dévoilement).
    func label(option: String?, number: Double?, text: String?, person: PronoFace?, personId: String? = nil) -> String {
        switch kind {
        case "choice": return options.first { $0.id == option }?.label ?? "—"
        case "number": return number.map(PronoFormat.number) ?? "—"
        case "person":
            let who = person ?? candidates?.first { $0.id == personId }
            return who?.label ?? "—"
        default: return text ?? "Réponse masquée"
        }
    }

    var resultLabel: String {
        guard let result else { return "" }
        switch kind {
        case "choice": return options.first { $0.id == result.optionId }?.label ?? ""
        case "number": return result.number.map(PronoFormat.number) ?? ""
        case "person": return result.person?.label ?? ""
        default: return ""
        }
    }
}

struct PronoCard: Codable, Identifiable, Hashable {
    let id: String
    let question: String
    let kind: String
    let points: Int
    let closesAt: String
    let state: String
    let revealed: Bool
    let mine: Bool
    let creator: PronoFace
    let group: PronoGroupRef?
    let event: PronoEventRef?
    let answeredCount: Int
    let players: Int
    let faces: [PronoFace]
    let answered: Bool
    let won: Bool
    let winners: [PronoFace]?
    let winnersCount: Int?

    /// À faire pour moi : résultat à donner, ou prono ouvert où je n'ai pas joué.
    var todo: Bool { (state == "closed" && mine) || (state == "open" && !answered) }
}

struct PronoBoard: Codable, Hashable {
    struct Row: Codable, Hashable, Identifiable {
        let user: PronoFace
        let points: Int
        let right: Int
        let played: Int
        var id: String { user.id }
    }
    let since: String?
    let manage: Bool
    let pronos: Int
    let rows: [Row]
}

enum PronoFormat {
    static func date(_ iso: String) -> Date? {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let d = f.date(from: iso) { return d }
        f.formatOptions = [.withInternetDateTime]
        return f.date(from: iso)
    }

    /// « sam. 21.11 à 18:00 » (heure de Suisse).
    static func short(_ iso: String) -> String {
        guard let d = date(iso) else { return "" }
        let f = DateFormatter()
        f.locale = Locale(identifier: "fr_CH")
        f.timeZone = TimeZone(identifier: "Europe/Zurich")
        f.dateFormat = "EEE d.MM 'à' HH:mm"
        return f.string(from: d)
    }

    static func number(_ n: Double) -> String {
        n == n.rounded() ? String(Int(n)) : String(n).replacingOccurrences(of: ".", with: ",")
    }

    static func points(_ n: Int) -> String { n > 1 ? "\(n) points" : "\(n) point" }

    static func stateLine(state: String, closesAt: String, revealed: Bool) -> String {
        switch state {
        case "open": return "Fin \(short(closesAt))"
        case "closed": return revealed ? "Fermé · réponses dévoilées" : "Fermé · résultat attendu"
        case "done": return "Terminé"
        default: return "Annulé"
        }
    }

    static func place(group: PronoGroupRef?, event: PronoEventRef?, creator: PronoFace) -> String {
        if let group { return "\(group.emoji) \(group.name)" }
        if let event { return "📅 \(event.title)" }
        return "Proposé par \(creator.me == true ? "toi" : creator.name)"
    }
}

@MainActor
final class PronosStore: ObservableObject {
    /// Pronos à jouer + résultats à donner (pastille de Réglages › Autres apps › Pronos).
    @Published private(set) var badge = 0

    private let api: PartyAPI
    private weak var web: WebStorage?
    private(set) lazy var moderation = ModerationStore(api: api, web: web)

    init(api: PartyAPI, web: WebStorage?) {
        self.api = api
        self.web = web
    }

    static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }()

    /// Appel du relais ; la réponse de la base (« result ») décodée en T.
    func call<T: Decodable>(_ fn: String, _ args: [String: Any] = [:], as: T.Type = T.self) async throws -> T {
        guard let token = await web?.accountToken() else { throw PartyAPIError.server("Connecte-toi à Party pour jouer aux pronos.") }
        let reply = try await api.pronosRPC(token: token, fn: fn, args: args)
        let result = reply["result"] ?? NSNull()
        let data = try JSONSerialization.data(withJSONObject: result, options: [.fragmentsAllowed])
        return try Self.decoder.decode(T.self, from: data)
    }

    /// Appel sans réponse utile (supprimer, remettre à zéro).
    func run(_ fn: String, _ args: [String: Any] = [:]) async throws {
        guard let token = await web?.accountToken() else { throw PartyAPIError.server("Connecte-toi à Party pour jouer aux pronos.") }
        _ = try await api.pronosRPC(token: token, fn: fn, args: args)
    }

    func refreshBadge() async {
        struct Badge: Decodable { let toPlay: Int; let toResult: Int }
        guard let b = try? await call("prono_badge", as: Badge.self) else { return }
        Motion.animate(Motion.snappy) { badge = b.toPlay + b.toResult }
    }

    static func message(_ error: Error) -> String {
        (error as? LocalizedError)?.errorDescription ?? "Ça n'a pas marché. Réessaie dans un instant."
    }
}

/// Où ouvrir les pronos depuis la page web (PartyNative.pronos) ou une notification.
enum PronoRoute: Identifiable, Equatable {
    case list(group: String?)
    case open(String)
    case create(group: String?, event: String?)

    var id: String {
        switch self {
        case .list(let g): return "list:\(g ?? "")"
        case .open(let id): return "open:\(id)"
        case .create(let g, let e): return "create:\(g ?? ""):\(e ?? "")"
        }
    }

    /// Message du pont : « open:<uuid> », « list », « list:<uuid> », « create », « create:group:<uuid> »,
    /// « create:event:<uuid> ». nil pour tout le reste (rien d'autre n'est accepté).
    static func parse(_ body: String) -> PronoRoute? {
        let parts = body.split(separator: ":", omittingEmptySubsequences: false).map(String.init)
        func uuid(_ s: String) -> String? { UUID(uuidString: s)?.uuidString.lowercased() }
        switch (parts.first, parts.count) {
        case ("open", 2): return uuid(parts[1]).map { .open($0) }
        case ("list", 1): return .list(group: nil)
        case ("list", 2): return uuid(parts[1]).map { .list(group: $0) }
        case ("create", 1): return .create(group: nil, event: nil)
        case ("create", 3):
            guard let id = uuid(parts[2]) else { return nil }
            if parts[1] == "group" { return .create(group: id, event: nil) }
            if parts[1] == "event" { return .create(group: nil, event: id) }
            return nil
        default: return nil
        }
    }

    /// Notification d'un prono : « /?tab=events&prono=<id> » (send-push, tapPath).
    static func requested(in url: URL) -> String? {
        guard let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems,
              items.first(where: { $0.name == "tab" })?.value == "events",
              let id = items.first(where: { $0.name == "prono" })?.value.flatMap(UUID.init(uuidString:)) else { return nil }
        return id.uuidString.lowercased()
    }
}

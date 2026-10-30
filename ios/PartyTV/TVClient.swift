import Foundation
import Security

/// JSON lu tel quel : les vues des 20 jeux n'ont pas toutes la même forme, la télé lit ce dont elle a besoin.
enum JSON: Decodable, Equatable {
    case object([String: JSON]), array([JSON]), string(String), number(Double), bool(Bool), null

    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { self = .null }
        else if let b = try? c.decode(Bool.self) { self = .bool(b) }
        else if let n = try? c.decode(Double.self) { self = .number(n) }
        else if let s = try? c.decode(String.self) { self = .string(s) }
        else if let a = try? c.decode([JSON].self) { self = .array(a) }
        else { self = .object(try c.decode([String: JSON].self)) }
    }

    subscript(_ key: String) -> JSON { if case .object(let o) = self { return o[key] ?? .null }; return .null }
    subscript(_ index: Int) -> JSON { if case .array(let a) = self, a.indices.contains(index) { return a[index] }; return .null }

    var string: String? {
        switch self {
        case .string(let s): return s
        case .number(let n): return n == n.rounded() ? String(Int(n)) : String(n)
        default: return nil
        }
    }
    var int: Int? { if case .number(let n) = self { return Int(n) }; return nil }
    var double: Double? { if case .number(let n) = self { return n }; return nil }
    var bool: Bool { if case .bool(let b) = self { return b }; return false }
    var array: [JSON] { if case .array(let a) = self { return a }; return [] }
    var isNull: Bool { self == .null }
}

enum TVError: LocalizedError {
    case offline, badPin, notFound(String), server(String)
    var errorDescription: String? {
        switch self {
        case .offline: return "Le site de la soirée ne répond pas. Vérifie le réseau de l'Apple TV."
        case .badPin: return "Code admin incorrect."
        case .notFound(let message): return message
        case .server(let message): return message
        }
    }
}

/// Accès au site de la soirée avec la session de l'hôte (cookie admin), comme la page /tv.
final class TVClient {
    let base: URL
    private let session: URLSession

    init(base: URL = TVClient.defaultBase, session: URLSession = .shared) {
        self.base = base
        self.session = session
    }

    static var defaultBase: URL {
        let raw = Bundle.main.object(forInfoDictionaryKey: "PartyBaseURL") as? String ?? ""
        return URL(string: raw).flatMap { $0.host == nil ? nil : $0 } ?? URL(string: "https://partytest.bobycharbon.ch")!
    }

    func login(pin: String) async throws {
        var request = URLRequest(url: base.appendingPathComponent("api/admin/login"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: ["pin": pin])
        let (_, response) = try await send(request)
        guard response.statusCode == 200 else { throw response.statusCode == 429 ? TVError.server("Trop d'essais : attends une minute.") : TVError.badPin }
    }

    /// 401 : la session admin a expiré (le code admin est redemandé au trousseau puis renvoyé).
    func get(_ path: String) async throws -> (JSON, Int) {
        let (data, response) = try await send(URLRequest(url: base.appendingPathComponent(path)))
        let json = (try? JSONDecoder().decode(JSON.self, from: data)) ?? .null
        return (json, response.statusCode)
    }

    private func send(_ request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        var request = request
        request.timeoutInterval = 8
        do {
            let (data, response) = try await session.data(for: request)
            guard let http = response as? HTTPURLResponse else { throw TVError.offline }
            return (data, http)
        } catch let error as TVError {
            throw error
        } catch {
            throw TVError.offline
        }
    }
}

/// Code admin gardé dans le trousseau de l'Apple TV (demandé une seule fois).
enum PinVault {
    private static let service = "ch.bobycharbon.party.tv"
    private static let account = "admin-pin"

    static func read() -> String? {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service,
                                    kSecAttrAccount as String: account, kSecReturnData as String: true]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess, let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    static func save(_ pin: String) {
        forget()
        let item: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service,
                                   kSecAttrAccount as String: account, kSecValueData as String: Data(pin.utf8),
                                   kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock]
        SecItemAdd(item as CFDictionary, nil)
    }

    static func forget() {
        SecItemDelete([kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service,
                       kSecAttrAccount as String: account] as CFDictionary)
    }
}

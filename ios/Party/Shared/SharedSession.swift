import Foundation
import Security

/// Session de l'invité partagée par l'app et son extension « Partager » (trousseau, groupe PartyKeychainGroup) :
/// adresse du site, identité (vp_guest, vp_name) et cookies (code d'accès, compte). L'app la met à jour à chaque
/// page chargée et à chaque réponse de la Musique native ; l'extension s'en sert pour ajouter un titre.
struct SessionSnapshot: Codable, Equatable {
    let base: URL
    let guestID: String
    var name: String
    var cookies: [StoredCookie]
}

/// Cookie enregistrable (HTTPCookie n'est pas Codable).
struct StoredCookie: Codable, Equatable {
    let name: String
    let value: String
    let domain: String
    let path: String
    let isSecure: Bool
    let expires: Date?

    init(_ cookie: HTTPCookie) {
        name = cookie.name
        value = cookie.value
        domain = cookie.domain
        path = cookie.path
        isSecure = cookie.isSecure
        expires = cookie.expiresDate
    }

    var cookie: HTTPCookie? {
        var properties: [HTTPCookiePropertyKey: Any] = [.name: name, .value: value, .domain: domain, .path: path]
        if isSecure { properties[.secure] = "TRUE" }
        if let expires { properties[.expires] = expires }
        return HTTPCookie(properties: properties)
    }
}

enum SharedSession {
    private static let service = "ch.bobycharbon.party.session"
    private static let account = "guest"
    /// Erreur du trousseau quand l'app n'est pas signée avec le groupe (simulateur, tests).
    private static let missingEntitlement: OSStatus = -34018

    private static var accessGroup: String? {
        (Bundle.main.object(forInfoDictionaryKey: "PartyKeychainGroup") as? String).flatMap { $0.isEmpty ? nil : $0 }
    }

    static func load() -> SessionSnapshot? {
        guard let data = read() else { return nil }
        return try? JSONDecoder().decode(SessionSnapshot.self, from: data)
    }

    static func save(_ snapshot: SessionSnapshot) {
        guard let data = try? JSONEncoder().encode(snapshot) else { return }
        write(data)
    }

    // MARK: Trousseau

    private static func query(group: String?) -> [String: Any] {
        var query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
                                    kSecAttrService as String: service, kSecAttrAccount as String: account]
        if let group { query[kSecAttrAccessGroup as String] = group }
        return query
    }

    private static func read() -> Data? {
        for group in [accessGroup, nil] {
            var item: CFTypeRef?
            var request = query(group: group)
            request[kSecReturnData as String] = true
            let status = SecItemCopyMatching(request as CFDictionary, &item)
            if status == errSecSuccess { return item as? Data }
            if status != missingEntitlement { return nil }
        }
        return nil
    }

    private static func write(_ data: Data) {
        for group in [accessGroup, nil] {
            let base = query(group: group)
            var status = SecItemUpdate(base as CFDictionary, [kSecValueData as String: data] as CFDictionary)
            if status == errSecItemNotFound {
                var add = base
                add[kSecValueData as String] = data
                // Lisible par l'extension même écran verrouillé après le premier déverrouillage.
                add[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
                status = SecItemAdd(add as CFDictionary, nil)
            }
            if status != missingEntitlement { return }
        }
    }
}

/// Cookies de la session copiée dans le trousseau (extension) ; les nouveaux cookies y sont réenregistrés.
@MainActor
final class SnapshotCookieJar: CookieJar {
    private(set) var snapshot: SessionSnapshot

    init(_ snapshot: SessionSnapshot) {
        self.snapshot = snapshot
    }

    func allCookies() async -> [HTTPCookie] {
        snapshot.cookies.compactMap(\.cookie)
    }

    func keep(_ cookies: [HTTPCookie]) async {
        let replaced = Set(cookies.map(\.name))
        snapshot.cookies = snapshot.cookies.filter { !replaced.contains($0.name) } + cookies.map(StoredCookie.init)
        SharedSession.save(snapshot)
    }
}

import Foundation
import Security

/// Trousseau partagé par l'app et ses extensions (groupe PartyKeychainGroup) : session de l'invité (SharedSession),
/// état du Zicou pour les widgets (PetWidgetStore). Hors du groupe (simulateur non signé, tests), le trousseau
/// propre à l'app sert de repli.
enum SharedKeychain {
    private static let service = "ch.bobycharbon.party.session"
    /// Erreur du trousseau quand l'app n'est pas signée avec le groupe (simulateur, tests).
    private static let missingEntitlement: OSStatus = -34018

    private static var accessGroup: String? {
        (Bundle.main.object(forInfoDictionaryKey: "PartyKeychainGroup") as? String).flatMap { $0.isEmpty ? nil : $0 }
    }

    private static func query(group: String?, account: String) -> [String: Any] {
        var query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
                                    kSecAttrService as String: service, kSecAttrAccount as String: account]
        if let group { query[kSecAttrAccessGroup as String] = group }
        return query
    }

    static func read(account: String) -> Data? {
        for group in [accessGroup, nil] {
            var item: CFTypeRef?
            var request = query(group: group, account: account)
            request[kSecReturnData as String] = true
            // Introuvable dans le groupe (app non signée : écrit dans le trousseau propre à l'app) : on y regarde aussi.
            if SecItemCopyMatching(request as CFDictionary, &item) == errSecSuccess { return item as? Data }
        }
        return nil
    }

    static func write(_ data: Data, account: String) {
        for group in [accessGroup, nil] {
            let base = query(group: group, account: account)
            var status = SecItemUpdate(base as CFDictionary, [kSecValueData as String: data] as CFDictionary)
            if status == errSecItemNotFound {
                var add = base
                add[kSecValueData as String] = data
                // Lisible par les extensions même écran verrouillé après le premier déverrouillage (widgets).
                add[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
                status = SecItemAdd(add as CFDictionary, nil)
            }
            if status != missingEntitlement { return }
        }
    }

    static func delete(account: String) {
        for group in [accessGroup, nil] {
            let status = SecItemDelete(query(group: group, account: account) as CFDictionary)
            if status != missingEntitlement { return }
        }
    }
}

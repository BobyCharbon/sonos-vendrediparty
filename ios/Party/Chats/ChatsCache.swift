import Foundation

/// Dernière liste des discussions et dernières conversations, gardées sur le téléphone : l'onglet s'affiche tout de
/// suite, sans chargement, puis se met à jour en direct (avis 945c932cbfa6). Un fichier par compte (dossier Caches :
/// iOS peut le vider, rien n'y est indispensable).
enum ChatsCache {
    private static let folder: URL? = {
        guard let caches = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first else { return nil }
        let url = caches.appendingPathComponent("chats", isDirectory: true)
        try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }()

    /// Compte du jeton (champ « sub » du jeton Supabase) : jamais la liste d'un autre compte.
    static func account(of token: String) -> String? {
        let parts = token.split(separator: ".")
        guard parts.count == 3 else { return nil }
        var payload = String(parts[1]).replacingOccurrences(of: "-", with: "+").replacingOccurrences(of: "_", with: "/")
        payload += String(repeating: "=", count: (4 - payload.count % 4) % 4)
        guard let data = Data(base64Encoded: payload),
              let claims = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let sub = claims["sub"] as? String, sub.range(of: "^[0-9a-fA-F-]{36}$", options: .regularExpression) != nil
        else { return nil }
        return sub.lowercased()
    }

    private static func file(_ account: String, _ name: String) -> URL? {
        guard name.range(of: "^[a-zA-Z0-9-]{1,60}$", options: .regularExpression) != nil else { return nil }
        return folder?.appendingPathComponent("\(account)-\(name).json")
    }

    static func load<T: Decodable>(_ type: T.Type, account: String, name: String) -> T? {
        guard let url = file(account, name), let data = try? Data(contentsOf: url) else { return nil }
        return try? JSONDecoder().decode(type, from: data)
    }

    static func save<T: Encodable>(_ value: T, account: String, name: String) {
        guard let url = file(account, name), let data = try? JSONEncoder().encode(value) else { return }
        try? data.write(to: url, options: .atomic)
    }
}

import Foundation

/// Dernier état de Zicou vu par l'app, gardé dans le trousseau partagé (comme la session de l'extension « Partager ») :
/// les widgets le lisent sans compte ni réseau. Effacé à la déconnexion.
enum PetWidgetStore {
    private static let account = "pet-widget"
    /// Genre du widget Zicou (WidgetCenter.reloadTimelines).
    static let widgetKind = "ZicouWidget"

    static func load() -> PetWidgetState? {
        guard let data = SharedKeychain.read(account: account), !data.isEmpty else { return nil }
        return try? decoder.decode(PetWidgetState.self, from: data)
    }

    static func save(_ state: PetWidgetState) {
        guard let data = try? encoder.encode(state) else { return }
        SharedKeychain.write(data, account: account)
    }

    static func clear() {
        SharedKeychain.delete(account: account)
    }

    private static var encoder: JSONEncoder {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .secondsSince1970
        return encoder
    }

    private static var decoder: JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .secondsSince1970
        return decoder
    }
}

/// Liens profonds vers Zicou (widgets, actions rapides de l'icône). La page ouvre le panneau du Compagnon avec
/// « pet=1 » (app/static/pet/pet.js) et compte l'ouverture selon « src ».
enum PetLinks {
    static var base: URL {
        let raw = Bundle.main.object(forInfoDictionaryKey: "PartyBaseURL") as? String ?? ""
        return URL(string: raw).flatMap { $0.host == nil ? nil : $0 } ?? URL(string: "https://party.bobycharbon.ch")!
    }

    /// src : widget (toucher d'un widget), link (action rapide, Live Activity).
    static func zicou(src: String, screen: String? = nil, base: URL = base) -> URL {
        var parts = URLComponents(url: base, resolvingAgainstBaseURL: false) ?? URLComponents()
        parts.path = "/"
        parts.queryItems = [URLQueryItem(name: "tab", value: "games"), URLQueryItem(name: "pet", value: "1"),
                            URLQueryItem(name: "src", value: src)]
            + (screen.map { [URLQueryItem(name: "screen", value: $0)] } ?? [])
        return parts.url ?? base
    }
}

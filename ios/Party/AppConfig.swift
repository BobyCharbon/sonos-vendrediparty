import SwiftUI

enum AppConfig {
    /// Site chargé : https://partytest… en Debug, https://party… en Release (PARTY_BASE_URL dans project.yml).
    static let baseURL: URL = {
        let raw = Bundle.main.object(forInfoDictionaryKey: "PartyBaseURL") as? String ?? ""
        return URL(string: raw) ?? URL(string: "https://party.bobycharbon.ch")!
    }()

    /// Domaines ouverts DANS l'app : le site, et les connexions qui doivent revenir avec les cookies du site.
    /// Tout le reste (open.spotify.com, Google Agenda, Maps…) part dans Safari ou l'app concernée.
    static let internalHosts = ["party.bobycharbon.ch", "partytest.bobycharbon.ch", "accounts.spotify.com"]
    static let internalHostSuffixes = [".supabase.co"]

    /// Ajouté à l'User-Agent : le site peut reconnaître l'app (`PartyApp-iOS/`).
    static let userAgentSuffix: String = {
        let version = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "1"
        return "PartyApp-iOS/\(version)"
    }()

    /// Fond de la page (#0e0b16, background_color du manifeste) : pas de flash blanc au lancement.
    static let background = Color(red: 14 / 255, green: 11 / 255, blue: 22 / 255)
    static let uiBackground = UIColor(red: 14 / 255, green: 11 / 255, blue: 22 / 255, alpha: 1)
    /// Rose de la webapp (--accent) : onglet actif de la barre native.
    static let uiAccent = UIColor(red: 1, green: 79 / 255, blue: 154 / 255, alpha: 1)

    static func isInternal(_ url: URL) -> Bool {
        guard let host = url.host?.lowercased() else { return false }
        return internalHosts.contains(host) || internalHostSuffixes.contains { host.hasSuffix($0) }
    }
}

extension Notification.Name {
    /// Adresse à ouvrir dans la vue web (toucher d'une notification).
    static let partyOpenURL = Notification.Name("partyOpenURL")
    /// Jeton APNs reçu ou erreur d'enregistrement.
    static let partyPushToken = Notification.Name("partyPushToken")
}

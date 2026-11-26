import SwiftUI

enum AppConfig {
    /// Site chargé : https://partytest… en Debug, https://party… en Release (PARTY_BASE_URL dans project.yml).
    static let baseURL: URL = {
        let raw = Bundle.main.object(forInfoDictionaryKey: "PartyBaseURL") as? String ?? ""
        return URL(string: raw) ?? URL(string: "https://party.bobycharbon.ch")!
    }()

    /// Domaines ouverts DANS l'app : le site, et les connexions qui doivent revenir avec les cookies du site.
    /// Tout le reste (open.spotify.com, Google Agenda, Maps…) part dans Safari ou l'app concernée.
    /// Le site de test (partytest…) ne s'ouvre DANS l'app que dans la BETA, jamais dans l'app de l'App Store
    /// (contrôle du 26.11 : Zicou et fonctions en essai y sont allumés).
    static var internalHosts: [String] {
        isStoreApp ? ["party.bobycharbon.ch", "accounts.spotify.com"]
                   : ["party.bobycharbon.ch", "partytest.bobycharbon.ch", "accounts.spotify.com"]
    }
    /// Base Supabase EXACTE (jamais n'importe quel `*.supabase.co`) : celle de la prod ; la BETA y ajoute la base de TEST.
    static var supabaseHosts: [String] {
        isStoreApp ? ["gsuetixzobooggeaubvb.supabase.co"]
                   : ["gsuetixzobooggeaubvb.supabase.co", "ewromqfsmcqsthftyhzm.supabase.co"]
    }

    /// Ajouté à l'User-Agent : le site peut reconnaître l'app (`PartyApp-iOS/`). L'app de l'App Store ajoute
    /// « PartyStore » : le site y masque Casino et Blackjack (jeux d'argent simulés, refusés par Apple pour un
    /// compte développeur individuel ; STORE_APP_MARK dans app/main.py). La BETA (TestFlight) les garde.
    static let userAgentSuffix: String = {
        let version = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "1"
        return "PartyApp-iOS/\(version)" + (isStoreApp ? " PartyStore" : "")
    }()

    /// Zicou (widget, éclosion, actions rapides) : compilé dans la BETA seulement (PARTY_SWIFT_CONDITIONS, project.yml).
    static let zicouBuild: Bool = {
        #if BETA
        return true
        #else
        return false
        #endif
    }()

    /// VendrediParty (ch.bobycharbon.party) et non Party BETA (….beta).
    static var isStoreApp: Bool { !(Bundle.main.bundleIdentifier ?? "").hasSuffix(".beta") }

    /// Fonctions en essai (Zicou, bar, Agenda, Pronos, cartes secrètes de la Pyramide) coupées dans le binaire de
    /// l'App Store, quoi que dise le serveur (refus 1.4.3, 2.5.19). Les recettes Release (E2E_HOOKS, jamais dans le
    /// build de l'App Store) les gardent.
    static var storeLocked: Bool {
        #if E2E_HOOKS
        return false
        #else
        return isStoreApp
        #endif
    }

    /// Fond de la page (#0e0b16, background_color du manifeste) : pas de flash blanc au lancement.
    static let background = Color(red: 14 / 255, green: 11 / 255, blue: 22 / 255)
    static let uiBackground = UIColor(red: 14 / 255, green: 11 / 255, blue: 22 / 255, alpha: 1)
    /// Rose de la webapp (--accent) : onglet actif de la barre native.
    static let uiAccent = UIColor(red: 1, green: 79 / 255, blue: 154 / 255, alpha: 1)

    /// Pages qui reçoivent le pont natif (`PartyNative` et ses gestionnaires) : le site de l'app seulement (et le site
    /// de TEST dans la BETA), jamais accounts.spotify.com ni la base Supabase, pourtant ouverts DANS l'app (contrôle
    /// Apple du 26.11).
    static var bridgeHosts: [String] {
        let base = baseURL.host?.lowercased() ?? ""
        return isStoreApp ? [base] : Array(Set([base, "partytest.bobycharbon.ch"])).sorted()
    }

    static func mayUseBridge(_ url: URL) -> Bool {
        guard let host = url.host?.lowercased() else { return false }
        return bridgeHosts.contains(host)
    }

    static func isInternal(_ url: URL) -> Bool {
        guard let host = url.host?.lowercased() else { return false }
        // Le site chargé par l'app (PARTY_BASE_URL) l'est toujours : serveur local des essais sur simulateur compris.
        return host == baseURL.host?.lowercased() || internalHosts.contains(host) || supabaseHosts.contains(host)
    }
}

extension Notification.Name {
    /// Adresse à ouvrir dans la vue web (toucher d'une notification).
    static let partyOpenURL = Notification.Name("partyOpenURL")
    /// Jeton APNs reçu ou erreur d'enregistrement.
    static let partyPushToken = Notification.Name("partyPushToken")
}

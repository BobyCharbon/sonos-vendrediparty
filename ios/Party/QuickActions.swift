import UIKit

/// Actions rapides de l'icône (appui long). « Ajouter un titre » est déclarée dans Info.plist (UIApplicationShortcutItems,
/// project.yml) : elle existe dès l'installation. « Zicou » et « Cadeau du jour » sont ajoutées par l'app seulement quand
/// le Compagnon répond (il est en bêta, éteint en production : /api/pet/* → 404), et retirées sinon.
enum QuickAction: String, CaseIterable {
    case zicou = "ch.bobycharbon.party.zicou"
    case gift = "ch.bobycharbon.party.gift"
    case addTrack = "ch.bobycharbon.party.addtrack"

    /// Type déclaré (Info.plist) → action ; un type inconnu (ancienne version) est ignoré.
    init?(type: String) {
        self.init(rawValue: type)
    }

    /// Ce que l'app ouvre : le panneau du Compagnon (adresse) ou l'onglet Musique, recherche prête.
    enum Target: Equatable {
        case page(URL)
        case addTrack
    }

    func target(base: URL = PetLinks.base) -> Target {
        switch self {
        case .zicou: return .page(PetLinks.zicou(src: "link", base: base))
        case .gift: return .page(PetLinks.zicou(src: "link", screen: "chest", base: base))
        case .addTrack: return .addTrack
        }
    }

    /// Actions du Compagnon, proposées tant qu'il est ouvert sur ce site.
    static let companion: [QuickAction] = [.zicou, .gift]

    var title: String {
        switch self {
        case .zicou: return "Zicou"
        case .gift: return "Cadeau du jour"
        case .addTrack: return "Ajouter un titre"
        }
    }

    var symbol: String {
        switch self {
        case .zicou: return "face.smiling"
        case .gift: return "gift"
        case .addTrack: return "music.note.list"
        }
    }

    /// Compagnon ouvert (Zicou reçu) ou fermé (404, déconnexion) : actions dynamiques mises à jour.
    @MainActor
    static func showCompanion(_ shown: Bool) {
        let items = shown && AppConfig.zicouBuild ? companion.map {
            UIApplicationShortcutItem(type: $0.rawValue, localizedTitle: $0.title, localizedSubtitle: nil,
                                      icon: UIApplicationShortcutIcon(systemImageName: $0.symbol))
        } : []
        if UIApplication.shared.shortcutItems?.map(\.type) != items.map(\.type) {
            UIApplication.shared.shortcutItems = items
        }
    }

    /// « Ajouter un titre » : le champ de recherche de Musique prend le clavier dès qu'il est affiché.
    @MainActor private static var musicSearchWanted = false

    @MainActor
    static func requestMusicSearch() {
        musicSearchWanted = true
        NotificationCenter.default.post(name: .partyMusicSearch, object: nil)
    }

    @MainActor
    static func takeMusicSearch() -> Bool {
        defer { musicSearchWanted = false }
        return musicSearchWanted
    }

    /// Action choisie, gardée jusqu'à ce que l'app soit prête (lancement à froid compris).
    @MainActor static var pending: QuickAction?

    @MainActor
    static func take() -> QuickAction? {
        defer { pending = nil }
        return pending
    }
}

/// Reçoit l'action rapide : au lancement (connectionOptions) ou app déjà en mémoire (performActionFor).
final class QuickActionSceneDelegate: NSObject, UIWindowSceneDelegate {
    func scene(_ scene: UIScene, willConnectTo session: UISceneSession, options: UIScene.ConnectionOptions) {
        guard let item = options.shortcutItem else { return }
        Task { @MainActor in QuickAction.pending = QuickAction(type: item.type) }
    }

    func windowScene(_ windowScene: UIWindowScene, performActionFor shortcutItem: UIApplicationShortcutItem,
                     completionHandler: @escaping (Bool) -> Void) {
        let action = QuickAction(type: shortcutItem.type)
        Task { @MainActor in
            QuickAction.pending = action
            NotificationCenter.default.post(name: .partyQuickAction, object: nil)
        }
        completionHandler(action != nil)
    }
}

extension Notification.Name {
    /// Action rapide de l'icône choisie (QuickAction.pending).
    static let partyQuickAction = Notification.Name("partyQuickAction")
    /// Action rapide « Ajouter un titre » : la recherche de Musique prend le clavier.
    static let partyMusicSearch = Notification.Name("partyMusicSearch")
}

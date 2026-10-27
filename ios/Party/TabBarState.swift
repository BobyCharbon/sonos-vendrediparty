import Foundation

/// Onglets décrits par la page (app/static/native-tabs.js) : la page reste la référence, l'app les dessine.
struct TabBarState: Decodable, Equatable {
    struct Tab: Decodable, Equatable {
        let id: String
        let label: String
        let active: Bool
        /// nil : pas de badge ; "" : un point ; sinon le texte (nombre…).
        let badge: String?
        /// Section annoncée « Bientôt » (Événements avant leur ouverture).
        let soon: Bool
    }

    /// Un jeu en plein écran masque la barre.
    let hidden: Bool
    let tabs: [Tab]
    /// Onglets que l'app peut afficher en natif (la page garde l'onglet Musique pour l'hôte).
    let native: [String]

    enum CodingKeys: String, CodingKey { case hidden, tabs, native }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        hidden = try c.decode(Bool.self, forKey: .hidden)
        tabs = try c.decode([Tab].self, forKey: .tabs)
        native = try c.decodeIfPresent([String].self, forKey: .native) ?? []
    }

    /// Onglet affiché en natif plutôt que dans la page, s'il y en a un.
    var nativeScreen: String? {
        activeIndex.map { tabs[$0].id }.flatMap { native.contains($0) ? $0 : nil }
    }

    var activeIndex: Int? { tabs.firstIndex(where: \.active) }

    /// Corps d'un message JavaScript (dictionnaire) → état ; nil si la page envoie autre chose.
    init?(message body: Any) {
        guard JSONSerialization.isValidJSONObject(body),
              let data = try? JSONSerialization.data(withJSONObject: body),
              let state = try? JSONDecoder().decode(TabBarState.self, from: data) else { return nil }
        self = state
    }
}

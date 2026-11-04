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
    /// L'hôte : l'écran natif lui propose « Gérer la soirée » (onglet Musique de la page, avec ses réglages).
    let host: Bool
    /// Page affichée, même sans bouton dans la barre (« feedback » : Réglages › Ton avis, depuis le 4.11).
    let screen: String?
    /// Ligne « Ton avis » / « Retours » des Réglages natifs : sortie de la barre d'onglets (onglet Zicou, 4.11).
    let feedback: FeedbackEntry?

    struct FeedbackEntry: Decodable, Equatable {
        let allowed: Bool
        let label: String
        /// nil : pas de pastille ; sinon le nombre d'avis à traiter (hôte) ou de réponses à lire.
        let badge: String?
    }

    enum CodingKeys: String, CodingKey { case hidden, tabs, native, host, screen, feedback }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        hidden = try c.decode(Bool.self, forKey: .hidden)
        tabs = try c.decode([Tab].self, forKey: .tabs)
        native = try c.decodeIfPresent([String].self, forKey: .native) ?? []
        host = try c.decodeIfPresent(Bool.self, forKey: .host) ?? false
        screen = try c.decodeIfPresent(String.self, forKey: .screen)
        feedback = try? c.decodeIfPresent(FeedbackEntry.self, forKey: .feedback)
    }

    /// Onglet affiché en natif plutôt que dans la page, s'il y en a un. Une page des Réglages sans bouton dans la
    /// barre (« Ton avis ») passe avant l'onglet Réglages qui reste allumé dessous.
    var nativeScreen: String? {
        if let screen, isSubScreen, native.contains(screen) { return screen }
        return activeIndex.map { tabs[$0].id }.flatMap { native.contains($0) ? $0 : nil }
    }

    /// La page affichée n'a pas de bouton dans la barre : c'est une page des Réglages (retour « ‹ Réglages »).
    var isSubScreen: Bool {
        guard let screen else { return false }
        return !tabs.contains { $0.id == screen }
    }

    var activeIndex: Int? { tabs.firstIndex(where: \.active) }

    private init(hidden: Bool, tabs: [Tab], native: [String], host: Bool, screen: String?, feedback: FeedbackEntry?) {
        self.hidden = hidden
        self.tabs = tabs
        self.native = native
        self.host = host
        self.screen = screen
        self.feedback = feedback
    }

    /// Onglets dessinés par l'app : Discussions fermées sur ce site (/api/features.discussions false, production) →
    /// ni bouton dans la barre ni écran natif, même si la page en décrit un (« Bientôt » compris).
    func visible(discussions: Bool) -> TabBarState {
        guard !discussions else { return self }
        let closed: Set<String> = ["chats"]
        return TabBarState(hidden: hidden, tabs: tabs.filter { !closed.contains($0.id) },
                           native: native.filter { !closed.contains($0) }, host: host,
                           screen: screen.flatMap { closed.contains($0) ? nil : $0 }, feedback: feedback)
    }

    /// Corps d'un message JavaScript (dictionnaire) → état ; nil si la page envoie autre chose.
    init?(message body: Any) {
        guard JSONSerialization.isValidJSONObject(body),
              let data = try? JSONSerialization.data(withJSONObject: body),
              let state = try? JSONDecoder().decode(TabBarState.self, from: data) else { return nil }
        self = state
    }
}

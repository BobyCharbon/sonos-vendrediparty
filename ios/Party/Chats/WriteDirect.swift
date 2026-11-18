import SwiftUI

/// « Envoyer un message » (mini-profil, fiche d'un membre, Mes amis dans Party) : ouvre LA conversation privée avec ce
/// membre dans Discussions. Discussions v2 (18.11) : passe par `open_direct_chat` (PeopleStore.openDirect) : la base
/// décide si c'est une conversation (« direct »), une demande de message (« request », ouverte aussi) ou rien
/// (« none », raison affichée). Donnée par l'app à toute la hiérarchie de vues ; nil quand Discussions n'est pas
/// disponible (production hors bêta-testeurs : « Bientôt ») : le bouton est alors caché.
struct WriteDirectAction {
    /// .opened quand la conversation s'ouvre ; .termsRequired : feuille des règles puis nouvel essai ; .refused : raison.
    let open: @MainActor (_ userID: String) async -> WriteDirectResult
}

private struct WriteDirectKey: EnvironmentKey {
    static let defaultValue: WriteDirectAction? = nil
}

extension EnvironmentValues {
    var writeDirect: WriteDirectAction? {
        get { self[WriteDirectKey.self] }
        set { self[WriteDirectKey.self] = newValue }
    }
}

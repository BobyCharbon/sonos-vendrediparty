import SwiftUI

/// « Écrire » (Mes amis dans Party, fiche d'un membre) : ouvre LA conversation privée avec ce membre dans
/// Discussions (messages directs, 4.11). Donnée par l'app à toute la hiérarchie de vues ; nil quand Discussions n'est
/// pas disponible (production hors bêta-testeurs : « Bientôt ») : le bouton « Écrire » est alors caché.
struct WriteDirectAction {
    /// Rend true quand la conversation s'ouvre ; false si l'on ne peut pas écrire à cette personne (message affiché).
    let open: @MainActor (_ userID: String) async -> Bool
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

import ActivityKit
import Foundation

/// Live Activity « Ton titre arrive » (écran verrouillé, Dynamic Island) : partagée par l'app, qui la démarre
/// et la tient à jour, et l'extension PartyWidgets, qui la dessine.
struct TrackActivityAttributes: ActivityAttributes {
    struct ContentState: Codable, Hashable {
        /// Heure de passage estimée (compte à rebours sur l'iPhone, sans serveur de notifications).
        var arrival: Date
        /// Le titre est en train de passer.
        var playing: Bool
    }

    /// Demande suivie (rid du serveur) : une activité par titre demandé.
    let requestID: String
    /// Titre Spotify : reconnu quand il passe (titre en cours de la soirée).
    let trackID: String
    let title: String
    let artist: String
}

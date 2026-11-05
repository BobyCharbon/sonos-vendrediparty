import ActivityKit
import Foundation

/// Live Activity « Éclosion » : un épisode borné de 3 minutes (l'œuf pondu → l'éclosion), jamais un Zicou permanent
/// (CLAUDE.md, conformité). Démarrée et terminée par l'app (HatchActivities), dessinée par PartyWidgets.
struct HatchActivityAttributes: ActivityAttributes {
    struct ContentState: Codable, Hashable {
        /// Moment de l'éclosion (décompte sur l'iPhone, sans serveur).
        var hatchAt: Date
        /// Éclos : « … est né ! Viens le voir », puis l'activité disparaît d'elle-même.
        var hatched: Bool
    }

    /// Nom du Zicou (filtré par le serveur, sinon « Zicou »).
    let name: String
    /// Moment de la ponte : départ de la barre de progression.
    let laidAt: Date
}

import Foundation

/// Un retour envoyé par cet invité (GET /api/feedback, app/feedback.py `mine`).
struct FeedbackItem: Decodable, Equatable, Identifiable {
    let id: String
    /// Secondes depuis 1970 (time.time() côté serveur).
    let at: Double
    let kind: String
    let text: String
    /// new · progress · done · declined (« sent » / « verify » arrivent déjà en « progress »).
    let status: String
    /// Mot de l'hôte, une fois le retour terminé ou refusé.
    let reply: String
    /// Terminé depuis la dernière visite de l'onglet : mis en avant, puis marqué « vu ».
    let unseen: Bool

    var date: Date { Date(timeIntervalSince1970: at) }
}

struct FeedbackList: Decodable {
    let mine: [FeedbackItem]
}

/// Types et états, avec les mêmes mots que la page web (index.html, FB_STATUS).
enum FeedbackKind: String, CaseIterable, Identifiable {
    case idea, bug, other

    var id: String { rawValue }

    var label: String {
        switch self {
        case .idea: return "💡 Idée"
        case .bug: return "🐞 Bug"
        case .other: return "💬 Autre"
        }
    }

    var placeholder: String {
        switch self {
        case .idea: return "Ex. : un mode d'équipe au Quiz, plus de cartes au Divan…"
        case .bug: return "Ce qui s'est passé, et sur quel écran"
        case .other: return "Ton message pour l'organisateur"
        }
    }

    static func label(for raw: String) -> String {
        FeedbackKind(rawValue: raw)?.label ?? ""
    }
}

enum FeedbackStatus {
    static func label(for status: String) -> String {
        switch status {
        case "new": return "Envoyé"
        case "progress": return "🔧 En cours de correction"
        case "done": return "✅ Terminé"
        case "declined": return "🚫 Pas retenu"
        default: return ""
        }
    }
}

/// Règles du serveur (app/main.py, send_feedback) rappelées avant l'envoi.
enum FeedbackRules {
    static let minimumLength = 30
    static let maximumLength = 1000

    /// « 12 / 1000 · encore 18 caractères minimum », puis « 42 / 1000 ».
    static func counter(_ count: Int) -> String {
        let missing = minimumLength - count
        guard missing > 0 else { return "\(count) / \(maximumLength)" }
        return "\(count) / \(maximumLength) · encore \(missing) caractère\(missing > 1 ? "s" : "") minimum"
    }
}

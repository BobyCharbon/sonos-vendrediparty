import SwiftUI

/// Groupes : nouveau graphisme (17.11). Chaque groupe porte un emoji et une des 6 couleurs de Party (base :
/// member_groups.emoji / color, migration 20261117100000) ; la tuile = son emoji sur le dégradé de sa couleur.
/// Mêmes couleurs que le module Événements (web/events/src/lib/groups.ts).
enum GroupLook {
    /// Dégradé (du clair au profond) d'une couleur de groupe ; couleur inconnue : rose, la couleur de Party.
    static func gradient(_ color: String?) -> (from: Color, to: Color) {
        switch color {
        case "coral": return (Color(hex: 0xFFC977), Color(hex: 0xFF7A59))
        case "mint": return (Color(hex: 0x7CEDBB), Color(hex: 0x22B07D))
        case "sky": return (Color(hex: 0x8FD6FF), Color(hex: 0x3D8BFF))
        case "lavender": return (Color(hex: 0xCBBDFF), Color(hex: 0x7B6CF6))
        case "lemon": return (Color(hex: 0xFFEA9C), Color(hex: 0xFFB347))
        default: return (Color(hex: 0xFF8FC0), Color(hex: 0xFF4F9A))
        }
    }

    /// Page du module Événements : la page d'un groupe (identifiant), sa création (« new ») ou la liste (nil).
    /// nil si l'identifiant n'est pas un UUID (rien d'autre n'est envoyé à la page).
    static func pagePath(_ target: String?) -> String? {
        guard let target else { return "/events/groups" }
        if target == "new" { return "/events/group/new" }
        guard let id = UUID(uuidString: target) else { return nil }
        return "/events/group/\(id.uuidString.lowercased())"
    }
}

/// Tuile d'un groupe (lignes de Discussions) : son emoji sur le dégradé de sa couleur, liseré clair.
struct GroupTile: View {
    let emoji: String
    let color: String?
    var size: CGFloat = 48

    var body: some View {
        let g = GroupLook.gradient(color)
        RoundedRectangle(cornerRadius: size * 0.3, style: .continuous)
            .fill(LinearGradient(colors: [g.from, g.to], startPoint: .topLeading, endPoint: .bottomTrailing))
            .overlay(RoundedRectangle(cornerRadius: size * 0.3, style: .continuous).strokeBorder(.white.opacity(0.28), lineWidth: 1.5))
            .overlay(Text(emoji).font(.system(size: size * 0.5)))
            .frame(width: size, height: size)
            .shadow(color: g.to.opacity(0.4), radius: size * 0.15, y: size * 0.06)
            .accessibilityHidden(true)
    }
}

/// « Gérer le groupe », ⓘ, ✎ « Nouveau groupe », Réglages › Groupes : la page web du groupe (nouveau graphisme), sa
/// création ou la liste, dans l'onglet Événements. Donnée par l'app à toute la hiérarchie de vues ; nil hors de l'app.
struct OpenGroupPageAction {
    /// nil : la liste des groupes ; "new" : la création en 2 étapes ; un identifiant : la page de ce groupe.
    let open: @MainActor (_ target: String?) -> Void
}

private struct OpenGroupPageKey: EnvironmentKey {
    static let defaultValue: OpenGroupPageAction? = nil
}

extension EnvironmentValues {
    var openGroupPage: OpenGroupPageAction? {
        get { self[OpenGroupPageKey.self] }
        set { self[OpenGroupPageKey.self] = newValue }
    }
}

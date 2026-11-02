import SwiftUI

/// Mouvements de la télé, tous au même endroit : un ressort doux pour l'état qui arrive chaque seconde, et un simple
/// fondu quand « Réduire les animations » est activé (Réglages > Accessibilité de l'Apple TV).
/// Rien ne se rejoue à chaque rafraîchissement : seul ce qui a réellement changé bouge.
enum Motion {
    static var reduced: Bool { UIAccessibility.isReduceMotionEnabled }

    /// Ce qui a changé depuis le dernier état (une ligne qui monte, un chiffre, une carte) glisse à sa place.
    static var update: Animation { reduced ? .easeInOut(duration: 0.25) : .spring(response: 0.5, dampingFraction: 0.82) }
    /// Arrivée marquée (annonce, podium, carte) : ressort plus vif, un léger rebond.
    static var pop: Animation { reduced ? .easeOut(duration: 0.25) : .spring(response: 0.5, dampingFraction: 0.62) }

    /// L'animation voulue, ou un fondu court si les animations sont réduites.
    static func animation(_ a: Animation) -> Animation { reduced ? .easeInOut(duration: 0.25) : a }
}

extension View {
    /// Petit sursaut quand `value` change (un vote de plus, un gobelet en moins) : l'œil voit ce qui vient de bouger.
    /// Ne se déclenche qu'au changement, jamais au rafraîchissement d'un état identique.
    @ViewBuilder func bump<V: Equatable>(on value: V, scale: CGFloat = 1.18) -> some View {
        if Motion.reduced {
            self
        } else {
            phaseAnimator([1, scale], trigger: value) { view, s in view.scaleEffect(s) } animation: { s in
                s == scale ? .spring(response: 0.22, dampingFraction: 0.5) : .spring(response: 0.35, dampingFraction: 0.7)
            }
        }
    }
}

extension AnyTransition {
    /// La transition voulue, ou un fondu si les animations sont réduites.
    static func motion(_ t: AnyTransition) -> AnyTransition { Motion.reduced ? .opacity : t }
    /// Arrivée d'un élément nouveau (prénom, carte, résultat) : il grossit en apparaissant.
    static var popIn: AnyTransition { .motion(.scale(scale: 0.5).combined(with: .opacity)) }
}

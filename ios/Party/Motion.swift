import SwiftUI
import UIKit

/// Animations communes de l'app native : les mêmes ressorts partout, sobres, façon Apple.
/// « Réduire les animations » (Réglages › Accessibilité) : plus de mouvement, un simple fondu court.
/// iOS 16 minimum : pas de .snappy / .smooth / .bouncy (iOS 17), leurs équivalents en ressorts classiques.
enum Motion {
    /// Réponse directe à un geste (bouton, ajout, retrait, bascule) : rapide, sans rebond visible.
    static let snappy = Animation.spring(response: 0.32, dampingFraction: 0.86)
    /// Changement d'état d'un écran (chargement → contenu, vide, erreur), carte qui apparaît : plus posé.
    static let smooth = Animation.spring(response: 0.45, dampingFraction: 0.92)
    /// Petit rebond : succès, réaction, pastille qui arrive.
    static let bouncy = Animation.spring(response: 0.38, dampingFraction: 0.7)
    /// Réduire les animations : fondu, sans déplacement ni changement d'échelle.
    static let fade = Animation.easeInOut(duration: 0.2)

    /// Hors d'une vue (store, rappel) : l'environnement SwiftUI n'est pas lisible, on lit le réglage d'iOS.
    static var reduced: Bool { UIAccessibility.isReduceMotionEnabled }

    /// L'animation à jouer : celle demandée, ou un fondu si Réduire les animations est activé.
    static func pick(_ animation: Animation, reduced: Bool = Motion.reduced) -> Animation {
        reduced ? fade : animation
    }

    /// withAnimation qui respecte Réduire les animations.
    @discardableResult
    static func animate<Result>(_ animation: Animation = snappy, _ body: () throws -> Result) rethrows -> Result {
        try withAnimation(pick(animation), body)
    }
}

extension AnyTransition {
    /// Carte, ligne ou bulle qui arrive : fondu + léger agrandissement depuis 96 % et petite montée.
    static var cardInsert: AnyTransition {
        .asymmetric(insertion: .opacity.combined(with: .scale(scale: 0.96)).combined(with: .offset(y: 8)),
                    removal: .opacity.combined(with: .scale(scale: 0.96)))
    }

    /// Bandeau d'information posé en bas de l'écran.
    static var banner: AnyTransition { .move(edge: .bottom).combined(with: .opacity) }

    /// Élément qui se déplie sous un autre (section, bandeau, détail) : fondu et courte descente, sans passer
    /// par-dessus ce qui est au-dessus (move(edge: .top) le faisait glisser sur l'en-tête).
    static var unfold: AnyTransition {
        .asymmetric(insertion: .opacity.combined(with: .offset(y: -8)), removal: .opacity)
    }
}

private struct MotionAnimation<Value: Equatable>: ViewModifier {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    let animation: Animation
    let value: Value

    func body(content: Content) -> some View {
        content.animation(Motion.pick(animation, reduced: reduceMotion), value: value)
    }
}

private struct MotionTransition: ViewModifier {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    let transition: AnyTransition

    func body(content: Content) -> some View {
        content.transition(reduceMotion ? .opacity : transition)
    }
}

/// Bouton qui s'enfonce légèrement sous le doigt (cartes, pastilles), comme les tuiles d'iOS.
struct PressableStyle: ButtonStyle {
    var scale: CGFloat = 0.96

    func makeBody(configuration: Configuration) -> some View {
        PressableBody(configuration: configuration, scale: scale)
    }

    private struct PressableBody: View {
        @Environment(\.accessibilityReduceMotion) private var reduceMotion
        let configuration: ButtonStyleConfiguration
        let scale: CGFloat

        var body: some View {
            configuration.label
                .scaleEffect(configuration.isPressed && !reduceMotion ? scale : 1)
                .opacity(configuration.isPressed ? 0.85 : 1)
                .animation(Motion.pick(Motion.snappy, reduced: reduceMotion), value: configuration.isPressed)
        }
    }
}

extension View {
    /// .animation(_:value:) qui devient un fondu avec Réduire les animations.
    func motion<Value: Equatable>(_ animation: Animation = Motion.snappy, value: Value) -> some View {
        modifier(MotionAnimation(animation: animation, value: value))
    }

    /// .transition(_:) qui devient un fondu avec Réduire les animations.
    func motionTransition(_ transition: AnyTransition = .cardInsert) -> some View {
        modifier(MotionTransition(transition: transition))
    }
}

/// Retours haptiques de l'app : un seul vocabulaire, partout le même sens.
@MainActor
enum Haptics {
    /// Toucher léger : bascule, choix dans une liste, ajout d'une réaction.
    static func tap() { UIImpactFeedbackGenerator(style: .light).impactOccurred() }
    /// Geste marqué : appui long, début d'un enregistrement, élément soulevé.
    static func press() { UIImpactFeedbackGenerator(style: .medium).impactOccurred() }
    /// Sélection qui change (onglet, cran d'une liste qu'on réordonne).
    static func selection() { UISelectionFeedbackGenerator().selectionChanged() }
    /// L'action a réussi (titre ajouté, message envoyé, événement créé).
    static func success() { UINotificationFeedbackGenerator().notificationOccurred(.success) }
    /// Avertissement : action refusée sans gravité.
    static func warning() { UINotificationFeedbackGenerator().notificationOccurred(.warning) }
    /// L'action a échoué.
    static func error() { UINotificationFeedbackGenerator().notificationOccurred(.error) }
}

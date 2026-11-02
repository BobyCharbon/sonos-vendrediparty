import SwiftUI

/// Carte à jouer (« QD », « 10H », « TS ») ; « ?? » = carte cachée, montrée de dos.
/// Quand une carte cachée est dévoilée (carte de la banque, Pyramide), elle se retourne en 3D.
struct PlayingCard: View {
    let code: String
    var width: CGFloat = 86

    private var hidden: Bool { code.isEmpty || code.contains("?") }
    private var suit: Character { code.last ?? "?" }
    private var rank: String {
        let r = String(code.dropLast())
        return r == "T" ? "10" : r
    }
    private var sign: String { ["S": "♠", "H": "♥", "D": "♦", "C": "♣"][String(suit)] ?? "" }
    private var red: Bool { suit == "H" || suit == "D" }

    var body: some View {
        ZStack {
            front.modifier(FlipSide(angle: hidden ? 180 : 0, isFront: true))
            back.modifier(FlipSide(angle: hidden ? 180 : 0, isFront: false))
        }
        .frame(width: width, height: width * 1.4)
        .shadow(color: .black.opacity(0.35), radius: 6, y: 4)
        .accessibilityElement()
        .accessibilityLabel(hidden ? "Carte cachée" : "\(rank) \(sign)")
    }

    private var front: some View {
        ZStack {
            RoundedRectangle(cornerRadius: width * 0.12).fill(.white)
            if !hidden {
                VStack(spacing: 0) {
                    Text(rank).font(.system(size: width * 0.38, weight: .heavy))
                    Text(sign).font(.system(size: width * 0.34))
                }
                .foregroundStyle(red ? Color(red: 0.85, green: 0.1, blue: 0.2) : .black)
            }
        }
    }

    private var back: some View {
        ZStack {
            RoundedRectangle(cornerRadius: width * 0.12)
                .fill(LinearGradient(colors: [TV.accent, TV.lavender], startPoint: .topLeading, endPoint: .bottomTrailing))
            Text("🎉").font(.system(size: width * 0.4))
        }
    }
}

/// Une face de carte pendant qu'elle se retourne : l'angle est animé (0 = face visible, 180 = dos visible), chaque face
/// n'est montrée que sur sa moitié du tour. Animations réduites : simple fondu d'une face à l'autre, sans rotation.
struct FlipSide: ViewModifier, Animatable {
    var angle: Double
    let isFront: Bool

    var animatableData: Double {
        get { angle }
        set { angle = newValue }
    }

    private var visible: Bool { isFront ? angle < 90 : angle >= 90 }

    func body(content: Content) -> some View {
        if Motion.reduced {
            content.opacity(isFront ? 1 - angle / 180 : angle / 180)
        } else {
            content
                .rotation3DEffect(.degrees(isFront ? angle : angle - 180), axis: (x: 0, y: 1, z: 0), perspective: 0.5)
                .opacity(visible ? 1 : 0)
        }
    }
}

/// Carte distribuée : elle arrive d'en haut à droite en tournant, comme lancée par le croupier.
private struct DealEffect: ViewModifier {
    let progress: Double
    func body(content: Content) -> some View {
        content
            .offset(x: 90 * (1 - progress), y: -140 * (1 - progress))
            .rotationEffect(.degrees(-18 * (1 - progress)))
            .opacity(progress)
    }
}

extension AnyTransition {
    static var deal: AnyTransition {
        .motion(.asymmetric(insertion: .modifier(active: DealEffect(progress: 0), identity: DealEffect(progress: 1)),
                            removal: .opacity))
    }
}

/// Main de cartes (qui se chevauchent) ; une nouvelle carte arrive distribuée, une carte dévoilée se retourne.
struct CardRow: View {
    let cards: [JSON]
    var width: CGFloat = 86
    var body: some View {
        HStack(spacing: -width * 0.25) {
            ForEach(Array(cards.enumerated()), id: \.offset) { _, c in
                PlayingCard(code: c.string ?? "??", width: width).transition(.deal)
            }
        }
    }
}

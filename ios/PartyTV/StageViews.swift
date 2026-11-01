import SwiftUI

/// Identité de la scène : un autre jeu (ou une autre partie) remplace la scène entière, avec sa transition ;
/// une nouvelle phase du même jeu, elle, ne fait que glisser ce qui change.
enum GameScene {
    static func key(_ shown: JSON) -> String { "\(shown["code"].string ?? "")-\(shown["type"].string ?? "")" }
}

/// Pause de l'animateur : un voile sur toute la télé, le symbole respire lentement (rien ne bouge si les animations
/// sont réduites).
struct PauseVeil: View {
    let by: String
    static let breath = 1.8

    var body: some View {
        ZStack {
            Color.black.opacity(0.6).ignoresSafeArea()
            VStack(spacing: 20) {
                Text("⏸").font(.system(size: 140)).breathing(period: Self.breath)
                Text("Pause").font(.system(size: 110, weight: .black))
                Text("\(by) a mis la partie en pause").font(.system(size: 40, weight: .semibold)).foregroundStyle(TV.muted)
            }
            .padding(70).glass(cornerRadius: 60)
            .transition(.motion(.scale(scale: 0.85).combined(with: .opacity)))
        }
    }
}

/// Barre de résultat (votes, répartition) : elle pousse de zéro jusqu'à sa part quand les résultats arrivent,
/// les barres l'une après l'autre (`order`), puis suit les changements. Animations réduites : à sa taille d'emblée.
struct GrowBar: View {
    let share: CGFloat
    let color: Color
    var order = 0
    var minWidth: CGFloat = 14
    @State private var grown = Motion.reduced

    var body: some View {
        GeometryReader { geo in
            Capsule().fill(color).frame(width: grown ? max(minWidth, geo.size.width * min(1, share)) : minWidth)
        }
        .onAppear {
            guard !grown else { return }
            withAnimation(.spring(response: 0.8, dampingFraction: 0.8).delay(0.25 + Double(order) * 0.12)) { grown = true }
        }
    }
}

extension View {
    /// Halo lumineux qui pulse lentement derrière le grand QR code (salle d'attente) : on le repère de loin.
    /// Le QR lui-même ne bouge jamais (un téléphone doit pouvoir le lire à tout moment).
    @ViewBuilder func qrHalo() -> some View {
        if Motion.reduced {
            self.shadow(color: TV.accent.opacity(0.5), radius: 30)
        } else {
            self.background {
                RoundedRectangle(cornerRadius: 40, style: .continuous).fill(TV.accent)
                    .blur(radius: 40)
                    .phaseAnimator([false, true]) { halo, on in
                        halo.opacity(on ? 0.75 : 0.25).scaleEffect(on ? 1.08 : 0.96)
                    } animation: { _ in .easeInOut(duration: 1.6) }
            }
        }
    }

    /// Respiration lente et continue (attire l'œil sans gêner la lecture) ; immobile si les animations sont réduites.
    @ViewBuilder func breathing(period: Double = 1.8, scale: CGFloat = 1.07) -> some View {
        if Motion.reduced {
            self
        } else {
            phaseAnimator([false, true]) { view, up in
                view.scaleEffect(up ? scale : 1).opacity(up ? 1 : 0.88)
            } animation: { _ in .easeInOut(duration: period / 2) }
        }
    }
}

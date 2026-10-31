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

extension View {
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

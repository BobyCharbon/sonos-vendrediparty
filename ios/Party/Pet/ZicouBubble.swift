import SwiftUI
import WebKit

/// Bulle de Zicou native (avis 3cd6d282745b de l'admin, 08.11) : sa petite tête par-dessus tous les écrans de l'app,
/// déplaçable d'un glisser vers un des six emplacements (coins et milieux des bords) pour libérer les boutons dessous,
/// et masquable dans Réglages › Bulle de Zicou. La page décrit Zicou (app/static/pet/zicou-home.js →
/// `PartyNative.zicou.update`) ; un toucher ouvre Zicou dans la page (`ZicouHome.openFromApp`).
struct ZicouBubbleState: Decodable, Equatable {
    /// Faux pendant une partie en plein écran, dans l'onglet Zicou, sous une feuille, sans compte…
    let visible: Bool
    let stage: String
    let emotion: String
    /// Point rouge rare : il a faim, un ami lui a offert quelque chose.
    let red: Bool
    let asleep: Bool
    /// Libellé VoiceOver (« Paillette : content »).
    let label: String
    /// « Psst… ton cadeau du jour ! » : affiché quelques secondes à côté de la bulle.
    let hint: String?

    init?(message body: Any) {
        guard JSONSerialization.isValidJSONObject(body),
              let data = try? JSONSerialization.data(withJSONObject: body),
              let state = try? JSONDecoder().decode(ZicouBubbleState.self, from: data) else { return nil }
        self = state
    }
}

/// Réglage de l'appareil (Réglages › Bulle de Zicou) et emplacement choisi d'un glisser.
enum ZicouBubblePrefs {
    static let shownKey = "zicouBubbleShown"
    static let spotKey = "zicouBubbleSpot"
}

/// Les six emplacements de la bulle ; le glisser la pose sur le plus proche.
enum ZicouSpot: String, CaseIterable {
    case topLeading, topTrailing, middleLeading, middleTrailing, bottomLeading, bottomTrailing

    var leading: Bool { [.topLeading, .middleLeading, .bottomLeading].contains(self) }

    /// Centre de la bulle dans une zone `size` (marges des bords et de l'encoche comprises).
    func center(in size: CGSize, insets: EdgeInsets, side: CGFloat) -> CGPoint {
        let half = side / 2
        let x = leading ? insets.leading + ZicouBubble.margin + half : size.width - insets.trailing - ZicouBubble.margin - half
        let top = insets.top + ZicouBubble.topClearance + half
        let bottom = size.height - ZicouBubble.margin - half
        switch self {
        case .topLeading, .topTrailing: return CGPoint(x: x, y: top)
        case .middleLeading, .middleTrailing: return CGPoint(x: x, y: (top + bottom) / 2)
        case .bottomLeading, .bottomTrailing: return CGPoint(x: x, y: bottom)
        }
    }

    static func nearest(to point: CGPoint, in size: CGSize, insets: EdgeInsets, side: CGFloat) -> ZicouSpot {
        allCases.min { a, b in
            a.center(in: size, insets: insets, side: side).distance(to: point) < b.center(in: size, insets: insets, side: side).distance(to: point)
        } ?? .bottomTrailing
    }
}

struct ZicouBubble: View {
    let state: ZicouBubbleState
    let insets: EdgeInsets
    let open: () -> Void

    static let side: CGFloat = 52
    static let margin: CGFloat = 14
    /// Sous le titre des écrans (et la cloche des Événements) : la bulle ne les couvre pas en haut.
    static let topClearance: CGFloat = 112
    private static let hintSeconds: Double = 4.5

    @AppStorage(ZicouBubblePrefs.spotKey) private var spotName = ZicouSpot.bottomTrailing.rawValue
    @State private var drag: CGSize = .zero
    @State private var dragging = false
    @State private var shownHint: String?
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private var spot: ZicouSpot { ZicouSpot(rawValue: spotName) ?? .bottomTrailing }

    var body: some View {
        GeometryReader { proxy in
            let base = spot.center(in: proxy.size, insets: insets, side: Self.side)
            ZStack {
                if let shownHint {
                    hintView(shownHint)
                        .position(x: hintX(base: base, width: proxy.size.width), y: base.y - Self.side / 2 - 22)
                        .transition(.opacity.combined(with: .scale(scale: 0.9)))
                }
                head
                    .position(x: base.x + drag.width, y: base.y + drag.height)
                    .gesture(moveGesture(base: base, size: proxy.size))
            }
        }
        .onAppear { showHint(state.hint) }
        .onChange(of: state.hint) { showHint($0) }
    }

    private var head: some View {
        Button {
            Haptics.tap()
            open()
        } label: {
            ZStack(alignment: .topTrailing) {
                ZicouFigure(emotion: state.emotion, stage: state.stage)
                    .padding(5)
                    .frame(width: Self.side, height: Self.side)
                    .background(Circle().fill(RadialGradient(colors: Z.night, center: .top, startRadius: 2, endRadius: Self.side)))
                    .overlay(Circle().strokeBorder(Z.mood[state.emotion] ?? Z.cyan, lineWidth: 2.5))
                    .saturation(state.asleep ? 0.7 : 1)
                    .brightness(state.asleep ? -0.08 : 0)
                    .environment(\.zicouForcedTint, false)
                if state.red {
                    Circle().fill(Color(hex: 0xFF3B30)).frame(width: 13, height: 13)
                        .overlay(Circle().stroke(AppConfig.background, lineWidth: 2))
                        .offset(x: 1, y: -1)
                }
            }
            .scaleEffect(dragging ? 1.12 : 1)
            .shadow(color: .black.opacity(dragging ? 0.5 : 0.35), radius: dragging ? 14 : 8, y: dragging ? 8 : 4)
        }
        .buttonStyle(.plain)
        .frame(width: Self.side + 8, height: Self.side + 8)  // zone de toucher de 60 pt
        .contentShape(Circle())
        .accessibilityLabel(state.label)
        .accessibilityHint("Ouvre Zicou. Se déplace en la faisant glisser ; se masque dans les Réglages.")
        .accessibilityIdentifier("zicou-bubble")
        .accessibilityActions {
            ForEach(ZicouSpot.allCases.filter { $0 != spot }, id: \.self) { target in
                Button(Self.spotName(target)) { move(to: target) }
            }
        }
    }

    private func hintView(_ text: String) -> some View {
        Text(text)
            .font(.footnote.weight(.bold))
            .foregroundStyle(Z.ink)
            .padding(.horizontal, 12).padding(.vertical, 7)
            .background(.white, in: Capsule())
            .shadow(color: .black.opacity(0.35), radius: 10, y: 4)
            .fixedSize()
            .allowsHitTesting(false)
    }

    /// Le message reste dans l'écran : collé au bord du côté de la bulle.
    private func hintX(base: CGPoint, width: CGFloat) -> CGFloat {
        let room: CGFloat = 110
        return spot.leading ? max(base.x + room - Self.side / 2, room + Self.margin) : min(base.x - room + Self.side / 2, width - room - Self.margin)
    }

    private func moveGesture(base: CGPoint, size: CGSize) -> some Gesture {
        DragGesture(minimumDistance: 8)
            .onChanged { value in
                if !dragging { Haptics.selection() }
                dragging = true
                drag = value.translation
            }
            .onEnded { value in
                let end = CGPoint(x: base.x + value.predictedEndTranslation.width, y: base.y + value.predictedEndTranslation.height)
                let target = ZicouSpot.nearest(to: end, in: size, insets: insets, side: Self.side)
                let landed = target.center(in: size, insets: insets, side: Self.side)
                // La bulle repart de là où le doigt l'a lâchée vers son nouvel emplacement, sans saut.
                spotName = target.rawValue
                drag = CGSize(width: base.x + value.translation.width - landed.x, height: base.y + value.translation.height - landed.y)
                withAnimation(Motion.pick(Motion.bouncy, reduced: reduceMotion)) {
                    drag = .zero
                    dragging = false
                }
                Haptics.tap()
            }
    }

    private func move(to target: ZicouSpot) {
        withAnimation(Motion.pick(Motion.smooth, reduced: reduceMotion)) { spotName = target.rawValue }
    }

    private func showHint(_ text: String?) {
        guard let text, !text.isEmpty else { return }
        withAnimation(Motion.pick(Motion.bouncy, reduced: reduceMotion)) { shownHint = text }
        DispatchQueue.main.asyncAfter(deadline: .now() + Self.hintSeconds) {
            withAnimation(Motion.pick(Motion.fade, reduced: reduceMotion)) { if shownHint == text { shownHint = nil } }
        }
    }

    static func spotName(_ spot: ZicouSpot) -> String {
        switch spot {
        case .topLeading: return "Placer en haut à gauche"
        case .topTrailing: return "Placer en haut à droite"
        case .middleLeading: return "Placer au milieu à gauche"
        case .middleTrailing: return "Placer au milieu à droite"
        case .bottomLeading: return "Placer en bas à gauche"
        case .bottomTrailing: return "Placer en bas à droite"
        }
    }
}

/// `PartyNative.zicou.update(state)` (page principale seulement) → bulle native.
final class ZicouBubbleHandler: NSObject, WKScriptMessageHandler {
    static let handler = "partyZicou"
    private weak var model: WebModel?

    init(model: WebModel) {
        self.model = model
    }

    @MainActor
    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.frameInfo.isMainFrame, AppConfig.isInternal(message.frameInfo.securityOrigin.url),
              let state = ZicouBubbleState(message: message.body) else { return }
        model?.showZicouBubble(state)
    }
}

private extension CGPoint {
    func distance(to other: CGPoint) -> CGFloat { hypot(x - other.x, y - other.y) }
}

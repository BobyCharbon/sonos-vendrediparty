import SwiftUI

/// Appui long sur une bulle, façon WhatsApp : le fil se voile, la bulle se soulève à sa place (remontée ou descendue
/// juste assez pour tout montrer), la barre de réactions au-dessus, le menu dessous (Répondre, Copier, Épingler,
/// Signaler, Supprimer). Toucher le voile referme. Réduire les animations : simple fondu.
struct BubbleFocusOverlay: View {
    let focus: BubbleFocus
    /// Réactions proposées (vide : pas de barre, par exemple sans pouvoir réagir).
    let reactions: [String]
    let actions: [BubbleAction]
    let onReact: (String) -> Void
    let onClose: () -> Void

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var shown = false

    private var accent: Color { Color(uiColor: AppConfig.uiAccent) }
    private static let rowHeight: CGFloat = 46
    private static let menuWidth: CGFloat = 236
    private static let emojiSide: CGFloat = 42
    private static let margin: CGFloat = 12
    private static let gap: CGFloat = 8

    var body: some View {
        GeometryReader { geo in
            let origin = geo.frame(in: .global).origin
            let f = focus.frame.offsetBy(dx: -origin.x, dy: -origin.y)
            let barHeight: CGFloat = reactions.isEmpty ? 0 : Self.emojiSide + 12
            let menuHeight = CGFloat(actions.count) * Self.rowHeight
            let room = geo.size.height - 2 * Self.margin - (barHeight > 0 ? barHeight + Self.gap : 0) - (menuHeight > 0 ? menuHeight + Self.gap : 0)
            let height = max(44, min(f.height, room))
            let minTop = Self.margin + (barHeight > 0 ? barHeight + Self.gap : 0)
            let maxTop = geo.size.height - Self.margin - (menuHeight > 0 ? menuHeight + Self.gap : 0) - height
            let top = min(max(f.minY, minTop), max(minTop, maxTop))
            let mine = focus.message.mine
            let barWidth = CGFloat(reactions.count) * Self.emojiSide + 12
            let barX = clampX(mine ? f.maxX - barWidth : f.minX, width: barWidth, in: geo.size.width)
            let menuX = clampX(mine ? f.maxX - Self.menuWidth : f.minX, width: Self.menuWidth, in: geo.size.width)

            ZStack(alignment: .topLeading) {
                // Voile : le fil flou derrière ; un toucher referme.
                Rectangle().fill(.ultraThinMaterial)
                    .overlay(Color.black.opacity(0.35))
                    .opacity(shown ? 1 : 0)
                    .ignoresSafeArea()
                    .onTapGesture { close() }
                    .accessibilityLabel("Fermer")
                    .accessibilityAddTraits(.isButton)
                    .accessibilityAction { close() }

                if !reactions.isEmpty {
                    reactionBar
                        .frame(width: barWidth, height: barHeight - 12)
                        .scaleEffect(shown || reduceMotion ? 1 : 0.4, anchor: mine ? .bottomTrailing : .bottomLeading)
                        .opacity(shown ? 1 : 0)
                        .offset(x: barX, y: top - Self.gap - (barHeight - 12))
                }

                focus.preview
                    .frame(width: f.width, height: height, alignment: .top)
                    .clipped()
                    .allowsHitTesting(false)
                    .scaleEffect(shown && !reduceMotion ? 1.02 : 1)
                    .shadow(color: .black.opacity(shown ? 0.35 : 0), radius: 16, y: 6)
                    .offset(x: f.minX, y: shown || reduceMotion ? top : f.minY)
                    .accessibilityHidden(true)

                if !actions.isEmpty {
                    menu
                        .frame(width: Self.menuWidth)
                        .scaleEffect(shown || reduceMotion ? 1 : 0.5, anchor: mine ? .topTrailing : .topLeading)
                        .opacity(shown ? 1 : 0)
                        .offset(x: menuX, y: top + height + Self.gap)
                }
            }
            .frame(width: geo.size.width, height: geo.size.height, alignment: .topLeading)
        }
        .accessibilityAddTraits(.isModal)
        .onAppear {
            Haptics.press()
            Motion.animate(Motion.bouncy) { shown = true }
        }
    }

    private func clampX(_ x: CGFloat, width: CGFloat, in total: CGFloat) -> CGFloat {
        min(max(Self.margin, x), max(Self.margin, total - Self.margin - width))
    }

    private func close(then work: (() -> Void)? = nil) {
        Motion.animate(Motion.snappy) { shown = false }
        DispatchQueue.main.asyncAfter(deadline: .now() + (reduceMotion ? 0.15 : 0.22)) {
            onClose()
            work?()
        }
    }

    private var reactionBar: some View {
        HStack(spacing: 0) {
            ForEach(Array(reactions.enumerated()), id: \.element) { index, emoji in
                let mineReaction = focus.message.reactions.contains { $0.emoji == emoji && $0.mine }
                Button {
                    Haptics.tap()
                    close { onReact(emoji) }
                } label: {
                    Text(verbatim: emoji).font(.system(size: 26))
                        .frame(width: Self.emojiSide, height: Self.emojiSide)
                        .background(mineReaction ? accent.opacity(0.3) : Color.clear, in: Circle())
                }
                .buttonStyle(PressableStyle(scale: 0.8))
                // Les émojis arrivent l'un après l'autre, comme dans WhatsApp.
                .scaleEffect(shown || reduceMotion ? 1 : 0.3)
                .animation(reduceMotion ? Motion.fade : Motion.bouncy.delay(Double(index) * 0.03), value: shown)
                .accessibilityLabel(emoji)
                .accessibilityHint(mineReaction ? "Retirer ma réaction" : "Réagir")
            }
        }
        .padding(.horizontal, 6)
        .background(Color(red: 0.16, green: 0.13, blue: 0.27), in: Capsule())
        .overlay(Capsule().stroke(Color.white.opacity(0.1)))
        .shadow(color: .black.opacity(0.3), radius: 12, y: 4)
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Réactions")
    }

    private var menu: some View {
        VStack(spacing: 0) {
            ForEach(actions) { action in
                Button {
                    Haptics.selection()
                    close(then: action.run)
                } label: {
                    HStack {
                        Text(action.title)
                        Spacer(minLength: 8)
                        Image(systemName: action.icon)
                    }
                    .font(.body)
                    .foregroundStyle(action.destructive ? Color.red : Color.white)
                    .padding(.horizontal, 16)
                    .frame(height: Self.rowHeight)
                    .contentShape(Rectangle())
                }
                .buttonStyle(MenuRowStyle())
                .accessibilityIdentifier("chat-menu-\(action.id)")
                if action.id != actions.last?.id { Divider().overlay(Color.white.opacity(0.06)) }
            }
        }
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .shadow(color: .black.opacity(0.3), radius: 14, y: 6)
    }
}

/// Ligne du menu : elle s'éclaire sous le doigt.
private struct MenuRowStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label.background(Color.white.opacity(configuration.isPressed ? 0.12 : 0))
    }
}

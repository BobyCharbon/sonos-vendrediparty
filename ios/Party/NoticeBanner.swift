import SwiftUI

/// Bandeau bref en bas de l'écran (titre ajouté, enregistré, erreur…), le même partout dans l'app native.
/// Il monte en glissant, s'efface tout seul, et son apparition s'accompagne du retour haptique qui va avec
/// (succès, erreur ; aucun pour une simple information). Un nouveau message relance le délai.
struct NoticeBanner: View {
    struct Notice: Equatable {
        enum Tone { case info, success, error }

        let text: String
        var tone: Tone = .info
        /// Identité du message : deux messages au même texte sont deux apparitions distinctes.
        var id: AnyHashable?

        var key: AnyHashable { id ?? AnyHashable(text) }
    }

    struct Action {
        let title: String
        let run: () -> Void
    }

    let notice: Notice?
    var action: Action?
    var seconds: Double = 3
    var material = false
    let dismiss: () -> Void

    var body: some View {
        ZStack(alignment: .bottom) {
            if let notice {
                capsule(notice)
                    .motionTransition(.banner)
                    .task(id: notice.key) {
                        try? await Task.sleep(for: .seconds(seconds))
                        guard !Task.isCancelled else { return }
                        dismiss()
                    }
                    .onAppear { feedback(notice) }
                    .onChange(of: notice.key) { _ in feedback(notice) }
            }
        }
        .frame(maxWidth: .infinity)
        // Apparition et disparition animées même quand le store change le message sans withAnimation.
        .motion(Motion.snappy, value: notice?.key)
    }

    private func capsule(_ notice: Notice) -> some View {
        HStack(spacing: 12) {
            Text(notice.text).font(.subheadline.weight(.semibold)).multilineTextAlignment(.center)
            if let action {
                Button(action.title) {
                    Haptics.tap()
                    action.run()
                }
                .font(.subheadline.weight(.bold)).foregroundStyle(Palette.accent)
            }
        }
        .padding(.horizontal, 16).padding(.vertical, 12)
        .background(background(notice), in: Capsule())
        .contentShape(Capsule())
        .onTapGesture { dismiss() }  // toucher le bandeau le ferme aussitôt
        .padding(.horizontal, 16).padding(.bottom, 12)
        .accessibilityAddTraits(.isStaticText)
    }

    private func background(_ notice: Notice) -> AnyShapeStyle {
        if notice.tone == .error { return AnyShapeStyle(Color.red.opacity(0.9)) }
        return material ? AnyShapeStyle(.ultraThinMaterial) : AnyShapeStyle(Palette.card)
    }

    private func feedback(_ notice: Notice) {
        switch notice.tone {
        case .success: Haptics.success()
        case .error: Haptics.error()
        case .info: break
        }
    }
}

extension NoticeBanner.Notice {
    init(text: String, isError: Bool, id: AnyHashable? = nil) {
        self.init(text: text, tone: isError ? .error : .success, id: id)
    }
}

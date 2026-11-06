import SwiftUI

/// « Créer avec l'IA » : « 1 La soirée · 2 Qui est invité · 3 C'est en ligne » (mêmes mots que la page web,
/// web/events/src/components/AIEventSteps.tsx). L'étape en cours en couleur, celles d'avant cochées.
struct AIEventSteps: View {
    let current: Int

    var body: some View {
        HStack(spacing: 6) {
            ForEach(Array(AIEvent.steps.enumerated()), id: \.offset) { index, label in
                let number = index + 1
                let done = number < current
                let on = number == current
                HStack(spacing: 6) {
                    ZStack {
                        Circle().fill(on || done ? Palette.accent : Color.white.opacity(0.12))
                        if done {
                            Image(systemName: "checkmark").font(.caption2.weight(.bold)).foregroundStyle(.black)
                        } else {
                            Text("\(number)").font(.caption2.weight(.bold)).foregroundStyle(on ? Color.black : Color.secondary)
                        }
                    }
                    .frame(width: 20, height: 20)
                    Text(label).font(.caption.weight(on ? .bold : .semibold))
                        .foregroundStyle(on ? Color.primary : Color.secondary)
                        .lineLimit(1).minimumScaleFactor(0.8)
                }
                .padding(.horizontal, 8).padding(.vertical, 7)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(on ? Palette.accent.opacity(0.2) : Color.white.opacity(0.06), in: Capsule())
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Étape \(current) sur 3 : \(AIEvent.steps[max(0, min(current, 3) - 1)])")
    }
}

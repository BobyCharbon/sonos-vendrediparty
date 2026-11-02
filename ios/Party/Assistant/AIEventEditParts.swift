import SwiftUI

/// « ✨ Modifier avec l'IA » : ce qu'on peut demander, avant de parler.
struct AIEditTips: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Dis ce qui change", systemImage: "sparkles").font(.title3.weight(.bold))
            Text("L'événement est déjà publié : l'IA ne touche qu'à ce que tu demandes, et te montre les changements avant d'enregistrer.")
                .foregroundStyle(.secondary)
            VStack(alignment: .leading, spacing: 6) {
                Text("Par exemple").font(.footnote.weight(.semibold)).foregroundStyle(.secondary)
                ForEach(Self.examples, id: \.self) { e in
                    Text("« \(e) »").font(.subheadline).italic().foregroundStyle(.secondary)
                }
            }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.white.opacity(0.06), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        }
        .accessibilityIdentifier("ai-edit-tips")
    }

    static let examples = [
        "Décale à 21 heures.",
        "Mets 15 bouteilles de vin et 3 paquets de chips dans qui amène quoi.",
        "Ajoute Tom en co-organisateur et invite Léa.",
        "Plus d'accompagnants, et 20 places maximum.",
    ]
}

/// La liste des changements (rien n'est encore écrit) et le choix de prévenir les invités.
struct AIChangesCard: View {
    let changes: [String]
    @Binding var announce: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label(changes.isEmpty ? "Rien ne change pour l'instant" : "Ce qui va changer", systemImage: "pencil.and.list.clipboard")
                .font(.headline).foregroundStyle(changes.isEmpty ? Color.secondary : Palette.accent)
            ForEach(changes, id: \.self) { c in Text("• \(c)").font(.subheadline) }
            if !changes.isEmpty {
                Toggle("Prévenir les invités dans la discussion", isOn: $announce)
                    .font(.subheadline)
                    .accessibilityIdentifier("ai-announce")
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Palette.accent.opacity(0.1), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .accessibilityIdentifier("ai-changes")
    }
}

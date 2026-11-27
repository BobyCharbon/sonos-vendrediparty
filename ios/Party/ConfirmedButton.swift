import SwiftUI

/// Bouton de suppression / retrait qui demande TOUJOURS une confirmation (règle de l'admin, 27.11) :
/// « <question> » puis <confirm> (rouge) / Annuler. À ne pas mettre dans un `Menu` (le menu se ferme avec son dialogue) :
/// là, un état dans la vue + `.confirmationDialog`.
struct ConfirmedButton<Label: View>: View {
    let question: String
    var confirm = "Supprimer"
    var message: String?
    let action: () -> Void
    @ViewBuilder let label: () -> Label
    @State private var asking = false

    var body: some View {
        Button(role: .destructive, action: { asking = true }, label: label)
            .confirmationDialog(question, isPresented: $asking, titleVisibility: .visible) {
                Button(confirm, role: .destructive, action: action)
                Button("Annuler", role: .cancel) {}
            } message: {
                if let message { Text(message) }
            }
    }
}

extension ConfirmedButton where Label == Text {
    init(_ title: String, question: String, confirm: String? = nil, message: String? = nil, action: @escaping () -> Void) {
        self.init(question: question, confirm: confirm ?? title, message: message, action: action) { Text(title) }
    }
}

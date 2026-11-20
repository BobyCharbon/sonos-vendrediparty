import SwiftUI

/// Réorganiser les discussions épinglées (avis e75a1d5af3ee, 20.11) : on glisse les poignées ≡, la première se place à
/// gauche des tuiles. « OK » enregistre (reorder_chat_pins), « Annuler » ne change rien.
struct ChatPinOrderSheet: View {
    @State var chats: [ChatSummary]
    let save: ([ChatSummary]) -> Void
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            List {
                Section {
                    ForEach(chats) { chat in
                        HStack(spacing: 12) {
                            ChatAvatar(chat: chat, size: 40)
                            Text(chat.name)
                                .font(.body.weight(.semibold))
                                .foregroundStyle(ChatNeon.t1)
                                .lineLimit(1)
                        }
                        .padding(.vertical, 4)
                        .listRowBackground(ChatNeon.theirs)
                        .accessibilityIdentifier("pin-order-\(chat.id)")
                    }
                    .onMove { from, to in chats.move(fromOffsets: from, toOffset: to) }
                } footer: {
                    Text("Glisse ≡ pour choisir l'ordre : la première est tout à gauche.")
                        .foregroundStyle(ChatNeon.t2)
                }
            }
            .environment(\.editMode, .constant(.active))
            .scrollContentBackground(.hidden)
            .background(ChatNeon.bg.ignoresSafeArea())
            .navigationTitle("Épinglées")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Annuler") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("OK") {
                        Haptics.tap()
                        save(chats)
                        dismiss()
                    }
                    .fontWeight(.bold)
                    .accessibilityIdentifier("pin-order-done")
                }
            }
        }
        .presentationDetents([.medium, .large])
        .accessibilityIdentifier("pin-order-sheet")
    }
}

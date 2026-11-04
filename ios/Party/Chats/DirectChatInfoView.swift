import SwiftUI

/// Infos d'un message direct (conversation privée à deux, 4.11) : la personne (sa fiche), les notifications de cette
/// conversation (tout ou rien) et le blocage. Personne d'autre ne lit cette conversation, ni les admins.
struct DirectChatInfoView: View {
    @ObservedObject var store: ChatsStore
    @ObservedObject private var contacts = ContactNames.shared
    @Environment(\.dismiss) private var dismiss
    @State private var showCard = false
    @State private var confirmBlock = false
    @State private var reporting: ReportTarget?

    var body: some View {
        NavigationStack {
            Form {
                if let chat = store.conversation, chat.isDirect {
                    let label = contacts.label(for: chat.userID, pseudo: chat.name)
                    Section {
                        VStack(spacing: 8) {
                            Initials(name: label.primary, photo: chat.photo, size: 88)
                            Text(label.primary).font(.title3.weight(.bold))
                            if let pseudo = label.secondary { Text(pseudo).foregroundStyle(.secondary) }
                            if chat.userID != nil {
                                Button("Voir la fiche") { showCard = true }.buttonStyle(.bordered)
                                    .accessibilityIdentifier("direct-card")
                            }
                        }
                        .frame(maxWidth: .infinity)
                        .listRowBackground(Color.clear)
                    }
                    Section {
                        Toggle("Nouveaux messages", isOn: Binding(get: { chat.notify != .none }, set: { on in
                            Haptics.selection()
                            Task { await store.setNotify(on ? .all : .none) }
                        }))
                        .accessibilityIdentifier("direct-notify")
                    } header: {
                        Text("Notifications")
                    } footer: {
                        Text("« Nouveau message de … » pour chaque message de cette conversation. Tous les messages directs se coupent dans Réglages › Notifications.")
                    }
                    Section {
                        if chat.blocked == true {
                            Button("Débloquer \(label.primary)") { Task { await store.setBlocked(false) } }
                                .accessibilityIdentifier("direct-unblock")
                        } else {
                            Button("Bloquer \(label.primary)", role: .destructive) { confirmBlock = true }
                                .accessibilityIdentifier("direct-block")
                        }
                        if let user = chat.userID {
                            Button("Signaler \(label.primary)") { reporting = ReportTarget(kind: .profile, id: user, label: label.primary) }
                                .accessibilityIdentifier("direct-report")
                        }
                    } header: {
                        Text("Confidentialité")
                    } footer: {
                        Text("Conversation privée : seuls vous deux la lisez. Une personne bloquée ne peut plus t'écrire (et toi non plus), ni te citer, t'inviter ou voir ta fiche ; elle n'en est pas prévenue. L'historique reste.")
                    }
                }
            }
            .scrollContentBackground(.hidden)
            .motion(Motion.smooth, value: store.conversation?.notify)
            .motion(Motion.smooth, value: store.conversation?.blocked)
            .background(AppConfig.background.ignoresSafeArea())
            .navigationTitle("Message direct")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("OK") { dismiss() } } }
            .confirmationDialog("Bloquer cette personne ?", isPresented: $confirmBlock, titleVisibility: .visible) {
                Button("Bloquer", role: .destructive) { Task { await store.setBlocked(true) } }
            } message: {
                Text("Elle ne pourra plus t'écrire. Tu pourras la débloquer ici.")
            }
            .sheet(item: $reporting) { ReportSheet(store: store.moderation, target: $0) }
            .sheet(isPresented: $showCard) {
                // Déjà dans la conversation : pas de « Écrire » sur sa fiche.
                if let user = store.conversation?.userID {
                    MemberCardView(store: store.privacy, memberID: user).environment(\.writeDirect, nil)
                }
            }
        }
        .preferredColorScheme(.dark)
    }
}

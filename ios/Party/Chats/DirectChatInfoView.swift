import SwiftUI

/// Infos d'un message direct (conversation privée à deux, 4.11) : la personne (son mini-profil), les notifications de
/// cette conversation (tout ou rien) et le blocage. Personne d'autre ne lit cette conversation, ni les admins.
/// Néon club (Discussions v2, 18.11).
struct DirectChatInfoView: View {
    @ObservedObject var store: ChatsStore
    @ObservedObject private var contacts = ContactNames.shared
    @Environment(\.dismiss) private var dismiss
    @Environment(\.conversationRoutes) private var routes
    @State private var person: PersonRef?
    @State private var confirmBlock = false
    @State private var reporting: ReportTarget?

    var body: some View {
        NavigationStack {
            Form {
                if let chat = store.conversation, chat.isDirect {
                    let label = contacts.label(for: chat.userID, pseudo: chat.name)
                    Section {
                        VStack(spacing: 10) {
                            ConvFace(id: chat.userID ?? chat.id, name: label.primary, photo: chat.photo, size: 96)
                                .overlay(Circle().strokeBorder(ConvNeon.lavender, lineWidth: 2))
                                .shadow(color: ConvNeon.lavDeep.opacity(0.5), radius: 18)
                            Text(label.primary).font(.system(.title2, design: .rounded).weight(.heavy)).foregroundStyle(ConvNeon.t1)
                            if let pseudo = label.secondary { Text(pseudo).foregroundStyle(ConvNeon.t2) }
                            if let user = chat.userID {
                                Button {
                                    Haptics.tap()
                                    person = PersonRef(id: user)
                                } label: {
                                    Text("Voir le profil").font(.subheadline.weight(.bold)).foregroundStyle(PronoTheme.fixed(0x120B26))
                                        .padding(.horizontal, 20).frame(minHeight: 44)
                                        .background(ConvNeon.lavender, in: Capsule())
                                }
                                .buttonStyle(PressableStyle())
                                .accessibilityIdentifier("direct-card")
                            }
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 6)
                        .listRowBackground(Color.clear)
                    }
                    Section {
                        Toggle("Nouveaux messages", isOn: Binding(get: { chat.notify != .none }, set: { on in
                            Haptics.selection()
                            Task { await store.setNotify(on ? .all : .none) }
                        }))
                        .tint(ConvNeon.lavDeep)
                        .accessibilityIdentifier("direct-notify")
                    } header: {
                        Text("Notifications")
                    } footer: {
                        Text("« Nouveau message de … » pour chaque message de cette conversation. Tous les messages directs se coupent dans Réglages › Notifications.")
                    }
                    .listRowBackground(ConvNeon.surface)
                    Section {
                        if chat.blocked == true {
                            Button("Débloquer \(label.primary)") { Task { await store.setBlocked(false) } }
                                .foregroundStyle(ConvNeon.lav)
                                .accessibilityIdentifier("direct-unblock")
                        } else {
                            Button("Bloquer \(label.primary)", role: .destructive) { confirmBlock = true }
                                .accessibilityIdentifier("direct-block")
                        }
                        if let user = chat.userID {
                            Button("Signaler \(label.primary)") { reporting = ReportTarget(kind: .profile, id: user, label: label.primary) }
                                .foregroundStyle(PronoTheme.pinkInk)
                                .accessibilityIdentifier("direct-report")
                        }
                    } header: {
                        Text("Confidentialité")
                    } footer: {
                        Text("Conversation privée : seuls vous deux la lisez. Une personne bloquée ne peut plus t'écrire (et toi non plus), ni te citer, t'inviter ou voir ta fiche ; elle n'en est pas prévenue. L'historique reste.")
                    }
                    .listRowBackground(ConvNeon.surface)
                }
            }
            .convNeonForm()
            .motion(Motion.smooth, value: store.conversation?.notify)
            .motion(Motion.smooth, value: store.conversation?.blocked)
            .navigationTitle("Message direct")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("OK") { dismiss() } } }
            .confirmationDialog("Bloquer cette personne ?", isPresented: $confirmBlock, titleVisibility: .visible) {
                Button("Bloquer", role: .destructive) { Task { await store.setBlocked(true) } }
            } message: {
                Text("Elle ne pourra plus t'écrire. Tu pourras la débloquer ici.")
            }
            .sheet(item: $reporting) { ReportSheet(store: store.moderation, target: $0) }
            // Déjà dans la conversation : pas de « Écrire » sur sa fiche.
            .personSheet($person, store: store, routes: routes, canWrite: false)
        }
        .preferredColorScheme(.dark)
    }
}

import SwiftUI

/// Infos du groupe : mes notifications (par défaut : mentions seulement), membres et admins du groupe.
struct ChatInfoView: View {
    @ObservedObject var store: ChatsStore
    @Environment(\.dismiss) private var dismiss
    @State private var profile: Conversation.Member?

    var body: some View {
        NavigationStack {
            Form {
                if let chat = store.conversation {
                    if chat.member {
                        Section {
                            Picker("Notifications", selection: Binding(get: { chat.notify }, set: { level in
                                Haptics.selection()
                                Task { await store.setNotify(level) }
                            })) {
                                ForEach(ChatNotify.allCases) { Text($0.label).tag($0) }
                            }
                            .pickerStyle(.segmented)
                        } header: {
                            Text("Notifications")
                        } footer: {
                            Text(chat.notify.hint)
                        }
                    }
                    Section {
                        if chat.admin {
                            Picker("@tout", selection: Binding(get: { chat.everyone ?? "all" }, set: { who in
                                Haptics.selection()
                                Task { await store.setEveryone(who) }
                            })) {
                                Text("Tous les membres").tag("all")
                                Text("Admins et organisateurs").tag("staff")
                            }
                            .pickerStyle(.segmented)
                            .accessibilityIdentifier("chat-everyone")
                        } else {
                            Text(chat.everyone == "staff" ? "Admins et organisateurs" : "Tous les membres")
                        }
                    } header: {
                        Text("Qui peut écrire @tout")
                    } footer: {
                        Text("@tout prévient tout le groupe. @annonce (message épinglé en haut, envoyé à tous) est réservé aux admins et organisateurs."
                             + (chat.admin ? "" : " Les admins du groupe choisissent."))
                    }
                    if chat.member {
                        // Même écran que Réglages › Groupes : ajouter ou inviter des membres, liens d'invitation.
                        Section {
                            NavigationLink {
                                GroupDetailView(store: store.groups, privacy: store.privacy, groupID: chat.id)
                                    .task { await store.groups.load(); await store.privacy.load() }
                                    .onDisappear { Task { await store.open(chat.id) } }
                            } label: {
                                Label("Gérer le groupe", systemImage: "person.2.badge.gearshape")
                            }
                            .accessibilityIdentifier("chat-manage-group")
                        } footer: {
                            Text("Membres, invitations et liens, comme dans Réglages › Groupes.")
                        }
                    }
                    Section {
                        ForEach(chat.members) { m in member(m, canName: chat.canNameAdmins) }
                    } header: {
                        Text("\(chat.members.count) membre\(chat.members.count > 1 ? "s" : "")")
                    } footer: {
                        Text("Les admins du groupe épinglent et suppriment les messages ; admins et organisateurs font et retirent les annonces. "
                             + (chat.canNameAdmins ? "Tu les nommes ici." : "Le créateur du groupe les nomme."))
                    }
                }
            }
            .scrollContentBackground(.hidden)
            // Réglage enregistré (l'explication change), admin nommé ou retiré : fondu plutôt que saut.
            .motion(Motion.smooth, value: store.conversation?.notify)
            .motion(Motion.snappy, value: store.conversation?.members)
            .background(AppConfig.background.ignoresSafeArea())
            .navigationTitle(store.conversation?.name ?? "Groupe")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("OK") { dismiss() } } }
            .sheet(item: $profile) { m in MemberCardView(store: store.privacy, memberID: m.id) }
        }
        .preferredColorScheme(.dark)
    }

    private var isAdmin: Bool { store.conversation?.admin == true }

    @ViewBuilder private func member(_ m: Conversation.Member, canName: Bool) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                // Un toucher sur la photo ou le nom ouvre sa fiche (numéro, « Ajouter aux contacts »).
                Button { profile = m } label: { Initials(name: m.name, photo: m.photo) }
                    .buttonStyle(.borderless)
                VStack(alignment: .leading, spacing: 2) {
                    Button { profile = m } label: { PersonName(id: m.id, pseudo: m.name).foregroundStyle(.primary) }
                        .buttonStyle(.borderless)
                        .accessibilityHint("Ouvre sa fiche")
                    if let call = m.call, let phone = m.phone {
                        // Numéro montré dans ce groupe : un toucher appelle, comme dans WhatsApp.
                        Link(destination: call) { Label(phone, systemImage: "phone.fill").font(.subheadline) }
                            .accessibilityLabel("Appeler \(m.name) au \(phone)")
                    }
                }
                Spacer()
                if m.creator { Text("Créateur · Admin").foregroundStyle(.secondary) } else if m.admin { Text("Admin").foregroundStyle(.secondary) }
                else if m.organizer == true { Text("Organisateur").foregroundStyle(.secondary) }
            }
            if canName && !m.creator {
                Toggle("Admin du groupe", isOn: Binding(get: { m.admin }, set: { on in Task { await store.setAdmin(m, on) } }))
                    .font(.subheadline)
                    .accessibilityLabel("\(m.name), admin du groupe")
            }
            if isAdmin && !m.creator && !m.admin {
                Toggle("Organisateur (annonces)", isOn: Binding(get: { m.organizer == true }, set: { on in Task { await store.setOrganizer(m, on) } }))
                    .font(.subheadline)
                    .accessibilityLabel("\(m.name), organisateur du groupe")
            }
        }
    }
}

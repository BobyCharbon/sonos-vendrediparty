import SwiftUI

/// Infos du groupe : mes notifications (par défaut : mentions seulement), membres et admins du groupe.
/// Néon club (Discussions v2, 18.11) : tuile du groupe en tête, un toucher sur un membre ouvre son mini-profil.
struct ChatInfoView: View {
    @ObservedObject var store: ChatsStore
    @Environment(\.dismiss) private var dismiss
    @Environment(\.people) private var people
    @Environment(\.groupHub) private var hub
    @Environment(\.conversationRoutes) private var routes
    @State private var person: PersonRef?

    var body: some View {
        NavigationStack {
            Form {
                if let chat = store.conversation {
                    let look = store.chats?.first { $0.id == chat.id }
                    Section {
                        VStack(spacing: 10) {
                            GroupTile(emoji: look?.emoji ?? "👥", color: look?.color, photo: look?.photo, system: look?.system ?? false, size: 84)
                                .shadow(color: GroupLook.gradient(look?.color).to.opacity(0.5), radius: 18)
                                .accessibilityHidden(true)
                            Text(chat.name).font(.system(.title2, design: .rounded).weight(.heavy)).foregroundStyle(ConvNeon.t1)
                                .multilineTextAlignment(.center)
                            Text(chat.members.count == 1 ? "1 membre" : "\(chat.members.count) membres").foregroundStyle(ConvNeon.t2)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 6)
                        .listRowBackground(Color.clear)
                    }
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
                        .listRowBackground(ConvNeon.surface)
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
                            Text(chat.everyone == "staff" ? "Admins et organisateurs" : "Tous les membres").foregroundStyle(ConvNeon.t1)
                        }
                    } header: {
                        Text("Qui peut écrire @tout")
                    } footer: {
                        Text("@tout prévient tout le groupe. @annonce (message épinglé en haut, envoyé à tous) est réservé aux admins et organisateurs."
                             + (chat.admin ? "" : " Les admins du groupe choisissent."))
                    }
                    .listRowBackground(ConvNeon.surface)
                    if chat.member, people != nil {
                        // Page du groupe en natif (18.11, « tout en natif ») : couverture, membres, événements, Inviter, réglages.
                        Section {
                            NavigationLink(value: GroupScreen.page(chat.id)) {
                                Label("Gérer le groupe", systemImage: "person.2.badge.gearshape").foregroundStyle(ConvNeon.lav)
                            }
                            .accessibilityIdentifier("chat-manage-group")
                        } footer: {
                            Text("La page du groupe : membres, événements, invitations et réglages.")
                        }
                        .listRowBackground(ConvNeon.surface)
                    } else if chat.member {
                        // Hors de l'app (aperçus) : l'écran natif d'avant.
                        Section {
                            NavigationLink {
                                GroupDetailView(store: store.groups, privacy: store.privacy, groupID: chat.id)
                                    .task { await store.groups.load(); await store.privacy.load() }
                                    .onDisappear { Task { await store.open(chat.id) } }
                            } label: {
                                Label("Gérer le groupe", systemImage: "person.2.badge.gearshape").foregroundStyle(ConvNeon.lav)
                            }
                            .accessibilityIdentifier("chat-manage-group")
                        } footer: {
                            Text("Membres, invitations et liens, comme dans Réglages › Groupes.")
                        }
                        .listRowBackground(ConvNeon.surface)
                    }
                    Section {
                        ForEach(chat.members) { m in member(m, canName: chat.canNameAdmins) }
                    } header: {
                        Text("\(chat.members.count) membre\(chat.members.count > 1 ? "s" : "")")
                    } footer: {
                        Text("Les admins du groupe épinglent et suppriment les messages ; admins et organisateurs font et retirent les annonces. "
                             + (chat.canNameAdmins ? "Tu les nommes ici." : "Le créateur du groupe les nomme."))
                    }
                    .listRowBackground(ConvNeon.surface)
                }
            }
            .convNeonForm()
            // Réglage enregistré (l'explication change), admin nommé ou retiré : fondu plutôt que saut.
            .motion(Motion.smooth, value: store.conversation?.notify)
            .motion(Motion.snappy, value: store.conversation?.members)
            .navigationTitle(store.conversation?.name ?? "Groupe")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("OK") { dismiss() } } }
            .personSheet($person, store: store, routes: routes)
            // Groupe quitté ou supprimé depuis sa page : la feuille se ferme.
            .navigationDestination(for: GroupScreen.self) { screen in screen.view(onGone: { dismiss() }) }
        }
        .environment(\.groupHub, hub?.closing(dismiss))
        .preferredColorScheme(.dark)
    }

    private var isAdmin: Bool { store.conversation?.admin == true }

    @ViewBuilder private func member(_ m: Conversation.Member, canName: Bool) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 12) {
                // Un toucher sur la photo ou le nom ouvre son mini-profil (Envoyer un message, fiche, en commun).
                Button { person = PersonRef(id: m.id) } label: { ConvFace(id: m.id, name: m.name, photo: m.photo, size: 36) }
                    .buttonStyle(.borderless)
                    .accessibilityLabel("Profil de \(m.name)")
                VStack(alignment: .leading, spacing: 2) {
                    Button { person = PersonRef(id: m.id) } label: { PersonName(id: m.id, pseudo: m.name).foregroundStyle(ConvNeon.t1) }
                        .buttonStyle(.borderless)
                        .accessibilityHint("Ouvre son profil")
                    if let call = m.call, let phone = m.phone {
                        // Numéro montré dans ce groupe : un toucher appelle, comme dans WhatsApp.
                        Link(destination: call) { Label(phone, systemImage: "phone.fill").font(.subheadline).foregroundStyle(ConvNeon.lav) }
                            .accessibilityLabel("Appeler \(m.name) au \(phone)")
                    }
                }
                Spacer()
                if m.creator { Text("Créateur · Admin").font(.subheadline).foregroundStyle(ConvNeon.lav) }
                else if m.admin { Text("Admin").font(.subheadline).foregroundStyle(ConvNeon.lav) }
                else if m.organizer == true { Text("Organisateur").font(.subheadline).foregroundStyle(ConvNeon.t2) }
            }
            if canName && !m.creator {
                Toggle("Admin du groupe", isOn: Binding(get: { m.admin }, set: { on in Task { await store.setAdmin(m, on) } }))
                    .font(.subheadline).tint(ConvNeon.lavDeep)
                    .accessibilityLabel("\(m.name), admin du groupe")
            }
            if isAdmin && !m.creator && !m.admin {
                Toggle("Organisateur (annonces)", isOn: Binding(get: { m.organizer == true }, set: { on in Task { await store.setOrganizer(m, on) } }))
                    .font(.subheadline).tint(ConvNeon.lavDeep)
                    .accessibilityLabel("\(m.name), organisateur du groupe")
            }
        }
    }
}

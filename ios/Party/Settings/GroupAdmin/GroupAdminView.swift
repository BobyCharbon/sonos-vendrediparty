import SwiftUI

/// Réglages › Administration du groupe, en natif : propositions à valider, demandes d'adhésion, règle de
/// validation, puis Membres, Rôles et droits, Journal. Annonces, Catégories et Utilisateurs s'ouvrent dans la page.
struct GroupAdminView: View {
    @ObservedObject var store: GroupAdminStore
    @ObservedObject var session: AccountStore
    let open: (WebModel.PagePlace) -> Void
    @State private var refusing: AdminOverview.Proposal?
    @State private var reason = ""

    var body: some View {
        List {
            if let overview = store.overview {
                if overview.access.can("events.approve") { proposals(overview) }
                if overview.access.can("members.approve") { requests(overview) }
                if let on = overview.requireApproval { rules(on) }
                manage(overview.access)
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle("Administration")
        .navigationBarTitleDisplayMode(.inline)
        .overlay { AdminLoading(loaded: store.overview != nil, error: store.error) { await store.loadOverview() } }
        .overlay(alignment: .bottom) { AdminNotice(notice: $store.notice) }
        .refreshable { await store.loadOverview() }
        .task { await store.loadOverview() }
        .alert("Refuser « \(refusing?.title ?? "") » ?", isPresented: Binding(get: { refusing != nil }, set: { if !$0 { refusing = nil } })) {
            TextField("Message pour l'organisateur (facultatif)", text: $reason)
            Button("Annuler", role: .cancel) { reason = "" }
            Button("Refuser", role: .destructive) {
                guard let proposal = refusing else { return }
                let text = reason.trimmingCharacters(in: .whitespacesAndNewlines)
                reason = ""
                Task { await store.decide(proposal, approve: false, reason: text.isEmpty ? nil : text) }
            }
        } message: {
            Text("L'organisateur reçoit ton message.")
        }
    }

    private func proposals(_ overview: AdminOverview) -> some View {
        Section("Propositions à valider") {
            if overview.events.isEmpty { Text("Rien à valider.").foregroundStyle(.secondary) }
            ForEach(overview.events) { proposal in
                VStack(alignment: .leading, spacing: 8) {
                    Button { open(.account("/event/\(proposal.id)")) } label: {
                        VStack(alignment: .leading, spacing: 3) {
                            Text(proposal.title).font(.headline)
                            Text("par \(proposal.author)\(AdminDate.text(proposal.at).map { " · \($0)" } ?? "")")
                                .font(.footnote).foregroundStyle(.secondary)
                            if !proposal.details.isEmpty { Text(proposal.details).font(.subheadline).foregroundStyle(.secondary) }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .foregroundStyle(.primary)
                    HStack {
                        Button("Approuver") { Task { await store.decide(proposal, approve: true) } }
                            .buttonStyle(.borderedProminent)
                        Button("Modifier") { open(.account("/event/\(proposal.id)/edit")) }.buttonStyle(.bordered)
                        Button("Refuser", role: .destructive) { refusing = proposal }.buttonStyle(.bordered)
                    }
                    .controlSize(.small)
                    .disabled(store.busy.contains(proposal.id))
                }
                .padding(.vertical, 4)
            }
        }
    }

    private func requests(_ overview: AdminOverview) -> some View {
        Section {
            if overview.requests.isEmpty { Text("Aucune demande.").foregroundStyle(.secondary) }
            ForEach(overview.requests) { request in
                VStack(alignment: .leading, spacing: 8) {
                    HStack(spacing: 12) {
                        AdminAvatar(photo: request.photo, name: request.name, size: 44)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(request.name.isEmpty ? "Profil à compléter" : request.name).font(.headline)
                            if !request.fullName.isEmpty { Text(request.fullName).foregroundStyle(.secondary) }
                            Text([request.phone.map { "+\($0.trimmingCharacters(in: CharacterSet(charactersIn: "+")))" },
                                  AdminDate.text(request.at)].compactMap { $0 }.joined(separator: " · "))
                                .font(.footnote).foregroundStyle(.secondary)
                        }
                    }
                    if let message = request.message, !message.isEmpty { Text("« \(message) »").font(.subheadline) }
                    if !request.complete {
                        Text("Nom, prénom, surnom et photo à compléter avant de pouvoir accepter.")
                            .font(.footnote).foregroundStyle(.secondary)
                    }
                    HStack {
                        Button("Accepter") { Task { await store.decide(request, accept: true) } }
                            .buttonStyle(.borderedProminent).disabled(!request.complete)
                        Button("Refuser", role: .destructive) { Task { await store.decide(request, accept: false) } }
                            .buttonStyle(.bordered)
                    }
                    .controlSize(.small)
                    .disabled(store.busy.contains(request.id))
                }
                .padding(.vertical, 4)
            }
        } header: {
            Text("Demandes d'adhésion")
        } footer: {
            Text("Accepter fait entrer la personne comme Membre VIP, dans le groupe Vendredi Party.")
        }
    }

    private func rules(_ on: Bool) -> some View {
        Section {
            Toggle(isOn: Binding(get: { on }, set: { value in Task { await store.setRequireApproval(value) } })) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Validation obligatoire")
                    Text("Les propositions des membres attendent ton accord").font(.footnote).foregroundStyle(.secondary)
                }
            }
            .disabled(store.busy.contains("approval"))
        } header: {
            Text("Règles du groupe")
        } footer: {
            Text("Qui publie sans validation, modifie le publié ou crée des tags : c'est dans « Rôles et droits ».")
        }
    }

    private func manage(_ access: AdminAccess) -> some View {
        Section("Gérer") {
            if access.seesMembers {
                NavigationLink { GroupMembersView(store: store) } label: {
                    SettingsRow(symbol: "person.2.fill", tint: .blue, title: "Membres", hint: "Rôles, accès, identité")
                }
            }
            if access.managesRoles {
                NavigationLink { GroupRolesView(store: store) } label: {
                    SettingsRow(symbol: "checklist", tint: .indigo, title: "Rôles et droits", hint: "Ce que chaque rôle peut faire")
                }
            }
            if access.full {
                NavigationLink { GroupJournalView(store: store, member: nil, name: nil) } label: {
                    SettingsRow(symbol: "list.bullet.rectangle.portrait.fill", tint: .gray, title: "Journal des membres",
                                hint: "Inscriptions, connexions, rôles, bêta, groupes, suppressions")
                }
                NavigationLink { GroupUsersView(store: store) } label: {
                    SettingsRow(symbol: "person.crop.rectangle.stack.fill", tint: .teal, title: "Utilisateurs",
                                hint: "Tous les inscrits : connexions, activité, tri")
                }
            }
            if access.can("announcements.publish") {
                NavigationLink { AnnouncementsView(store: session, canPublish: true) } label: {
                    SettingsRow(symbol: "megaphone.fill", tint: .orange, title: "Annonces admin", hint: "Un message obligatoire pour tout le groupe")
                }
            }
            if access.can("taxonomy.manage") {
                NavigationLink { GroupTaxonomyView(store: store) } label: {
                    SettingsRow(symbol: "tag.fill", tint: .pink, title: "Catégories et tags", hint: "Créer, renommer, archiver")
                }
            }
        }
    }
}

/// Photo de profil ronde, ou l'initiale.
struct AdminAvatar: View {
    let photo: String?
    let name: String
    var size: CGFloat = 40

    var body: some View {
        AsyncImage(url: photo.flatMap(URL.init(string:))) { image in
            image.resizable().scaledToFill()
        } placeholder: {
            Text(name.first.map(String.init) ?? "?").font(.headline)
        }
        .frame(width: size, height: size)
        .background(Palette.accent.opacity(0.35))
        .clipShape(Circle())
        .accessibilityHidden(true)
    }
}

/// Premier chargement : roue, ou l'erreur avec « Réessayer ».
struct AdminLoading: View {
    let loaded: Bool
    let error: String?
    let retry: () async -> Void

    var body: some View {
        if !loaded {
            if let error {
                VStack(spacing: 12) {
                    Text(error).multilineTextAlignment(.center).foregroundStyle(.secondary)
                    Button("Réessayer") { Task { await retry() } }
                }
                .padding()
            } else {
                ProgressView()
            }
        }
    }
}

/// Bandeau de confirmation ou de refus, effacé au bout de 3 s.
struct AdminNotice: View {
    @Binding var notice: String?

    var body: some View {
        if let notice {
            Text(notice)
                .font(.subheadline.weight(.semibold))
                .multilineTextAlignment(.center)
                .padding(.horizontal, 16).padding(.vertical, 12)
                .background(Palette.card, in: Capsule())
                .padding(.bottom, 12).padding(.horizontal, 16)
                .task(id: notice) {
                    try? await Task.sleep(for: .seconds(3))
                    self.notice = nil
                }
        }
    }
}

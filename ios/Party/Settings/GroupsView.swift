import SwiftUI

/// Mes groupes (POST /api/account/groups) : ceux que j'ai créés et ceux dont je fais partie ; people = personnes
/// que je peux y ajouter (annuaire, selon mes droits).
struct GroupList: Decodable, Equatable {
    struct Person: Decodable, Equatable, Identifiable {
        let id: String
        let name: String
    }

    struct Group: Decodable, Equatable, Identifiable {
        let id: String
        let name: String
        /// Groupe du système (« Vendredi Party », les VIP) : composé par les admins.
        let system: Bool
        /// Créé par moi : je le compose et je peux le supprimer.
        let mine: Bool
        /// J'en fais partie : je peux y montrer mon numéro.
        let inside: Bool
        let members: [Person]

        enum CodingKeys: String, CodingKey { case id, name, system, mine, inside, members }

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            id = try c.decode(String.self, forKey: .id)
            name = try c.decode(String.self, forKey: .name)
            system = try c.decodeIfPresent(Bool.self, forKey: .system) ?? false
            mine = try c.decodeIfPresent(Bool.self, forKey: .mine) ?? false
            inside = try c.decodeIfPresent(Bool.self, forKey: .inside) ?? false
            members = try c.decodeIfPresent([Person].self, forKey: .members) ?? []
        }
    }

    let groups: [Group]
    let people: [Person]
}

/// Invitation reçue (par mon compte ou mon numéro) : acceptée ou refusée dans Réglages › Groupes.
struct GroupInvitation: Decodable, Equatable, Identifiable {
    let id: String
    let groupID: String
    let group: String
    let invitedBy: String?

    enum CodingKeys: String, CodingKey { case id, group, groupID = "group_id", invitedBy = "invited_by" }
}

private struct GroupInvitations: Decodable { let invitations: [GroupInvitation] }
private struct GroupLinkResponse: Decodable { let url: String }
private struct GroupInviteResult: Decodable { let invited: String }

extension PartyAPI {
    func groups(token: String) async throws -> GroupList { try await postDecoding("/api/account/groups", body: ["token": token]) }

    func groupInvitations(token: String) async throws -> [GroupInvitation] {
        let r: GroupInvitations = try await postDecoding("/api/account/groups/invitations", body: ["token": token])
        return r.invitations
    }

    func answerGroupInvitation(token: String, id: String, accept: Bool) async throws -> [GroupInvitation] {
        let r: GroupInvitations = try await postDecoding("/api/account/groups/invitations/answer",
                                                         body: ["token": token, "id": id, "accept": accept])
        return r.invitations
    }

    func groupLink(token: String, groupID: String, renew: Bool) async throws -> URL? {
        let r: GroupLinkResponse = try await postDecoding("/api/account/groups/link", body: ["token": token, "group_id": groupID, "renew": renew])
        return URL(string: r.url)
    }

    /// true : la personne (compte) a reçu l'invitation ; false : gardée pour un numéro pas encore inscrit.
    func inviteToGroup(token: String, groupID: String, member: String?, phone: String?) async throws -> Bool {
        var body: [String: Any] = ["token": token, "group_id": groupID]
        if let member { body["member"] = member }
        if let phone { body["phone"] = phone }
        let r: GroupInviteResult = try await postDecoding("/api/account/groups/invite", body: body)
        return r.invited == "member"
    }

    func createGroup(token: String, name: String) async throws -> GroupList {
        try await postDecoding("/api/account/groups/create", body: ["token": token, "name": name])
    }

    func setGroupMember(token: String, groupID: String, userID: String, on: Bool) async throws -> GroupList {
        try await postDecoding("/api/account/groups/member", body: ["token": token, "group_id": groupID, "user_id": userID, "on": on])
    }

    func deleteGroup(token: String, groupID: String) async throws -> GroupList {
        try await postDecoding("/api/account/groups/delete", body: ["token": token, "group_id": groupID])
    }
}

/// Réglages › Groupes : données et actions, avec la session du compte.
@MainActor
final class GroupsStore: ObservableObject {
    @Published private(set) var list: GroupList?
    @Published private(set) var invitations: [GroupInvitation] = []
    @Published private(set) var links: [String: URL] = [:]
    @Published private(set) var error: String?
    @Published private(set) var busy: Set<String> = []
    @Published var notice: String?

    private let api: PartyAPI
    private weak var web: WebStorage?

    init(api: PartyAPI, web: WebStorage?) {
        self.api = api
        self.web = web
    }

    func load() async {
        await run("load") { token in
            list = try await api.groups(token: token)
            invitations = (try? await api.groupInvitations(token: token)) ?? []
        }
    }

    func answer(_ invitation: GroupInvitation, accept: Bool) async {
        await run(invitation.id) { token in
            invitations = try await api.answerGroupInvitation(token: token, id: invitation.id, accept: accept)
            list = try await api.groups(token: token)
            notice = accept ? "Tu as rejoint « \(invitation.group) »" : "Invitation refusée"
        }
    }

    func link(for group: GroupList.Group, renew: Bool = false) async {
        await run("link.\(group.id)") { token in
            links[group.id] = try await api.groupLink(token: token, groupID: group.id, renew: renew)
            if renew { notice = "Nouveau lien : l'ancien ne marche plus" }
        }
    }

    /// Surnom d'un compte (liste des personnes) ou numéro de téléphone (inscrit ou pas encore).
    func invite(_ typed: String, to group: GroupList.Group) async -> Bool {
        let text = typed.trimmingCharacters(in: .whitespaces)
        let digits = text.filter(\.isNumber)
        let byPhone = digits.count >= 8 && text.allSatisfy { $0.isNumber || " +().-".contains($0) }
        let person = byPhone ? nil : list?.people.first { $0.name.caseInsensitiveCompare(text.trimmingCharacters(in: ["@"])) == .orderedSame }
        guard byPhone || person != nil else {
            notice = "Personne avec ce surnom. Essaie son numéro de téléphone."
            return false
        }
        let phone = byPhone ? (LoginPhone.parse(text, country: .ch).map { String($0.dropFirst()) } ?? digits) : nil
        var done = false
        await run("invite.\(group.id)") { token in
            let reached = try await api.inviteToGroup(token: token, groupID: group.id, member: person?.id, phone: phone)
            notice = reached ? "\(person?.name ?? "La personne") a reçu ton invitation"
                             : "Invitation gardée pour ce numéro : elle l'attendra dès son inscription"
            done = true
        }
        return done
    }

    func create(_ name: String) async -> Bool {
        var created = false
        await run("create") { token in
            list = try await api.createGroup(token: token, name: name)
            created = true
        }
        return created
    }

    func toggle(_ person: GroupList.Person, in group: GroupList.Group) async {
        let on = !group.members.contains(where: { $0.id == person.id })
        await run("\(group.id).\(person.id)") { token in
            list = try await api.setGroupMember(token: token, groupID: group.id, userID: person.id, on: on)
        }
    }

    func delete(_ group: GroupList.Group) async {
        await run(group.id) { token in
            list = try await api.deleteGroup(token: token, groupID: group.id)
            notice = "Groupe « \(group.name) » supprimé"
        }
    }

    private func run(_ key: String, _ work: (String) async throws -> Void) async {
        guard let token = await web?.accountToken() else {
            error = "Connecte-toi pour voir et créer des groupes"
            return
        }
        busy.insert(key)
        defer { busy.remove(key) }
        do {
            try await work(token)
            error = nil
        } catch PartyAPIError.needsCode {
            error = "Ta connexion a expiré : reconnecte-toi dans Événements"
        } catch {
            if list == nil { self.error = error.localizedDescription } else { notice = error.localizedDescription }
        }
    }
}

struct GroupsView: View {
    @ObservedObject var store: GroupsStore
    let privacy: PrivacyStore
    @State private var newName = ""
    @FocusState private var naming: Bool

    var body: some View {
        List {
            Section {
                HStack {
                    TextField("Nom du nouveau groupe", text: $newName).focused($naming).submitLabel(.done)
                        .onSubmit(create)
                    Button("Créer", action: create)
                        .disabled(newName.trimmingCharacters(in: .whitespaces).isEmpty || store.busy.contains("create"))
                }
            } header: {
                Text("Nouveau groupe")
            } footer: {
                Text("Un groupe sert à inviter plusieurs personnes d'un coup à un événement. Quelqu'un qui rejoint le groupe plus tard est aussi invité aux événements à venir.")
            }
            if !store.invitations.isEmpty {
                Section("Invitations reçues") {
                    ForEach(store.invitations) { invitation in
                        VStack(alignment: .leading, spacing: 8) {
                            Text(invitation.group).font(.headline)
                            Text("\(invitation.invitedBy ?? "Quelqu'un") t'invite dans ce groupe").font(.footnote).foregroundStyle(.secondary)
                            HStack {
                                Button("Accepter") { Task { await store.answer(invitation, accept: true) } }.buttonStyle(.borderedProminent)
                                Button("Refuser") { Task { await store.answer(invitation, accept: false) } }.buttonStyle(.bordered)
                            }
                            .controlSize(.small)
                            .disabled(store.busy.contains(invitation.id))
                        }
                        .padding(.vertical, 4)
                    }
                }
            }
            if let list = store.list {
                Section("Mes groupes") {
                    if list.groups.isEmpty { Text("Tu ne fais partie d'aucun groupe pour l'instant.").foregroundStyle(.secondary) }
                    ForEach(list.groups) { group in
                        NavigationLink {
                            GroupDetailView(store: store, privacy: privacy, groupID: group.id)
                        } label: {
                            VStack(alignment: .leading, spacing: 3) {
                                Text(group.name).font(.headline)
                                Text(subtitle(group)).font(.footnote).foregroundStyle(.secondary).lineLimit(1)
                            }
                        }
                    }
                }
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle("Groupes")
        .navigationBarTitleDisplayMode(.inline)
        .overlay {
            if store.list == nil {
                if let error = store.error {
                    VStack(spacing: 12) {
                        Text(error).multilineTextAlignment(.center).foregroundStyle(.secondary)
                        Button("Réessayer") { Task { await store.load() } }
                    }
                    .padding()
                } else {
                    ProgressView()
                }
            }
        }
        .overlay(alignment: .bottom) { GroupNotice(store: store) }
        .refreshable { await store.load() }
        .task {
            await store.load()
            await privacy.load()
        }
    }

    private func subtitle(_ group: GroupList.Group) -> String {
        let role = group.system ? "Les VIP" : group.mine ? "Créé par toi" : "Tu en fais partie"
        return "\(role) · \(group.members.count) personne\(group.members.count > 1 ? "s" : "")"
    }

    private func create() {
        let name = newName.trimmingCharacters(in: .whitespaces)
        guard !name.isEmpty else { return }
        naming = false
        Task { if await store.create(name) { newName = "" } }
    }
}

/// Un groupe : ses membres ; pour mes groupes, ajouter ou retirer des personnes d'un toucher, et le supprimer.
struct GroupDetailView: View {
    @ObservedObject var store: GroupsStore
    @ObservedObject var privacy: PrivacyStore
    let groupID: String
    @State private var confirmDelete = false
    @State private var profile: ProfileTarget?
    @State private var guest = ""
    @Environment(\.dismiss) private var dismiss

    /// Fiche à ouvrir (un membre touché dans la liste).
    struct ProfileTarget: Identifiable { let id: String }

    private func invite(_ group: GroupList.Group) {
        let typed = guest
        Task { if await store.invite(typed, to: group) { guest = "" } }
    }

    var body: some View {
        List {
            if let group = store.list?.groups.first(where: { $0.id == groupID }) {
                if group.inside {
                    Section {
                        Toggle(isOn: Binding(get: { privacy.sharesPhone(in: group.id) },
                                             set: { on in Task { await privacy.setPhone(on, group: group.id) } })) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Montrer mon numéro dans ce groupe")
                                Text("Les membres de ce groupe le voient sur ta fiche profil. Caché par défaut.")
                                    .font(.footnote).foregroundStyle(.secondary)
                            }
                        }
                        .disabled(privacy.saving || privacy.privacy == nil)
                    } footer: {
                        if let error = privacy.error { Text(error).foregroundStyle(.red) }
                    }
                }
                if group.mine {
                    Section {
                        if store.list?.people.isEmpty == true {
                            Text("Personne d'autre à ajouter pour l'instant.").foregroundStyle(.secondary)
                        }
                        ForEach(store.list?.people ?? []) { person in
                            let inside = group.members.contains { $0.id == person.id }
                            Button { Task { await store.toggle(person, in: group) } } label: {
                                HStack {
                                    Text(person.name)
                                    Spacer()
                                    if store.busy.contains("\(group.id).\(person.id)") {
                                        ProgressView()
                                    } else {
                                        Image(systemName: inside ? "checkmark.circle.fill" : "circle")
                                            .foregroundStyle(inside ? Palette.accent : .secondary)
                                    }
                                }
                            }
                            .foregroundStyle(.primary)
                            .accessibilityAddTraits(inside ? .isSelected : [])
                            .contextMenu {
                                Button { profile = ProfileTarget(id: person.id) } label: { Label("Voir le profil", systemImage: "person.crop.circle") }
                            }
                        }
                    } header: {
                        Text("Membres · \(group.members.count)")
                    } footer: {
                        Text("Touche une personne pour l'ajouter ou la retirer.")
                    }
                    Section {
                        HStack {
                            TextField("Surnom ou numéro", text: $guest)
                                .textInputAutocapitalization(.never)
                                .autocorrectionDisabled()
                                .onSubmit { invite(group) }
                            Button("Inviter") { invite(group) }
                                .disabled(guest.trimmingCharacters(in: .whitespaces).isEmpty || store.busy.contains("invite.\(group.id)"))
                        }
                    } header: {
                        Text("Inviter")
                    } footer: {
                        Text("La personne accepte ou refuse dans ses Réglages. Un numéro pas encore inscrit : l'invitation l'attend.")
                    }
                    Section {
                        if let url = store.links[group.id] {
                            Text(url.absoluteString).font(.footnote).textSelection(.enabled)
                            ShareLink(item: url, subject: Text("Invitation Party"),
                                      message: Text("Rejoins le groupe « \(group.name) » sur Party")) {
                                Label("Partager le lien", systemImage: "square.and.arrow.up")
                            }
                            Button("Nouveau lien (l'ancien ne marchera plus)") { Task { await store.link(for: group, renew: true) } }
                        } else {
                            Button("Afficher le lien d'invitation") { Task { await store.link(for: group) } }
                                .disabled(store.busy.contains("link.\(group.id)"))
                        }
                    } header: {
                        Text("Lien d'invitation")
                    } footer: {
                        Text("Qui l'ouvre s'inscrit avec son numéro, complète son profil, puis rejoint ce groupe. Rien n'est visible avant. Tu es prévenu à chaque arrivée.")
                    }
                    Section {
                        Button("Supprimer le groupe", role: .destructive) { confirmDelete = true }
                    } footer: {
                        Text("Les invités qui ont déjà répondu gardent l'accès à leurs événements.")
                    }
                } else {
                    Section {
                        ForEach(group.members) { person in
                            Button { profile = ProfileTarget(id: person.id) } label: {
                                HStack {
                                    Text(person.name)
                                    Spacer()
                                    Image(systemName: "person.crop.circle").foregroundStyle(.secondary)
                                }
                            }
                            .foregroundStyle(.primary)
                            .accessibilityHint("Ouvre sa fiche profil")
                        }
                    } header: {
                        Text("Membres · \(group.members.count)")
                    } footer: {
                        Text(group.system ? "Les VIP : être dans ce groupe donne accès aux événements du groupe. Les admins le composent."
                                          : "Seule la personne qui l'a créé peut le modifier.")
                    }
                }
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle(store.list?.groups.first(where: { $0.id == groupID })?.name ?? "Groupe")
        .navigationBarTitleDisplayMode(.inline)
        .overlay(alignment: .bottom) { GroupNotice(store: store) }
        .sheet(item: $profile) { target in MemberCardView(store: privacy, memberID: target.id) }
        .confirmationDialog("Supprimer ce groupe ?", isPresented: $confirmDelete, titleVisibility: .visible) {
            Button("Supprimer", role: .destructive) {
                guard let group = store.list?.groups.first(where: { $0.id == groupID }) else { return }
                Task {
                    await store.delete(group)
                    dismiss()
                }
            }
        }
    }
}

private struct GroupNotice: View {
    @ObservedObject var store: GroupsStore

    var body: some View {
        if let notice = store.notice {
            Text(notice)
                .font(.subheadline.weight(.semibold))
                .padding(.horizontal, 16).padding(.vertical, 12)
                .background(Palette.card, in: Capsule())
                .padding(.bottom, 12)
                .task(id: notice) {
                    try? await Task.sleep(for: .seconds(3))
                    store.notice = nil
                }
        }
    }
}

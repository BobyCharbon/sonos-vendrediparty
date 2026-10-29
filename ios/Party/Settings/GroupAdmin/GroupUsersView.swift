import SwiftUI

/// Utilisateurs (Root, Admin) : tous les inscrits, triés et filtrés ; une ligne ouvre la fiche du membre.
struct GroupUsersView: View {
    @ObservedObject var store: GroupAdminStore
    @State private var search = ""
    @State private var filter: UserList.Filter = .all
    @State private var sort: UserList.Sort = .lastSignIn
    @State private var descending = true

    var body: some View {
        List {
            if let members = store.members {
                let rows = UserList.arrange(members.people, search: search, filter: filter, sort: sort, descending: descending)
                Section {
                    Picker("Trier par", selection: Binding(get: { sort }, set: { choose($0) })) {
                        ForEach(UserList.Sort.allCases) { Text($0.label).tag($0) }
                    }
                    Toggle(sort == .name ? "De Z à A" : "Plus ancien d'abord",
                           isOn: Binding(get: { sort == .name ? descending : !descending },
                                         set: { descending = sort == .name ? $0 : !$0 }))
                    Picker("Afficher", selection: $filter) {
                        ForEach(UserList.Filter.allCases) { Text($0.label).tag($0) }
                    }
                } footer: {
                    Text("\(rows.count) sur \(members.people.count) inscrit(s)")
                }
                Section {
                    ForEach(rows) { person in
                        NavigationLink { MemberDetailView(store: store, memberID: person.id) } label: { UserRow(person: person) }
                    }
                }
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .searchable(text: $search, prompt: "Surnom, prénom, nom, numéro")
        .navigationTitle("Utilisateurs")
        .navigationBarTitleDisplayMode(.inline)
        .overlay { AdminLoading(loaded: store.members != nil, error: store.error) { await store.loadMembers() } }
        .overlay(alignment: .bottom) { AdminNotice(notice: $store.notice) }
        .refreshable { await store.loadMembers() }
        .task { await store.loadMembers() }
    }

    private func choose(_ next: UserList.Sort) {
        sort = next
        descending = next.descendingByDefault
    }
}

private struct UserRow: View {
    let person: AdminMembers.Person

    var body: some View {
        HStack(spacing: 12) {
            AdminAvatar(photo: person.photo, name: person.name)
            VStack(alignment: .leading, spacing: 2) {
                Text(person.displayName).font(.body.weight(.semibold))
                Text([person.banned ? "Accès retiré" : person.roleText, person.beta ? "Bêta" : nil,
                      person.complete ? nil : "Profil incomplet"].compactMap { $0 }.joined(separator: " · "))
                    .font(.footnote).foregroundStyle(.secondary)
                Text(details).font(.caption).foregroundStyle(.secondary).lineLimit(2)
            }
        }
        .accessibilityElement(children: .combine)
    }

    private var details: String {
        var parts = ["Inscrit le \(AdminDate.text(person.createdAt) ?? "?")"]
        if let last = AdminDate.text(person.lastSignInAt) { parts.append("vu le \(last)") }
        parts.append("\(person.signInCount) connexion(s)")
        parts.append("\(person.rsvpCount) réponse(s), \(person.messageCount) message(s)")
        if !person.groups.isEmpty { parts.append(person.groups.joined(separator: ", ")) }
        return parts.joined(separator: " · ")
    }
}

/// Catégories et tags (droit taxonomy.manage) : créer, renommer, changer de couleur, archiver ou restaurer.
struct GroupTaxonomyView: View {
    @ObservedObject var store: GroupAdminStore
    @State private var kind: Taxonomy.Kind = .categories
    @State private var newName = ""
    @State private var newColor = Taxonomy.Topic.palette[0]
    @State private var renaming: Taxonomy.Topic?
    @State private var rename = ""

    var body: some View {
        List {
            Section {
                Picker("Liste", selection: $kind) {
                    ForEach(Taxonomy.Kind.allCases) { Text($0.label).tag($0) }
                }
                .pickerStyle(.segmented)
            }
            .listRowBackground(Color.clear)
            if let taxonomy = store.taxonomy {
                Section {
                    HStack {
                        TextField(kind == .tags ? "Nouveau tag" : "Nouvelle catégorie", text: $newName)
                            .textInputAutocapitalization(kind == .tags ? .never : .sentences)
                            .onSubmit(create)
                        Button { newColor = Self.next(newColor) } label: { ColorDot(hex: newColor) }
                            .buttonStyle(.borderless)
                            .accessibilityLabel("Couleur suivante")
                        Button("Créer", action: create)
                            .buttonStyle(.borderless)
                            .disabled(newName.trimmingCharacters(in: .whitespaces).isEmpty || store.busy.contains("taxonomy"))
                    }
                } header: {
                    Text("Ajouter")
                }
                Section {
                    if taxonomy.items(kind).isEmpty { Text("Rien pour l'instant.").foregroundStyle(.secondary) }
                    ForEach(taxonomy.items(kind)) { topic in row(topic) }
                } header: {
                    Text(kind.label)
                } footer: {
                    Text("Glisse vers la gauche pour renommer ou archiver ; touche la pastille pour changer de couleur. Un élément archivé n'est plus proposé, les événements gardent le leur.")
                }
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle("Catégories et tags")
        .navigationBarTitleDisplayMode(.inline)
        .overlay { AdminLoading(loaded: store.taxonomy != nil, error: store.error) { await store.loadTaxonomy() } }
        .overlay(alignment: .bottom) { AdminNotice(notice: $store.notice) }
        .refreshable { await store.loadTaxonomy() }
        .task { await store.loadTaxonomy() }
        .alert("Renommer", isPresented: Binding(get: { renaming != nil }, set: { if !$0 { renaming = nil } })) {
            TextField("Nom", text: $rename)
            Button("Annuler", role: .cancel) {}
            Button("Enregistrer") {
                guard let topic = renaming else { return }
                Task { await store.saveTopic(kind, topic, name: rename) }
            }
        }
    }

    private func row(_ topic: Taxonomy.Topic) -> some View {
        HStack(spacing: 12) {
            Button { Task { await store.saveTopic(kind, topic, color: topic.nextColor) } } label: { ColorDot(hex: topic.color) }
                .buttonStyle(.borderless)
                .accessibilityLabel("Changer la couleur de \(topic.name)")
            Text(kind == .tags ? "#\(topic.name)" : topic.name)
                .foregroundStyle(topic.archived ? .secondary : .primary)
            Spacer()
            if topic.archived { Text("Archivé").font(.caption).foregroundStyle(.secondary) }
        }
        .swipeActions(edge: .trailing) {
            Button(topic.archived ? "Restaurer" : "Archiver") {
                Task { await store.saveTopic(kind, topic, archived: !topic.archived) }
            }
            .tint(topic.archived ? .green : .orange)
            Button("Renommer") { rename = topic.name; renaming = topic }.tint(.blue)
        }
        .contextMenu {
            Button("Renommer") { rename = topic.name; renaming = topic }
            Button(topic.archived ? "Restaurer" : "Archiver") {
                Task { await store.saveTopic(kind, topic, archived: !topic.archived) }
            }
        }
    }

    static func next(_ color: String) -> String {
        let palette = Taxonomy.Topic.palette
        return palette[((palette.firstIndex(of: color) ?? -1) + 1) % palette.count]
    }

    private func create() {
        let name = newName.trimmingCharacters(in: .whitespaces)
        guard !name.isEmpty else { return }
        Task { if await store.createTopic(kind, name: name, color: newColor) { newName = "" } }
    }
}

/// Pastille de couleur (#RRGGBB).
struct ColorDot: View {
    let hex: String

    var body: some View {
        Circle().fill(Color(hex: hex) ?? Palette.accent).frame(width: 24, height: 24)
            .overlay(Circle().stroke(.white.opacity(0.3), lineWidth: 1))
    }
}

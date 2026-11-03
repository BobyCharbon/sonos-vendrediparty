import SwiftUI

/// Rôles et droits : la liste des rôles (du plus haut au plus bas : l'ordre est la hiérarchie), à réordonner par
/// glisser-déposer ; « + » crée un rôle ; un rôle ouvre sa fiche (nom, couleur, icône, droits, suppression).
/// Seulement les rôles en dessous du sien ; on ne donne que les droits qu'on a soi-même (la base vérifie tout).
struct GroupRolesView: View {
    @ObservedObject var store: GroupAdminStore
    @State private var editMode: EditMode = .inactive
    @State private var creating = false

    var body: some View {
        List {
            if let roles = store.roles {
                Section {
                    ForEach(roles.descending) { role in
                        let editable = roles.isEditable(role)
                        Group {
                            if editable {
                                NavigationLink { RoleDetailView(store: store, key: role.key) } label: { RoleRow(role: role, locked: false) }
                            } else {
                                RoleRow(role: role, locked: true)
                            }
                        }
                        .moveDisabled(!roles.canManage || !editable || role.key == "guest" || role.key == "admin")
                    }
                    .onMove { from, to in move(roles, from: from, to: to) }
                } header: {
                    Text("Rôles")
                } footer: {
                    Text(footer(roles))
                }
                if roles.editable.isEmpty {
                    Text("Aucun rôle en dessous du tien à régler.").foregroundStyle(.secondary)
                }
            }
        }
        .environment(\.editMode, $editMode)
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle("Rôles et droits")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if store.roles?.canManage == true {
                ToolbarItemGroup(placement: .navigationBarTrailing) {
                    Button(editMode.isEditing ? "OK" : "Réordonner") {
                        withAnimation { editMode = editMode.isEditing ? .inactive : .active }
                    }
                    Button { creating = true } label: { Image(systemName: "plus") }
                        .accessibilityLabel("Nouveau rôle")
                }
            }
        }
        .sheet(isPresented: $creating) { NewRoleSheet(store: store) }
        .overlay { AdminLoading(loaded: store.roles != nil, error: store.error) { await store.loadRoles() } }
        .overlay(alignment: .bottom) { AdminNotice(notice: $store.notice) }
        .refreshable { await store.loadRoles() }
        .task { await store.loadRoles() }
    }

    private func footer(_ roles: AdminRoles) -> String {
        guard roles.canManage else {
            return "Touche un rôle pour choisir ce qu'il peut faire. Les changements s'appliquent tout de suite, à tous les comptes de ce rôle."
        }
        return "L'ordre est la hiérarchie : « Réordonner » pour glisser les rôles. Guest reste en bas, Admin en haut, "
            + "et tu ne ranges que les rôles en dessous du tien. Touche un rôle pour son nom, sa couleur et ses droits."
    }

    private func move(_ roles: AdminRoles, from: IndexSet, to: Int) {
        guard let keys = RoleOrder.moved(roles.descending, from: from, to: to, myRank: roles.access.rank) else {
            store.notice = "Ce déplacement n'est pas permis : Guest en bas, Admin en haut, et seulement sous ton rôle."
            return
        }
        Task { await store.reorderRoles(keys) }
    }

    /// Membre VIP d'abord (le plus souvent réglé), sinon le plus haut rôle modifiable.
    static func initial(_ roles: AdminRoles) -> MemberRole? {
        roles.editable.contains(.member) ? .member : roles.editable.first
    }
}

/// Une ligne de la liste : pastille de couleur, icône, nom, nombre de comptes ; cadenas au-dessus de soi.
private struct RoleRow: View {
    let role: MemberRole
    let locked: Bool

    var body: some View {
        HStack(spacing: 12) {
            Circle().fill(Color(hex: role.color ?? "") ?? Color.secondary.opacity(0.4)).frame(width: 14, height: 14)
            Text(role.title).foregroundStyle(locked ? .secondary : .primary)
            Spacer()
            if let members = role.members { Text("\(members)").foregroundStyle(.secondary).monospacedDigit() }
            if locked { Image(systemName: "lock.fill").font(.footnote).foregroundStyle(.secondary) }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(role.label)\(role.members.map { ", \($0) compte(s)" } ?? "")\(locked ? ", au-dessus de toi" : "")")
    }
}

/// Nom, icône (emoji) et couleur d'un rôle.
private struct RoleFields: View {
    @Binding var draft: RoleDraft

    var body: some View {
        TextField("Nom du rôle", text: $draft.label)
            .textInputAutocapitalization(.sentences)
        TextField("Icône (un emoji, facultatif)", text: $draft.icon)
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 10) {
                ForEach(RoleDraft.colors, id: \.self) { hex in
                    Button { draft.color = hex } label: {
                        Circle().fill(Color(hex: hex) ?? .gray).frame(width: 30, height: 30)
                            .overlay { if draft.color == hex { Image(systemName: "checkmark").font(.caption.bold()).foregroundStyle(.white) } }
                            .frame(width: 44, height: 44)
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Couleur \(hex)")
                    .accessibilityAddTraits(draft.color == hex ? .isSelected : [])
                }
            }
        }
    }
}

/// Nouveau rôle : nom, icône, couleur, et les droits d'un rôle existant comme point de départ.
private struct NewRoleSheet: View {
    @ObservedObject var store: GroupAdminStore
    @Environment(\.dismiss) private var dismiss
    @State private var draft = RoleDraft()
    @State private var copyFrom: MemberRole?

    var body: some View {
        NavigationStack {
            Form {
                Section("Rôle") { RoleFields(draft: $draft) }
                Section {
                    Picker("Partir des droits de", selection: $copyFrom) {
                        Text("Aucun droit").tag(MemberRole?.none)
                        ForEach(store.roles?.editable ?? []) { Text($0.title).tag(Optional($0)) }
                    }
                } footer: {
                    Text("Seulement les droits que tu as toi-même. Le rôle se place juste au-dessus de Guest : glisse-le ensuite à sa place.")
                }
            }
            .navigationTitle("Nouveau rôle")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Annuler") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Créer") { Task { if await store.createRole(draft, copyFrom: copyFrom) { dismiss() } } }
                        .disabled(!draft.valid || store.busy.contains("role.create"))
                }
            }
        }
        .presentationDetents([.medium, .large])
    }
}

/// Fiche d'un rôle : nom, couleur, icône ; ses droits par rubrique ; supprimer (en passant ses comptes à un autre rôle).
struct RoleDetailView: View {
    @ObservedObject var store: GroupAdminStore
    let key: String
    @Environment(\.dismiss) private var dismiss
    @State private var draft = RoleDraft()
    @State private var moveTo: MemberRole?
    @State private var confirming = false

    var body: some View {
        List {
            if let roles = store.roles, let role = roles.access.role(key) {
                if roles.canManage { edit(role) }
                permissions(roles, role)
                if roles.canDelete { removal(roles, role) }
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle(store.roles?.access.role(key)?.label ?? "Rôle")
        .navigationBarTitleDisplayMode(.inline)
        .overlay(alignment: .bottom) { AdminNotice(notice: $store.notice) }
        .onAppear { reset() }
        .onChange(of: saved) { _ in reset() }
        .confirmationDialog("Supprimer ce rôle ?", isPresented: $confirming, titleVisibility: .visible) {
            Button("Supprimer", role: .destructive) { remove() }
        } message: {
            Text(moveTo.map { "Ses comptes passent à \($0.label). Ses droits disparaissent." } ?? "Ses droits disparaissent.")
        }
    }

    /// Nom, couleur et icône enregistrés (les rôles se comparent par clé : on suit ces champs).
    private var saved: String {
        store.roles?.access.role(key).map { "\($0.label)|\($0.color ?? "")|\($0.icon ?? "")" } ?? ""
    }

    private func reset() {
        if let role = store.roles?.access.role(key) { draft = RoleDraft(role) }
    }

    private func edit(_ role: MemberRole) -> some View {
        Section {
            RoleFields(draft: $draft)
            Button("Enregistrer") { Task { await store.updateRole(role, draft: draft) } }
                .disabled(!draft.valid || draft == RoleDraft(role) || store.busy.contains("role.\(role.key)"))
        } header: {
            Text("Nom, icône et couleur")
        } footer: {
            Text(role.builtin ? "Rôle de base : il se renomme mais ne se supprime pas." : "")
        }
    }

    @ViewBuilder
    private func permissions(_ roles: AdminRoles, _ role: MemberRole) -> some View {
        ForEach(roles.groups) { group in
            Section(group.name) {
                ForEach(group.perms) { perm in
                    let on = roles.granted(perm.key, to: role)
                    Toggle(isOn: Binding(get: { on }, set: { value in Task { await store.toggle(perm.key, for: role, on: value) } })) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(perm.label)
                            if let hint = perm.hint { Text(hint).font(.footnote).foregroundStyle(.secondary) }
                        }
                    }
                    .disabled(!roles.canToggle(perm.key, for: role) || store.busy.contains("\(role.key).\(perm.key)"))
                }
            }
        }
    }

    @ViewBuilder
    private func removal(_ roles: AdminRoles, _ role: MemberRole) -> some View {
        if !role.builtin {
            let occupied = (role.members ?? 0) > 0
            Section {
                if occupied {
                    Picker("Ses comptes passent à", selection: $moveTo) {
                        Text("Choisir…").tag(MemberRole?.none)
                        ForEach(roles.editable.filter { $0 != role }) { Text($0.title).tag(Optional($0)) }
                    }
                }
                Button("Supprimer ce rôle", role: .destructive) { confirming = true }
                    .disabled((occupied && moveTo == nil) || store.busy.contains("role.\(role.key)"))
            } footer: {
                Text(occupied ? "\(role.members ?? 0) compte(s) ont ce rôle : choisis le rôle qui les reprend." : "Aucun compte n'a ce rôle.")
            }
        }
    }

    private func remove() {
        guard let role = store.roles?.access.role(key) else { return }
        let target = (role.members ?? 0) > 0 ? moveTo : nil
        Task { if await store.deleteRole(role, moveTo: target) { dismiss() } }
    }
}

/// Journal des membres (Root, Admin) : tout, ou celui d'un membre. Lecture seule, 100 lignes par page.
struct GroupJournalView: View {
    @ObservedObject var store: GroupAdminStore
    let member: String?
    let name: String?
    @State private var entries: [AdminJournal.Entry] = []
    @State private var more = false
    @State private var loaded = false

    var body: some View {
        List {
            Section {
                if loaded && entries.isEmpty { Text("Rien dans le journal pour l'instant.").foregroundStyle(.secondary) }
                ForEach(entries) { entry in
                    VStack(alignment: .leading, spacing: 2) {
                        Text(entry.text)
                        if let at = AdminDate.text(entry.at) { Text(at).font(.footnote).foregroundStyle(.secondary) }
                    }
                    .accessibilityElement(children: .combine)
                }
                if more {
                    Button("Plus ancien") { Task { await load(before: entries.last?.id) } }
                        .disabled(store.busy.contains("journal"))
                }
            } footer: {
                Text(member == nil ? "Inscriptions, connexions, rôles, bêta, groupes, accès retirés, suppressions et consultations de la liste. Rien n'y est modifiable."
                                   : "Tout ce qui concerne \(name ?? "ce membre"). Rien n'y est modifiable.")
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle(member == nil ? "Journal" : "Journal de \(name ?? "")")
        .navigationBarTitleDisplayMode(.inline)
        .overlay { if !loaded { ProgressView() } }
        .overlay(alignment: .bottom) { AdminNotice(notice: $store.notice) }
        .refreshable { await load(before: nil) }
        .task { if !loaded { await load(before: nil) } }
    }

    private func load(before: Int?) async {
        guard let page = await store.journal(member: member, before: before) else {
            loaded = true
            return
        }
        entries = before == nil ? page.entries : entries + page.entries
        more = page.more
        loaded = true
    }
}

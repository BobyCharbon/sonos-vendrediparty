import SwiftUI

/// Rôles et droits : on choisit un rôle (en dessous du sien), puis on coche ce qu'il peut faire.
struct GroupRolesView: View {
    @ObservedObject var store: GroupAdminStore
    @State private var role: MemberRole?

    var body: some View {
        List {
            if let roles = store.roles, let current = role ?? Self.initial(roles) {
                Section {
                    Picker("Rôle", selection: Binding(get: { current }, set: { role = $0 })) {
                        ForEach(roles.editable) { Text($0.label).tag($0) }
                    }
                } footer: {
                    Text("Les changements s'appliquent tout de suite, à tous les comptes de ce rôle."
                         + (roles.access.rank >= AdminAccess.rootRank ? " En tant que root, tu as toujours tous les droits."
                                                                      : " Tu ne peux donner que les droits que tu as toi-même."))
                }
                ForEach(roles.groups) { group in
                    Section(group.name) {
                        ForEach(group.perms) { perm in
                            let on = roles.granted(perm.key, to: current)
                            Toggle(isOn: Binding(get: { on }, set: { value in Task { await store.toggle(perm.key, for: current, on: value) } })) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(perm.label)
                                    if let hint = perm.hint { Text(hint).font(.footnote).foregroundStyle(.secondary) }
                                }
                            }
                            .disabled(!roles.canToggle(perm.key, for: current) || store.busy.contains("\(current.rawValue).\(perm.key)"))
                        }
                    }
                }
            } else if store.roles != nil {
                Text("Aucun rôle en dessous du tien à régler.").foregroundStyle(.secondary)
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle("Rôles et droits")
        .navigationBarTitleDisplayMode(.inline)
        .overlay { AdminLoading(loaded: store.roles != nil, error: store.error) { await store.loadRoles() } }
        .overlay(alignment: .bottom) { AdminNotice(notice: $store.notice) }
        .refreshable { await store.loadRoles() }
        .task { await store.loadRoles() }
    }

    /// Membre VIP d'abord (le plus souvent réglé), sinon le plus haut rôle modifiable.
    static func initial(_ roles: AdminRoles) -> MemberRole? {
        roles.editable.contains(.member) ? .member : roles.editable.first
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

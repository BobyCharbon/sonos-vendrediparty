import SwiftUI

/// Membres : par rôle, recherche ; une fiche par personne pour son rôle, son accès, la bêta, le journal, la suppression.
struct GroupMembersView: View {
    @ObservedObject var store: GroupAdminStore
    @State private var search = ""

    var body: some View {
        List {
            if let members = store.members {
                Section {
                } footer: {
                    Text("\(members.people.count) compte(s) inscrit(s)")
                }
                ForEach(members.sections(matching: search)) { section in
                    Section(section.title) {
                        ForEach(section.people) { person in
                            NavigationLink { MemberDetailView(store: store, memberID: person.id) } label: { MemberRow(person: person, me: members.access.me) }
                        }
                    }
                }
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .searchable(text: $search, prompt: "Surnom, prénom, nom, numéro")
        .navigationTitle("Membres")
        .navigationBarTitleDisplayMode(.inline)
        .overlay { AdminLoading(loaded: store.members != nil, error: store.error) { await store.loadMembers() } }
        .overlay(alignment: .bottom) { AdminNotice(notice: $store.notice) }
        .refreshable { await store.loadMembers() }
        .task { await store.loadMembers() }
    }
}

private struct MemberRow: View {
    let person: AdminMembers.Person
    let me: String

    var body: some View {
        HStack(spacing: 12) {
            AdminAvatar(photo: person.photo, name: person.name)
            VStack(alignment: .leading, spacing: 2) {
                Text(person.displayName + (person.id == me ? " (toi)" : "")).font(.body.weight(.semibold))
                Text([person.root ? "Root" : nil, person.fullName.isEmpty ? nil : person.fullName, person.beta ? "Bêta" : nil]
                    .compactMap { $0 }.joined(separator: " · "))
                    .font(.footnote).foregroundStyle(.secondary).lineLimit(1)
            }
        }
    }
}

/// Fiche d'un membre. Ce qui est proposé suit MemberRules ; la base revérifie tout.
struct MemberDetailView: View {
    @ObservedObject var store: GroupAdminStore
    let memberID: String
    @State private var deleting = false
    @State private var typed = ""
    @Environment(\.dismiss) private var dismiss

    private static let confirmWord = "supprimer"

    var body: some View {
        List {
            if let members = store.members, let person = members.people.first(where: { $0.id == memberID }) {
                let rules = MemberRules(access: members.access, person: person)
                identity(person, full: members.full)
                if rules.changesRole { roles(person, rules: rules, access: members.access) }
                if rules.setsBeta { beta(person) }
                if rules.bans { access(person) }
                if members.full { tools(person, rules: rules) }
                if !rules.below && members.access.canRoles {
                    Section {
                    } footer: {
                        Text(person.id == members.access.me ? "C'est ton compte : un autre administrateur doit le modifier."
                                                            : "Rôle égal ou supérieur au tien : tu ne peux pas le modifier.")
                    }
                }
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle(store.members?.people.first(where: { $0.id == memberID })?.displayName ?? "Membre")
        .navigationBarTitleDisplayMode(.inline)
        .overlay(alignment: .bottom) { AdminNotice(notice: $store.notice) }
        .disabled(store.busy.contains(memberID))
        .alert("Supprimer le compte ?", isPresented: $deleting) {
            TextField(expected, text: $typed).textInputAutocapitalization(.never).autocorrectionDisabled()
            Button("Annuler", role: .cancel) { typed = "" }
            Button("Supprimer définitivement", role: .destructive) { remove() }
        } message: {
            Text("Tout sera effacé : profil, photo, numéro, réponses, messages. Tape « \(expected) » pour confirmer.")
        }
    }

    private var person: AdminMembers.Person? { store.members?.people.first(where: { $0.id == memberID }) }
    /// Surnom à retaper ; « supprimer » pour un profil sans surnom (la base compare alors au surnom vide).
    private var expected: String { person?.name.isEmpty == false ? person!.name : Self.confirmWord }

    private func identity(_ person: AdminMembers.Person, full: Bool) -> some View {
        Section {
            HStack(spacing: 14) {
                AdminAvatar(photo: person.photo, name: person.name, size: 58)
                VStack(alignment: .leading, spacing: 3) {
                    Text(person.displayName).font(.title3.weight(.semibold))
                    if !person.fullName.isEmpty { Text(person.fullName).foregroundStyle(.secondary) }
                    Text(person.banned ? "Accès retiré" : person.roleText).font(.footnote).foregroundStyle(.secondary)
                }
            }
            if let phone = person.phone { LabeledContent("Numéro", value: "+\(phone.trimmingCharacters(in: CharacterSet(charactersIn: "+")))") }
            if full, let created = AdminDate.text(person.createdAt) { LabeledContent("Inscrit le", value: created) }
            if full, let seen = AdminDate.text(person.lastSignInAt) { LabeledContent("Connecté le", value: seen) }
        }
    }

    private func roles(_ person: AdminMembers.Person, rules: MemberRules, access: AdminAccess) -> some View {
        Section {
            ForEach(access.assignable.reversed()) { role in
                Button { Task { await store.setRole(role, of: person) } } label: {
                    HStack {
                        Text(role.label)
                        Spacer()
                        if person.role == role { Image(systemName: "checkmark").foregroundStyle(Palette.accent) }
                    }
                }
                .foregroundStyle(rules.allows(role) || person.role == role ? .primary : .secondary)
                .disabled(!rules.allows(role))
                .allowsHitTesting(person.role != role)
                .accessibilityAddTraits(person.role == role ? .isSelected : [])
            }
        } header: {
            Text("Rôle")
        } footer: {
            Text(person.complete ? "Membre : mêmes droits que Guest, sans être dans le groupe Vendredi Party. Membre VIP et plus : dans le groupe."
                                 : "Profil incomplet : il reste Guest ou Membre tant qu'il manque nom, prénom, surnom ou photo.")
        }
    }

    private func beta(_ person: AdminMembers.Person) -> some View {
        Section {
            Toggle(isOn: Binding(get: { person.beta }, set: { on in Task { await store.setBeta(on, person) } })) {
                Label("Bêta-testeur", systemImage: "testtube.2")
            }
        } footer: {
            Text(person.beta && person.role.rank == 0
                 ? "Encore \(person.role.label) : l'onglet s'ouvre, mais il faut aussi le passer Membre VIP pour qu'il voie les événements."
                 : "Voit les Événements en production avant tout le monde.")
        }
    }

    private func access(_ person: AdminMembers.Person) -> some View {
        Section {
            if person.active {
                Button("Retirer l'accès", role: .destructive) { Task { await store.setBanned(true, person) } }
            } else {
                Button("Réintégrer") { Task { await store.setBanned(false, person) } }
            }
        } footer: {
            Text(person.active ? "La personne ne peut plus rien voir ni faire dans Party ; tu peux la réintégrer ensuite." : "")
        }
    }

    private func tools(_ person: AdminMembers.Person, rules: MemberRules) -> some View {
        Section {
            NavigationLink("Journal de \(person.displayName)") { GroupJournalView(store: store, member: person.id, name: person.displayName) }
            if rules.deletes {
                Button("Supprimer le compte", role: .destructive) { typed = ""; deleting = true }
            }
        } footer: {
            if rules.deletes { Text("Irréversible. La personne pourra se réinscrire par SMS et repartira Guest.") }
        }
    }

    private func remove() {
        guard let person else { return }
        let same = typed.trimmingCharacters(in: .whitespaces).lowercased() == expected.trimmingCharacters(in: .whitespaces).lowercased()
        guard same else {
            store.notice = "Le surnom tapé ne correspond pas."
            return
        }
        let confirm = person.name.isEmpty ? "" : typed
        typed = ""
        Task { if await store.delete(person, confirmName: confirm) { dismiss() } }
    }
}

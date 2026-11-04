import SwiftUI

/// Réglages › Mes amis dans Party (avis 84fab3987f68) : les personnes de mes contacts inscrites sur Party, A–Z sous
/// le nom que je leur ai donné, et l'onglet « À inviter » (contacts sans compte, calculé sur l'iPhone).
struct FriendsView: View {
    enum Tab: String, CaseIterable, Identifiable {
        case friends = "Sur Party", invite = "À inviter"
        var id: String { rawValue }
    }

    @ObservedObject var store: FriendsStore
    let privacy: PrivacyStore
    /// « Écrire » : message direct (conversation privée à deux) ; nil = celui de l'app (Discussions), s'il est disponible.
    var onWrite: ((PartyFriend) -> Void)? = nil
    @Environment(\.writeDirect) private var writeDirect
    @State private var writeProblem: String?

    @ObservedObject private var contacts = ContactNames.shared
    @State private var tab: Tab = .friends
    @State private var query = ""
    @State private var profile: FriendTarget?
    @State private var contactSheet: FriendTarget?
    @State private var draft: MessageDraft?
    @State private var sharing: SharedInvite?
    @State private var explaining = false
    @State private var picking = false
    @Environment(\.openURL) private var openURL
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        List {
            Section {
                Picker("Liste", selection: $tab) {
                    ForEach(Tab.allCases) { Text($0.rawValue).tag($0) }
                }
                .pickerStyle(.segmented)
                .accessibilityIdentifier("friends-tab")
            }
            .listRowBackground(Color.clear)
            .listRowInsets(EdgeInsets())
            if store.canInvite, let invite = store.invite, query.isEmpty {
                InviteBanner(link: invite) { Task { await store.renewLink() } }
            }
            if !contacts.access.canRead {
                AccessSection(access: contacts.access, ask: { explaining = true },
                              openSettings: { if let url = URL(string: UIApplication.openSettingsURLString) { openURL(url) } })
            } else {
                if contacts.access == .limited { limitedRow }
                switch tab {
                case .friends: friendsContent
                case .invite:
                    InviteList(store: store, query: query, link: store.invite?.url, compose: { draft = $0 },
                               share: { candidate, text in sharing = SharedInvite(candidate: candidate, text: text) })
                }
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle("Mes amis")
        .navigationBarTitleDisplayMode(.large)
        .searchable(text: $query, prompt: tab == .friends ? "Nom ou pseudo" : "Rechercher un contact")
        .refreshable { await store.load(force: true) }
        .task { await store.load() }
        .onChange(of: scenePhase) { phase in if phase == .active { contacts.appBecameActive() } }
        .motion(Motion.smooth, value: tab)
        .motion(Motion.smooth, value: contacts.access)
        .motion(Motion.smooth, value: store.friends.count)
        .modifier(LimitedPicker(isPresented: $picking))
        .alert("Écrire", isPresented: Binding(get: { writeProblem != nil }, set: { if !$0 { writeProblem = nil } })) {
            Button("OK", role: .cancel) {}
        } message: { Text(writeProblem ?? "") }
        .sheet(item: $profile) { MemberCardView(store: privacy, memberID: $0.id) }
        .sheet(item: $contactSheet) { target in
            if let contact = contacts.contactIdentifier(for: target.id).flatMap(ContactCardSheet.existing) {
                ContactCardSheet(mode: .existing(contact)) { contactSheet = nil }.ignoresSafeArea()
            }
        }
        .sheet(item: $draft) { draft in composer(draft) }
        // Feuille de partage d'iOS (WhatsApp, Instagram, Snapchat, Messages, Mail, Copier…) : partagé = « Invité ».
        .sheet(item: $sharing) { item in
            ShareSheet(text: item.text) { shared in
                sharing = nil
                if shared { store.markInvited(item.candidate); Haptics.success() }
            }
            .presentationDetents([.medium, .large])
        }
        .sheet(isPresented: $explaining) {
            ContactsExplainer { allow in
                explaining = false
                contacts.promptShown()
                if allow { Task { await contacts.requestAccess(); await store.load() } }
            }
            .presentationDetents([.medium, .large])
        }
        .overlay(alignment: .bottom) {
            NoticeBanner(notice: store.notice.map { NoticeBanner.Notice(text: $0, isError: false) }) { store.notice = nil }
        }
    }

    // MARK: Sur Party

    @ViewBuilder private var friendsContent: some View {
        let all = store.rows
        let shown = FriendsLogic.filter(all, query: query)
        if let error = store.error, all.isEmpty {
            Section {
                Label(error, systemImage: "exclamationmark.triangle.fill").foregroundStyle(.orange)
                Button("Réessayer") { Task { await store.load(force: true) } }
            }
        } else if !store.loaded && all.isEmpty {
            Section { HStack { Spacer(); ProgressView(); Spacer() } }.listRowBackground(Color.clear)
        } else if all.isEmpty {
            Section {
                EmptyState(symbol: "person.2.slash", title: "Aucun ami sur Party pour l'instant",
                           text: "Aucun numéro de tes contacts n'a encore de compte Party. Invite-les depuis « À inviter ».")
                Button("Voir les contacts à inviter") { tab = .invite }
            }
        } else if shown.isEmpty {
            Section { Text("Aucun résultat pour « \(query) »").foregroundStyle(.secondary) }
        } else {
            let newcomers = query.isEmpty ? FriendsLogic.newcomers(all) : []
            if !newcomers.isEmpty {
                Section("Nouveaux sur Party") { ForEach(newcomers) { row(for: $0, showJoined: true) } }
            }
            ForEach(FriendsLogic.sections(shown), id: \.letter) { section in
                Section(section.letter) { ForEach(section.rows) { row(for: $0, showJoined: false) } }
            }
            Section {
            } footer: {
                Text("\(all.count) contact\(all.count > 1 ? "s" : "") sur Party, reconnu\(all.count > 1 ? "s" : "") grâce à une empreinte chiffrée des numéros : tes contacts restent sur ton iPhone.")
            }
        }
    }

    private func row(for row: FriendRow, showJoined: Bool) -> some View {
        Button { Haptics.tap(); profile = FriendTarget(id: row.id) } label: {
            FriendRowView(row: row, showJoined: showJoined)
        }
        .foregroundStyle(.primary)
        .contextMenu { menu(for: row) }
        .accessibilityIdentifier("friend-\(row.id)")
    }

    /// « Écrire » : le point d'accroche donné, sinon la conversation privée dans Discussions.
    private var write: ((PartyFriend) -> Void)? {
        if let onWrite { return onWrite }
        guard let writeDirect else { return nil }
        return { friend in
            Haptics.tap()
            Task {
                writeProblem = await writeDirect.open(friend.id) ? nil : "Tu ne peux pas écrire à \(friend.displayName) pour l'instant. Réessaie."
            }
        }
    }

    @ViewBuilder private func menu(for row: FriendRow) -> some View {
        Button { profile = FriendTarget(id: row.id) } label: { Label("Voir le profil", systemImage: "person.crop.circle") }
        if let write { Button { write(row.friend) } label: { Label("Écrire", systemImage: "bubble.left.fill") } }
        if let phone = store.phone(of: row.friend) {
            Button {
                draft = MessageDraft(recipient: phone, body: "")
            } label: { Label("Message", systemImage: "message.fill") }
        }
        if !store.myGroups.isEmpty {
            Menu {
                ForEach(store.myGroups) { group in
                    Button(group.name) { Task { await store.add(row.friend, to: group, as: row.contactName) } }
                }
            } label: { Label("Ajouter à un groupe", systemImage: "person.3.fill") }
        }
        if contacts.contactIdentifier(for: row.id) != nil {
            Button { contactSheet = FriendTarget(id: row.id) } label: { Label("Voir le contact", systemImage: "person.text.rectangle") }
        }
    }

    private var limitedRow: some View {
        Section {
            Button { picking = true } label: {
                Label("Choisir d'autres contacts", systemImage: "person.crop.circle.badge.plus")
            }
        } footer: {
            Text("Accès limité : Party ne voit que les contacts que tu as choisis.")
        }
    }

    @ViewBuilder private func composer(_ draft: MessageDraft) -> some View {
        if MessageComposer.available {
            MessageComposer(draft: draft) { sent in finish(draft, sent) }.ignoresSafeArea()
        } else {
            ShareSheet(text: draft.body.isEmpty ? draft.recipient : draft.body) { shared in finish(draft, shared) }
                .presentationDetents([.medium, .large])
        }
    }

    private func finish(_ sent: MessageDraft, _ done: Bool) {
        draft = nil
        if done, let candidate = sent.candidate {
            store.markInvited(candidate)
            Haptics.success()
        }
    }
}

struct FriendTarget: Identifiable { let id: String }

struct SharedInvite: Identifiable {
    let id = UUID()
    let candidate: InviteCandidate
    let text: String
}

/// Une ligne : photo, « Nom du contact · pseudo », puis les groupes en commun ou la date d'arrivée.
struct FriendRowView: View {
    let row: FriendRow
    let showJoined: Bool

    var body: some View {
        HStack(spacing: 12) {
            AdminAvatar(photo: row.friend.photo, name: row.label.primary, size: 42)
            VStack(alignment: .leading, spacing: 2) {
                HStack(alignment: .firstTextBaseline, spacing: 4) {
                    Text(row.label.primary).font(.body.weight(.medium)).lineLimit(1)
                    if let nick = row.label.secondary {
                        Text("· \(nick)").font(.footnote).foregroundStyle(.secondary).lineLimit(1).layoutPriority(-1)
                    }
                }
                if let detail { Text(detail).font(.footnote).foregroundStyle(.secondary).lineLimit(1) }
            }
            Spacer(minLength: 0)
        }
        .padding(.vertical, 2)
        .contentShape(Rectangle())
        .accessibilityElement(children: .combine)
    }

    private var detail: String? {
        if showJoined, let joined = row.friend.joinedAt {
            return "Arrivé sur Party \(joined.formatted(.relative(presentation: .named)))"
        }
        return row.friend.commonGroups.isEmpty ? nil : "En commun : " + row.friend.commonGroups.joined(separator: ", ")
    }
}

/// « Invite tes amis » : mon lien personnel, à partager (ShareLink), et qui est arrivé grâce à lui.
private struct InviteBanner: View {
    let link: AppInviteLink
    let renew: () -> Void
    @State private var confirmRenew = false

    var body: some View {
        Section {
            HStack(spacing: 14) {
                Image(systemName: "envelope.open.fill")
                    .font(.system(size: 22, weight: .semibold)).foregroundStyle(.white)
                    .frame(width: 46, height: 46)
                    .background(Palette.accent.gradient, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 3) {
                    Text("Invite tes amis").font(.headline)
                    Text(link.joined == 0 ? "Ils s'inscrivent avec leur numéro ; tu es prévenu à leur arrivée."
                                          : "\(link.joined) personne\(link.joined > 1 ? "s ont" : " a") rejoint grâce à toi")
                        .font(.footnote).foregroundStyle(.secondary)
                }
            }
            .padding(.vertical, 4)
            // Feuille de partage d'iOS : WhatsApp, Instagram, Snapchat, Messages, Mail… (aperçu riche du lien : Open Graph).
            ShareLink(item: link.url, subject: Text("Rejoins-moi sur Party"),
                      message: Text("Rejoins-moi sur Party, pour nos soirées et événements")) {
                Label("Partager mon lien", systemImage: "square.and.arrow.up")
            }
            .accessibilityIdentifier("friends-share-link")
            Button("Nouveau lien", role: .destructive) { confirmRenew = true }
                .font(.footnote)
                .confirmationDialog("L'ancien lien ne marchera plus.", isPresented: $confirmRenew, titleVisibility: .visible) {
                    Button("Créer un nouveau lien", role: .destructive, action: renew)
                }
        }
    }
}

/// Accès aux contacts pas encore donné, refusé ou bloqué.
private struct AccessSection: View {
    let access: ContactsAccess
    let ask: () -> Void
    let openSettings: () -> Void

    var body: some View {
        Section {
            EmptyState(symbol: access == .notDetermined ? "person.crop.circle.badge.questionmark" : "person.crop.circle.badge.xmark",
                       title: access == .notDetermined ? "Retrouve tes amis" : "Accès aux contacts refusé",
                       text: access == .notDetermined
                           ? "Party compare une empreinte chiffrée des numéros de tes contacts pour te montrer qui est déjà inscrit. Tes contacts restent sur ton iPhone."
                           : access == .restricted ? "Les restrictions de cet iPhone empêchent l'accès aux contacts."
                                                   : "Autorise Contacts pour Party dans les Réglages de l'iPhone pour voir tes amis.")
            if access == .notDetermined {
                Button("Continuer", action: ask).accessibilityIdentifier("friends-allow")
            } else if access == .denied {
                Button("Ouvrir les Réglages de l'iPhone", action: openSettings)
            }
        }
    }
}

struct EmptyState: View {
    let symbol: String
    let title: String
    let text: String

    var body: some View {
        VStack(spacing: 10) {
            Image(systemName: symbol).font(.system(size: 40, weight: .semibold)).foregroundStyle(Palette.accent)
                .accessibilityHidden(true)
            Text(title).font(.headline).multilineTextAlignment(.center)
            Text(text).font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 14)
        .accessibilityElement(children: .combine)
    }
}

/// Fiche d'un membre › « Invité par » : admins seulement (droit « Voir qui a invité qui », vérifié par la base).
struct InvitedBySection: View {
    let rows: [InvitedBy]

    var body: some View {
        Section {
            ForEach(rows) { row in
                VStack(alignment: .leading, spacing: 2) {
                    Text(row.inviter.isEmpty ? "Compte supprimé" : row.inviter).font(.body.weight(.medium))
                    Text(row.how + (row.at.map { " · " + $0.formatted(date: .abbreviated, time: .omitted) } ?? ""))
                        .font(.footnote).foregroundStyle(.secondary)
                }
                .accessibilityElement(children: .combine)
            }
        } header: {
            Text("Invité par")
        } footer: {
            Text("Visible seulement des admins (droit « Voir qui a invité qui »).")
        }
    }
}

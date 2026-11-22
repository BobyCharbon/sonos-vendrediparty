import SwiftUI

/// Réglages du groupe (⚙ de sa page), comme web/events/src/app/group/[id]/settings.tsx, mêmes droits : Modifier (nom,
/// emoji, couleur, photo : son créateur ou un Admin du site), montrer mon numéro, règles des événements, membres
/// (retirer), autres liens d'invitation, supprimer ; quitter soi-même (jamais Membres Vendredi Party, ni le créateur).
struct GroupSettingsView: View {
    let groupID: String
    var onGone: () -> Void = {}

    @Environment(\.people) private var people
    @Environment(\.dismiss) private var dismiss
    @State private var page: GroupPage?
    @State private var loadError: String?
    @State private var name = ""
    @State private var emoji = "🪩"
    @State private var color = "pink"
    @State private var busy = false
    @State private var error: String?
    @State private var note: String?
    @State private var askTerms: (() -> Void)?
    @State private var removing: GroupPage.Member?
    @State private var confirmLeave = false
    @State private var confirmDelete = false

    private var api: GroupsAPI? { people.map { GroupsAPI(people: $0) } }
    private var clean: String { name.split(whereSeparator: \.isWhitespace).joined(separator: " ") }

    var body: some View {
        Form {
            if let page {
                if let error { Section { Text(error).foregroundStyle(PronoTheme.pinkInk) }.listRowBackground(ConvNeon.surface) }
                lookSection(page)
                if page.member { privacySection(page) }
                if page.canSetRules {
                    GroupRulesSection(page: page, save: saveRules, saveInvite: page.manage && !page.group.system ? saveMembersInvite : nil)
                }
                if page.manage { membersSection(page) }
                if page.manage { GroupLinksSection(groupID: groupID) }
                dangerSection(page)
            } else if let loadError {
                Section { Text(loadError).foregroundStyle(PronoTheme.t2) }.listRowBackground(ConvNeon.surface)
            } else {
                Section { ProgressView().frame(maxWidth: .infinity) }.listRowBackground(Color.clear)
            }
        }
        .convNeonForm()
        .navigationTitle("Réglages du groupe")
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
        .motion(Motion.smooth, value: page?.members.map(\.id))
        .sheet(isPresented: Binding(get: { askTerms != nil }, set: { if !$0 { askTerms = nil } })) {
            if let people {
                TermsAcceptSheet(store: people.moderation) { accepted in
                    let retry = askTerms
                    askTerms = nil
                    if accepted { retry?() }
                }
            }
        }
        .confirmationDialog(removing.map { "Retirer \($0.name) du groupe ?" } ?? "", isPresented: Binding(get: { removing != nil },
                            set: { if !$0 { removing = nil } }), titleVisibility: .visible, presenting: removing) { m in
            Button("Retirer", role: .destructive) { run(ok: "\(m.name) a quitté le groupe") { try await $0.removeMember(groupID, m.id) } }
        }
        .confirmationDialog("Quitter le groupe ?", isPresented: $confirmLeave, titleVisibility: .visible) {
            Button("Quitter le groupe", role: .destructive) { run(gone: true) { try await $0.leave(groupID) } }
        } message: { Text("Tu ne verras plus sa discussion ni ses événements réservés au groupe.") }
        .confirmationDialog("Supprimer le groupe ?", isPresented: $confirmDelete, titleVisibility: .visible) {
            Button("Supprimer le groupe", role: .destructive) { run(gone: true) { try await $0.delete(groupID) } }
        } message: { Text("Les invités qui ont déjà répondu gardent l’accès à leurs événements. On ne peut pas revenir en arrière.") }
        .overlay(alignment: .bottom) {
            if let note {
                Text(note).font(.subheadline.weight(.semibold)).foregroundStyle(PronoTheme.t1)
                    .padding(.horizontal, 16).padding(.vertical, 12)
                    .background(.ultraThinMaterial, in: Capsule())
                    .padding(.bottom, 12)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                    .task(id: note) {
                        try? await Task.sleep(for: .seconds(2.5))
                        Motion.animate(Motion.smooth) { self.note = nil }
                    }
            }
        }
    }

    // MARK: Sections

    @ViewBuilder private func lookSection(_ page: GroupPage) -> some View {
        if page.manage {
            Section {
                HStack(spacing: 12) {
                    GroupTile(emoji: emoji, color: color, photo: page.group.photo, size: 56)
                    TextField("Nom du groupe", text: $name)
                        .font(.title3.weight(.semibold))
                        .onChange(of: name) { value in if value.count > GroupText.nameMax { name = String(value.prefix(GroupText.nameMax)) } }
                        .accessibilityLabel("Nom du groupe")
                        .accessibilityIdentifier("group-settings-name")
                }
                VStack(alignment: .leading, spacing: 8) {
                    Text("Un emoji").font(.subheadline.weight(.semibold)).foregroundStyle(PronoTheme.t2)
                    GroupEmojiGrid(selection: $emoji)
                }
                VStack(alignment: .leading, spacing: 8) {
                    Text("Une couleur").font(.subheadline.weight(.semibold)).foregroundStyle(PronoTheme.t2)
                    GroupColorRow(selection: $color)
                }
                Button { saveLook() } label: {
                    Text("Enregistrer").font(.headline).frame(maxWidth: .infinity, minHeight: 44)
                }
                .disabled(!changed(page) || clean.isEmpty || busy)
                .accessibilityIdentifier("group-settings-save")
                GroupPhotoField(has: page.group.photo != nil, busy: busy, picked: { sendPhoto($0) }, remove: { removePhoto() })
                    .padding(.vertical, 4)
            } header: {
                Text("Modifier le groupe")
            }
            .listRowBackground(ConvNeon.surface)
        } else {
            Section {
                HStack(spacing: 12) {
                    GroupTile(emoji: page.group.emoji, color: page.group.color, photo: page.group.photo, system: page.group.system, size: 56)
                    Text(page.group.system
                         ? "Tous les Membres VIP et au-dessus, tenu à jour tout seul : passer quelqu’un Membre VIP l’ajoute, le remettre Guest le retire (Administration → Membres)."
                         : "Seul le créateur du groupe change son nom, son emoji, sa couleur et sa photo.")
                        .font(.footnote).foregroundStyle(PronoTheme.t2)
                }
            } header: {
                Text(page.group.title)
            }
            .listRowBackground(ConvNeon.surface)
        }
    }

    private func privacySection(_ page: GroupPage) -> some View {
        Section {
            Toggle("Montrer mon numéro dans ce groupe", isOn: Binding(get: { page.phoneShared }, set: { on in
                Haptics.selection()
                self.page?.phoneShared = on
                run { try await $0.setPhone(groupID, visible: on) }
            }))
            .tint(PronoTheme.lavB)
            .disabled(busy)
            .accessibilityIdentifier("group-settings-phone")
        } header: {
            Text("Ma confidentialité")
        } footer: {
            Text("Les membres de ce groupe le voient sur ta fiche profil. Caché par défaut.")
        }
        .listRowBackground(ConvNeon.surface)
    }

    private func membersSection(_ page: GroupPage) -> some View {
        Section {
            NavigationLink(value: GroupScreen.invite(groupID)) {
                Label("Inviter des gens", systemImage: "hand.wave.fill").foregroundStyle(PronoTheme.lav)
            }
            ForEach(page.members) { m in
                HStack(spacing: 10) {
                    PronoAvatar(face: m.face, size: 34)
                    PersonName(id: m.id, pseudo: m.name).foregroundStyle(PronoTheme.t1).lineLimit(1)
                    if m.creator { Text("· Créateur").font(.footnote).foregroundStyle(PronoTheme.t2) }
                    Spacer()
                    if !m.creator && !m.me {
                        Button("Retirer", role: .destructive) { removing = m }
                            .buttonStyle(.borderless)
                            .frame(minHeight: 44)
                            .accessibilityLabel("Retirer \(m.name) du groupe")
                    }
                }
            }
        } header: {
            Text("Membres · \(page.members.count)")
        }
        .listRowBackground(ConvNeon.surface)
    }

    @ViewBuilder private func dangerSection(_ page: GroupPage) -> some View {
        if page.canLeave || page.manage {
            Section {
                if page.canLeave {
                    Button("Quitter le groupe", role: .destructive) { confirmLeave = true }
                        .frame(minHeight: 44)
                        .accessibilityIdentifier("group-settings-leave")
                }
                if page.manage {
                    Button("Supprimer le groupe", role: .destructive) { confirmDelete = true }
                        .frame(minHeight: 44)
                        .accessibilityIdentifier("group-settings-delete")
                }
            } footer: {
                if page.manage { Text("Les invités qui ont déjà répondu gardent l’accès à leurs événements.") }
            }
            .listRowBackground(ConvNeon.surface)
        }
    }

    // MARK: Actions

    private func changed(_ page: GroupPage) -> Bool {
        clean != page.group.name || emoji != page.group.emoji || color != (page.group.color ?? "pink")
    }

    private func load() async {
        guard let api else { loadError = "Connecte-toi à Party pour voir tes groupes."; return }
        do {
            let fresh = try await api.page(groupID)
            if page == nil || !changed(page!) {  // garde une saisie en cours
                name = fresh.group.name
                emoji = fresh.group.emoji
                color = fresh.group.color ?? "pink"
            }
            page = fresh
            loadError = nil
        } catch {
            if page == nil { loadError = PeopleStore.message(error) }
        }
    }

    /// Une action de la base, puis la page relue ; gone : le groupe n'est plus à moi (quitté, supprimé).
    private func run(ok: String? = nil, gone: Bool = false, _ work: @escaping (GroupsAPI) async throws -> Void) {
        guard let api, !busy else { return }
        busy = true
        Task {
            defer { busy = false }
            do {
                try await work(api)
                error = nil
                if gone {
                    Haptics.success()
                    onGone()
                    return
                }
                if let ok { Motion.animate(Motion.smooth) { note = ok } }
                await load()
            } catch PartyAPIError.termsRequired {
                askTerms = { run(ok: ok, gone: gone, work) }
            } catch {
                Haptics.error()
                self.error = PeopleStore.message(error)
                await load()
            }
        }
    }

    private func saveLook() {
        let (n, e, c) = (clean, emoji, color)
        run(ok: "Groupe enregistré") { try await $0.update(groupID, name: n, emoji: e, color: c) }
    }

    private func sendPhoto(_ jpeg: Data) {
        guard let people else { return }
        run(ok: "Photo enregistrée") { _ in try await people.uploadGroupPhoto(groupID, jpeg: jpeg) }
    }

    private func removePhoto() {
        run(ok: "Photo retirée") { try await $0.removePhoto(groupID) }
    }

    private func saveRules(_ needApproval: Bool, _ mode: String) {
        run { try await $0.setRules(groupID, needApproval: needApproval, mode: mode) }
    }

    private func saveMembersInvite(_ allowed: Bool) {
        run(ok: allowed ? "Tous les membres peuvent inviter" : "Seuls ceux qui gèrent le groupe invitent") {
            try await $0.setMembersInvite(groupID, allowed: allowed)
        }
    }
}

/// Règles du groupe, comme settings.tsx et GroupEventRules.tsx : « Tous les membres peuvent inviter » (22.11, allumé par
/// défaut, qui gère le groupe), « Événements à valider » (éteint par défaut) et les notifications (06.11) ; Membres
/// Vendredi Party : les Co-admins et plus, seule l'annonce s'y règle.
struct GroupRulesSection: View {
    let page: GroupPage
    let save: (_ needApproval: Bool, _ mode: String) -> Void
    var saveInvite: ((Bool) -> Void)?

    var body: some View {
        Section {
            if let saveInvite {
                VStack(alignment: .leading, spacing: 6) {
                    Toggle("Tous les membres peuvent inviter", isOn: Binding(get: { page.group.membersInvite }, set: { on in
                        Haptics.selection()
                        saveInvite(on)
                    }))
                    .font(.subheadline.weight(.semibold))
                    .accessibilityIdentifier("group-members-invite")
                    Text(page.group.membersInvite
                         ? "Chaque membre peut ajouter quelqu’un et partager le lien du groupe."
                         : "Seuls toi et ceux qui gèrent le groupe invitent et partagent le lien du groupe.")
                        .font(.footnote).foregroundStyle(PronoTheme.t2)
                }
                .padding(.vertical, 4)
            }
            if !page.group.system {
                VStack(alignment: .leading, spacing: 6) {
                    Toggle("Événements à valider", isOn: Binding(get: { page.group.eventsNeedApproval }, set: { on in
                        Haptics.selection()
                        save(on, page.group.announceMode)
                    }))
                    .font(.subheadline.weight(.semibold))
                    .accessibilityIdentifier("group-events-approval")
                    Text(page.group.eventsNeedApproval
                         ? "Un événement créé pour le groupe par un membre attend ton accord (ou celui d’un admin du groupe) avant que le groupe le voie. Tu es prévenu et tu acceptes ou refuses dans Activité › À valider."
                         : "Un membre qui crée un événement pour le groupe le rend visible tout de suite à tout le groupe.")
                        .font(.footnote).foregroundStyle(PronoTheme.t2)
                }
                .padding(.vertical, 4)
            }
            VStack(alignment: .leading, spacing: 8) {
                Text("Notifications des événements").font(.subheadline.weight(.semibold))
                Picker("Notifications", selection: Binding(get: { page.group.announceMode }, set: { mode in
                    Haptics.selection()
                    save(page.group.eventsNeedApproval, mode)
                })) {
                    Text("Sur demande").tag("request")
                    Text("Libres").tag("free")
                }
                .pickerStyle(.segmented)
                Text(page.group.announceMode == "request"
                     ? "« Prévenir le groupe » d’un membre devient une demande : toi, les admins et les organisateurs du groupe l’acceptez ou la refusez. Sans réponse sous 48 h, l’annonce part automatiquement."
                     : "Chaque membre décide lui-même de prévenir le groupe quand il publie un événement.")
                    .font(.footnote).foregroundStyle(PronoTheme.t2)
                Text("Les admins et organisateurs du groupe préviennent toujours le groupe sans demande.")
                    .font(.caption).foregroundStyle(PronoTheme.t3)
            }
            .padding(.vertical, 4)
        } header: {
            Text("Règles du groupe")
        }
        .listRowBackground(ConvNeon.surface)
    }
}

/// « Autres liens d'invitation » (comme InviteLinkCard.tsx, groupe) : lien unique (une personne, une fois, 7 jours ;
/// ceux créés, Annuler) ou lien réutilisable (renouvelable : l'ancien ne marche plus).
struct GroupLinksSection: View {
    let groupID: String

    @Environment(\.people) private var people
    @State private var reusable = false
    @State private var fresh: GroupLinkURL?
    @State private var shared: GroupLinkURL?
    @State private var links: [GroupLinkRow] = []
    @State private var busy = false
    @State private var error: String?
    @State private var confirmRenew = false

    var body: some View {
        Section {
            Picker("Type de lien", selection: $reusable) {
                Text("Lien unique").tag(false)
                Text("Réutilisable").tag(true)
            }
            .pickerStyle(.segmented)
            if reusable {
                Text("Lien réutilisable : il marche pour tout le monde, jusqu’à ce que tu le renouvelles. Pratique pour une conversation de groupe ; chacun s’inscrit, complète son profil puis rejoint le groupe. Tu es prévenu à chaque arrivée.")
                    .font(.footnote).foregroundStyle(PronoTheme.t2)
                if let shared {
                    linkActions(shared)
                    Button("Nouveau lien", role: .destructive) { confirmRenew = true }.frame(minHeight: 44)
                } else {
                    Button("Afficher le lien réutilisable") { Task { await loadShared(renew: false) } }.frame(minHeight: 44).disabled(busy)
                }
            } else {
                VStack(alignment: .leading, spacing: 4) {
                    Text("🔒 Lien unique").font(.subheadline.weight(.bold))
                    Text("Il ne marche qu’une fois, pour une seule personne, pendant 7 jours. Crée un lien pour chaque personne que tu invites. Elle s’inscrit avec son numéro, complète son profil, puis rejoint ce groupe. Tu es prévenu à son arrivée.")
                        .font(.footnote).foregroundStyle(PronoTheme.t2)
                }
                if let fresh { linkActions(fresh) }
                Button(fresh == nil ? "Créer un lien unique" : "Créer un autre lien unique") { Task { await createSingle() } }
                    .frame(minHeight: 44).disabled(busy)
                    .accessibilityIdentifier("group-links-single")
                ForEach(links) { l in
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(GroupText.linkStatus(l)).font(.subheadline)
                            Text("Créé le \(GroupText.shortDate(l.createdAt))"
                                 + (l.status == "pending" ? " · expire le \(GroupText.shortDate(l.expiresAt))" : ""))
                                .font(.caption).foregroundStyle(PronoTheme.t2)
                        }
                        Spacer()
                        if l.status == "pending" {
                            Button("Annuler", role: .destructive) { Task { await revoke(l) } }
                                .buttonStyle(.borderless).frame(minHeight: 44)
                                .accessibilityLabel("Annuler ce lien")
                        }
                    }
                }
            }
            if let error { Text(error).font(.footnote).foregroundStyle(PronoTheme.pinkInk) }
        } header: {
            Text("Autres liens d’invitation")
        }
        .listRowBackground(ConvNeon.surface)
        .task { await loadLinks() }
        .confirmationDialog("L’ancien lien ne marchera plus.", isPresented: $confirmRenew, titleVisibility: .visible) {
            Button("Créer un nouveau lien", role: .destructive) { Task { await loadShared(renew: true) } }
        }
    }

    private func linkActions(_ link: GroupLinkURL) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(link.url).font(.footnote.monospaced().weight(.semibold)).textSelection(.enabled).lineLimit(2)
            HStack {
                Button {
                    UIPasteboard.general.string = link.url
                    Haptics.success()
                } label: { Label("Copier", systemImage: "doc.on.doc").frame(maxWidth: .infinity, minHeight: 44) }
                .buttonStyle(.bordered)
                ShareLink(item: link.url) { Label("Partager", systemImage: "square.and.arrow.up").frame(maxWidth: .infinity, minHeight: 44) }
                    .buttonStyle(.bordered)
            }
            .tint(PronoTheme.lav)
        }
    }

    private func loadLinks() async {
        guard let people else { return }
        links = (try? await GroupsAPI(people: people).links(groupID)) ?? links
    }

    private func createSingle() async {
        guard let people else { return }
        busy = true
        defer { busy = false }
        do {
            fresh = try await GroupsAPI(people: people).singleLink(groupID)
            error = nil
            Haptics.success()
            await loadLinks()
        } catch {
            self.error = PeopleStore.message(error)
        }
    }

    private func loadShared(renew: Bool) async {
        guard let people else { return }
        busy = true
        defer { busy = false }
        do {
            shared = try await GroupsAPI(people: people).link(groupID, renew: renew)
            error = nil
        } catch {
            self.error = "Le lien n’a pas pu être créé. Réessaie."
        }
    }

    private func revoke(_ link: GroupLinkRow) async {
        guard let people else { return }
        do {
            try await GroupsAPI(people: people).revoke(link.token)
            if fresh?.token == link.token { fresh = nil }
        } catch {
            self.error = "Le lien n’a pas pu être annulé."
        }
        await loadLinks()
    }
}

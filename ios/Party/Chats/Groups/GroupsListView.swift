import SwiftUI

/// Réglages › Groupes en natif (comme web/events/src/app/groups.tsx) : invitations reçues (Rejoindre / Refuser), mes
/// groupes façon WhatsApp (dernier message, non lus, prochain événement), « Nouveau groupe », recherche ; les Admins du
/// site voient aussi les autres groupes, dans une section repliée. Chaque groupe s'ouvre sur sa page native.
struct GroupsListView: View {
    @Environment(\.people) private var people
    @State private var home: GroupsHome?
    @State private var error: String?
    @State private var query = ""
    @State private var showOthers = false
    @State private var busy = false
    @State private var path: GroupScreen?

    var body: some View {
        List {
            if let home {
                content(home)
            } else if let error {
                Text(error).foregroundStyle(PronoTheme.t2).listRowBackground(Color.clear)
            } else {
                ProgressView().tint(PronoTheme.lav).frame(maxWidth: .infinity).padding(.top, 80).listRowBackground(Color.clear)
            }
        }
        .listStyle(.plain)
        .scrollContentBackground(.hidden)
        .background(PeopleBackground())
        .navigationTitle("Groupes")
        .navigationBarTitleDisplayMode(.large)
        .searchable(text: $query, prompt: "Chercher un groupe")
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                NavigationLink(value: GroupScreen.create) {
                    Image(systemName: "plus").font(.body.weight(.bold)).frame(width: 44, height: 44)
                }
                .accessibilityLabel("Nouveau groupe")
                .accessibilityIdentifier("groups-new")
            }
        }
        .refreshable { await load() }
        .onAppear { Task { await load() } }  // relue au retour des réglages ou d'un groupe
        .motion(Motion.smooth, value: home == nil)
    }

    @ViewBuilder private func content(_ home: GroupsHome) -> some View {
        let q = query.trimmingCharacters(in: .whitespaces)
        let groups = home.groups.filter { q.isEmpty || $0.title.localizedCaseInsensitiveContains(q) }
        if !home.invitations.isEmpty && q.isEmpty {
            Section {
                ForEach(home.invitations) { inv in invitation(inv) }
            } header: { header("Invitations reçues") }
        }
        if !home.groups.contains(where: { !$0.system }) && q.isEmpty {
            emptyHero.listRowSeparator(.hidden).listRowBackground(Color.clear)
        }
        Section {
            ForEach(groups) { g in
                NavigationLink(value: GroupScreen.page(g.id)) { GroupOverviewRow(group: g) }
                    .listRowBackground(Color.clear)
                    .accessibilityIdentifier("groups-row")
            }
            if !q.isEmpty && groups.isEmpty {
                Text("Aucun groupe ne s’appelle comme ça.").foregroundStyle(PronoTheme.t2).frame(maxWidth: .infinity)
                    .listRowBackground(Color.clear)
            }
        } header: {
            if !groups.isEmpty { header(home.groups.contains(where: { !$0.system }) || !q.isEmpty ? "Tes groupes · \(groups.count)" : "Ta communauté") }
        }
        if !home.others.isEmpty && q.isEmpty {
            Section {
                Button {
                    Haptics.selection()
                    Motion.animate(Motion.snappy) { showOthers.toggle() }
                } label: {
                    Text(showOthers ? "Masquer les autres groupes"
                         : "Voir les \(home.others.count) autre\(home.others.count > 1 ? "s" : "") groupe\(home.others.count > 1 ? "s" : "")")
                        .font(.subheadline.weight(.semibold)).foregroundStyle(PronoTheme.lav).frame(minHeight: 44)
                }
                .listRowBackground(Color.clear)
                if showOthers {
                    Text("Groupes dont tu ne fais pas partie : visibles par les Admins seulement.").font(.footnote).foregroundStyle(PronoTheme.t2)
                        .listRowBackground(Color.clear)
                    ForEach(home.others) { g in
                        NavigationLink(value: GroupScreen.page(g.id)) {
                            HStack(spacing: 12) {
                                GroupTile(emoji: g.emoji, color: g.color, photo: g.photo, system: g.system, size: 40)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(GroupText.name(g.name, system: g.system)).font(.body.weight(.bold)).foregroundStyle(PronoTheme.t1)
                                    Text(GroupText.members(g.members)).font(.footnote).foregroundStyle(PronoTheme.t2)
                                }
                            }
                            .frame(minHeight: 52)
                        }
                        .listRowBackground(Color.clear)
                        .accessibilityLabel("Groupe \(GroupText.name(g.name, system: g.system)) (admin)")
                    }
                }
            } header: { header("Tous les groupes (admin)") }
        }
    }

    private func header(_ text: String) -> some View {
        Text(text.uppercased()).font(.footnote.weight(.bold)).tracking(1.2).foregroundStyle(PronoTheme.t2)
    }

    private func invitation(_ inv: GroupInvitationRow) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 12) {
                GroupTile(emoji: inv.emoji ?? "👯", color: inv.color, size: 46)
                VStack(alignment: .leading, spacing: 2) {
                    Text(inv.group).font(.headline).foregroundStyle(PronoTheme.t1)
                    Text("\(inv.invitedBy ?? "Quelqu’un") t’invite dans ce groupe").font(.footnote).foregroundStyle(PronoTheme.t2)
                }
            }
            HStack(spacing: 8) {
                PeoplePinkButton(title: "Rejoindre", busy: busy) { answer(inv, accept: true) }
                PeopleGhostButton(title: "Refuser") { answer(inv, accept: false) }.disabled(busy)
            }
        }
        .padding(14)
        .background(PronoTheme.pink.opacity(0.12), in: RoundedRectangle(cornerRadius: PronoTheme.Radius.card, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: PronoTheme.Radius.card, style: .continuous).strokeBorder(PronoTheme.pink.opacity(0.35), lineWidth: 1))
        .listRowBackground(Color.clear)
        .listRowSeparator(.hidden)
        .buttonStyle(.borderless)
    }

    /// Aucun groupe à moi : la grande carte qui donne envie d'en créer un.
    private var emptyHero: some View {
        VStack(spacing: 12) {
            HStack(spacing: -10) {
                ForEach(["🎉", "🪩", "🍕"], id: \.self) { e in
                    GroupTile(emoji: e, color: ["🎉": "pink", "🪩": "lavender", "🍕": "coral"][e], size: 54)
                }
            }
            Text("Crée le groupe de ta bande").font(.system(.title2, design: .rounded).weight(.heavy)).foregroundStyle(PronoTheme.t1)
            Text("Tes soirées et ta discussion au même endroit. Invite avec un lien ou un code QR.")
                .font(.subheadline).foregroundStyle(PronoTheme.t2).multilineTextAlignment(.center)
            NavigationLink(value: GroupScreen.create) {
                Label("Nouveau groupe", systemImage: "plus").font(.headline).foregroundStyle(PeopleNeon.pinkInk)
                    .frame(maxWidth: .infinity, minHeight: 52)
                    .background(LinearGradient(colors: [PeopleNeon.pinkTop, PronoTheme.pink], startPoint: .top, endPoint: .bottom),
                                in: RoundedRectangle(cornerRadius: PronoTheme.Radius.button, style: .continuous))
            }
            .buttonStyle(PronoKitPressStyle())
        }
        .padding(20)
        .background(PronoTheme.s1, in: RoundedRectangle(cornerRadius: PronoTheme.Radius.card, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: PronoTheme.Radius.card, style: .continuous).strokeBorder(PronoTheme.line2, lineWidth: 1))
    }

    private func load() async {
        guard let people else { error = "Connecte-toi à Party pour voir tes groupes."; return }
        do {
            home = try await GroupsAPI(people: people).home()
            error = nil
        } catch {
            if home == nil { self.error = PeopleStore.message(error) }
        }
    }

    private func answer(_ inv: GroupInvitationRow, accept: Bool) {
        guard let people, !busy else { return }
        busy = true
        Haptics.tap()
        Task {
            defer { busy = false }
            do {
                try await GroupsAPI(people: people).answer(inv.id, accept: accept)
                Haptics.success()
                await load()
            } catch {
                self.error = PeopleStore.message(error)
            }
        }
    }
}

/// Ligne d'un groupe (façon WhatsApp) : tuile, nom, dernier message ou prochain événement, heure, non lus.
struct GroupOverviewRow: View {
    let group: GroupOverview

    private var line: String {
        if let last = group.last { return [group.lastBy, last].compactMap { $0 }.joined(separator: " : ") }
        if let next = group.nextEvent { return "📅 \(next.title)" }
        return group.system ? "Toute la communauté" : GroupText.members(group.members)
    }

    var body: some View {
        HStack(spacing: 12) {
            GroupTile(emoji: group.emoji, color: group.color, photo: group.photo, system: group.system, size: 52)
            VStack(alignment: .leading, spacing: 3) {
                HStack {
                    Text(group.title).font(.body.weight(.bold)).foregroundStyle(PronoTheme.t1).lineLimit(1)
                    Spacer(minLength: 6)
                    if let at = ChatDates.parse(group.lastAt) {
                        Text(at, format: .dateTime.hour().minute().locale(.party)).font(.caption).foregroundStyle(group.unread > 0 ? PronoTheme.pinkInk : PronoTheme.t3)
                    }
                }
                HStack {
                    Text(line).font(.subheadline).foregroundStyle(PronoTheme.t2).lineLimit(1)
                    Spacer(minLength: 6)
                    if group.unread > 0 {
                        Text("\(group.unread)").font(.caption.weight(.heavy)).monospacedDigit().foregroundStyle(PeopleNeon.pinkInk)
                            .padding(.horizontal, 7).frame(minWidth: 22, minHeight: 22).background(PronoTheme.pink, in: Capsule())
                    }
                }
                if let next = group.nextEvent, group.last != nil {
                    Text("📅 \(next.title)").font(.caption).foregroundStyle(PronoTheme.amberInk).lineLimit(1)
                }
            }
        }
        .frame(minHeight: 60)
        .accessibilityElement(children: .combine)
        .accessibilityLabel(group.unread > 0 ? "\(group.title), \(group.unread) non lus" : group.title)
    }
}

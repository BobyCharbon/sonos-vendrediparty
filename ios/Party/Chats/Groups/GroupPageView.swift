import SwiftUI

/// Page d'un groupe en natif (maquette A « Néon & couvertures », comme web/events/src/app/group/[id]/index.tsx) :
/// couverture (dégradé de sa couleur + son emoji, ou sa photo ; Membres Vendredi Party : le logo officiel), membres,
/// « Créer un événement pour le groupe » (formulaire web, groupe coché), « Inviter », « Discussion », « Pronos et
/// classement », prochains événements (seulement ceux que je peux voir), membres ; ⚙ ouvre ses réglages.
struct GroupPageView: View {
    let groupID: String
    var onGone: () -> Void = {}

    @Environment(\.people) private var people
    @Environment(\.groupHub) private var hub
    @Environment(\.chatsRoutes) private var routes
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var page: GroupPage?
    @State private var error: String?
    @State private var allMembers = false
    @State private var showPast = false
    @State private var person: PersonRef?
    @State private var reporting: ReportTarget?

    static let membersShown = 12

    var body: some View {
        ScrollView {
            if let page {
                content(page).transition(.opacity)
            } else if let error {
                VStack(spacing: 12) {
                    Text("Groupe introuvable").font(.title2.weight(.heavy)).foregroundStyle(PronoTheme.t1)
                    Text(error).foregroundStyle(PronoTheme.t2).multilineTextAlignment(.center)
                }
                .padding(32)
                .frame(maxWidth: .infinity)
                .padding(.top, 80)
            } else {
                ProgressView().tint(PronoTheme.lav).frame(maxWidth: .infinity).padding(.top, 160)
            }
        }
        .background(PeopleBackground(tint: GroupLook.gradient(page?.group.color).to))
        .ignoresSafeArea(edges: .top)
        .navigationTitle(page?.group.title ?? "Groupe")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(.hidden, for: .navigationBar)
        .toolbar {
            ToolbarItem(placement: .principal) { Text("") }
            ToolbarItem(placement: .navigationBarTrailing) {
                if let page, page.showsSettings {
                    NavigationLink(value: GroupScreen.settings(groupID)) {
                        Image(systemName: "gearshape.fill").font(.body.weight(.semibold))
                            .frame(width: 44, height: 44)
                    }
                    .accessibilityLabel("Réglages du groupe")
                    .accessibilityIdentifier("group-settings")
                }
            }
        }
        .refreshable { await load() }
        .onAppear { Task { await load() } }  // relue au retour des réglages ou d'un groupe
        .motion(Motion.smooth, value: page == nil)
        .sheet(item: $person) { p in routes.miniProfile?(p.id) }
        .sheet(item: $reporting) { target in
            if let people { ReportSheet(store: people.moderation, target: target) }
        }
    }

    private func load() async {
        guard let people else { error = "Connecte-toi à Party pour voir tes groupes."; return }
        do {
            let fresh = try await GroupsAPI(people: people).page(groupID)
            page = fresh
            error = nil
        } catch {
            if page == nil { self.error = PeopleStore.message(error) }
        }
    }

    // MARK: Contenu

    @ViewBuilder private func content(_ page: GroupPage) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            GroupCover(group: page.group)
            VStack(alignment: .leading, spacing: 14) {
                GroupTile(emoji: page.group.emoji, color: page.group.color, photo: page.group.photo, system: page.group.system, size: 88)
                    .padding(4)
                    .background(PronoTheme.bg, in: RoundedRectangle(cornerRadius: 30, style: .continuous))
                    .padding(.top, -64)
                Text(page.group.title)
                    .font(.system(.largeTitle, design: .rounded).weight(.heavy))
                    .foregroundStyle(PronoTheme.t1)
                    .accessibilityAddTraits(.isHeader)
                    .accessibilityIdentifier("group-page-name")
                HStack(spacing: 10) {
                    let faces = page.members.filter { !$0.me }.prefix(5).map(\.face)
                    if !faces.isEmpty { PronoAvatarStack(faces: Array(faces), size: 28, ring: PronoTheme.bg, max: 5) }
                    Text(GroupText.subtitle(page)).font(.subheadline).foregroundStyle(PronoTheme.t2)
                }
                .accessibilityElement(children: .combine)
                actions(page)
                events(page)
                members(page)
                footer(page)
            }
            .padding(.horizontal, PronoTheme.Space.screen)
            .padding(.bottom, 40)
        }
    }

    @ViewBuilder private func actions(_ page: GroupPage) -> some View {
        if page.canCreateEvent {
            PeoplePinkButton(title: "Créer un événement pour le groupe", systemImage: "calendar.badge.plus") {
                Haptics.tap()
                guard let hub else { return }
                hub.leave { hub.createEvent(groupID) }
            }
            .accessibilityIdentifier("group-create-event")
        }
        let discussion = page.member && hub != nil
        if page.showsInvite || discussion {
            HStack(spacing: 10) {
                if page.showsInvite {
                    NavigationLink(value: GroupScreen.invite(groupID)) {
                        GroupActionLabel(title: "Inviter", systemImage: "hand.wave.fill")
                    }
                    .buttonStyle(PronoKitPressStyle())
                    .accessibilityIdentifier("group-invite")
                }
                if discussion {
                    Button {
                        Haptics.tap()
                        guard let hub else { return }
                        hub.leave { hub.openChat(groupID) }
                    } label: {
                        GroupActionLabel(title: "Discussion", systemImage: "bubble.left.and.bubble.right.fill", badge: page.unread)
                    }
                    .buttonStyle(PronoKitPressStyle())
                    .accessibilityLabel(page.unread > 0 ? "Discussion, \(page.unread) non lus" : "Discussion")
                    .accessibilityIdentifier("group-chat")
                }
            }
        }
        if page.showsPronos, hub?.pronos != nil {
            NavigationLink(value: GroupScreen.pronos(groupID)) {
                GroupActionLabel(title: "Pronos et classement", systemImage: "sparkles")
            }
            .buttonStyle(PronoKitPressStyle())
            .accessibilityIdentifier("group-pronos")
        }
    }

    @ViewBuilder private func events(_ page: GroupPage) -> some View {
        HStack {
            PeopleSectionLabel(text: "Prochains événements", systemImage: "calendar")
            if !page.upcoming.isEmpty {
                Text("\(page.upcoming.count)").font(.footnote.weight(.bold)).foregroundStyle(GroupLook.gradient(page.group.color).from)
            }
        }
        .padding(.top, 10)
        if page.upcoming.isEmpty {
            VStack(spacing: 6) {
                Text(page.group.emoji).font(.system(size: 30))
                Text("Aucun événement prévu").font(.headline).foregroundStyle(PronoTheme.t1)
                Text(page.canCreateEvent ? "Lance la prochaine : le groupe sera déjà coché, tu choisis ensuite de le prévenir."
                     : "Les événements du groupe apparaîtront ici.")
                    .font(.footnote).foregroundStyle(PronoTheme.t2).multilineTextAlignment(.center)
            }
            .frame(maxWidth: .infinity)
            .padding(20)
            .background(PronoTheme.s1, in: RoundedRectangle(cornerRadius: PronoTheme.Radius.card, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: PronoTheme.Radius.card, style: .continuous)
                .strokeBorder(GroupLook.gradient(page.group.color).to.opacity(0.4), style: StrokeStyle(lineWidth: 1, dash: [6, 4])))
            .accessibilityElement(children: .combine)
        } else {
            ForEach(page.upcoming) { card in eventRow(card, past: false) }
        }
        if !page.past.isEmpty {
            Button {
                Haptics.selection()
                Motion.animate(Motion.snappy) { showPast.toggle() }
            } label: {
                Text(showPast ? "Masquer les événements passés"
                     : page.past.count == 1 ? "Voir 1 événement passé" : "Voir \(page.past.count) événements passés")
                    .font(.subheadline.weight(.semibold)).foregroundStyle(PronoTheme.lav).frame(maxWidth: .infinity, minHeight: 44)
            }
            if showPast { ForEach(page.past) { card in eventRow(card, past: true) } }
        }
    }

    private func eventRow(_ card: ChatEventCard, past: Bool) -> some View {
        Button {
            Haptics.tap()
            guard let hub else { return }
            hub.leave { hub.openEvent(card.id) }
        } label: {
            HStack(spacing: 12) {
                PeopleDateTile(start: card.start, past: past)
                VStack(alignment: .leading, spacing: 2) {
                    Text(card.title).font(.headline).foregroundStyle(PronoTheme.t1).lineLimit(2).multilineTextAlignment(.leading)
                    let line = [card.date.map(EventCardBubble.hour), card.place].compactMap { $0 }.joined(separator: " · ")
                    if !line.isEmpty { Text(line).font(.subheadline).foregroundStyle(PronoTheme.t2).lineLimit(1) }
                    if let going = card.going, going > 0 {
                        Text(going == 1 ? "1 présent" : "\(going) présents").font(.footnote).foregroundStyle(PronoTheme.t3)
                    }
                }
                Spacer(minLength: 0)
                Image(systemName: "chevron.right").font(.footnote.weight(.bold)).foregroundStyle(PronoTheme.t3)
            }
            .padding(12)
            .frame(minHeight: 44)
            .background(PronoTheme.s1, in: RoundedRectangle(cornerRadius: PronoTheme.Radius.inner, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: PronoTheme.Radius.inner, style: .continuous).strokeBorder(PronoTheme.line, lineWidth: 1))
        }
        .buttonStyle(PronoKitPressStyle())
        .accessibilityLabel("\(card.title), \(PeopleDate.spoken(card.start) ?? "date à définir")")
        .accessibilityHint("Ouvre la fiche de l'événement")
    }

    @ViewBuilder private func members(_ page: GroupPage) -> some View {
        PeopleSectionLabel(text: "Membres · \(page.members.count)", systemImage: "person.2.fill").padding(.top, 10)
        let shown = allMembers ? page.members : Array(page.members.prefix(Self.membersShown))
        VStack(spacing: 0) {
            ForEach(Array(shown.enumerated()), id: \.element.id) { i, m in
                Button {
                    Haptics.selection()
                    if routes.miniProfile != nil { person = PersonRef(id: m.id) }
                } label: {
                    HStack(spacing: 12) {
                        PronoAvatar(face: m.face, size: 40)
                        PersonName(id: m.id, pseudo: m.me ? "\(m.name) (toi)" : m.name, pseudoFont: .footnote)
                            .font(.body.weight(.semibold)).foregroundStyle(PronoTheme.t1).lineLimit(1)
                        Spacer(minLength: 8)
                        if m.creator {
                            Text("Créateur").font(.footnote.weight(.bold)).foregroundStyle(GroupLook.gradient(page.group.color).from)
                        }
                    }
                    .padding(.horizontal, 12)
                    .frame(minHeight: 58)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel(m.creator ? "\(m.name), créateur du groupe" : m.name)
                .accessibilityHint(routes.miniProfile != nil ? "Ouvre son profil" : "")
                if i < shown.count - 1 { Divider().overlay(PronoTheme.line).padding(.leading, 64) }
            }
        }
        .background(PronoTheme.s1, in: RoundedRectangle(cornerRadius: PronoTheme.Radius.card, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: PronoTheme.Radius.card, style: .continuous).strokeBorder(PronoTheme.line, lineWidth: 1))
        if page.members.count > Self.membersShown {
            Button {
                Haptics.selection()
                Motion.animate(Motion.snappy) { allMembers.toggle() }
            } label: {
                Text(allMembers ? "Moins de membres" : "Voir les \(page.members.count) membres")
                    .font(.subheadline.weight(.semibold)).foregroundStyle(PronoTheme.lav).frame(maxWidth: .infinity, minHeight: 44)
            }
        }
    }

    @ViewBuilder private func footer(_ page: GroupPage) -> some View {
        if let line = GroupText.createdLine(page.group.createdAt) {
            Text(line).font(.footnote).foregroundStyle(PronoTheme.t3).frame(maxWidth: .infinity).padding(.top, 8)
        }
        if page.canReportPhoto {
            Button {
                reporting = ReportTarget(kind: .groupPhoto, id: page.group.id, label: "la photo du groupe")
            } label: {
                Label("Signaler la photo du groupe", systemImage: "flag").font(.subheadline).foregroundStyle(PronoTheme.t2)
                    .frame(maxWidth: .infinity, minHeight: 44)
            }
            .accessibilityIdentifier("group-report-photo")
        }
    }
}

/// Couverture : sa photo plein cadre fondue dans la nuit, ou le dégradé de sa couleur avec son emoji en motif.
struct GroupCover: View {
    let group: GroupPage.Info
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var float = false

    var body: some View {
        let g = GroupLook.gradient(group.color)
        ZStack {
            LinearGradient(colors: [g.to, g.to.opacity(0.6), PronoTheme.bg], startPoint: .top, endPoint: .bottom)
            RadialGradient(colors: [g.from.opacity(0.8), .clear], center: UnitPoint(x: 0.2, y: 0), startRadius: 0, endRadius: 280)
            if let photo = group.photo.flatMap(URL.init(string:)), !group.system {
                AsyncImage(url: photo) { phase in
                    if let image = phase.image { image.resizable().scaledToFill() } else { Color.clear }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .clipped()
                .accessibilityLabel("Photo du groupe \(group.name)")
                LinearGradient(colors: [PronoTheme.bg.opacity(0.35), .clear, PronoTheme.bg.opacity(0.55), PronoTheme.bg],
                               startPoint: .top, endPoint: .bottom)
            } else {
                GeometryReader { geo in
                    ForEach(Array(Self.spots.enumerated()), id: \.offset) { i, spot in
                        Text(group.emoji).font(.system(size: spot.size)).opacity(spot.opacity)
                            .position(x: geo.size.width * spot.x, y: geo.size.height * spot.y + (float && !reduceMotion ? -6 : 6) * (i.isMultiple(of: 2) ? 1 : -1))
                    }
                }
                .accessibilityHidden(true)
            }
        }
        .frame(height: 236)
        .clipped()
        .onAppear {
            guard !reduceMotion else { return }
            withAnimation(.easeInOut(duration: 3.2).repeatForever(autoreverses: true)) { float = true }
        }
    }

    private static let spots: [(x: CGFloat, y: CGFloat, size: CGFloat, opacity: Double)] = [
        (0.38, 0.32, 22, 0.22), (0.68, 0.45, 26, 0.2), (0.22, 0.62, 20, 0.18), (0.86, 0.7, 24, 0.2),
    ]
}

/// Bouton secondaire de la page (verre sombre, 50 pt), avec pastille de non-lus.
struct GroupActionLabel: View {
    let title: String
    let systemImage: String
    var badge = 0

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: systemImage).foregroundStyle(PronoTheme.lav)
            Text(title).font(.headline).foregroundStyle(PronoTheme.t1).lineLimit(1).minimumScaleFactor(0.8)
            if badge > 0 {
                Text("\(badge)").font(.caption.weight(.heavy)).monospacedDigit().foregroundStyle(PeopleNeon.pinkInk)
                    .padding(.horizontal, 7).frame(minWidth: 22, minHeight: 22)
                    .background(PronoTheme.pink, in: Capsule())
            }
        }
        .frame(maxWidth: .infinity, minHeight: 50)
        .padding(.horizontal, 12)
        .background(PronoTheme.s1b, in: RoundedRectangle(cornerRadius: PronoTheme.Radius.button, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: PronoTheme.Radius.button, style: .continuous).strokeBorder(PronoTheme.line2, lineWidth: 1))
    }
}

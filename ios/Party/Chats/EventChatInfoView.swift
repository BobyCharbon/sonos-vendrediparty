import SwiftUI

/// Infos de la discussion d'un événement, façon « Infos du groupe » de WhatsApp : grande couverture, titre, date et lieu,
/// description, notifications (Mentions seulement par défaut) et sourdine, médias / liens / vocaux, messages épinglés,
/// recherche, participants par réponse, réglages de l'organisation (qui peut écrire, description).
/// Les invités sans réponse n'apparaissent que pour l'organisation (règle du 11.11 : un invité ne voit pas les noms).
/// Toucher un participant : sa fiche, Signaler, Bloquer (modération commune de l'app).
struct EventChatInfoView: View {
    @ObservedObject var store: ChatsStore
    @ObservedObject private var contacts = ContactNames.shared
    @Environment(\.dismiss) private var dismiss
    /// Mini-profil de Discussions v2 (route de l'app) ; absent : la fiche native du membre.
    @Environment(\.conversationRoutes) private var routes
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    enum Route: Hashable { case notifications, media, pinned, search, settings }

    @State private var path: [Route] = []
    @State private var previews: [ChatMediaItem] = []
    @State private var chosen: Conversation.Member?
    @State private var profile: PersonRef?
    @State private var blocking: Conversation.Member?
    @State private var reporting: ReportTarget?
    @State private var notice: String?
    @State private var appeared = false

    private struct Bucket: Identifiable {
        let id: String
        let title: String
        let people: [Conversation.Member]
    }

    private func buckets(_ chat: Conversation) -> [Bucket] {
        let organizers = chat.members.filter { $0.organizer == true }
        let rest = chat.members.filter { $0.organizer != true }
        return [
            Bucket(id: "orga", title: "Organisation", people: organizers),
            Bucket(id: "yes", title: "Présents", people: rest.filter { $0.rsvp == "yes" }),
            Bucket(id: "maybe", title: "Peut-être", people: rest.filter { $0.rsvp == "maybe" }),
            Bucket(id: "no", title: "Pas présents", people: rest.filter { $0.rsvp == "no" }),
            // Le serveur ne les envoie qu'à l'organisation ; gardé ici aussi par prudence.
            Bucket(id: "invited", title: "Invités sans réponse",
                   people: chat.isStaff ? rest.filter { $0.rsvp == nil && $0.invited == true } : []),
            Bucket(id: "other", title: "Autres personnes de la discussion", people: rest.filter { $0.rsvp == nil && $0.invited != true }),
        ].filter { !$0.people.isEmpty }
    }

    private var accent: Color { Color(uiColor: AppConfig.uiAccent) }

    var body: some View {
        NavigationStack(path: $path) {
            List {
                if let chat = store.conversation {
                    header(chat)
                    about(chat)
                    notifications(chat)
                    content(chat)
                    if chat.isStaff { staff(chat) }
                    ForEach(buckets(chat)) { bucket in
                        Section {
                            ForEach(bucket.people) { person in participant(person, chat: chat) }
                        } header: {
                            Text("\(bucket.title) · \(bucket.people.count)")
                        }
                        .listRowBackground(ConvNeon.surface)
                    }
                } else if let error = store.error {
                    Text(error).foregroundStyle(.secondary)
                } else {
                    ProgressView().frame(maxWidth: .infinity).listRowBackground(Color.clear)
                }
            }
            .listStyle(.insetGrouped)
            // Néon club (Discussions v2) : fond de nuit, accents lavande, lignes sur surface.
            .convNeonForm()
            .motion(Motion.smooth, value: store.conversation?.description)
            .motion(Motion.smooth, value: store.isMuted)
            .motion(Motion.snappy, value: store.conversation?.members)
            .motion(Motion.smooth, value: previews.map(\.url))
            .navigationTitle("Infos de la discussion")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("OK") { dismiss() } } }
            .navigationDestination(for: Route.self) { route in
                switch route {
                case .notifications: EventChatNotificationsView(store: store)
                case .media: EventChatMediaView(store: store, onJump: jump)
                case .pinned: EventChatPinnedView(store: store, onJump: jump)
                case .search: EventChatSearchView(store: store, onPick: jump)
                case .settings: EventChatSettingsView(store: store)
                }
            }
            .overlay(alignment: .bottom) {
                if let notice {
                    Text(notice).font(.subheadline.weight(.medium)).padding(.horizontal, 16).padding(.vertical, 10)
                        .background(.ultraThinMaterial, in: Capsule()).padding(.bottom, 12)
                        .motionTransition(.banner)
                        .task {
                            try? await Task.sleep(for: .seconds(3))
                            Motion.animate { self.notice = nil }
                        }
                }
            }
            .confirmationDialog(chosen?.name ?? "", isPresented: Binding(get: { chosen != nil }, set: { if !$0 { chosen = nil } }),
                                titleVisibility: .visible, presenting: chosen) { person in
                Button(routes.miniProfile == nil ? "Voir la fiche" : "Voir le profil") { profile = PersonRef(id: person.id) }
                Button("Signaler \(person.name)") {
                    reporting = ReportTarget(kind: .profile, id: person.id, label: person.name)
                }
                if isBlocked(person) {
                    Button("Débloquer \(person.name)") { Task { await block(person, false) } }
                } else {
                    Button("Bloquer \(person.name)", role: .destructive) { blocking = person }
                }
            }
            .alert("Bloquer \(blocking?.name ?? "") ?", isPresented: Binding(get: { blocking != nil }, set: { if !$0 { blocking = nil } }),
                   presenting: blocking) { person in
                Button("Bloquer", role: .destructive) { Task { await block(person, true) } }
                Button("Annuler", role: .cancel) {}
            } message: { _ in
                Text("Ses messages disparaissent pour toi et la modération est prévenue. Elle ne pourra plus t'écrire, te citer ni t'inviter ; elle n'en est pas prévenue. Tu peux la débloquer dans Réglages › Personnes bloquées.")
            }
            .personSheet($profile, store: store, routes: routes)
            .sheet(item: $reporting) { ReportSheet(store: store.moderation, target: $0) }
            .task {
                async let blocked: Void = store.moderation.loadBlocked()
                let media = await store.media()
                previews = Array(media.filter { $0.kind == "photo" }.prefix(8))
                await blocked
            }
        }
        .presentationDragIndicator(.visible)
        .preferredColorScheme(.dark)
    }

    /// Résultat de recherche, épinglé, média : montré dans la discussion, la feuille se ferme.
    private func jump(_ id: String) {
        store.jumpTo = id
        dismiss()
    }

    // MARK: En-tête

    @ViewBuilder private func header(_ chat: Conversation) -> some View {
        let card = chat.eventCard
        Section {
            VStack(spacing: 10) {
                cover(card?.cover, title: card?.title ?? chat.name)
                    .scaleEffect(appeared || reduceMotion ? 1 : 0.85)
                    .opacity(appeared ? 1 : 0)
                    .onAppear { Motion.animate(Motion.bouncy) { appeared = true } }
                Text(card?.title ?? chat.name).font(.title2.weight(.bold)).multilineTextAlignment(.center)
                    .accessibilityAddTraits(.isHeader)
                if let when = Self.when(card) {
                    Label(when, systemImage: "calendar").font(.subheadline).foregroundStyle(.secondary)
                }
                if let place = card?.place, !place.isEmpty {
                    Label(place, systemImage: "mappin.and.ellipse").font(.subheadline).foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                }
                Text(Self.people(chat)).font(.footnote.weight(.medium)).foregroundStyle(.secondary)
                HStack(spacing: 10) {
                    quickAction(store.isMuted ? "Sourdine" : "Notifications",
                                icon: store.isMuted ? "bell.slash.fill" : "bell.fill", route: .notifications)
                    quickAction("Rechercher", icon: "magnifyingglass", route: .search)
                    quickAction("Médias", icon: "photo.on.rectangle", route: .media)
                }
                .padding(.top, 6)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 4)
            .listRowBackground(Color.clear)
            .listRowInsets(EdgeInsets(top: 8, leading: 0, bottom: 8, trailing: 0))
        }
    }

    private func cover(_ url: String?, title: String) -> some View {
        ZStack {
            LinearGradient(colors: [accent, Color(red: 0.45, green: 0.3, blue: 0.95)], startPoint: .topLeading, endPoint: .bottomTrailing)
            Text("🎉").font(.system(size: 52))
            if let url = url.flatMap(URL.init(string:)) {
                AsyncImage(url: url, transaction: Transaction(animation: Motion.pick(Motion.fade))) { phase in
                    if let image = phase.image { image.resizable().scaledToFill().transition(.opacity) }
                }
            }
        }
        .frame(width: 120, height: 120)
        .clipShape(Circle())
        .overlay(Circle().stroke(Color.white.opacity(0.12), lineWidth: 1))
        .shadow(color: accent.opacity(0.35), radius: 18, y: 6)
        .accessibilityHidden(true)
    }

    private func quickAction(_ title: String, icon: String, route: Route) -> some View {
        Button {
            Haptics.tap()
            path.append(route)
        } label: {
            VStack(spacing: 6) {
                Image(systemName: icon).font(.title3).foregroundStyle(accent)
                Text(title).font(.caption.weight(.medium)).foregroundStyle(.primary)
            }
            .frame(maxWidth: .infinity).padding(.vertical, 12)
            .background(Color.white.opacity(0.07), in: RoundedRectangle(cornerRadius: 12))
        }
        .buttonStyle(PressableStyle())
        .accessibilityIdentifier("event-chat-quick-\(route)")
    }

    // MARK: Description

    @ViewBuilder private func about(_ chat: Conversation) -> some View {
        let text = (chat.description ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        if !text.isEmpty {
            Section {
                Text(Mentions.linked(AttributedString(text))).font(.body).fixedSize(horizontal: false, vertical: true)
                    .textSelection(.enabled)
                    .accessibilityIdentifier("event-chat-description-text")
                if chat.isStaff {
                    Button { path.append(.settings) } label: { Label("Modifier la description", systemImage: "pencil") }
                } else {
                    // Apple 1.2 : tout contenu publié se signale (la base copie la description dans le signalement).
                    Button {
                        reporting = ReportTarget(kind: .event, id: chat.id, label: "la description de la discussion")
                    } label: {
                        Label("Signaler la description", systemImage: "exclamationmark.bubble")
                    }
                    .foregroundStyle(.red)
                    .accessibilityIdentifier("event-chat-report-description")
                }
            } header: {
                Text("Description")
            }
        } else if chat.isStaff {
            Section {
                Button { path.append(.settings) } label: { Label("Ajouter une description", systemImage: "text.alignleft") }
            } footer: {
                Text("Programme, code vestimentaire, parking : visible de toute la discussion.")
            }
        }
    }

    // MARK: Notifications et sourdine

    private func notifications(_ chat: Conversation) -> some View {
        Section {
            NavigationLink(value: Route.notifications) {
                HStack {
                    Label("Notifications", systemImage: EventChatText.icon(store.effectiveLevel))
                    Spacer()
                    Text(EventChatText.title(store.effectiveLevel)).foregroundStyle(.secondary)
                }
            }
            .accessibilityIdentifier("event-chat-notify")
            Menu {
                if store.isMuted {
                    Button { Task { await store.mute(until: nil) } } label: { Label("Réactiver", systemImage: "bell") }
                } else {
                    Button("8 heures") { Task { await store.mute(until: Date().addingTimeInterval(8 * 3600)) } }
                    Button("1 semaine") { Task { await store.mute(until: Date().addingTimeInterval(7 * 24 * 3600)) } }
                    Button("Toujours") { Task { await store.mute(until: .distantFuture) } }
                }
            } label: {
                HStack {
                    Label("Sourdine", systemImage: store.isMuted ? "moon.zzz.fill" : "moon")
                        .foregroundStyle(.primary)
                    Spacer()
                    Text(store.isMuted ? (EventChatText.muteEnd(chat.mutedUntil) == nil ? "Toujours" : "Activée") : "Non")
                        .foregroundStyle(.secondary)
                    Image(systemName: "chevron.up.chevron.down").font(.caption).foregroundStyle(.tertiary)
                }
            }
            .accessibilityIdentifier("event-chat-mute")
        } header: {
            Text("Notifications")
        } footer: {
            Text(store.isMuted ? EventChatText.muteLabel(chat.mutedUntil) + "."
                 : EventChatText.title(store.effectiveLevel) + " : " + EventChatText.hint(store.effectiveLevel).lowercasedFirst)
        }
    }

    // MARK: Médias, épinglés, recherche

    private func content(_ chat: Conversation) -> some View {
        Section {
            NavigationLink(value: Route.media) {
                VStack(alignment: .leading, spacing: 10) {
                    Label("Médias, liens et vocaux", systemImage: "photo.on.rectangle.angled")
                    if !previews.isEmpty {
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 6) {
                                ForEach(previews, id: \.url) { item in
                                    AsyncImage(url: URL(string: item.url)) { phase in
                                        if let image = phase.image { image.resizable().scaledToFill() } else { Color.white.opacity(0.06) }
                                    }
                                    .frame(width: 64, height: 64).clipShape(RoundedRectangle(cornerRadius: 8))
                                    .motionTransition()
                                }
                            }
                        }
                        .allowsHitTesting(false)
                        .accessibilityHidden(true)
                    }
                }
            }
            .accessibilityIdentifier("event-chat-media")
            NavigationLink(value: Route.pinned) {
                HStack {
                    Label("Messages épinglés", systemImage: "pin")
                    Spacer()
                    let count = chat.pins.count
                    if count > 0 { Text("\(count)").foregroundStyle(.secondary) }
                }
            }
            .accessibilityIdentifier("event-chat-pinned")
            NavigationLink(value: Route.search) {
                Label("Rechercher dans la discussion", systemImage: "magnifyingglass")
            }
            .accessibilityIdentifier("event-chat-search")
        } footer: {
            if chat.writeMode == "staff" && !chat.isStaff {
                Text("Seule l'organisation écrit dans cette discussion ; tu peux lire, réagir et signaler.")
            }
        }
    }

    // MARK: Organisation

    private func staff(_ chat: Conversation) -> some View {
        Section {
            NavigationLink(value: Route.settings) {
                HStack {
                    Label("Réglages de la discussion", systemImage: "gearshape")
                    Spacer()
                    Text(chat.writeMode == "staff" ? "Organisation" : "Tout le monde").foregroundStyle(.secondary)
                }
            }
            .accessibilityIdentifier("event-chat-settings")
        } header: {
            Text("Organisation")
        } footer: {
            Text("Qui peut écrire, description, @toutlemonde, @present et annonces.")
        }
    }

    // MARK: Participants

    private func participant(_ person: Conversation.Member, chat: Conversation) -> some View {
        let me = person.id == chat.me
        return Button {
            guard !me else { return }
            Haptics.tap()
            chosen = person
        } label: {
            HStack(spacing: 12) {
                ConvFace(id: person.id, name: person.name, photo: person.photo, size: 38)
                VStack(alignment: .leading, spacing: 2) {
                    PersonName(id: person.id, pseudo: person.name).foregroundStyle(.primary)
                    if isBlocked(person) {
                        Text("Bloqué").font(.caption).foregroundStyle(.red)
                    }
                }
                Spacer()
                if me { Text("Toi").font(.caption).foregroundStyle(.secondary) }
                else if person.organizer == true { Text("Organisation").font(.caption.weight(.semibold)).foregroundStyle(accent) }
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .combine)
        .accessibilityHint(me ? "" : "Fiche, signaler ou bloquer")
    }

    private func isBlocked(_ person: Conversation.Member) -> Bool {
        store.moderation.blocked?.contains { $0.id == person.id } == true
    }

    private func block(_ person: Conversation.Member, _ on: Bool) async {
        await store.moderation.setBlocked(person.id, on)
        if let error = store.moderation.error {
            Haptics.error()
            Motion.animate { notice = error }
            return
        }
        Haptics.success()
        Motion.animate { notice = on ? "\(person.name) est bloqué·e" : "\(person.name) est débloqué·e" }
        if let id = store.conversation?.id { await store.open(id) }  // ses messages disparaissent du fil
    }

    // MARK: Textes

    /// « samedi 22 novembre · 20:00 – 23:30 ».
    static func when(_ card: Conversation.EventCard?) -> String? {
        guard let start = ChatDates.parse(card?.startsAt) else { return nil }
        let fr = Locale(identifier: "fr_CH")
        var text = start.formatted(.dateTime.weekday(.wide).day().month(.wide).locale(fr)) + " · "
            + start.formatted(.dateTime.hour().minute().locale(fr))
        if let end = ChatDates.parse(card?.endsAt) {
            text += " – " + (Calendar.current.isDate(start, inSameDayAs: end)
                ? end.formatted(.dateTime.hour().minute().locale(fr))
                : end.formatted(.dateTime.day().month(.abbreviated).hour().minute().locale(fr)))
        }
        return text
    }

    /// « 12 présents · 3 peut-être » (carte de l'événement), sinon « 15 personnes ».
    static func people(_ chat: Conversation) -> String {
        if let card = chat.eventCard, card.going != nil || card.maybe != nil {
            let going = card.going ?? 0
            var text = "\(going) présent\(going > 1 ? "s" : "")"
            if let maybe = card.maybe, maybe > 0 { text += " · \(maybe) peut-être" }
            if let organizer = card.organizerName, !organizer.isEmpty { text += " · organisé par \(organizer)" }
            return text
        }
        let count = chat.members.count
        return "\(count) personne\(count > 1 ? "s" : "") dans la discussion"
    }
}

private extension String {
    var lowercasedFirst: String { prefix(1).lowercased() + dropFirst() }
}

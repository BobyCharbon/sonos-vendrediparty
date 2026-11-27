import SwiftUI

/// Écrans des personnes (agent I2, ios/Party/Chats/People/) branchés sur la liste sans en dépendre à la compilation :
/// « Nouveau message » (NewMessageView(eventID:)) et le mini-profil (MiniProfileSheet(userID:)). nil : pas encore
/// branché (le bouton flottant et « Voir le profil » sont alors cachés).
/// Branchement, une ligne (PartyApp ou ChatsView) :
/// `.environment(\.chatsRoutes, ChatsRoutes(newMessage: { AnyView(NewMessageView(eventID: $0)) },
///                                          miniProfile: { AnyView(MiniProfileSheet(userID: $0)) }))`
struct ChatsRoutes {
    var newMessage: (@MainActor (_ eventID: String?) -> AnyView)?
    var miniProfile: (@MainActor (_ userID: String) -> AnyView)?
}

private struct ChatsRoutesKey: EnvironmentKey {
    static let defaultValue = ChatsRoutes()
}

extension EnvironmentValues {
    var chatsRoutes: ChatsRoutes {
        get { self[ChatsRoutesKey.self] }
        set { self[ChatsRoutesKey.self] = newValue }
    }
}

/// Écrans poussés depuis la liste.
enum ChatRoute: Hashable {
    /// Groupe ou message direct (ConversationView du store des Discussions).
    case chat(String)
    /// Discussion d'un événement : l'écran natif existant (store des discussions d'événement).
    case event(String)
    case requests
    case archived
}

/// Onglet « Discussions » natif, Discussions v2 « Néon club » (maquettes 1-neon) : grand titre, recherche
/// (Personnes / Discussions / Messages), filtres, épinglées en tuiles, Demandes et Archivées, lignes direct / groupe /
/// soirée, bouton flottant « Nouveau message », gestes (glisser, appui long). Données : chat_list (ChatsStore).
struct ChatsView: View {
    @ObservedObject var store: ChatsStore
    let topInset: CGFloat

    @State private var path: [ChatRoute] = []
    @State private var creating = false
    @State private var query = ""
    @State private var filter = ChatFilter.all
    @State private var collapsed = false
    @State private var topY: CGFloat?
    @State private var writing = false
    @State private var profile: ProfileTarget?
    @State private var muting: ChatSummary?
    @State private var blocking: ChatSummary?
    @State private var ordering: [ChatSummary]?
    /// Tuile épinglée dont on montre les actions (appui long).
    @State private var tileMenu: ChatSummary?
    @Environment(\.openGroupPage) private var openGroupPage
    @Environment(\.chatsRoutes) private var routes
    #if BETA || E2E_HOOKS
    @Environment(\.souvenirs) private var souvenirs
    #endif

    private struct ProfileTarget: Identifiable { let id: String }

    var body: some View {
        NavigationStack(path: $path) {
            content
                .motion(Motion.smooth, value: listPhase)
                .background(NeonGlow())
                .background(NeonNavigationBar())
                .navigationTitle("Discussions")
                .navigationBarTitleDisplayMode(.large)
                .searchable(text: $query, placement: .navigationBarDrawer(displayMode: .always), prompt: "Personnes, groupes, événements, messages")
                .toolbar {
                    ToolbarItemGroup(placement: .navigationBarTrailing) {
                        ChatsMoonMenu(store: store.pause)
                        moreMenu
                    }
                }
                .navigationDestination(for: ChatRoute.self) { route in
                    switch route {
                    case .chat(let id): ConversationView(store: store, group: id)
                    case .event(let id): ConversationView(store: store.events, group: id)
                    case .requests: ChatRequestsView(store: store)
                    case .archived:
                        ChatArchivedView(store: store, open: open, askMute: { muting = $0 }, askBlock: { blocking = $0 },
                                         showProfile: showProfile)
                    }
                }
                .overlay(alignment: .bottomTrailing) { fab }
                .overlay(alignment: .bottom) { noticeBanner }
                .sheet(isPresented: $creating) { NewGroupSheet(store: store) }
                .sheet(isPresented: $writing) { routes.newMessage?(nil) }
                .sheet(item: $profile) { target in routes.miniProfile?(target.id) }
                .sheet(isPresented: Binding(get: { ordering != nil }, set: { if !$0 { ordering = nil } })) {
                    if let ordering { ChatPinOrderSheet(chats: ordering) { order in Task { await store.reorderPins(order) } } }
                }
                .confirmationDialog(muting.map { "Sourdine : \($0.name)" } ?? "", isPresented: Binding(get: { muting != nil }, set: { if !$0 { muting = nil } }),
                                    titleVisibility: .visible, presenting: muting) { chat in
                    ForEach(ChatMuteSpan.allCases) { span in
                        Button(span.label) { Task { await store.mute(chat, span) } }
                    }
                } message: { _ in
                    Text("Plus de notification de cette discussion pendant ce temps. Les messages arrivent quand même.")
                }
                .confirmationDialog(tileMenu?.name ?? "", isPresented: Binding(get: { tileMenu != nil }, set: { if !$0 { tileMenu = nil } }),
                                    titleVisibility: .visible, presenting: tileMenu) { chat in
                    tileActions(chat)
                }
                .confirmationDialog("Bloquer cette personne ?", isPresented: Binding(get: { blocking != nil }, set: { if !$0 { blocking = nil } }),
                                    titleVisibility: .visible, presenting: blocking) { chat in
                    Button("Bloquer", role: .destructive) { Task { await store.block(chat) } }
                } message: { _ in
                    Text("Elle ne pourra plus t'écrire. Tu pourras la débloquer dans les infos de la discussion.")
                }
        }
        .tint(Color(uiColor: AppConfig.uiAccent))
        .padding(.top, topInset)
        .background(ChatNeon.bg.ignoresSafeArea())
        .task(id: path.isEmpty) {
            // Liste visible : relue au retour d'une conversation, puis toutes les 30 s (secours du temps réel).
            guard path.isEmpty else { return store.stopListLive() }
            await store.loadList()
            openRequested()
            #if BETA || E2E_HOOKS
            await souvenirs?.refreshBubbles()  // bulles des Souvenirs (story, labo)
            #endif
            await store.startListLive()  // nouveaux messages : la liste se met à jour en direct
            while !Task.isCancelled {
                try? await Task.sleep(for: ChatsStore.listEvery)
                guard !Task.isCancelled else { break }
                await store.loadList()
                #if BETA || E2E_HOOKS
                await souvenirs?.refreshBubbles()
                #endif
            }
        }
        .onDisappear { store.stopListLive() }
        .onReceive(NotificationCenter.default.publisher(for: .partyBlockChanged)) { _ in Task { await store.loadList() } }
        .onChange(of: store.requested) { _ in openRequested() }
    }

    private func openRequested() {
        guard let chat = store.requested else { return }
        store.requested = nil
        path = [store.chat(chat)?.isEvent == true ? .event(chat) : .chat(chat)]
    }

    private func open(_ chat: ChatSummary) {
        ChatTiming.mark("row.tap")
        Haptics.selection()
        if chat.isEvent && chat.needsReading { Task { await store.markEventRead(chat.id) } }
        path.append(chat.isEvent ? .event(chat.id) : .chat(chat.id))
    }

    /// Actions d'une tuile épinglée (les mêmes que l'appui long d'une ligne).
    @ViewBuilder private func tileActions(_ chat: ChatSummary) -> some View {
        let later = { (work: @escaping () -> Void) in DispatchQueue.main.asyncAfter(deadline: .now() + 0.35, execute: work) }
        Button(chat.needsReading ? "Marquer comme lu" : "Marquer comme non lu") {
            Task { if chat.needsReading { await store.markRead(chat) } else { await store.setState(chat, unread: true) } }
        }
        Button("Désépingler") { Task { await store.setState(chat, pinned: false) } }
        if ChatListLogic.pinned(store.chats ?? [], filter: .all).count > 1 {
            Button("Réorganiser les épinglées") { later { ordering = ChatListLogic.pinned(store.chats ?? [], filter: .all) } }
        }
        if chat.isMuted() {
            Button("Réactiver les notifications") { Task { await store.mute(chat, nil) } }
        } else {
            Button("Sourdine…") { later { muting = chat } }
        }
        Button("Archiver") { Task { await store.setState(chat, archived: true) } }
        if chat.direct, let user = chat.userID, let showProfile {
            Button("Voir le profil") { later { showProfile(user) } }
        }
        if chat.direct, !chat.blocked {
            Button("Bloquer", role: .destructive) { later { blocking = chat } }
        }
        Button("Annuler", role: .cancel) {}
    }

    private var showProfile: ((String) -> Void)? {
        routes.miniProfile == nil ? nil : { profile = ProfileTarget(id: $0) }
    }

    private func newGroup() {
        if let openGroupPage { openGroupPage.open("new") } else { creating = true }
    }

    // MARK: Contenu

    @ViewBuilder private var content: some View {
        if let chats = store.chats {
            if !query.trimmingCharacters(in: .whitespaces).isEmpty {
                ChatSearchResults(query: query, store: store, open: open) { hit in
                    if let chat = store.chat(hit.chatID) { open(chat) } else {
                        Haptics.selection()
                        path.append(hit.kind == .event ? .event(hit.chatID) : .chat(hit.chatID))
                    }
                }
                .transition(.opacity)
            } else if chats.isEmpty {
                ChatsEmptyView(crossed: store.suggestions?.crossed ?? [], write: { person in Task { await store.openDirect(person.id) } },
                               newMessage: routes.newMessage == nil ? nil : { writing = true }, newGroup: newGroup)
                    .transition(.opacity)
            } else {
                list(chats).transition(.opacity)
            }
        } else if let error = store.error {
            ContentUnavailable(text: error).transition(.opacity)
        } else {
            ProgressView().tint(ChatNeon.lav).frame(maxWidth: .infinity, maxHeight: .infinity).transition(.opacity)
        }
    }

    private func list(_ chats: [ChatSummary]) -> some View {
        let pinned = ChatListLogic.pinned(chats, filter: filter)
        let rows = ChatListLogic.rows(chats, filter: filter)
        let requests = ChatListLogic.requests(chats).count
        let archived = ChatListLogic.archived(chats).count
        return List {
            #if BETA || E2E_HOOKS
            if let souvenirs {
                SouvenirBubblesRow(store: souvenirs)
                    .listRowInsets(EdgeInsets())
                    .listRowSeparator(.hidden)
                    .listRowBackground(Color.clear)
            }
            #endif
            filters(unread: ChatListLogic.unreadChats(chats))
                .listRowInsets(EdgeInsets())
                .listRowSeparator(.hidden)
                .listRowBackground(Color.clear)
            if !pinned.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 4) {
                        ForEach(pinned) { chat in
                            // Appui long : SES actions, en feuille d'actions en bas. Toutes les tuiles sont dans UNE ligne de
                            // la liste, où iOS ne garde qu'un menu contextuel (l'appui long ouvrait le menu de la première
                            // tuile) ; un menu sous le doigt pouvait aussi se choisir en levant le doigt (recette du 20.11).
                            ChatPinnedTile(chat: chat)
                                .onTapGesture { open(chat) }
                                .onLongPressGesture(minimumDuration: 0.45) {
                                    Haptics.tap()
                                    tileMenu = chat
                                }
                                .accessibilityAddTraits(.isButton)
                                .accessibilityAction { open(chat) }
                                .accessibilityAction(named: "Options") { tileMenu = chat }
                                .accessibilityIdentifier("chat-pin-\(chat.id)")
                        }
                    }
                    .padding(.horizontal, 10)
                }
                .listRowInsets(EdgeInsets(top: 10, leading: 0, bottom: 4, trailing: 0))
                .listRowSeparator(.hidden)
                .listRowBackground(Color.clear)
                .accessibilityElement(children: .contain)
                .accessibilityLabel("Épinglées")
            }
            if requests > 0 || archived > 0 {
                HStack(spacing: 8) {
                    if requests > 0 {
                        Button { path.append(.requests) } label: {
                            ChatSlimLink(title: "Demandes", systemImage: "tray", count: requests > 1 ? requests : 0, dot: true)
                        }
                        .accessibilityIdentifier("chats-requests")
                    }
                    if archived > 0 {
                        Button { path.append(.archived) } label: {
                            ChatSlimLink(title: "Archivées", systemImage: "archivebox", count: archived)
                        }
                        .accessibilityIdentifier("chats-archived")
                    }
                }
                .buttonStyle(.plain)
                .padding(.horizontal, 16)
                .listRowInsets(EdgeInsets(top: 10, leading: 0, bottom: 6, trailing: 0))
                .listRowSeparator(.hidden)
                .listRowBackground(Color.clear)
            }
            ForEach(rows) { chat in
                Button { open(chat) } label: { ChatListRow(chat: chat).padding(.horizontal, 16) }
                    .buttonStyle(ChatRowPressStyle())
                    .chatRowActions(chat, store: store, askMute: { muting = $0 }, askBlock: { blocking = $0 }, showProfile: showProfile)
                    .neonRow()
                    .accessibilityIdentifier("chat-row-\(chat.id)")
            }
            if rows.isEmpty && pinned.isEmpty {
                Text(Self.emptyFilter(filter))
                    .font(.subheadline).foregroundStyle(ChatNeon.t2)
                    .frame(maxWidth: .infinity).padding(.top, 40)
                    .listRowBackground(Color.clear)
                    .listRowSeparator(.hidden)
            }
            // Place sous le bouton flottant : la dernière ligne reste lisible.
            Color.clear.frame(height: 76).listRowBackground(Color.clear).listRowSeparator(.hidden)
        }
        .listStyle(.plain)
        .environment(\.defaultMinListRowHeight, 0)  // bulles des Souvenirs absentes : leur ligne ne prend aucune place
        .scrollContentBackground(.hidden)
        .onAppear { ChatTiming.mark("list.shown") }
        // Nouveau message : sa discussion remonte en tête en glissant, sans saut.
        .motion(Motion.snappy, value: chats.map(\.id))
        .motion(Motion.smooth, value: filter)
        .refreshable { await store.loadList() }
        .onPreferenceChange(ChatsTopKey.self) { y in
            guard let y else { return }
            if topY == nil { topY = y }
            let down = y < (topY ?? y) - 24
            if down != collapsed { Motion.animate(Motion.snappy) { collapsed = down } }
        }
    }

    static func emptyFilter(_ filter: ChatFilter) -> String {
        switch filter {
        case .all: return "Aucune discussion pour l'instant."
        case .unread: return "Tout est lu 🎉"
        case .people: return "Aucun message direct."
        case .groups: return "Aucune discussion de groupe."
        case .events: return "Aucune discussion de soirée en ce moment."
        }
    }

    private func filters(unread: Int) -> some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(ChatFilter.allCases) { f in
                    ChatFilterChip(filter: f, selected: filter == f, count: f == .unread ? unread : 0) {
                        Haptics.selection()
                        filter = f
                    }
                }
            }
            .padding(.horizontal, 16)
        }
        .padding(.top, 4)
        .background(GeometryReader { g in Color.clear.preference(key: ChatsTopKey.self, value: g.frame(in: .global).minY) })
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Filtrer")
    }

    // MARK: Barre du haut, bouton flottant, bandeau

    private var moreMenu: some View {
        let chats = store.chats ?? []
        let requests = ChatListLogic.requests(chats).count
        let archived = ChatListLogic.archived(chats).count
        return Menu {
            if routes.newMessage != nil {
                Button { writing = true } label: { Label("Nouveau message", systemImage: "square.and.pencil") }
            }
            Button { newGroup() } label: { Label("Nouveau groupe", systemImage: "person.2") }
                .accessibilityIdentifier("chats-new-group")
            Divider()
            Button { path.append(.requests) } label: {
                Label(requests > 0 ? "Demandes de message (\(requests))" : "Demandes de message", systemImage: "tray")
            }
            Button { path.append(.archived) } label: {
                Label(archived > 0 ? "Archivées (\(archived))" : "Archivées", systemImage: "archivebox")
            }
            if ChatListLogic.unreadChats(chats) > 0 {
                Button { Task { await store.markAllRead() } } label: { Label("Tout marquer comme lu", systemImage: "checkmark.circle") }
            }
            let pinned = ChatListLogic.pinned(chats, filter: .all)
            if pinned.count > 1 {
                Button { ordering = pinned } label: { Label("Réorganiser les épinglées", systemImage: "arrow.left.arrow.right") }
                    .accessibilityIdentifier("chats-reorder-pins")
            }
        } label: {
            NeonCircleLabel(systemImage: "ellipsis")
        }
        .accessibilityLabel("Plus : nouveau groupe, demandes de message, archivées")
        .accessibilityIdentifier("chats-more")
    }

    @ViewBuilder private var fab: some View {
        if routes.newMessage != nil, query.isEmpty, store.chats?.isEmpty == false, path.isEmpty {
            Button {
                Haptics.tap()
                writing = true
            } label: {
                HStack(spacing: 10) {
                    Image(systemName: "square.and.pencil").font(.system(size: 19, weight: .bold))
                    if !collapsed {
                        Text("Nouveau message").font(.body.weight(.bold)).fixedSize()
                            .transition(.opacity.combined(with: .move(edge: .trailing)))
                    }
                }
                .foregroundStyle(ChatNeon.onPink)
                .padding(.horizontal, collapsed ? 0 : 20)
                .frame(width: collapsed ? 56 : nil, height: 56)
                .background(ChatNeon.pinkGradient, in: Capsule())
                .overlay(Capsule().strokeBorder(.white.opacity(0.25), lineWidth: 1))
                .shadow(color: ChatNeon.pink.opacity(0.6), radius: 18, y: 8)
            }
            .buttonStyle(PronoKitPressStyle())
            .padding(16)
            .accessibilityLabel("Nouveau message")
            .accessibilityIdentifier("chats-new-message")
            .transition(.scale(scale: 0.8).combined(with: .opacity))
        }
    }

    @ViewBuilder private var noticeBanner: some View {
        if let notice = store.notice, path.isEmpty {
            ChatNoticeBanner(text: notice) { if store.notice == notice { store.notice = nil } }
                .motionTransition(.banner)
        }
    }

    /// Chargement → liste ou erreur : fondu (une relecture de la liste ne rejoue rien).
    private var listPhase: Int { store.chats != nil ? 2 : store.error != nil ? 1 : 0 }
}

/// Erreur d'un geste de la liste (épingler au-delà de 5, demande refusée…) : bandeau en bas, parti après 4 s ou au toucher.
private struct ChatNoticeBanner: View {
    let text: String
    let close: () -> Void

    var body: some View {
        Text(text)
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(ChatNeon.t1)
            .multilineTextAlignment(.center)
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .background(.ultraThinMaterial, in: Capsule())
            .overlay(Capsule().strokeBorder(ChatNeon.glassLine, lineWidth: 1))
            .padding(.horizontal, 16)
            .padding(.bottom, 84)
            .onTapGesture(perform: close)
            .task(id: text) {
                try? await Task.sleep(for: .seconds(4))
                guard !Task.isCancelled else { return }
                Motion.animate(Motion.smooth, close)
            }
    }
}

/// Position de la rangée des filtres : le bouton flottant se replie en ✎ dès qu'on fait défiler, revient en haut.
private struct ChatsTopKey: PreferenceKey {
    static let defaultValue: CGFloat? = nil
    static func reduce(value: inout CGFloat?, nextValue: () -> CGFloat?) { value = nextValue() ?? value }
}

/// Lune : couper les notifications de toutes les Discussions (30 min…8 h), même réglage que Réglages › Notifications.
private struct ChatsMoonMenu: View {
    @ObservedObject var store: PauseStore

    var body: some View {
        TimelineView(.periodic(from: .now, by: 30)) { context in
            let until = store.active(.chats, now: context.date)
            Menu {
                PauseMenuItems(store: store, scope: .chats, until: until)
            } label: {
                NeonCircleLabel(systemImage: until == nil ? "moon" : "moon.fill", active: until != nil)
            }
            .disabled(store.busy)
            .accessibilityLabel(until.map { "Discussions en pause jusqu'à \(NotificationPause.label($0))" }
                                ?? "Couper les notifications des Discussions")
            .accessibilityIdentifier("chats-pause-button")
        }
        .task { await store.load() }
    }
}

/// Nouveau groupe depuis Discussions : le même champ que Réglages › Groupes ; le créateur en fait partie d'office,
/// puis sa discussion s'ouvre.
private struct NewGroupSheet: View {
    @ObservedObject var store: ChatsStore
    @ObservedObject private var groups: GroupsStore
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @FocusState private var naming: Bool

    init(store: ChatsStore) {
        self.store = store
        _groups = ObservedObject(wrappedValue: store.groups)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    NewGroupField(name: $name, focus: $naming, busy: groups.busy.contains("create"), onCreate: create)
                } footer: {
                    Text("Le même groupe que dans Réglages › Groupes : tu en fais partie d'office, comme Créateur · Admin. Ajoute ensuite des membres depuis les infos de la discussion (ⓘ › Gérer le groupe).")
                }
                if let problem = store.notice {
                    Text(problem).font(.footnote).foregroundStyle(.red)
                }
            }
            .scrollContentBackground(.hidden)
            .background(AppConfig.background.ignoresSafeArea())
            .navigationTitle("Nouveau groupe")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Annuler") { dismiss() } } }
            .onAppear { naming = true; store.notice = nil }
            .onDisappear { store.notice = nil }
        }
        .preferredColorScheme(.dark)
        .presentationDetents([.medium])
    }

    private func create() {
        let clean = name.trimmingCharacters(in: .whitespaces)
        guard !clean.isEmpty else { return }
        Haptics.tap()
        Task { if await store.createGroup(clean) { dismiss() } }
    }
}

private struct ContentUnavailable: View {
    let text: String
    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "bubble.left.and.bubble.right").font(.largeTitle).foregroundStyle(ChatNeon.lav)
            Text(text).multilineTextAlignment(.center).foregroundStyle(ChatNeon.t2)
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

/// Pastille ronde aux initiales (ou photo) : groupes et auteurs des messages.
struct Initials: View {
    let name: String
    var photo: String?
    var size: CGFloat = 32

    private var letters: String {
        name.split(separator: " ").prefix(2).compactMap(\.first).map(String.init).joined().uppercased()
    }

    /// Teinte stable d'un lancement à l'autre (hashValue change à chaque lancement : la pastille changeait de couleur).
    private var hue: Double {
        let sum = name.unicodeScalars.reduce(UInt32(5381)) { ($0 &* 33) &+ $1.value }
        return Double(sum % 360) / 360
    }

    var body: some View {
        // Photo téléchargée : fondu depuis les initiales, plus d'apparition sèche.
        AsyncImage(url: photo.flatMap(URL.init(string:)), transaction: Transaction(animation: Motion.pick(Motion.fade))) { phase in
            if let image = phase.image {
                image.resizable().scaledToFill().transition(.opacity)
            } else {
                Text(letters.isEmpty ? "?" : letters).font(.system(size: size * 0.36, weight: .bold)).foregroundStyle(.black)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(Color(hue: hue, saturation: 0.45, brightness: 0.95))
            }
        }

        .frame(width: size, height: size)
        .clipShape(Circle())
        .accessibilityHidden(true)
    }
}

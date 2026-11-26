import SwiftUI

/// App iOS « Party ! » : la webapp affichée en plein écran, à l'identique de l'app ajoutée à l'écran d'accueil.
@main
struct PartyApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var model = WebModel(start: AppConfig.baseURL)
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            ContentView(model: model)
                // Lien universel (QR code, lien partagé) ou toucher d'une notification : on l'ouvre dans l'app.
                .onOpenURL { model.open($0) }
                // Suivi de la file en direct (Live Activity « Ton titre arrive ») tant que l'app est au premier plan,
                // quel que soit l'onglet, et aussi pour l'hôte en « Gérer la soirée » (écran natif non affiché).
                .onChange(of: scenePhase) { phase in
                    if phase == .active { model.refreshFeatures(); model.dropAccountIfGone() }
                    if phase == .active { model.music?.start() } else if phase == .background { model.music?.stop() }
                    // « Partager › Party › Créer un événement » : l'assistant IA démarre avec le lien mis de côté.
                    if phase == .active, let link = SharedSession.takePendingEvent() { model.startAIEvent(link: link) }
                    // Noms des contacts : accès changé dans Réglages, ou reconnaissance ancienne (12 h).
                    if phase == .active { ContactNames.shared.appBecameActive() }
                    // Agenda : pastille des demandes relue ; plages « pris » renvoyées si cet iPhone partage ses dispos.
                    #if BETA || E2E_HOOKS
                    if phase == .active, model.settings?.agendaOn == true, let agenda = model.settings?.agenda { Task { await agenda.appBecameActive() } }
                    #endif
                    // Action rapide de l'icône (lancement à froid compris) ; éclosion de Zicou finie app fermée.
                    if phase == .active, let action = QuickAction.take() { model.perform(action) }
                    if phase == .active && AppConfig.zicouBuild { PetWidgetBridge.appBecameActive() }
                }
                #if DEBUG
                .task { TrackActivities.startDemoIfAsked() }
                .task { QuickAction.registerBase() }
                .task { HatchActivities.startDemoIfAsked() }
                .overlay { MotionDemo(model: model) }
                #endif
                // Recette réelle (simulateur, serveur local, base de TEST) et tests d'interface en Release : aussi avec
                // E2E_HOOKS, jamais dans l'app de l'App Store (le réglage n'est passé qu'en ligne de commande).
                #if DEBUG || E2E_HOOKS
                .overlay { HostDemo(model: model) }
                .overlay { GroupAdminDemo(model: model) }
                .overlay { AIEventDemo(model: model) }
                #endif
                .onReceive(NotificationCenter.default.publisher(for: .partyOpenURL)) { note in
                    if let url = note.object as? URL { model.open(url) }
                }
                .onReceive(NotificationCenter.default.publisher(for: .partyQuickAction)) { _ in
                    if let action = QuickAction.take() { model.perform(action) }
                }
        }
    }
}

struct ContentView: View {
    @ObservedObject var model: WebModel
    @AppStorage(ZicouBubblePrefs.shownKey) private var zicouBubbleShown = true
    /// iPhone Duo : côté de la barre verticale du système ; nil sur les autres iPhone (barre d'onglets en bas).
    @State private var barEdge: HorizontalEdge?
    /// Largeur que la barre verticale prend en plus de la zone sûre (souvent 0 : elle loge sous la barre d'état).
    @State private var barExtraInset: CGFloat = 0

    private var sideBarVisible: Bool {
        barEdge != nil && model.visibleTabs.map { !$0.hidden } == true && !model.failed
    }

    /// Barre d'onglets verticale (Duo) : plus de barre en bas, les boutons flottants évitent la barre d'accueil.
    private func homeInset(_ proxy: GeometryProxy) -> CGFloat {
        sideBarVisible ? proxy.safeAreaInsets.bottom : 0
    }

    /// Bulle de Zicou : au-dessus de la barre d'accueil (Duo) et, posé comme un portable, au-dessus du pli.
    private func zicouBottom(_ proxy: GeometryProxy) -> CGFloat {
        guard model.fold?.posture == .laptop, let fold = model.fold?.fold else { return homeInset(proxy) }
        // Hauteur de la zone sous la page (même cadre que la vue web) moins le haut du pli.
        let full = proxy.size.height + proxy.safeAreaInsets.top + proxy.safeAreaInsets.bottom
        let area = barEdge == nil && model.visibleTabs.map({ !$0.hidden }) == true
            ? full - NativeTabBar.height - proxy.safeAreaInsets.bottom : full
        return max(homeInset(proxy), area - fold.minY)
    }

    /// « Gérer la soirée » (écran natif de l'hôte) / « Gérer les retours » (page) : réservé à l'hôte.
    private func hostTools(_ screen: String) -> (() -> Void)? {
        guard model.isHost else { return nil }
        if screen == "music" { return { [model] in Motion.animate(Motion.smooth) { model.hostNativeMusic = true } } }
        return { [model] in Motion.animate(Motion.smooth) { model.setHostManages(true, screen: screen) } }
    }

    var body: some View {
        GeometryReader { proxy in
            ZStack {
                AppConfig.background.ignoresSafeArea()
                // La page gère elle-même l'encoche (viewport-fit=cover + env(safe-area-inset-*)). La barre
                // d'onglets native est SOUS la vue web : la page s'arrête au-dessus, rien n'est caché derrière.
                VStack(spacing: 0) {
                    ZStack {
                        PartyWebView(model: model)
                        if model.nativeScreen == "music", let music = model.music {
                            if model.isHost && model.hostNativeMusic, let host = model.hostMusic {
                                HostMusicView(store: host, topInset: proxy.safeAreaInsets.top,
                                              guestView: { Motion.animate(Motion.smooth) { model.hostNativeMusic = false } },
                                              pageView: { Motion.animate(Motion.smooth) { model.manageMusicInPage() } })
                                    .sideSafeArea(proxy)
                                    .transition(.opacity)
                            } else {
                                // Vue invité ↔ Gérer la soirée : fondu enchaîné dans les deux sens (avant : seulement à l'aller).
                                MusicView(store: music, topInset: proxy.safeAreaInsets.top, manage: hostTools("music"),
                                          signIn: model.settings?.session)
                                    .sideSafeArea(proxy)
                                    .transition(.opacity)
                            }
                        }
                        if model.nativeScreen == "feedback", let feedback = model.feedback {
                            // Page des Réglages depuis le 4.11 (l'onglet Zicou a pris sa place) : « ‹ Réglages ».
                            FeedbackView(store: feedback, topInset: proxy.safeAreaInsets.top, admin: model.isHost ? model.feedbackAdmin : nil,
                                         back: model.tabs?.isSubScreen == true ? { Motion.animate(Motion.smooth) { model.selectTab("account") } } : nil)
                                .sideSafeArea(proxy)
                        }
                        if model.nativeScreen == "chats", let chats = model.chats {
                            ChatsView(store: chats, topInset: proxy.safeAreaInsets.top)
                                .sideSafeArea(proxy, ChatNeon.bg)
                        }
                        if model.nativeScreen == "account", let settings = model.settings {
                            SettingsView(store: settings, topInset: proxy.safeAreaInsets.top, isHost: model.isHost, hostMusic: model.hostMusic,
                                         feedbackEntry: model.tabs?.feedback, zicouAvailable: model.zicouBubble != nil) { place in
                                Motion.animate(Motion.smooth) { model.show(place) }
                            }
                            .sideSafeArea(proxy)
                        }
                        if model.pageDetail != nil {
                            Button {
                                Motion.animate(Motion.smooth) { model.closePageDetail() }
                            } label: {
                                Label("Réglages", systemImage: "chevron.left")
                                    .font(.subheadline.weight(.semibold))
                                    .padding(.horizontal, 14).padding(.vertical, 10)
                                    .background(.ultraThinMaterial, in: Capsule())
                            }
                            .tint(.white)
                            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottomLeading)
                            .padding(16)
                            .padding(.leading, proxy.safeAreaInsets.leading)
                            .padding(.bottom, homeInset(proxy))
                            .accessibilityHint("Revient aux Réglages de l'app")
                            .motionTransition(.opacity.combined(with: .scale(scale: 0.9, anchor: .bottomLeading)))
                        }
                        if let managed = model.hostManagedScreen {
                            Button {
                                Motion.animate(Motion.smooth) { model.setHostManages(false, screen: managed) }
                            } label: {
                                Label("Vue invité", systemImage: "person.2")
                                    .font(.subheadline.weight(.semibold))
                                    .padding(.horizontal, 14).padding(.vertical, 10)
                                    .background(.ultraThinMaterial, in: Capsule())
                            }
                            .tint(.white)
                            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottomTrailing)
                            .padding(16)
                            .padding(.trailing, proxy.safeAreaInsets.trailing)
                            .padding(.bottom, homeInset(proxy))
                            .accessibilityHint("Affiche l'écran Musique des invités ; le choix est retenu")
                            .motionTransition(.opacity.combined(with: .scale(scale: 0.9, anchor: .bottomTrailing)))
                        }
                        // Pyramide : les cartes à mémoriser, en bas de l'écran de jeu, protégées des captures.
                        if let secret = model.secretCards {
                            SecretCardsView(state: secret)
                                // iPhone Duo entrouvert en livre : les cartes à droite du pli, jamais dessus.
                                .padding(.leading, 16 + max(proxy.safeAreaInsets.leading, model.fold?.posture == .book ? model.fold?.fold?.maxX ?? 0 : 0))
                                .padding(.trailing, 16 + proxy.safeAreaInsets.trailing)
                                .padding(.bottom, proxy.safeAreaInsets.bottom + 16)
                                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottom)
                                .motionTransition(.move(edge: .bottom).combined(with: .opacity))
                        }
                        // Bulle de Zicou (BETA) : par-dessus la page et les écrans natifs, déplaçable, masquable.
                        if zicouBubbleShown, let zicou = model.zicouBubble, zicou.visible, model.tabs?.hidden != true {
                            ZicouBubble(state: zicou, insets: EdgeInsets(top: proxy.safeAreaInsets.top, leading: proxy.safeAreaInsets.leading,
                                                                         bottom: zicouBottom(proxy), trailing: proxy.safeAreaInsets.trailing)) {
                                model.openZicouBubble()
                            }
                            .motionTransition(.opacity.combined(with: .scale(scale: 0.6)))
                        }
                    }
                    if let tabs = model.visibleTabs, !tabs.hidden, barEdge == nil {
                        NativeTabBar(state: tabs, select: model.selectTab)
                            .frame(height: NativeTabBar.height + proxy.safeAreaInsets.bottom)
                            .motionTransition(.move(edge: .bottom))
                    }
                }
                .padding(barEdge == .leading ? .leading : .trailing, sideBarVisible ? barExtraInset : 0)
                .ignoresSafeArea()
                // Barre d'onglets native qui se cache (plein écran d'un jeu) ou revient : glissement court,
                // fondu avec Réduire les animations.
                .motion(Motion.snappy, value: model.tabs?.hidden ?? true)
                .motion(Motion.snappy, value: zicouBubbleShown && model.zicouBubble?.visible == true)
                .motion(Motion.smooth, value: model.notice)
                .motion(Motion.smooth, value: model.secretCards)
                // Discussion ouverte : la page derrière (fiche, barre d'onglets) sort de VoiceOver et des tests d'interface.
                .accessibilityHidden(model.eventChatID != nil)

                // Discussion d'un événement (17.11) : arrive de la droite par-dessus la fiche et la barre d'onglets, comme
                // une page poussée ; « ‹ » ou un glissé depuis le bord gauche ramène à la fiche.
                if let id = model.eventChatID, let store = model.eventChats {
                    EventChatScreen(store: store, eventID: id,
                                    onClose: { Motion.animate(Motion.smooth) { model.closeEventChat() } },
                                    info: $model.eventChatInfo)
                        .id(id)
                        .zIndex(1)
                        .motionTransition(.move(edge: .trailing))
                }

                // iPhone Duo : barre d'onglets verticale du système, sur le côté (voir SystemTabBar).
                if #available(iOS 27.1, *), sideBarVisible, let tabs = model.visibleTabs {
                    SystemTabBar(state: tabs, select: model.selectTab, back: model.canGoBack ? { [model] in model.goBack() } : nil) { barExtraInset = $0 }
                        .ignoresSafeArea()
                        .motionTransition(.opacity)
                }

                // Maintenance, information, annonce (notice.js) : par-dessus la page, les écrans natifs et la barre.
                if let notice = model.notice, !model.failed {
                    PartyNoticeView(notice: notice, topInset: proxy.safeAreaInsets.top,
                                    close: { Motion.animate(Motion.smooth) { model.hideNotice(notice.id) } },
                                    manage: { Motion.animate(Motion.smooth) { model.show(.tab("notice")) } })
                        // Bandeau : haut et bas seulement, il évite sur les côtés la colonne de la barre d'état du Duo ;
                        // maintenance : tout l'écran, barre d'onglets verticale comprise.
                        .ignoresSafeArea(.container, edges: notice.blocks ? .all : .vertical)
                        .motionTransition(.opacity)
                }

                if model.failed {
                    OfflineView(busy: model.serverBusy, quietRetry: { model.retryQuietly() }) { model.reload() }
                }
            }
        }
        .background(VerticalBarEdgeReader { edge in Motion.animate(Motion.snappy) { barEdge = edge } })
        .preferredColorScheme(.dark)
        // Fiche d'un membre › son Zicou : visite (ami) ou « Adopter le mien », dans l'onglet Zicou de la page.
        .environment(\.openZicou, OpenZicouAction { visit in model.openZicou(visit: visit) })
        // Groupes : « Nouveau groupe », Réglages › Groupes → écrans natifs (18.11) ; sans Discussions, pages du module Événements.
        .environment(\.openGroupPage, OpenGroupPageAction { target in model.openGroupPage(target) })
        .sheet(isPresented: $model.aiEventOpen, onDismiss: { model.aiEditEventId = nil }) {
            if let settings = model.settings {
                AIEventView(store: settings.aiEvent, editing: model.aiEditEventId,
                            open: { id in model.openEvent(id) }, openInvite: { created in model.openInvite(created) })
                    .presentationDragIndicator(.visible)
            }
        }
        // Pronos (17.11) : écrans natifs par-dessus la page (bouton de la page, notification) ; « ✕ » ramène à la page.
        // BETA seulement : absents du binaire de l'App Store.
        #if BETA || E2E_HOOKS
        .fullScreenCover(item: $model.pronoRoute) { route in
            if let store = model.settings?.pronos {
                PronoRouteView(store: store, route: route) { model.pronoRoute = nil }
            }
        }
        #endif
        // Souvenirs (24.11) : appareil photo et story, plein écran par-dessus tout ; la page relit sa fiche à la fermeture.
        // BETA seulement : absents du binaire de l'App Store.
        #if BETA || E2E_HOOKS
        .fullScreenCover(item: $model.souvenirRoute, onDismiss: { model.souvenirsClosed() }) { route in
            if let store = model.souvenirs {
                switch route {
                case .camera(let event): SouvenirCameraView(store: store, eventID: event) { model.souvenirRoute = nil }
                case .story(let event): SouvenirStoryView(store: store, eventID: event) { model.souvenirRoute = nil }
                }
            }
        }
        #endif
        // Groupes en natif (18.11, « tout en natif ») : Réglages › Groupes, « Nouveau groupe », page d'un groupe ; « ✕ » ferme.
        .fullScreenCover(item: $model.groupRoute) { route in
            GroupsHostView(route: route) { model.groupRoute = nil }
                .preferredColorScheme(.dark)
        }
        .sheet(isPresented: $model.ticketScanOpen, onDismiss: { model.finishTicketScan(nil) }) {
            QRScannerSheet(title: "Scanner un billet",
                           fallback: "Caméra indisponible : autorise-la pour Party ! dans Réglages, ou tape le code du billet.") { text in
                model.finishTicketScan(text)
            }
        }
        // Discussions v2 (18.11) : mini-profil ou « Nouveau message » demandés par la page (PartyNative.chat).
        .sheet(item: $model.peopleRoute) { route in
            switch route {
            case .profile(let user): MiniProfileSheet(userID: user)
            case .newMessage(let event): NewMessageView(eventID: event)
            }
        }
        // « Envoyer un message » (mini-profil, fiches, Mes amis) : la conversation privée s'ouvre dans Discussions (si
        // disponible) ; personnes (Nouveau message, mini-profil). Posés en dernier : les feuilles et écrans plein écran
        // ci-dessus (discussion d'événement, pronos, personnes) les reçoivent aussi.
        .environment(\.writeDirect, model.canWriteDirect ? WriteDirectAction { user in await model.writeDirect(to: user) } : nil)
        .environment(\.people, model.canWriteDirect ? model.people : nil)
        // Bulles des Souvenirs en haut des Discussions.
        #if BETA || E2E_HOOKS
        .environment(\.souvenirs, model.souvenirs)
        #endif
        // Groupes natifs : ce qu'ils ouvrent ailleurs (discussion, fiche d'un événement, création d'un événement, pronos).
        .environment(\.groupHub, model.canWriteDirect ? GroupHub(
            pronos: model.groupPronos,
            leave: { then in
                guard model.groupRoute != nil else { return then() }
                model.groupRoute = nil
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.45) { then() }
            },
            openChat: { model.openChatNow($0) }, openEvent: { model.openEvent($0) },
            createEvent: { model.openNewEvent(group: $0) }) : nil)
        .environment(\.chatsRoutes, model.canWriteDirect
            ? ChatsRoutes(newMessage: { AnyView(NewMessageView(eventID: $0)) },
                          miniProfile: { AnyView(MiniProfileSheet(userID: $0)) })
            : ChatsRoutes())
        // Dans une discussion, toucher une personne ouvre son mini-profil (note privée, « À venir ensemble »), plus
        // l'ancienne fiche (recette iPhone du 22.11) ; « Voir » ouvre la fiche de l'événement.
        .environment(\.conversationRoutes, ConversationRoutes(miniProfile: { AnyView(MiniProfileSheet(userID: $0)) },
                                                              openEvent: { model.openEvent($0) }))
    }
}

#if DEBUG || E2E_HOOKS
/// Simulateur : PARTY_DEBUG_HOST_DEMO=<état JSON de /api/admin/state> affiche « Gérer la soirée » sur un état figé.
private struct HostDemo: View {
    @ObservedObject var model: WebModel
    @State private var shown = false

    var body: some View {
        GeometryReader { proxy in
            if shown, let store = model.hostMusic {
                HostMusicView(store: store, topInset: proxy.safeAreaInsets.top, guestView: {}, pageView: {})
                    .ignoresSafeArea()
            }
        }
        .task {
            guard let json = ProcessInfo.processInfo.environment["PARTY_DEBUG_HOST_DEMO"],
                  let state = try? JSONDecoder().decode(AdminState.self, from: Data(json.utf8)) else { return }
            try? await Task.sleep(for: .seconds(1))
            model.hostMusic?.showDemo(state)
            shown = true
        }
    }
}

/// Simulateur : PARTY_DEBUG_GROUP_ADMIN=<GroupAdminStore.Demo en JSON> affiche Administration du groupe sur un état figé.
private struct GroupAdminDemo: View {
    @ObservedObject var model: WebModel
    @State private var shown = false

    var body: some View {
        Group {
            if shown, let store = model.settings?.groupAdmin {
                NavigationStack { GroupAdminView(store: store, session: model.settings!.session, open: { _ in }) }
                    .tint(Palette.accent)
                    .background(AppConfig.background.ignoresSafeArea())
            }
        }
        .task {
            guard let json = ProcessInfo.processInfo.environment["PARTY_DEBUG_GROUP_ADMIN"] else { return }
            do {
                let demo = try JSONDecoder().decode(GroupAdminStore.Demo.self, from: Data(json.utf8))
                try? await Task.sleep(for: .seconds(1))
                model.settings?.groupAdmin.showDemo(demo)
                shown = true
            } catch {
                assertionFailure("PARTY_DEBUG_GROUP_ADMIN illisible : \(error)")
            }
        }
    }
}
#endif

#if DEBUG || E2E_HOOKS
/// Simulateur : PARTY_DEBUG_AI_EVENT=tips|<AIEvent.Draft en JSON> ouvre « Créer avec l'IA » (conseils, ou fiche figée).
private struct AIEventDemo: View {
    @ObservedObject var model: WebModel

    var body: some View {
        Color.clear.task {
            guard let value = ProcessInfo.processInfo.environment["PARTY_DEBUG_AI_EVENT"] else { return }
            try? await Task.sleep(for: .seconds(1))
            if let draft = try? JSONDecoder().decode(AIEvent.Draft.self, from: Data(value.utf8)) {
                await model.settings?.aiEvent.showDemo(draft, said: ProcessInfo.processInfo.environment["PARTY_DEBUG_AI_SAID"] ?? "")
                // PARTY_DEBUG_AI_PICK=1 : le premier lieu trouvé est confirmé (« Oui, continuer » actif).
                if ProcessInfo.processInfo.environment["PARTY_DEBUG_AI_PICK"] == "1", let store = model.settings?.aiEvent {
                    store.choose(store.candidates.first ?? store.asSaid)
                }
            }
            // PARTY_DEBUG_AI_CREATED=<AIEvent.Created en JSON> : l'étape 2 (brouillon enregistré), sans ouverture automatique.
            if let created = ProcessInfo.processInfo.environment["PARTY_DEBUG_AI_CREATED"],
               let demo = try? JSONDecoder().decode(AIEvent.Created.self, from: Data(created.utf8)) {
                model.settings?.aiEvent.showDemoCreated(demo)
            }
            // PARTY_DEBUG_AI_ERROR=<message> : un message affiché avant tout échange (ex. accord IA refusé).
            if let message = ProcessInfo.processInfo.environment["PARTY_DEBUG_AI_ERROR"] {
                model.settings?.aiEvent.error = message
            }
            model.aiEventOpen = true
        }
        .allowsHitTesting(false)
    }
}
#endif

/// iPhone Duo, écran extérieur : la colonne de la barre d'état (heure, réseau) et la barre d'onglets verticale sont sur le
/// côté. La page s'arrête avant (env(safe-area-inset-*)) ; les écrans natifs aussi, sur le même fond (recette du 19.11 :
/// « Entrer » et la consigne de Musique passaient dessous). Ailleurs (iPhone en portrait), marges nulles : rien ne change.
private extension View {
    func sideSafeArea(_ proxy: GeometryProxy, _ fill: Color = AppConfig.background) -> some View {
        padding(.leading, proxy.safeAreaInsets.leading)
            .padding(.trailing, proxy.safeAreaInsets.trailing)
            .background(fill)
    }
}

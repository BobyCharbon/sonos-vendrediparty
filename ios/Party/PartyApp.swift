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
                    if phase == .active { model.refreshFeatures() }
                    if phase == .active { model.music?.start() } else if phase == .background { model.music?.stop() }
                    // « Partager › Party › Créer un événement » : l'assistant IA démarre avec le lien mis de côté.
                    if phase == .active, let link = SharedSession.takePendingEvent() { model.startAIEvent(link: link) }
                    // Noms des contacts : accès changé dans Réglages, ou reconnaissance ancienne (12 h).
                    if phase == .active { ContactNames.shared.appBecameActive() }
                    // Action rapide de l'icône (lancement à froid compris) ; éclosion de Zicou finie app fermée.
                    if phase == .active, let action = QuickAction.take() { model.perform(action) }
                    if phase == .active && AppConfig.zicouBuild { PetWidgetBridge.appBecameActive() }
                }
                #if DEBUG
                .task { TrackActivities.startDemoIfAsked() }
                .task { HatchActivities.startDemoIfAsked() }
                .overlay { HostDemo(model: model) }
                .overlay { GroupAdminDemo(model: model) }
                .overlay { MotionDemo(model: model) }
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
                                    .transition(.opacity)
                            } else {
                                // Vue invité ↔ Gérer la soirée : fondu enchaîné dans les deux sens (avant : seulement à l'aller).
                                MusicView(store: music, topInset: proxy.safeAreaInsets.top, manage: hostTools("music"),
                                          signIn: model.settings?.session)
                                    .transition(.opacity)
                            }
                        }
                        if model.nativeScreen == "feedback", let feedback = model.feedback {
                            // Page des Réglages depuis le 4.11 (l'onglet Zicou a pris sa place) : « ‹ Réglages ».
                            FeedbackView(store: feedback, topInset: proxy.safeAreaInsets.top, admin: model.isHost ? model.feedbackAdmin : nil,
                                         back: model.tabs?.isSubScreen == true ? { Motion.animate(Motion.smooth) { model.selectTab("account") } } : nil)
                        }
                        if model.nativeScreen == "chats", let chats = model.chats {
                            ChatsView(store: chats, topInset: proxy.safeAreaInsets.top)
                        }
                        if model.nativeScreen == "account", let settings = model.settings {
                            SettingsView(store: settings, topInset: proxy.safeAreaInsets.top, isHost: model.isHost, hostMusic: model.hostMusic,
                                         feedbackEntry: model.tabs?.feedback) { place in
                                Motion.animate(Motion.smooth) { model.show(place) }
                            }
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
                            .accessibilityHint("Affiche l'écran Musique des invités ; le choix est retenu")
                            .motionTransition(.opacity.combined(with: .scale(scale: 0.9, anchor: .bottomTrailing)))
                        }
                    }
                    if let tabs = model.visibleTabs, !tabs.hidden {
                        NativeTabBar(state: tabs, select: model.selectTab)
                            .frame(height: NativeTabBar.height + proxy.safeAreaInsets.bottom)
                            .motionTransition(.move(edge: .bottom))
                    }
                }
                .ignoresSafeArea()
                // Barre d'onglets native qui se cache (plein écran d'un jeu) ou revient : glissement court,
                // fondu avec Réduire les animations.
                .motion(Motion.snappy, value: model.tabs?.hidden ?? true)

                if model.failed {
                    OfflineView { model.reload() }
                }
            }
        }
        .preferredColorScheme(.dark)
        // « Écrire » (Mes amis, fiches des membres) : la conversation privée s'ouvre dans Discussions (si disponible).
        // Fiche d'un membre › son Zicou : visite (ami) ou « Adopter le mien », dans l'onglet Zicou de la page.
        .environment(\.openZicou, OpenZicouAction { visit in model.openZicou(visit: visit) })
        .environment(\.writeDirect, model.canWriteDirect ? WriteDirectAction { user in await model.writeDirect(to: user) } : nil)
        .sheet(isPresented: $model.aiEventOpen, onDismiss: { model.aiEditEventId = nil }) {
            if let settings = model.settings {
                AIEventView(store: settings.aiEvent, editing: model.aiEditEventId) { id in model.openEvent(id) }
                    .presentationDragIndicator(.visible)
            }
        }
        .sheet(isPresented: $model.ticketScanOpen, onDismiss: { model.finishTicketScan(nil) }) {
            QRScannerSheet(title: "Scanner un billet",
                           fallback: "Caméra indisponible : autorise-la pour Party ! dans Réglages, ou tape le code du billet.") { text in
                model.finishTicketScan(text)
            }
        }
    }
}

#if DEBUG
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

/// Simulateur : PARTY_DEBUG_AI_EVENT=tips|<AIEvent.Draft en JSON> ouvre « Créer avec l'IA » (conseils, ou fiche figée).
private struct AIEventDemo: View {
    @ObservedObject var model: WebModel

    var body: some View {
        Color.clear.task {
            guard let value = ProcessInfo.processInfo.environment["PARTY_DEBUG_AI_EVENT"] else { return }
            try? await Task.sleep(for: .seconds(1))
            if let draft = try? JSONDecoder().decode(AIEvent.Draft.self, from: Data(value.utf8)) {
                await model.settings?.aiEvent.showDemo(draft, said: ProcessInfo.processInfo.environment["PARTY_DEBUG_AI_SAID"] ?? "")
            }
            model.aiEventOpen = true
        }
        .allowsHitTesting(false)
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

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
                    if phase == .active { model.music?.start() } else if phase == .background { model.music?.stop() }
                }
                #if DEBUG
                .task { TrackActivities.startDemoIfAsked() }
                .overlay { HostDemo(model: model) }
                .overlay { GroupAdminDemo(model: model) }
                #endif
                .onReceive(NotificationCenter.default.publisher(for: .partyOpenURL)) { note in
                    if let url = note.object as? URL { model.open(url) }
                }
        }
    }
}

struct ContentView: View {
    @ObservedObject var model: WebModel

    /// « Gérer la soirée » (écran natif de l'hôte) / « Gérer les retours » (page) : réservé à l'hôte.
    private func hostTools(_ screen: String) -> (() -> Void)? {
        guard model.isHost else { return nil }
        if screen == "music" { return { [model] in withAnimation { model.hostNativeMusic = true } } }
        return { [model] in withAnimation { model.setHostManages(true, screen: screen) } }
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
                                              guestView: { withAnimation { model.hostNativeMusic = false } },
                                              pageView: { withAnimation { model.manageMusicInPage() } })
                                    .transition(.opacity)
                            } else {
                                MusicView(store: music, topInset: proxy.safeAreaInsets.top, manage: hostTools("music"))
                            }
                        }
                        if model.nativeScreen == "feedback", let feedback = model.feedback {
                            FeedbackView(store: feedback, topInset: proxy.safeAreaInsets.top, admin: model.isHost ? model.feedbackAdmin : nil)
                        }
                        if model.nativeScreen == "account", let settings = model.settings {
                            SettingsView(store: settings, topInset: proxy.safeAreaInsets.top, isHost: model.isHost, hostMusic: model.hostMusic) { place in
                                withAnimation { model.show(place) }
                            }
                        }
                        if model.pageDetail != nil {
                            Button {
                                withAnimation { model.closePageDetail() }
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
                        }
                        if let managed = model.hostManagedScreen {
                            Button {
                                withAnimation { model.setHostManages(false, screen: managed) }
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
                        }
                    }
                    if let tabs = model.tabs, !tabs.hidden {
                        NativeTabBar(state: tabs, select: model.selectTab)
                            .frame(height: NativeTabBar.height + proxy.safeAreaInsets.bottom)
                            .transition(.move(edge: .bottom))
                    }
                }
                .ignoresSafeArea()
                .animation(.easeInOut(duration: 0.25), value: model.tabs?.hidden ?? true)
                if model.failed {
                    OfflineView { model.reload() }
                }
            }
        }
        .preferredColorScheme(.dark)
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

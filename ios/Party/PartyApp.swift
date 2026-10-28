import SwiftUI

/// App iOS « Party ! » : la webapp affichée en plein écran, à l'identique de l'app ajoutée à l'écran d'accueil.
@main
struct PartyApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var model = WebModel(start: AppConfig.baseURL)

    var body: some Scene {
        WindowGroup {
            ContentView(model: model)
                // Lien universel (QR code, lien partagé) ou toucher d'une notification : on l'ouvre dans l'app.
                .onOpenURL { model.open($0) }
                .onReceive(NotificationCenter.default.publisher(for: .partyOpenURL)) { note in
                    if let url = note.object as? URL { model.open(url) }
                }
        }
    }
}

struct ContentView: View {
    @ObservedObject var model: WebModel

    /// « Gérer la soirée » / « Gérer les retours » : réservé à l'hôte.
    private func hostTools(_ screen: String) -> (() -> Void)? {
        guard model.isHost else { return nil }
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
                            MusicView(store: music, topInset: proxy.safeAreaInsets.top, manage: hostTools("music"))
                        }
                        if model.nativeScreen == "feedback", let feedback = model.feedback {
                            FeedbackView(store: feedback, topInset: proxy.safeAreaInsets.top, manage: hostTools("feedback"))
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

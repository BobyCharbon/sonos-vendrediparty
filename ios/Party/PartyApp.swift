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

    var body: some View {
        ZStack {
            AppConfig.background.ignoresSafeArea()
            // La page gère elle-même les zones sûres (viewport-fit=cover + env(safe-area-inset-*)), comme la PWA.
            PartyWebView(model: model).ignoresSafeArea()
            if model.failed {
                OfflineView { model.reload() }
            }
        }
        .preferredColorScheme(.dark)
    }
}

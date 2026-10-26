import SwiftUI

/// Affiché quand le site ne répond pas (pas de réseau, serveur arrêté) au lieu d'une page blanche.
struct OfflineView: View {
    let retry: () -> Void

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "wifi.exclamationmark")
                .font(.system(size: 44, weight: .semibold))
                .foregroundStyle(.secondary)
            Text("Party ! est injoignable")
                .font(.title3.weight(.semibold))
            Text("Vérifie ta connexion puis réessaie.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Button("Réessayer", action: retry)
                .buttonStyle(.borderedProminent)
                .tint(.purple)
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(AppConfig.background.ignoresSafeArea())
        .foregroundStyle(.white)
    }
}

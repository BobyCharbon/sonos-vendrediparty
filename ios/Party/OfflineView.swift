import SwiftUI

/// Affiché quand le site ne répond pas (pas de réseau, serveur arrêté) au lieu d'une page blanche.
/// Serveur qui redémarre (mise à jour, avis eb710b132330) : « Mise à jour en cours », jamais « injoignable » :
/// les joueurs croyaient à un bug. Dans tous les cas l'app réessaie toute seule.
struct OfflineView: View {
    /// Réponses du relais quand le serveur redémarre.
    static let busyStatuses: Set<Int> = [502, 503, 504]
    static let busyRetry: Duration = .seconds(4)
    static let offlineRetry: Duration = .seconds(10)

    var busy = false
    /// Essai automatique, sans quitter cet écran (il part quand la page a vraiment chargé) : pas de clignotement.
    var quietRetry: (() -> Void)?
    let retry: () -> Void

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: busy ? "wrench.and.screwdriver.fill" : "wifi.exclamationmark")
                .font(.system(size: 44, weight: .semibold))
                .foregroundStyle(busy ? Palette.accent : .secondary)
            Text(busy ? "Mise à jour en cours" : "Party ne répond pas")
                .font(.title3.weight(.semibold))
            Text(busy ? "Party revient tout seul dans une minute. Ta partie est gardée."
                      : "Vérifie ta connexion. On réessaie tout seul.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
            if busy {
                HStack(spacing: 10) {
                    ProgressView().tint(.secondary)
                    Text("Ça revient tout seul").font(.footnote).foregroundStyle(.secondary)
                }
            } else {
                Button("Réessayer", action: retry)
                    .buttonStyle(.borderedProminent)
                    .tint(.purple)
            }
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(AppConfig.background.ignoresSafeArea())
        .foregroundStyle(.white)
        .accessibilityIdentifier(busy ? "offline-busy" : "offline")
        // Nouvel essai tout seul : vite pendant une mise à jour, plus calmement sans réseau.
        .task(id: busy) {
            while !Task.isCancelled {
                try? await Task.sleep(for: busy ? Self.busyRetry : Self.offlineRetry)
                guard !Task.isCancelled else { return }
                (quietRetry ?? retry)()
            }
        }
    }
}

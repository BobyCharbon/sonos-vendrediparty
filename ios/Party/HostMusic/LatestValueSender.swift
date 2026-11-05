import Foundation

/// Envoie la valeur d'un curseur (volume) au serveur, de façon fluide :
/// - au plus une requête toutes les `interval` (≈ 4 par seconde) pendant le glissement ;
/// - une seule requête en vol : pendant qu'elle part, seule la dernière valeur est gardée, puis envoyée ;
/// - la valeur finale (au relâché) part toujours ;
/// - une requête en vol n'est JAMAIS annulée : annuler la tâche annulait la requête URLSession, que PartyAPI
///   traduisait en « Party ! est injoignable » alors que le serveur avait bien réglé le volume (soirée du 05.11.2026) ;
/// - une erreur n'est montrée que pour la dernière valeur voulue (pas pour une valeur déjà dépassée).
@MainActor
final class LatestValueSender {
    private let interval: Duration
    private let send: (Int) async throws -> Void
    private let onError: (Error) -> Void
    private var pending: Int?
    private var draining = false
    private var lastSentAt: ContinuousClock.Instant?
    private let clock = ContinuousClock()

    init(interval: Duration = .milliseconds(250), send: @escaping (Int) async throws -> Void,
         onError: @escaping (Error) -> Void) {
        self.interval = interval
        self.send = send
        self.onError = onError
    }

    /// Nouvelle valeur du curseur : remplace celle qui attend ; la première part tout de suite.
    func submit(_ value: Int) {
        pending = value
        guard !draining else { return }
        draining = true
        Task { await drain() }
    }

    private func drain() async {
        defer { draining = false }
        while pending != nil {
            if let lastSentAt {
                let wait = interval - (clock.now - lastSentAt)
                if wait > .zero { try? await Task.sleep(for: wait) }
            }
            guard let value = pending else { break }  // la plus récente, après l'attente
            pending = nil
            lastSentAt = clock.now
            do {
                try await send(value)
            } catch is CancellationError {
                continue
            } catch {
                if pending == nil { onError(error) }  // une valeur plus récente part déjà : pas d'alerte
            }
        }
    }
}

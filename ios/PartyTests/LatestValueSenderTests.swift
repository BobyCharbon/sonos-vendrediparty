import Foundation
import Testing
@testable import Party

/// Curseurs de volume (soirée du 05.11.2026) : « Party ! est injoignable » s'affichait alors que le serveur réglait bien
/// le volume. Cause : chaque mouvement annulait la requête précédente déjà partie.
@MainActor
struct LatestValueSenderTests {
    /// Faux serveur : chaque requête dure `delay` ; garde les valeurs reçues et le nombre de requêtes simultanées.
    final class FakeServer {
        var received: [Int] = []
        var inFlight = 0
        var maxInFlight = 0
        var failing: Set<Int> = []
        let delay: Duration

        init(delay: Duration) { self.delay = delay }

        func send(_ value: Int) async throws {
            inFlight += 1
            maxInFlight = max(maxInFlight, inFlight)
            defer { inFlight -= 1 }
            try await Task.sleep(for: delay)
            received.append(value)
            if failing.contains(value) { throw PartyAPIError.offline }
        }
    }

    private func waitIdle(_ server: FakeServer, until: @escaping () -> Bool) async {
        for _ in 0..<200 where !until() { try? await Task.sleep(for: .milliseconds(20)) }
    }

    @Test("Glissé continu : une requête en vol au plus, ≈ 4 par seconde, la valeur finale arrive, aucune erreur")
    func throttlesAndKeepsTheLastValue() async {
        let server = FakeServer(delay: .milliseconds(120))
        var errors: [Error] = []
        let sender = LatestValueSender(interval: .milliseconds(250), send: server.send, onError: { errors.append($0) })
        for value in 0...60 {  // 60 mouvements en ~1,2 s
            sender.submit(value)
            try? await Task.sleep(for: .milliseconds(20))
        }
        await waitIdle(server) { server.received.last == 60 && server.inFlight == 0 }
        #expect(server.received.last == 60)
        #expect(server.received.first == 0)
        #expect(server.maxInFlight == 1)
        #expect(server.received.count <= 8)
        #expect(errors.isEmpty)
    }

    @Test("Une erreur sur une valeur dépassée par une plus récente n'est pas montrée")
    func supersededFailureIsSilent() async {
        let server = FakeServer(delay: .milliseconds(80))
        server.failing = [10]
        var errors: [Error] = []
        let sender = LatestValueSender(interval: .milliseconds(50), send: server.send, onError: { errors.append($0) })
        sender.submit(10)
        try? await Task.sleep(for: .milliseconds(20))
        sender.submit(20)  // arrive pendant que 10 est en vol
        await waitIdle(server) { server.received.last == 20 && server.inFlight == 0 }
        #expect(server.received == [10, 20])
        #expect(errors.isEmpty)
    }

    @Test("La dernière valeur en échec est signalée (vraie panne)")
    func lastFailureIsShown() async {
        let server = FakeServer(delay: .milliseconds(10))
        server.failing = [30]
        var errors: [Error] = []
        let sender = LatestValueSender(interval: .milliseconds(50), send: server.send, onError: { errors.append($0) })
        sender.submit(30)
        await waitIdle(server) { !errors.isEmpty }
        #expect(errors.count == 1)
    }

    @Test("Une annulation n'est jamais signalée comme « injoignable »")
    func cancellationIsSilent() async {
        var errors: [Error] = []
        var calls = 0
        let sender = LatestValueSender(interval: .milliseconds(10), send: { _ in
            calls += 1
            throw CancellationError()
        }, onError: { errors.append($0) })
        sender.submit(5)
        for _ in 0..<20 where calls == 0 { try? await Task.sleep(for: .milliseconds(10)) }
        try? await Task.sleep(for: .milliseconds(30))
        #expect(calls == 1)
        #expect(errors.isEmpty)
    }
}

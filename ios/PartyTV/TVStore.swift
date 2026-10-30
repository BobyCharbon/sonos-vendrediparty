import SwiftUI

/// État de l'app Apple TV : code admin → code de la partie → la partie en direct (chaque seconde) et la musique
/// (toutes les 5 s). Session admin expirée : reconnexion silencieuse avec le code gardé dans le trousseau.
@MainActor
final class TVStore: ObservableObject {
    enum Screen: Equatable { case pin, code, watching(String) }

    static let gameEvery: Duration = .seconds(1)
    static let musicEvery: Duration = .seconds(5)

    @Published private(set) var screen: Screen
    @Published private(set) var game: JSON = .null
    @Published private(set) var music: JSON = .null
    @Published private(set) var problem: String?
    @Published private(set) var busy = false
    /// Parties en cours de la soirée (raccourci sur l'écran du code).
    @Published private(set) var games: [JSON] = []

    private let client: TVClient
    private var loops: [Task<Void, Never>] = []
    /// Démonstration (simulateur, captures) : partie figée, aucun appel au site.
    private let demo: Bool
    /// Démonstration en deux temps : l'état « avant » d'abord, puis la partie (pour voir l'annonce d'un résultat).
    private var demoNext: JSON?

    init(client: TVClient = TVClient(), demo: (game: JSON, music: JSON)? = nil, before: JSON = .null) {
        self.client = client
        self.demo = demo != nil
        if let demo {
            screen = .watching(demo.game["code"].string ?? "0000")
            game = before.isNull ? demo.game : before
            demoNext = before.isNull ? nil : demo.game
            music = demo.music
        } else {
            screen = PinVault.read() == nil ? .pin : .code
        }
    }

    /// Adresse que les téléphones ouvrent pour rejoindre la partie regardée (QR code de la télé).
    var joinURL: URL? {
        guard case .watching(let code) = screen,
              var parts = URLComponents(url: client.base, resolvingAgainstBaseURL: false) else { return nil }
        parts.path = "/"
        parts.queryItems = [URLQueryItem(name: "game", value: code)]
        return parts.url
    }

    func submitPin(_ pin: String) async {
        let pin = pin.filter(\.isNumber)
        guard !pin.isEmpty else { return }
        busy = true
        defer { busy = false }
        do {
            try await client.login(pin: pin)
            PinVault.save(pin)
            problem = nil
            screen = .code
            await refreshMusic()
        } catch {
            problem = error.localizedDescription
        }
    }

    /// Code à 4 chiffres : la partie s'ouvre si elle existe.
    func watch(_ code: String) async {
        let code = code.filter(\.isNumber)
        guard code.count == 4 else { return problem = "Le code d'une partie a 4 chiffres." }
        busy = true
        defer { busy = false }
        do {
            let (json, status) = try await authorized("api/tv/game/\(code)")
            guard status == 200 else { throw TVError.notFound(json["detail"]["message"].string ?? json["detail"].string ?? "Partie introuvable ou terminée.") }
            game = json
            problem = nil
            screen = .watching(code)
            start(code)
        } catch {
            problem = error.localizedDescription
        }
    }

    func leave() {
        stop()
        game = .null
        screen = .code
        Task { await refreshMusic() }
    }

    func forgetPin() {
        stop()
        PinVault.forget()
        screen = .pin
    }

    func appear() async {
        if demo, let next = demoNext {
            demoNext = nil
            try? await Task.sleep(for: .seconds(1.5))
            game = next
        }
        guard !demo else { return }
        if screen == .code { await refreshMusic() }
        if case .watching(let code) = screen, loops.isEmpty { start(code) }
    }

    private func start(_ code: String) {
        stop()
        loops.append(Task { [weak self] in
            while !Task.isCancelled {
                await self?.refreshGame(code)
                try? await Task.sleep(for: Self.gameEvery)
            }
        })
        loops.append(Task { [weak self] in
            while !Task.isCancelled {
                await self?.refreshMusic()
                try? await Task.sleep(for: Self.musicEvery)
            }
        })
    }

    func stop() {
        loops.forEach { $0.cancel() }
        loops = []
    }

    private func refreshGame(_ code: String) async {
        guard let (json, status) = try? await authorized("api/tv/game/\(code)") else {
            return problem = TVError.offline.localizedDescription
        }
        if status == 404 {
            problem = "Cette partie est terminée."
            game = json["detail"]["ended"].isNull ? game : game
            return
        }
        guard status == 200 else { return }
        problem = nil
        if json != game { game = json }
    }

    func refreshMusic() async {
        guard let (json, status) = try? await authorized("api/tv"), status == 200 else { return }
        if json != music { music = json }
        games = json["games"].array
    }

    /// Requête de l'hôte ; si la session a expiré, reconnexion avec le code admin du trousseau puis nouvel essai.
    private func authorized(_ path: String) async throws -> (JSON, Int) {
        let first = try await client.get(path)
        guard first.1 == 401, let pin = PinVault.read() else { return first }
        do {
            try await client.login(pin: pin)
        } catch TVError.badPin {
            PinVault.forget()
            stop()
            screen = .pin
            throw TVError.badPin
        }
        return try await client.get(path)
    }
}

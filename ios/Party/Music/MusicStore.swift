import Combine
import Foundation
import UIKit

/// Invité tel que la page web le connaît (localStorage : vp_guest, vp_name) : même identité dans les deux écrans.
struct GuestIdentity: Equatable {
    let id: String
    var name: String
}

/// Accès de l'écran natif à la page web : identité de l'invité et réglages partagés (localStorage).
@MainActor
protocol WebStorage: AnyObject {
    func guestIdentity() async -> GuestIdentity?
    func readLocal(_ key: String) async -> String?
    func writeLocal(_ key: String, _ value: String?)
    /// Copie la session pour l'extension « Partager ».
    func shareSession() async
    /// La page recalcule la pastille de « Ton avis » (retours vus ou envoyés depuis l'écran natif).
    func refreshFeedbackBadge()
    /// Ouvre une adresse du site dans la page (QR code d'une partie de jeu…).
    func openInPage(_ url: URL)
}

/// Onglet Musique natif : état de la soirée en direct, recherche, ajout, messages à l'hôte.
@MainActor
final class MusicStore: ObservableObject {
    enum Phase: Equatable {
        case loading
        case needsCode
        case closed
        case ready(PartyState)
        case offline(String)
    }

    struct Notice: Equatable {
        let text: String
        let isError: Bool
    }

    @Published private(set) var phase: Phase = .loading
    /// Moment de la dernière réponse : les heures de passage (eta) en dépendent.
    @Published private(set) var receivedAt = Date()
    @Published var query = "" { didSet { scheduleSearch() } }
    @Published private(set) var results: [SpotifyTrack] = []
    @Published private(set) var searching = false
    @Published private(set) var busyTrack: String?
    @Published var notice: Notice?
    /// Prénom demandé avant le premier ajout (même règle que la page web).
    @Published var asksName = false
    @Published private(set) var notifyWhenPlaying = false

    private let api: PartyAPI
    private weak var web: WebStorage?
    private var identity: GuestIdentity?
    private var waitingTrack: SpotifyTrack?
    private var liveTask: Task<Void, Never>?
    private var searchTask: Task<Void, Never>?

    private static let searchDelay: Duration = .milliseconds(350)
    private static let reconnectDelay: Duration = .seconds(3)
    private static let minimumQuery = 2
    private static let pushKey = "vp_native_push:/"
    private static let artworkAttempts = 2
    private static let artworkRetryDelay: Duration = .seconds(2)

    init(api: PartyAPI, web: WebStorage) {
        self.api = api
        self.web = web
    }

    private let artCache = NSCache<NSString, UIImage>()

    /// L'enceinte Sonos met parfois trop de temps à fournir une pochette : une seconde tentative un peu plus tard.
    func artwork(_ path: String) async -> UIImage? {
        guard !path.isEmpty else { return nil }
        if let hit = artCache.object(forKey: path as NSString) { return hit }
        for attempt in 0..<Self.artworkAttempts {
            if attempt > 0 { try? await Task.sleep(for: Self.artworkRetryDelay) }
            guard !Task.isCancelled else { return nil }
            if let data = await api.imageData(path), let image = UIImage(data: data) {
                artCache.setObject(image, forKey: path as NSString)
                return image
            }
        }
        return nil
    }

    // MARK: Cycle de vie : actif tant que l'onglet est affiché

    func start() {
        Task { await reload() }
        guard liveTask == nil else { return }
        liveTask = Task { [weak self] in await self?.followLiveEvents() }
    }

    func stop() {
        liveTask?.cancel()
        liveTask = nil
    }

    private func followLiveEvents() async {
        while !Task.isCancelled {
            do {
                for try await line in try await api.liveEvents().lines where line.hasPrefix("data:") {
                    await reload()
                }
            } catch {
                // Coupure réseau ou serveur redémarré : on se reconnecte.
            }
            try? await Task.sleep(for: Self.reconnectDelay)
        }
    }

    func reload() async {
        guard let me = await currentIdentity() else { return }
        do {
            let state = try await api.state(guestID: me.id)
            receivedAt = Date()
            phase = state.active ? .ready(state) : .closed
            if let serverName = state.name, !serverName.isEmpty, serverName != me.name { remember(name: serverName) }
            notifyWhenPlaying = await hasPushSubscription()
            await web?.shareSession()
        } catch PartyAPIError.needsCode {
            phase = .needsCode
        } catch {
            if case .ready = phase { return }  // une coupure brève ne fait pas disparaître la soirée affichée
            phase = .offline(error.localizedDescription)
        }
    }

    // MARK: Actions

    func join(code: String) async {
        let code = code.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !code.isEmpty else { return }
        do {
            try await api.join(code: code)
            await reload()
        } catch {
            show(error)
        }
    }

    /// QR code scanné : code de la soirée → rejoindre ; partie de jeu → ouverte dans la page.
    func handleScanned(_ text: String) async {
        switch PartyLink.parse(text, isInternal: AppConfig.isInternal) {
        case .party(let code)?:
            await join(code: code)
            if case .ready = phase { notice = Notice(text: "Bienvenue dans la soirée 🎉", isError: false) }
        case .page(let url)?:
            web?.openInPage(url)
        case nil:
            notice = Notice(text: "Ce QR code n'est pas celui d'une soirée Party", isError: true)
        }
    }

    func add(_ track: SpotifyTrack) async {
        guard let me = await currentIdentity() else { return }
        guard !me.name.isEmpty else {
            waitingTrack = track
            asksName = true
            return
        }
        busyTrack = track.id
        defer { busyTrack = nil }
        do {
            try await api.enqueue(trackID: track.id, guestID: me.id, name: me.name)
            query = ""
            notice = Notice(text: "« \(track.title) » ajouté 🎶", isError: false)
            await reload()
        } catch {
            show(error)
        }
    }

    func confirm(name: String) async {
        let name = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !name.isEmpty, let me = await currentIdentity() else { return }
        remember(name: name)
        try? await api.hello(guestID: me.id, name: name)
        if let track = waitingTrack {
            waitingTrack = nil
            await add(track)
        }
    }

    func remove(_ item: QueueItem) async {
        guard let rid = item.rid, let me = await currentIdentity() else { return }
        do {
            try await api.remove(requestID: rid, guestID: me.id)
            await reload()
        } catch {
            show(error)
        }
    }

    func send(message: String) async -> Bool {
        let text = message.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, let me = await currentIdentity() else { return false }
        do {
            try await api.message(text, guestID: me.id, name: me.name.isEmpty ? "Invité" : me.name)
            notice = Notice(text: "Message envoyé à l'hôte", isError: false)
            await reload()
            return true
        } catch {
            show(error)
            return false
        }
    }

    func setNotifyWhenPlaying(_ on: Bool) async {
        guard let me = await currentIdentity() else { return }
        do {
            if on {
                let token = try await PushRegistrar.shared.register()
                let device: [String: Any] = [
                    "endpoint": "apns:\(token)",
                    "apns": ["token": token, "environment": PushRegistrar.environment,
                             "topic": Bundle.main.bundleIdentifier ?? ""],
                ]
                try await api.subscribePush(guestID: me.id, device: device)
                web?.writeLocal(Self.pushKey, String(data: try JSONSerialization.data(withJSONObject: device), encoding: .utf8))
                notice = Notice(text: "Tu seras prévenu quand ton titre passe 🔔", isError: false)
            } else {
                if let saved = await web?.readLocal(Self.pushKey),
                   let data = saved.data(using: .utf8),
                   let endpoint = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["endpoint"] as? String {
                    try? await api.unsubscribePush(endpoint: endpoint)
                }
                web?.writeLocal(Self.pushKey, nil)
            }
        } catch {
            show(error)
        }
        notifyWhenPlaying = await hasPushSubscription()
    }

    // MARK: Recherche

    private func scheduleSearch() {
        searchTask?.cancel()
        let text = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard text.count >= Self.minimumQuery else {
            results = []
            searching = false
            return
        }
        searchTask = Task { [weak self] in
            try? await Task.sleep(for: Self.searchDelay)
            guard !Task.isCancelled, let self else { return }
            self.searching = true
            defer { self.searching = false }
            do {
                let found = try await self.api.search(text)
                if !Task.isCancelled { self.results = found }
            } catch {
                if !Task.isCancelled { self.show(error) }
            }
        }
    }

    // MARK: Outils

    private func currentIdentity() async -> GuestIdentity? {
        if let identity { return identity }
        identity = await web?.guestIdentity()
        return identity
    }

    private func remember(name: String) {
        identity?.name = name
        web?.writeLocal("vp_name", name)
    }

    private func hasPushSubscription() async -> Bool {
        guard await web?.readLocal(Self.pushKey) != nil else { return false }
        return await PushRegistrar.shared.status() == "granted"
    }

    private func show(_ error: Error) {
        if case PartyAPIError.needsCode = error { phase = .needsCode; return }
        notice = Notice(text: error.localizedDescription, isError: true)
    }
}

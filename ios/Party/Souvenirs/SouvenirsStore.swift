import Photos
import SwiftUI
import UIKit

/// Souvenirs : appels au serveur Party avec le jeton du compte (relais `POST /api/account/souvenirs/rpc` et envoi
/// `POST /api/account/souvenirs/photo?event_id=`, corps brut, `Authorization: Bearer`). Refus : `SouvenirRefusal`.
@MainActor
final class SouvenirsStore: ObservableObject {
    /// Bulles des Discussions (souvenir_stories) : stories ouvertes (néon) et soirées au labo (grises, cadenas).
    @Published private(set) var bubbles: [SouvenirBubble] = []

    private let api: PartyAPI
    private weak var web: WebStorage?
    private let session: URLSession
    /// CGU à accepter avant la première photo (TermsAcceptSheet).
    private(set) lazy var moderation = ModerationStore(api: api, web: web)
    /// Toucher d'une bulle : la story s'ouvre (WebModel).
    var openStory: (String) -> Void = { _ in }

    /// protocolClasses : serveur simulé des tests (URLProtocol) ; nil en vrai.
    init(api: PartyAPI, web: WebStorage?, protocolClasses: [AnyClass]? = nil) {
        self.api = api
        self.web = web
        let config = URLSessionConfiguration.default
        if let protocolClasses { config.protocolClasses = protocolClasses }
        config.httpCookieStorage = nil
        config.httpShouldSetCookies = false
        config.requestCachePolicy = .reloadIgnoringLocalCacheData
        config.timeoutIntervalForRequest = 25
        config.httpAdditionalHeaders = ["X-Party-Native": "ios"]
        session = URLSession(configuration: config)
    }

    static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }()

    // MARK: Relais

    private func token() async throws -> String {
        guard let token = await web?.accountToken() else {
            throw SouvenirRefusal(code: "forbidden", detail: "Connecte-toi à Party pour les Souvenirs.")
        }
        return token
    }

    /// La réponse de la base (« result ») décodée en T.
    func call<T: Decodable>(_ fn: String, _ args: [String: Any] = [:], as: T.Type = T.self) async throws -> T {
        guard let url = api.url("/api/account/souvenirs/rpc") else { throw PartyAPIError.offline }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: ["token": try await token(), "fn": fn, "args": args])
        let data = try await send(request)
        let reply = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
        let result = try JSONSerialization.data(withJSONObject: reply?["result"] ?? NSNull(), options: [.fragmentsAllowed])
        return try Self.decoder.decode(T.self, from: result)
    }

    func run(_ fn: String, _ args: [String: Any] = [:]) async throws {
        _ = try await call(fn, args, as: SouvenirAnyReply.self)
    }

    /// Réponse ou refus lisible : 2xx → données ; {"code", "detail"} → SouvenirRefusal ; 401 → reconnexion.
    private func send(_ request: URLRequest) async throws -> Data {
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw PartyAPIError.offline
        }
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        if (200..<300).contains(status) { return data }
        let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
        let detail = json?["detail"] as? String ?? ""
        if let code = json?["code"] as? String { throw SouvenirRefusal(code: code, detail: detail) }
        if status == 401 { throw SouvenirRefusal(code: "expired", detail: "Ta connexion a expiré. Reconnecte-toi.") }
        if status >= 500 { throw PartyAPIError.offline }
        throw SouvenirRefusal(code: "error", detail: detail)
    }

    // MARK: Appareil photo

    func counter(_ event: String) async throws -> SouvenirCounter {
        try await call("souvenir_counter", ["e": event])
    }

    /// La photo part au labo : le serveur retire EXIF / GPS, réduit, dépose, puis la base l'enregistre (souvenir_take).
    func upload(_ jpeg: Data, event: String) async throws -> SouvenirTaken {
        guard var parts = api.url("/api/account/souvenirs/photo").flatMap({ URLComponents(url: $0, resolvingAgainstBaseURL: true) })
        else { throw PartyAPIError.offline }
        parts.queryItems = [URLQueryItem(name: "event_id", value: event)]
        guard let url = parts.url else { throw PartyAPIError.offline }
        var request = URLRequest(url: url, timeoutInterval: 60)
        request.httpMethod = "POST"
        request.setValue("image/jpeg", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(try await token())", forHTTPHeaderField: "Authorization")
        request.httpBody = jpeg
        return try Self.decoder.decode(SouvenirTaken.self, from: try await send(request))
    }

    /// « Annuler » (5 s à l'écran, 8 s en base) : la photo est effacée sans être revue ; rend le nombre de poses restantes.
    func cancel(_ photo: String) async throws -> Int? {
        struct Cancelled: Decodable { let left: Int? }
        return try await call("souvenir_cancel", ["id": photo], as: Cancelled.self).left
    }

    // MARK: Story

    func story(_ event: String) async throws -> SouvenirStory {
        try await call("souvenir_story", ["e": event])
    }

    /// ⭐ Garder / Gardée : true si la photo est maintenant dans mes souvenirs.
    func setKept(_ photo: String, _ on: Bool) async throws -> Bool {
        struct Kept: Decodable { let kept: Bool }
        return try await call(on ? "souvenir_keep" : "souvenir_unkeep", ["id": photo], as: Kept.self).kept
    }

    func markSeen(_ event: String) async {
        try? await run("souvenir_mark_seen", ["e": event])
        if let i = bubbles.firstIndex(where: { $0.eventId == event && !$0.waiting }), bubbles[i].seen != true {
            bubbles[i] = SouvenirBubble(eventId: bubbles[i].eventId, title: bubbles[i].title, phase: bubbles[i].phase,
                                        revealAt: bubbles[i].revealAt, until: bubbles[i].until, count: bubbles[i].count, seen: true)
        }
    }

    /// Signaler (type souvenir) : la photo est masquée aussitôt pour tous ; organisation et modération prévenues.
    func report(_ photo: String, reason: SouvenirReportReason) async throws {
        try await run("report_content", ["p_kind": "souvenir", "p_target": photo, "p_reason": reason.rawValue])
    }

    /// Bloquer (set_direct_block, comme dans les Discussions) : ses photos disparaissent, dans les deux sens.
    func block(_ user: String) async throws {
        let token = try await token()
        do {
            try await api.blockDirect(token: token, user: user, on: true)
        } catch PartyAPIError.server(let message) {
            throw SouvenirRefusal(code: "error", detail: message)
        }
    }

    // MARK: Bulles des Discussions

    func refreshBubbles() async {
        guard let list: [SouvenirBubble] = try? await call("souvenir_stories") else { return }
        if list != bubbles { Motion.animate(Motion.smooth) { bubbles = list } }
    }

    // MARK: Photothèque

    /// `PartyNative.souvenirs.save(url)` : la photo dans la Photothèque (accès « ajouter seulement »). Rend nil si c'est
    /// fait, sinon la phrase à montrer.
    func save(_ url: URL) async -> String? {
        guard SouvenirLinks.savable(url) else { return "Cette photo ne peut pas être enregistrée." }
        guard let (data, response) = try? await session.data(from: url),
              (response as? HTTPURLResponse)?.statusCode ?? 200 < 300, let image = UIImage(data: data) else {
            return "La photo n'a pas pu être chargée. Réessaie."
        }
        return await Self.addToPhotos(image)
    }

    static func addToPhotos(_ image: UIImage) async -> String? {
        let status = await PHPhotoLibrary.requestAuthorization(for: .addOnly)
        guard status == .authorized || status == .limited else {
            return "Autorise Party à ajouter des photos dans Réglages › Party › Photos."
        }
        do {
            try await PHPhotoLibrary.shared().performChanges { PHAssetChangeRequest.creationRequestForAsset(from: image) }
            return nil
        } catch {
            return "La photo n'a pas pu être enregistrée. Réessaie."
        }
    }
}

/// Réponse JSON quelconque (fonctions dont on n'utilise pas le résultat).
private enum SouvenirAnyReply: Decodable {
    case any

    init(from decoder: Decoder) throws { self = .any }
}

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

    /// La photo part au labo, telle quelle : la base l'enregistre (souvenir_take), puis le serveur garde l'original 7 jours
    /// (GPS et numéros de série retirés) et fait la version écran.
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

    /// `PartyNative.souvenirs.save(url)` : la photo dans la Photothèque (accès « ajouter seulement »), le fichier tel que
    /// le serveur le donne (l'original pendant 7 jours, avec sa date de prise). Rend nil si c'est fait, sinon la phrase.
    func save(_ url: URL) async -> String? {
        guard SouvenirLinks.savable(url) else { return "Cette photo ne peut pas être enregistrée." }
        guard let (data, response) = try? await session.data(from: url),
              (response as? HTTPURLResponse)?.statusCode ?? 200 < 300, UIImage(data: data) != nil else {
            return "La photo n'a pas pu être chargée. Réessaie."
        }
        return await Self.addToPhotos(data)
    }

    static func addToPhotos(_ data: Data) async -> String? {
        let status = await PHPhotoLibrary.requestAuthorization(for: .addOnly)
        guard status == .authorized || status == .limited else {
            return "Autorise Party à ajouter des photos dans Réglages › Party › Photos."
        }
        do {
            try await PHPhotoLibrary.shared().performChanges {
                PHAssetCreationRequest.forAsset().addResource(with: .photo, data: data, options: nil)
            }
            return nil
        } catch {
            return "La photo n'a pas pu être enregistrée. Réessaie."
        }
    }

    // MARK: Photos vues

    /// La version écran d'une photo de la story : d'abord le cache (photos déjà vues), sinon le serveur (lien signé).
    func image(for photo: SouvenirPhoto) async -> UIImage? {
        if let hit = SouvenirImageCache.shared.image(photo.id) { return hit }
        guard let raw = photo.url, let url = SouvenirLinks.resolve(raw),
              let (data, response) = try? await session.data(from: url),
              (response as? HTTPURLResponse)?.statusCode == 200, let image = UIImage(data: data) else { return nil }
        SouvenirImageCache.shared.store(data, image: image, id: photo.id)
        return image
    }
}

/// Photos déjà vues (version écran 2048 px) : en mémoire et dans Caches/souvenirs, rangées par photo (le lien signé change
/// à chaque lecture, la photo non) : rouvrir la story ne retélécharge rien. Seules les photos que la base liste encore sont
/// demandées au cache (une photo retirée ou signalée ne revient jamais) ; 3 jours au plus sur l'appareil.
final class SouvenirImageCache {
    static let shared = SouvenirImageCache()
    static let maxAge: TimeInterval = 3 * 86_400

    private let memory = NSCache<NSString, UIImage>()
    private let folder: URL?

    init(folder: URL? = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first?
        .appendingPathComponent("souvenirs", isDirectory: true)) {
        self.folder = folder
        memory.countLimit = 40
        trim()
    }

    private func file(_ id: String) -> URL? {
        guard let id = UUID(uuidString: id)?.uuidString.lowercased() else { return nil }
        return folder?.appendingPathComponent("\(id).jpg")
    }

    func image(_ id: String) -> UIImage? {
        if let hit = memory.object(forKey: id as NSString) { return hit }
        guard let file = file(id), let data = try? Data(contentsOf: file), let image = UIImage(data: data) else { return nil }
        memory.setObject(image, forKey: id as NSString)
        return image
    }

    func store(_ data: Data, image: UIImage, id: String) {
        memory.setObject(image, forKey: id as NSString)
        guard let folder, let file = file(id) else { return }
        try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        try? data.write(to: file, options: [.atomic, .completeFileProtection])
    }

    /// Plus vieilles que 3 jours : effacées (la story dure 24 h).
    func trim(now: Date = Date()) {
        guard let folder, let files = try? FileManager.default.contentsOfDirectory(
            at: folder, includingPropertiesForKeys: [.contentModificationDateKey]) else { return }
        for f in files {
            let at = (try? f.resourceValues(forKeys: [.contentModificationDateKey]))?.contentModificationDate ?? .distantPast
            if now.timeIntervalSince(at) > Self.maxAge { try? FileManager.default.removeItem(at: f) }
        }
    }
}

/// Réponse JSON quelconque (fonctions dont on n'utilise pas le résultat).
private enum SouvenirAnyReply: Decodable {
    case any

    init(from decoder: Decoder) throws { self = .any }
}

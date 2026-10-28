import Foundation
import OSLog

enum PartyAPIError: LocalizedError, Equatable {
    /// Le code de la soirée est demandé (cookie absent ou nouveau code).
    case needsCode
    /// Message du serveur (« Ce titre est déjà dans la file 🙂 »…).
    case server(String)
    /// Titre déjà dans la file : à confirmer (ajout de l'hôte).
    case duplicate(String)
    case offline

    var errorDescription: String? {
        switch self {
        case .needsCode: return "Code de la soirée requis"
        case .server(let message), .duplicate(let message): return message
        case .offline: return "Party ! est injoignable : vérifie ta connexion"
        }
    }
}

/// Cookies de la session (code d'accès, compte) : ceux de la vue web dans l'app (WebCookieJar),
/// une copie prise dans le trousseau partagé dans l'extension « Partager » (SharedSession).
@MainActor
protocol CookieJar: AnyObject {
    func allCookies() async -> [HTTPCookie]
    func keep(_ cookies: [HTTPCookie]) async
}

/// Appels au serveur Party pour les écrans natifs, avec la MÊME session que la vue web : les cookies sont
/// joints à chaque appel, et ceux que le serveur pose sont rangés.
/// (Un HTTPCookieStorage à part n'est pas fiable sur iOS : les cookies passent donc explicitement.)
@MainActor
final class PartyAPI {
    private let base: URL
    private let jar: CookieJar
    private let session: URLSession
    private let log = Logger(subsystem: "ch.bobycharbon.party", category: "api")

    init(base: URL, jar: CookieJar) {
        self.base = base
        self.jar = jar
        let config = URLSessionConfiguration.default
        config.httpCookieStorage = nil
        config.httpShouldSetCookies = false
        config.httpCookieAcceptPolicy = .never
        config.requestCachePolicy = .reloadIgnoringLocalCacheData
        config.timeoutIntervalForRequest = 15
        // L'app se signale : l'hôte connecté n'a pas à saisir le code des invités (app/main.py, require_guest).
        config.httpAdditionalHeaders = ["X-Party-Native": "ios"]
        session = URLSession(configuration: config)
    }

    func url(_ path: String) -> URL? {
        URL(string: path, relativeTo: base)?.absoluteURL
    }

    func state(guestID: String) async throws -> PartyState {
        try await get("/api/state", query: ["guest_id": guestID])
    }

    func search(_ query: String) async throws -> [SpotifyTrack] {
        try await get("/api/search", query: ["q": query])
    }

    func join(code: String) async throws {
        try await post("/api/join", body: ["pin": code])
    }

    func hello(guestID: String, name: String) async throws {
        try await post("/api/hello", body: ["guest_id": guestID, "guest_name": name])
    }

    func enqueue(trackID: String, guestID: String, name: String) async throws {
        try await post("/api/queue", body: ["track_id": trackID, "guest_id": guestID, "guest_name": name])
    }

    func message(_ text: String, guestID: String, name: String) async throws {
        try await post("/api/message", body: ["guest_id": guestID, "guest_name": name, "text": text])
    }

    /// Notification « ton titre passe » : appareil inscrit chez Apple (APNs), comme push.js dans l'app.
    /// keepPrefs : abonnement depuis les Réglages, sans allumer « Mon titre passe » (sinon le serveur l'allume).
    func subscribePush(guestID: String, device: [String: Any], keepPrefs: Bool = false) async throws {
        try await post("/api/push/subscribe", body: ["guest_id": guestID, "subscription": device, "keep_prefs": keepPrefs])
    }

    func unsubscribePush(endpoint: String) async throws {
        try await post("/api/push/unsubscribe", body: ["endpoint": endpoint])
    }

    /// Live Activity tenue à jour par le serveur : jeton de l'activité d'une demande (vide : plus suivie).
    func activityToken(guestID: String, requestID: String, token: String, environment: String) async throws {
        try await post("/api/activity", body: ["guest_id": guestID, "request_id": requestID, "token": token,
                                               "environment": environment, "topic": Bundle.main.bundleIdentifier ?? ""])
    }

    /// Jeton de démarrage par push (iOS 17.2+) ; vide : plus de démarrage (réglage coupé).
    func activityStartToken(guestID: String, token: String, environment: String) async throws {
        try await post("/api/activity/start", body: ["guest_id": guestID, "token": token,
                                                     "environment": environment, "topic": Bundle.main.bundleIdentifier ?? ""])
    }

    func remove(requestID: String, guestID: String) async throws {
        try await post("/api/queue/remove", body: ["request_id": requestID, "guest_id": guestID])
    }

    // MARK: Réglages › Notifications

    /// Ce que l'invité reçoit du serveur Party (titre qui passe, réponse à ses avis, nouvelles parties).
    func notifyPrefs(guestID: String) async throws -> GuestNotifyState {
        try await get("/api/notify", query: ["guest_id": guestID])
    }

    func setNotify(guestID: String, kind: String, on: Bool) async throws -> GuestNotifyState {
        try await postDecoding("/api/notify", body: ["guest_id": guestID, "kind": kind, "on": on])
    }

    /// Hôte seulement (session vp_admin) : messages, nouvelles parties, nouveaux avis.
    func adminNotifyPrefs() async throws -> AdminNotifyState {
        try await get("/api/admin/notify", query: [:])
    }

    func setAdminNotify(kind: String, on: Bool) async throws -> AdminNotifyState {
        try await postDecoding("/api/admin/notify", body: ["kind": kind, "on": on])
    }

    func subscribeAdminPush(device: [String: Any]) async throws {
        try await post("/api/admin/push/subscribe", body: ["subscription": device])
    }

    /// Préférences des événements du compte (Supabase), avec le jeton de session du membre.
    func eventNotifyPrefs(token: String) async throws -> EventNotifyState {
        try await postDecoding("/api/account/notifications", body: ["token": token])
    }

    /// patch : champs de notification_prefs ; NSNull() coupe les heures de silence.
    func updateEventNotifyPrefs(token: String, patch: [String: Any]) async throws -> EventNotifyState {
        try await postDecoding("/api/account/notifications/update", body: ["token": token, "patch": patch])
    }

    // MARK: Réglages › Mon profil (session du compte)

    func profile(token: String) async throws -> MemberProfile {
        try await postDecoding("/api/account/profile", body: ["token": token])
    }

    /// photo : JPEG carré déjà réduit (ProfilePhoto.jpeg) ; nil garde la photo actuelle.
    func updateProfile(token: String, firstName: String, lastName: String, nickname: String, photo: Data?) async throws -> MemberProfile {
        var body: [String: Any] = ["token": token, "first_name": firstName, "last_name": lastName, "display_name": nickname]
        if let photo { body["photo"] = photo.base64EncodedString() }
        return try await postDecoding("/api/account/profile/update", body: body)
    }

    /// Notifications des événements du compte sur cet iPhone (jeton APNs, envoyé par Supabase).
    func registerEventsPush(token: String, device: String, on: Bool) async throws {
        try await post("/api/account/push", body: ["token": token, "device": device, "on": on])
    }

    func subscriptions(token: String) async throws -> Subscriptions {
        try await postDecoding("/api/account/subscriptions", body: ["token": token])
    }

    /// kind : category | tag.
    func setSubscription(token: String, kind: String, id: String, on: Bool) async throws -> Subscriptions {
        try await postDecoding("/api/account/subscriptions/set", body: ["token": token, "kind": kind, "id": id, "on": on])
    }

    // MARK: Ton avis (pas besoin du code de la soirée)

    func feedback(guestID: String) async throws -> [FeedbackItem] {
        let list: FeedbackList = try await get("/api/feedback", query: ["guest_id": guestID])
        return list.mine
    }

    func sendFeedback(guestID: String, name: String, kind: String, text: String, fromTab: String?) async throws -> [FeedbackItem] {
        var body: [String: Any] = ["guest_id": guestID, "name": name, "kind": kind, "text": text]
        if let fromTab { body["context"] = ["tab": fromTab] }  // l'onglet d'où vient l'idée, pour l'hôte
        let list: FeedbackList = try await postDecoding("/api/feedback", body: body)
        return list.mine
    }

    func markFeedbackSeen(guestID: String) async throws {
        try await post("/api/feedback/seen", body: ["guest_id": guestID])
    }

    /// Pochette : les pochettes Sonos passent par /art, réservé aux invités (cookie de la session).
    func imageData(_ path: String) async -> Data? {
        guard let url = url(path) else { return nil }
        return try? await send(URLRequest(url: url))
    }

    /// Flux en direct du serveur (SSE) : une ligne par changement d'état.
    func liveEvents() async throws -> URLSession.AsyncBytes {
        guard let url = url("/api/events") else { throw PartyAPIError.offline }
        var request = URLRequest(url: url, timeoutInterval: .infinity)
        request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
        await attachCookies(to: &request)
        let (bytes, _) = try await session.bytes(for: request)
        return bytes
    }

    // MARK: Requêtes

    func get<T: Decodable>(_ path: String, query: [String: String]) async throws -> T {
        guard var parts = url(path).flatMap({ URLComponents(url: $0, resolvingAgainstBaseURL: true) }) else {
            throw PartyAPIError.offline
        }
        parts.queryItems = query.map { URLQueryItem(name: $0.key, value: $0.value) }
        guard let url = parts.url else { throw PartyAPIError.offline }
        let data = try await send(URLRequest(url: url))
        return try JSONDecoder().decode(T.self, from: data)
    }

    func postDecoding<T: Decodable>(_ path: String, body: [String: Any]) async throws -> T {
        guard let url = url(path) else { throw PartyAPIError.offline }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        return try JSONDecoder().decode(T.self, from: try await send(request))
    }

    func post(_ path: String, body: [String: Any]) async throws {
        guard let url = url(path) else { throw PartyAPIError.offline }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        _ = try await send(request)
    }

    private func send(_ request: URLRequest) async throws -> Data {
        var request = request
        await attachCookies(to: &request)
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            log.error("\(request.url?.path ?? "?", privacy: .public) : \(error.localizedDescription, privacy: .public)")
            throw PartyAPIError.offline
        }
        await keepCookies(from: response)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        if !(200..<300).contains(status) {
            log.error("\(request.url?.path ?? "?", privacy: .public) : HTTP \(status)")
        }
        if status == 401 && request.url?.path != "/api/join" { throw PartyAPIError.needsCode }
        guard (200..<300).contains(status) else {
            let detail = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["detail"]
            // Doublon (ajout de l'hôte) : {"duplicate": true, "message": …} ; l'hôte décide d'ajouter quand même.
            if let info = detail as? [String: Any], info["duplicate"] as? Bool == true {
                throw PartyAPIError.duplicate(info["message"] as? String ?? "Ce titre est déjà dans la file")
            }
            throw PartyAPIError.server(detail as? String ?? (detail as? [String: Any])?["message"] as? String ?? "Erreur, réessaie")
        }
        return data
    }

    // MARK: Cookies partagés avec la vue web

    private func attachCookies(to request: inout URLRequest) async {
        guard let url = request.url else { return }
        let matching = await jar.allCookies().filter { Self.cookie($0, appliesTo: url) }
        for (field, value) in HTTPCookie.requestHeaderFields(with: matching) {
            request.setValue(value, forHTTPHeaderField: field)
        }
    }

    private func keepCookies(from response: URLResponse) async {
        guard let http = response as? HTTPURLResponse, let url = http.url,
              let fields = http.allHeaderFields as? [String: String] else { return }
        let received = HTTPCookie.cookies(withResponseHeaderFields: fields, for: url)
        if !received.isEmpty { await jar.keep(received) }
    }

    /// Règles d'envoi d'un cookie : domaine (sous-domaines compris s'il commence par « . »), chemin, HTTPS.
    nonisolated static func cookie(_ cookie: HTTPCookie, appliesTo url: URL) -> Bool {
        guard let host = url.host?.lowercased() else { return false }
        let domain = cookie.domain.lowercased()
        let bare = domain.hasPrefix(".") ? String(domain.dropFirst()) : domain
        let domainOK = host == bare || host.hasSuffix("." + bare)
        let pathOK = url.path.isEmpty ? cookie.path == "/" : url.path.hasPrefix(cookie.path)
        return domainOK && pathOK && (!cookie.isSecure || url.scheme == "https")
    }
}

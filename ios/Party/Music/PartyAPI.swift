import Foundation
import WebKit

enum PartyAPIError: LocalizedError, Equatable {
    /// Le code de la soirée est demandé (cookie absent ou nouveau code).
    case needsCode
    /// Message du serveur (« Ce titre est déjà dans la file 🙂 »…).
    case server(String)
    case offline

    var errorDescription: String? {
        switch self {
        case .needsCode: return "Code de la soirée requis"
        case .server(let message): return message
        case .offline: return "Party ! est injoignable : vérifie ta connexion"
        }
    }
}

/// Appels au serveur Party pour les écrans natifs, avec la MÊME session que la vue web :
/// les cookies (code d'accès, compte) sont repris du WKWebView avant chaque appel et rendus après.
@MainActor
final class PartyAPI {
    private let base: URL
    private let cookieStore: WKHTTPCookieStore
    private let session: URLSession
    private let cookies = HTTPCookieStorage()

    init(base: URL, cookieStore: WKHTTPCookieStore) {
        self.base = base
        self.cookieStore = cookieStore
        let config = URLSessionConfiguration.default
        config.httpCookieStorage = cookies
        config.httpShouldSetCookies = true
        config.requestCachePolicy = .reloadIgnoringLocalCacheData
        config.timeoutIntervalForRequest = 15
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
    func subscribePush(guestID: String, device: [String: Any]) async throws {
        try await post("/api/push/subscribe", body: ["guest_id": guestID, "subscription": device])
    }

    func unsubscribePush(endpoint: String) async throws {
        try await post("/api/push/unsubscribe", body: ["endpoint": endpoint])
    }

    func remove(requestID: String, guestID: String) async throws {
        try await post("/api/queue/remove", body: ["request_id": requestID, "guest_id": guestID])
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
        let (bytes, _) = try await session.bytes(for: request)
        return bytes
    }

    // MARK: Requêtes

    private func get<T: Decodable>(_ path: String, query: [String: String]) async throws -> T {
        guard var parts = url(path).flatMap({ URLComponents(url: $0, resolvingAgainstBaseURL: true) }) else {
            throw PartyAPIError.offline
        }
        parts.queryItems = query.map { URLQueryItem(name: $0.key, value: $0.value) }
        guard let url = parts.url else { throw PartyAPIError.offline }
        let data = try await send(URLRequest(url: url))
        return try JSONDecoder().decode(T.self, from: data)
    }

    private func post(_ path: String, body: [String: Any]) async throws {
        guard let url = url(path) else { throw PartyAPIError.offline }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        _ = try await send(request)
    }

    private func send(_ request: URLRequest) async throws -> Data {
        await importWebCookies()
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw PartyAPIError.offline
        }
        await exportCookies()
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        if status == 401 && request.url?.path != "/api/join" { throw PartyAPIError.needsCode }
        guard (200..<300).contains(status) else {
            let detail = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["detail"] as? String
            throw PartyAPIError.server(detail ?? "Erreur, réessaie")
        }
        return data
    }

    // MARK: Cookies partagés avec la vue web

    private func importWebCookies() async {
        for cookie in await cookieStore.allCookies() {
            cookies.setCookie(cookie)
        }
    }

    private func exportCookies() async {
        for cookie in cookies.cookies ?? [] {
            await cookieStore.setCookie(cookie)
        }
    }
}

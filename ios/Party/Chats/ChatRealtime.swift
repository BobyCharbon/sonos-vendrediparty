import Foundation

/// Temps réel des Discussions : un WebSocket vers Supabase Realtime (protocole Phoenix), avec la session du compte.
/// Chaque changement d'un message ou d'une réaction du groupe ouvert (ou de n'importe quel groupe, pour la liste)
/// appelle `changed` aussitôt : plus besoin d'attendre le rafraîchissement suivant. La base (RLS) ne transmet que
/// ce que le compte a le droit de lire. Coupé ou refusé : l'écran garde son rafraîchissement de secours.
@MainActor
final class ChatRealtime {
    struct Endpoint: Decodable, Equatable {
        let url: String
        let key: String
    }

    static let heartbeatEvery: Duration = .seconds(25)
    static let reconnectAfter: Duration = .seconds(3)

    private let endpoint: Endpoint
    private let token: String
    private let topic: String
    private let filter: String?
    private let changed: () -> Void
    private var socket: URLSessionWebSocketTask?
    private var tasks: [Task<Void, Never>] = []
    private var ref = 0
    private var stopped = false

    /// group : écoute un groupe (conversation) ; nil : tous les groupes lisibles (liste des discussions).
    init(endpoint: Endpoint, token: String, group: String?, changed: @escaping () -> Void) {
        self.endpoint = endpoint
        self.token = token
        self.topic = "realtime:party-chat-\(group ?? "list")-\(UUID().uuidString.prefix(8))"
        self.filter = group.map { "group_id=eq.\($0)" }
        self.changed = changed
    }

    func start() {
        stopped = false
        connect()
    }

    func stop() {
        stopped = true
        tasks.forEach { $0.cancel() }
        tasks = []
        socket?.cancel(with: .goingAway, reason: nil)
        socket = nil
    }

    private func nextRef() -> String {
        ref += 1
        return String(ref)
    }

    private func connect() {
        guard var parts = URLComponents(string: endpoint.url) else { return }
        parts.queryItems = [URLQueryItem(name: "apikey", value: endpoint.key), URLQueryItem(name: "vsn", value: "1.0.0")]
        guard let url = parts.url, url.scheme == "wss" else { return }
        let socket = URLSession.shared.webSocketTask(with: url)
        self.socket = socket
        socket.resume()
        send(Self.joinMessage(topic: topic, filter: filter, token: token, ref: nextRef()))
        tasks.append(Task { [weak self] in await self?.listen(socket) })
        tasks.append(Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: Self.heartbeatEvery)
                guard let self, !Task.isCancelled else { return }
                self.send(["topic": "phoenix", "event": "heartbeat", "payload": [String: Any](), "ref": self.nextRef()])
            }
        })
    }

    /// Abonnement : messages du groupe (ou de tous les groupes) et réactions ; la base filtre selon les droits du compte.
    nonisolated static func joinMessage(topic: String, filter: String?, token: String, ref: String) -> [String: Any] {
        var messages: [String: Any] = ["event": "*", "schema": "public", "table": "group_messages"]
        if let filter { messages["filter"] = filter }
        let reactions: [String: Any] = ["event": "*", "schema": "public", "table": "group_message_reactions"]
        return [
            "topic": topic, "event": "phx_join", "ref": ref, "join_ref": ref,
            "payload": ["config": ["broadcast": ["self": false], "presence": ["key": ""], "postgres_changes": [messages, reactions]],
                        "access_token": token],
        ]
    }

    private func send(_ message: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: message), let text = String(data: data, encoding: .utf8) else { return }
        socket?.send(.string(text)) { _ in }
    }

    private func listen(_ socket: URLSessionWebSocketTask) async {
        while !Task.isCancelled {
            guard let message = try? await socket.receive() else { break }
            if case .string(let text) = message, Self.isChange(text) { changed() }
        }
        // Coupure (réseau, app en arrière-plan) : on se reconnecte tant que l'écran est ouvert.
        guard !stopped, !Task.isCancelled else { return }
        try? await Task.sleep(for: Self.reconnectAfter)
        guard !stopped else { return }
        tasks.forEach { $0.cancel() }
        tasks = []
        connect()
    }

    /// Un événement « postgres_changes » (nouveau message, suppression, réaction…) ; le reste (réponses, battements) est ignoré.
    nonisolated static func isChange(_ text: String) -> Bool {
        guard let data = text.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return false }
        return json["event"] as? String == "postgres_changes"
    }
}

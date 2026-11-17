import UserNotifications
import WebKit

/// Notifications de la discussion d'un événement, façon WhatsApp (17.11.2026) : regroupées par discussion
/// (thread-id « event-chat:<id> », send-push), « Répondre » sans ouvrir l'app et « Marquer comme lu ».
/// La réponse part par la MÊME route que l'écran (/api/account/event-chat/send : filtre, CGU, blocage, « Organisation
/// seulement », @toutlemonde réservé : la base décide). Refusée ou impossible : une notification locale le dit, jamais
/// d'échec silencieux. Le toucher de la notification ouvre la discussion (url « ?tab=events&event=<id>&chat=1 »).
@MainActor
enum ChatNotificationActions {
    /// Catégories posées par send-push (`aps.category`) : avec « Répondre », ou « Marquer comme lu » seul quand la
    /// personne ne peut pas écrire (discussion « Organisation seulement », data.can_reply = false).
    nonisolated static let category = "EVENT_CHAT"
    nonisolated static let readOnlyCategory = "EVENT_CHAT_READONLY"
    nonisolated static let replyAction = "EVENT_CHAT_REPLY"
    nonisolated static let readAction = "EVENT_CHAT_READ"

    /// La page de l'app, qui détient la session du compte (jeton Supabase) : posée par WebModel.attach
    /// (`ChatNotificationActions.web = self`). App fermée (lancée en arrière-plan pour l'action) : pas de page, donc
    /// pas de jeton ; la réponse n'est pas envoyée et une notification locale invite à ouvrir Party.
    static weak var web: WebStorage?

    /// Discussion affichée à l'écran (« event-chat:<id> ») : sa notification ne s'affiche pas par-dessus (WhatsApp).
    /// Posée par l'écran de la discussion à son apparition, remise à nil à sa disparition.
    static var visibleThread: String?

    /// Au lancement (AppDelegate) : les deux catégories. Répondre demande le déverrouillage (personne d'autre
    /// n'écrit au nom du propriétaire depuis l'écran verrouillé).
    nonisolated static func register(_ center: UNUserNotificationCenter = .current()) {
        let reply = UNTextInputNotificationAction(identifier: replyAction, title: "Répondre",
                                                  options: [.authenticationRequired],
                                                  textInputButtonTitle: "Envoyer", textInputPlaceholder: "Message")
        let read = UNNotificationAction(identifier: readAction, title: "Marquer comme lu", options: [])
        center.setNotificationCategories([
            UNNotificationCategory(identifier: category, actions: [reply, read], intentIdentifiers: [],
                                   options: []),
            UNNotificationCategory(identifier: readOnlyCategory, actions: [read], intentIdentifiers: [], options: []),
        ])
    }

    /// Événement de la notification (`event_id` de la charge utile, sinon l'adresse du toucher) ; nil : pas une
    /// notification de discussion d'événement.
    nonisolated static func eventID(of info: [AnyHashable: Any]) -> String? {
        let raw = (info["event_id"] as? String)
            ?? (info["url"] as? String).flatMap { URL(string: $0, relativeTo: AppConfig.baseURL) }
                .flatMap { WebModel.eventChatRequested(in: $0) }
        guard let raw, raw.range(of: "^[0-9a-fA-F-]{36}$", options: .regularExpression) != nil else { return nil }
        return raw.lowercased()
    }

    nonisolated static func thread(_ event: String) -> String { "event-chat:\(event)" }

    /// Action de l'une des catégories ; false : rien à faire ici (toucher simple, autre notification).
    static func handle(_ response: UNNotificationResponse) async -> Bool {
        guard [replyAction, readAction].contains(response.actionIdentifier),
              let event = eventID(of: response.notification.request.content.userInfo) else { return false }
        if response.actionIdentifier == readAction {
            if let token = await token() {
                _ = try? await api.post("/api/account/event-chat/read", body: ["token": token, "event_id": event])
            }
            await clearDelivered(event)  // lu sur ce téléphone, même si le serveur l'apprendra à la prochaine ouverture
            return true
        }
        let text = ((response as? UNTextInputNotificationResponse)?.userText ?? "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return true }
        guard let token = await token() else {
            await notSent(event, text: text, reason: "Ouvre Party pour l'envoyer dans la discussion.")
            return true
        }
        do {
            try await api.sendEventChat(token: token, event: event, body: String(text.prefix(4000)), replyTo: nil,
                                        photoPath: nil, mentions: [], id: UUID().uuidString.lowercased())
            // Répondre, c'est avoir lu : comme WhatsApp, la discussion passe à lu et ses notifications s'effacent.
            _ = try? await api.post("/api/account/event-chat/read", body: ["token": token, "event_id": event])
            await clearDelivered(event)
        } catch PartyAPIError.termsRequired {
            await notSent(event, text: text, reason: "Accepte d'abord les conditions d'utilisation dans Party.")
        } catch PartyAPIError.server(let message) {
            await notSent(event, text: text, reason: message)
        } catch {
            await notSent(event, text: text, reason: "Ouvre Party pour l'envoyer dans la discussion.")
        }
        return true
    }

    /// Notification à ne pas montrer : celle de la discussion ouverte à l'écran.
    static func hides(_ notification: UNNotification) -> Bool {
        guard let visibleThread, !notification.request.identifier.hasPrefix("event-chat-unsent.") else { return false }
        return notification.request.content.threadIdentifier == visibleThread
    }

    // MARK: - Interne

    /// Appels au serveur avec les cookies de la vue web (même magasin que la page, PartyWebView : .default()).
    private static let api = PartyAPI(base: AppConfig.baseURL, jar: WebCookieJar(WKWebsiteDataStore.default().httpCookieStore))

    /// Jeton du compte, demandé à la page ; 8 s au plus (vue web en arrière-plan qui ne répond pas).
    private static func token() async -> String? {
        guard let web else { return nil }
        return await withCheckedContinuation { (reply: CheckedContinuation<String?, Never>) in
            let once = Once(reply)
            Task { @MainActor in once.resume(await web.accountToken()) }
            Task { @MainActor in
                try? await Task.sleep(nanoseconds: 8_000_000_000)
                once.resume(nil)
            }
        }
    }

    private static func clearDelivered(_ event: String) async {
        let center = UNUserNotificationCenter.current()
        let ids = await center.deliveredNotifications()
            .filter { $0.request.content.threadIdentifier == thread(event) }
            .map(\.request.identifier)
        center.removeDeliveredNotifications(withIdentifiers: ids)
    }

    /// Réponse refusée ou impossible : on le dit (jamais d'échec silencieux), le toucher ouvre la discussion.
    private static func notSent(_ event: String, text: String, reason: String) async {
        let content = UNMutableNotificationContent()
        content.title = "Message non envoyé : ouvre Party"
        content.body = "« \(text.prefix(80)) » · \(reason)"
        content.threadIdentifier = thread(event)
        content.sound = .default
        content.userInfo = ["url": "/?tab=events&event=\(event)&chat=1", "event_id": event]
        try? await UNUserNotificationCenter.current()
            .add(UNNotificationRequest(identifier: "event-chat-unsent.\(UUID().uuidString)", content: content, trigger: nil))
    }

    /// Première des deux réponses (jeton ou délai) seulement.
    private final class Once {
        private var reply: CheckedContinuation<String?, Never>?
        init(_ reply: CheckedContinuation<String?, Never>) { self.reply = reply }
        @MainActor func resume(_ value: String?) {
            reply?.resume(returning: value)
            reply = nil
        }
    }
}

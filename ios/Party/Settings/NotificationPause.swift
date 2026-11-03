import Foundation
import SwiftUI

/// Pause des notifications (avis de l'admin du 3 novembre 2026) : pendant la lune (en haut à droite des Réglages),
/// toutes les notifications, admin comprises, arrivent SANS son ni vibration ; deux sourdines distinctes font de même
/// pour les messages des Discussions des groupes et pour ceux des discussions des événements. L'heure de fin est
/// calculée par la base (set_notification_pause, heure de Zurich). Le décompte de la Dynamic Island n'est pas concerné.
enum NotificationPause {
    enum Scope: String {
        case all, chats
        case eventChats = "event_chats"

        var subject: String {
            switch self {
            case .all: "Notifications"
            case .chats: "Discussions des groupes"
            case .eventChats: "Discussions des événements"
            }
        }
    }

    struct Span: Identifiable, Equatable {
        let key: String
        let label: String
        var id: String { key }
    }

    static let off = "off"
    /// La lune propose 1 h, 2 h et 8 h du matin ; les Discussions aussi 30 minutes.
    static func spans(_ scope: Scope) -> [Span] {
        let common = [Span(key: "1h", label: "1 heure"), Span(key: "2h", label: "2 heures"),
                      Span(key: "morning", label: "Jusqu'à 8 h du matin")]
        return scope == .all ? common : [Span(key: "30m", label: "30 minutes")] + common
    }

    static let zurich = TimeZone(identifier: "Europe/Zurich") ?? .current

    /// Date Postgres (« 2026-11-03T07:00:00+00:00 », fractions de seconde possibles) → date ; nil si illisible.
    static func date(_ text: String?) -> Date? {
        guard var text, !text.isEmpty else { return nil }
        text = text.replacingOccurrences(of: #"\.\d+"#, with: "", options: .regularExpression)
        let formatter = ISO8601DateFormatter()
        return formatter.date(from: text) ?? formatter.date(from: text.replacingOccurrences(of: " ", with: "T"))
    }

    /// Fin d'une pause encore en cours ; une pause passée ne compte plus.
    static func activeUntil(_ text: String?, now: Date = Date()) -> Date? {
        date(text).flatMap { $0 > now ? $0 : nil }
    }

    /// « 14:30 », ou « demain 08:00 » si la pause finit un autre jour (heure du groupe).
    static func label(_ until: Date, now: Date = Date()) -> String {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = zurich
        let c = calendar.dateComponents([.hour, .minute], from: until)
        let time = String(format: "%02d:%02d", c.hour ?? 0, c.minute ?? 0)
        return calendar.isDate(until, inSameDayAs: now) ? time : "demain \(time)"
    }
}

/// Pauses du compte connecté, lues et changées par le serveur Party (session du membre).
@MainActor
final class PauseStore: ObservableObject {
    @Published private(set) var allUntil: Date?
    @Published private(set) var chatsUntil: Date?
    @Published private(set) var eventChatsUntil: Date?
    @Published private(set) var busy = false
    @Published private(set) var signedIn = false
    @Published var error: String?

    private let api: PartyAPI
    private weak var web: WebStorage?

    init(api: PartyAPI, web: WebStorage?) {
        self.api = api
        self.web = web
    }

    func load() async {
        guard let token = await web?.accountToken() else {
            signedIn = false; allUntil = nil; chatsUntil = nil; eventChatsUntil = nil
            return
        }
        signedIn = true
        if let state = try? await api.eventNotifyPrefs(token: token) { apply(state.prefs) }
    }

    func set(_ scope: NotificationPause.Scope, _ span: String) async {
        guard !busy, let token = await web?.accountToken() else { return }
        busy = true
        defer { busy = false }
        do {
            apply(try await api.setNotificationPause(token: token, what: scope.rawValue, span: span).prefs)
            error = nil
        } catch {
            self.error = "La pause n'a pas été enregistrée. Réessaie dans un instant."
        }
    }

    func apply(_ prefs: EventNotificationPrefs) {
        allUntil = NotificationPause.activeUntil(prefs.mutedUntil)
        chatsUntil = NotificationPause.activeUntil(prefs.chatsMutedUntil)
        eventChatsUntil = NotificationPause.activeUntil(prefs.eventChatsMutedUntil)
    }

    /// Pause encore en cours à cet instant (une pause finie s'éteint toute seule à l'écran).
    func active(_ scope: NotificationPause.Scope, now: Date = Date()) -> Date? {
        let until = switch scope {
        case .all: allUntil
        case .chats: chatsUntil
        case .eventChats: eventChatsUntil
        }
        return until.flatMap { $0 > now ? $0 : nil }
    }
}

/// Menu d'une pause : les durées, et « Réactiver » quand elle est en cours.
struct PauseMenuItems: View {
    @ObservedObject var store: PauseStore
    let scope: NotificationPause.Scope
    let until: Date?

    var body: some View {
        if let until {
            Section("\(scope.subject) en pause jusqu'à \(NotificationPause.label(until))") {
                Button { Task { await store.set(scope, NotificationPause.off) } } label: {
                    Label("Réactiver", systemImage: "bell")
                }
            }
        }
        Section(scope == .all ? "Tout arrive sans son ni vibration" : "\(scope.subject) : messages sans son ni vibration") {
            ForEach(NotificationPause.spans(scope)) { span in
                Button(span.label) { Task { await store.set(scope, span.key) } }
            }
        }
    }
}

/// Lune en haut à droite de la racine des Réglages ; pleine quand tout est en pause.
struct MoonMenu: View {
    @ObservedObject var store: PauseStore

    var body: some View {
        TimelineView(.periodic(from: .now, by: 30)) { context in
            let until = store.active(.all, now: context.date)
            Menu {
                PauseMenuItems(store: store, scope: .all, until: until)
            } label: {
                Image(systemName: until == nil ? "moon" : "moon.fill")
                    .foregroundStyle(until == nil ? Color.primary : Color.orange)
            }
            .disabled(store.busy)
            .accessibilityLabel(until.map { "Notifications en pause jusqu'à \(NotificationPause.label($0))" }
                                ?? "Mettre les notifications en pause")
            .accessibilityIdentifier("settings-moon")
        }
    }
}

/// Bandeau en tête des Réglages pendant la lune, avec « Réactiver ».
struct MoonBanner: View {
    @ObservedObject var store: PauseStore

    var body: some View {
        TimelineView(.periodic(from: .now, by: 30)) { context in
            if let until = store.active(.all, now: context.date) {
                HStack(spacing: 12) {
                    Image(systemName: "moon.fill").foregroundStyle(.orange).accessibilityHidden(true)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Notifications en pause jusqu'à \(NotificationPause.label(until))")
                        Text("Elles arrivent sans son ni vibration").font(.footnote).foregroundStyle(.secondary)
                    }
                    Spacer(minLength: 0)
                    Button("Réactiver") { Task { await store.set(.all, NotificationPause.off) } }
                        .buttonStyle(.borderless)
                        .disabled(store.busy)
                }
                .accessibilityElement(children: .contain)
            }
        }
    }
}

/// Ligne « Sourdine » d'une sorte de discussion (Réglages › Notifications) : menu des durées.
struct ChatsPauseRow: View {
    @ObservedObject var store: PauseStore
    var scope: NotificationPause.Scope = .chats

    var body: some View {
        TimelineView(.periodic(from: .now, by: 30)) { context in
            let until = store.active(scope, now: context.date)
            Menu {
                PauseMenuItems(store: store, scope: scope, until: until)
            } label: {
                SettingsRow(symbol: until == nil ? "bell.slash" : "bell.slash.fill", tint: .indigo,
                            title: until.map { "\(scope.subject) en pause jusqu'à \(NotificationPause.label($0))" }
                                ?? "Sourdine : \(scope.subject)",
                            hint: "Messages sans son ni vibration : 30 min, 1 h, 2 h ou jusqu'à 8 h")
            }
            .foregroundStyle(.primary)
            .disabled(store.busy)
            .accessibilityIdentifier(scope == .chats ? "chats-pause" : "event-chats-pause")
        }
    }
}

/// Bouton de la barre des Discussions : sourdine des groupes ; cloche barrée pleine pendant la pause.
struct ChatsPauseButton: View {
    @ObservedObject var store: PauseStore

    var body: some View {
        TimelineView(.periodic(from: .now, by: 30)) { context in
            let until = store.active(.chats, now: context.date)
            Menu {
                PauseMenuItems(store: store, scope: .chats, until: until)
            } label: {
                Image(systemName: until == nil ? "bell" : "bell.slash.fill")
            }
            .disabled(store.busy)
            .accessibilityLabel(until.map { "Discussions des groupes en pause jusqu'à \(NotificationPause.label($0))" }
                                ?? "Sourdine des Discussions des groupes")
            .accessibilityIdentifier("chats-pause-button")
        }
        .task { await store.load() }
    }
}

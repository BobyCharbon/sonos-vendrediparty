import Foundation
import UserNotifications

/// « Ton contact Léa est sur Party » (avis 84fab3987f68) : notification LOCALE de l'iPhone. Les contacts ne quittent pas
/// l'appareil, donc seul l'iPhone sait qu'un nouveau compte Party est dans le répertoire.
/// Calculée à chaque actualisation des noms des contacts : jamais à la toute première comparaison, seulement pour des
/// comptes arrivés sur Party récemment (pas un ami de longue date qu'on vient d'ajouter aux contacts), une seule fois par
/// compte, regroupée au-delà de 3. Elle suit les Réglages du compte : interrupteur « Un contact arrive sur Party »
/// (notification_prefs.contact_joins), lune et pause (sans son), heures de silence (reportée à leur fin).
@MainActor
final class ContactJoinNotifier {
    static let shared = ContactJoinNotifier()

    /// Arrivé sur Party depuis moins longtemps que ça : « nouveau ». Au-delà, il était déjà là.
    static let recentJoin: TimeInterval = 3 * 86_400
    private static let notifiedKey = "party.contacts.joinNotified"
    static let identifier = "party.contact-joins"

    private var api: PartyAPI?
    private weak var web: WebStorage?
    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) { self.defaults = defaults }

    func configure(api: PartyAPI, web: WebStorage) {
        self.api = api
        self.web = web
    }

    /// Appelé par ContactNames après chaque nouvelle comparaison.
    func matchesChanged(before: ContactNamesSnapshot, after: ContactNamesSnapshot) {
        let fresh = FriendsLogic.newlyMatched(before: before, after: after)
            .filter { !notified.contains($0) }
        guard !fresh.isEmpty else { return }
        Task { await notify(fresh, names: after.names) }
    }

    private var notified: Set<String> { Set(defaults.stringArray(forKey: Self.notifiedKey) ?? []) }

    private func notify(_ ids: [String], names: [String: String]) async {
        guard let api, let token = await web?.accountToken() else { return }
        guard let friends = try? await api.contactFriends(token: token, ids: ids),
              let state = try? await api.eventNotifyPrefs(token: token) else { return }
        let joined = Self.recentlyJoined(friends, now: Date())
        defaults.set(Array(notified.union(ids)).suffix(2000), forKey: Self.notifiedKey)  // vus : jamais deux fois
        guard state.prefs.contactJoins != false,
              let body = FriendsLogic.joinMessage(joined.compactMap { names[$0.id] }) else { return }
        let center = UNUserNotificationCenter.current()
        let settings = await center.notificationSettings()
        guard [.authorized, .provisional, .ephemeral].contains(settings.authorizationStatus) else { return }
        let content = UNMutableNotificationContent()
        content.title = "Mes amis dans Party"
        content.body = body
        content.threadIdentifier = Self.identifier
        content.userInfo = ["kind": "contact_join"]
        // Lune ou pause : livrée en silence, comme les notifications envoyées par Party.
        content.sound = Self.isMuted(state.prefs, now: Date()) ? nil : .default
        let delay = Self.delayForQuietHours(start: state.prefs.quietStart, end: state.prefs.quietEnd, now: Date())
        let trigger = delay > 0 ? UNTimeIntervalNotificationTrigger(timeInterval: delay, repeats: false) : nil
        try? await center.add(UNNotificationRequest(identifier: "\(Self.identifier).\(UUID().uuidString)", content: content, trigger: trigger))
    }

    nonisolated static func recentlyJoined(_ friends: [PartyFriend], now: Date) -> [PartyFriend] {
        friends.filter { ($0.joinedAt ?? .distantPast) >= now.addingTimeInterval(-recentJoin) }
    }

    nonisolated static func isMuted(_ prefs: EventNotificationPrefs, now: Date) -> Bool {
        NotificationPause.activeUntil(prefs.mutedUntil, now: now) != nil
    }

    /// Secondes jusqu'à la fin des heures de silence (0 hors silence). « 23:00 → 08:00 » passe minuit.
    nonisolated static func delayForQuietHours(start: String?, end: String?, now: Date, calendar: Calendar = .current) -> TimeInterval {
        guard let start, let end else { return 0 }
        let from = QuietTime.date(start, on: now, calendar: calendar)
        var until = QuietTime.date(end, on: now, calendar: calendar)
        let quiet: Bool
        if from <= until {
            quiet = now >= from && now < until
        } else {
            quiet = now >= from || now < until
            if now >= from { until = calendar.date(byAdding: .day, value: 1, to: until) ?? until }
        }
        return quiet ? max(0, until.timeIntervalSince(now)) : 0
    }
}

import Combine
import EventKit
import Foundation

/// Agenda de Party côté app : la pastille « demandes de rendez-vous en attente » (Réglages › Autres apps › Agenda) et
/// l'envoi des plages « pris » de l'iPhone (EventKit, calcul local) par le relais POST /api/account/agenda/rpc.
@MainActor
final class AgendaStore: ObservableObject {
    /// Demandes de rendez-vous en attente (agenda_badge) ; 0 sans compte ou hors ligne.
    @Published private(set) var pending = 0

    let store = EKEventStore()
    let prefs = AgendaPrefs()
    private let api: PartyAPI
    private weak var web: WebStorage?
    private var endpoint: ChatRealtime.Endpoint?
    private var live: ChatRealtime?
    private var liveAccount: String?
    private var syncing = false

    init(api: PartyAPI, web: WebStorage?) {
        self.api = api
        self.web = web
    }

    // MARK: Accès aux calendriers

    nonisolated static func access(_ status: EKAuthorizationStatus) -> String {
        switch status {
        case .notDetermined: return "notDetermined"
        case .denied: return "denied"
        case .restricted: return "restricted"
        default:
            if #available(iOS 17.0, *) { return status == .fullAccess ? "full" : status == .writeOnly ? "writeOnly" : "denied" }
            return "full"  // iOS 16 : « authorized »
        }
    }

    var access: String { Self.access(EKEventStore.authorizationStatus(for: .event)) }

    /// La page a montré son écran « Rien n'est envoyé » avant : seulement ici la demande d'iOS.
    func requestAccess() async -> String {
        if access == "notDetermined" {
            if #available(iOS 17.0, *) {
                _ = try? await store.requestFullAccessToEvents()
            } else {
                _ = try? await store.requestAccess(to: .event)
            }
            store.reset()
        }
        return access
    }

    // MARK: Calendriers et rendez-vous de l'iPhone (affichage local)

    func calendars() -> [[String: Any]] {
        guard access == "full" else { return [] }
        return store.calendars(for: .event).map { cal in
            let excluded = AgendaCalendars.excluded(type: cal.type, title: cal.title)
            let p = prefs.get(cal.calendarIdentifier, excluded: excluded)
            var row: [String: Any] = [
                "id": cal.calendarIdentifier, "title": cal.title, "color": Self.hex(cal.cgColor),
                "source": AgendaCalendars.source(type: cal.source?.sourceType, title: cal.source?.title),
                "shown": p.shown, "countsBusy": p.countsBusy,
            ]
            if let excluded { row["excluded"] = excluded }
            return row
        }
    }

    /// Préférence gardée sur l'iPhone ; un calendrier exclu d'office (Vendredi Party, anniversaires) ne compte jamais.
    func setCalendar(_ id: String, shown: Bool?, countsBusy: Bool?) -> Bool {
        guard let cal = store.calendar(withIdentifier: id) else { return false }
        let excluded = AgendaCalendars.excluded(type: cal.type, title: cal.title)
        prefs.set(id, shown: shown, countsBusy: excluded == nil ? countsBusy : false)
        return true
    }

    /// Rendez-vous des calendriers affichés, pour l'écran seulement : rien de ceci ne part au serveur.
    func events(from: Date, to: Date) -> [[String: Any]] {
        guard access == "full", to > from, to.timeIntervalSince(from) <= 62 * 86_400 else { return [] }
        let shown = store.calendars(for: .event).filter {
            prefs.get($0.calendarIdentifier, excluded: AgendaCalendars.excluded(type: $0.type, title: $0.title)).shown
        }
        guard !shown.isEmpty else { return [] }
        let found = store.events(matching: store.predicateForEvents(withStart: from, end: to, calendars: shown))
        return found.filter { !AgendaBusy.isParty(Self.entry($0)) }.map { event in
            [
                "id": event.eventIdentifier ?? UUID().uuidString, "calendarId": event.calendar.calendarIdentifier,
                "title": event.title ?? "", "location": event.location ?? "",
                "start": AgendaBusy.iso(event.startDate), "end": AgendaBusy.iso(event.endDate),
                "allDay": event.isAllDay, "color": Self.hex(event.calendar.cgColor),
            ] as [String: Any]
        }
    }

    nonisolated static func entry(_ event: EKEvent) -> AgendaBusy.Entry {
        AgendaBusy.Entry(calendarID: event.calendar?.calendarIdentifier ?? "", start: event.startDate, end: event.endDate,
                         allDay: event.isAllDay, availability: event.availability, url: event.url,
                         externalID: event.calendarItemExternalIdentifier)
    }

    nonisolated static func hex(_ color: CGColor?) -> String {
        guard let color, let rgb = color.converted(to: CGColorSpace(name: CGColorSpace.sRGB)!, intent: .defaultIntent, options: nil),
              let c = rgb.components, c.count >= 3 else { return "#8E8E93" }
        let v = c.prefix(3).map { Int((max(0, min(1, $0)) * 255).rounded()) }
        return String(format: "#%02X%02X%02X", v[0], v[1], v[2])
    }

    // MARK: Mes dispos (envoi des plages « pris »)

    /// Calcule et envoie les plages des calendriers cochés, seulement si le partage est actif (un groupe coché ou un lien
    /// de dispo actif) : sinon rien ne part, pas même une liste vide.
    func syncBusy() async -> [String: Any] {
        guard !syncing, let token = await web?.accountToken() else { return ["sent": 0, "updatedAt": NSNull()] }
        syncing = true
        defer { syncing = false }
        guard let sharing = try? await rpc(token, "agenda_sharing") as? [String: Any], Self.isSharing(sharing) else {
            return ["sent": 0, "updatedAt": NSNull(), "sharing": false]
        }
        guard access == "full" else { return ["sent": 0, "updatedAt": NSNull(), "access": access] }
        let now = Date()
        let busy = Set(store.calendars(for: .event).map(\.calendarIdentifier).filter {
            guard let cal = store.calendar(withIdentifier: $0) else { return false }
            return prefs.get($0, excluded: AgendaCalendars.excluded(type: cal.type, title: cal.title)).countsBusy
        })
        var entries: [AgendaBusy.Entry] = []
        if !busy.isEmpty {
            let calendars = store.calendars(for: .event).filter { busy.contains($0.calendarIdentifier) }
            let end = now.addingTimeInterval(Double(AgendaBusy.horizonDays) * 86_400)
            entries = store.events(matching: store.predicateForEvents(withStart: now, end: end, calendars: calendars)).map(Self.entry)
        }
        let blocks = AgendaBusy.blocks(entries, busyCalendars: busy, now: now)
        do {
            let saved = try await rpc(token, "agenda_set_busy", ["source": "device", "blocks": AgendaBusy.payload(blocks)]) as? [String: Any]
            prefs.synced = true
            return ["sent": blocks.count, "updatedAt": saved?["updated_at"] ?? NSNull()]
        } catch {
            // « Active d'abord le partage » (arrêté entre-temps) : rien n'est parti, sans erreur pour la page.
            return ["sent": 0, "updatedAt": NSNull(), "error": error.localizedDescription]
        }
    }

    nonisolated static func isSharing(_ sharing: [String: Any]) -> Bool {
        let groups = sharing["groups"] as? [[String: Any]] ?? []
        return groups.contains { $0["shared"] as? Bool == true } || (sharing["links_active"] as? Int ?? 0) > 0
    }

    // MARK: Pastille

    func refreshBadge() async {
        guard let token = await web?.accountToken() else {
            pending = 0
            return
        }
        guard let reply = try? await api.agendaRPC(token: token, fn: "agenda_badge") else { return }
        pending = Self.pending(reply["result"])
        if let raw = reply["realtime"], let data = try? JSONSerialization.data(withJSONObject: raw) {
            endpoint = try? JSONDecoder().decode(ChatRealtime.Endpoint.self, from: data)
        }
    }

    nonisolated static func pending(_ result: Any?) -> Int {
        max(0, (result as? [String: Any])?["pending"] as? Int ?? 0)
    }

    /// Réglages affichés : signal temps réel « user:<id> » (une demande arrive, est décidée, expire) → pastille relue.
    func startLive() async {
        await refreshBadge()
        guard let endpoint, let token = await web?.accountToken(), let account = ChatsCache.account(of: token) else { return }
        if live != nil && liveAccount == account { return }
        stopLive()
        let live = ChatRealtime(endpoint: endpoint, token: token, signal: "user:\(account)") { [weak self] in
            Task { await self?.refreshBadge() }
        }
        self.live = live
        liveAccount = account
        live.start()
    }

    func stopLive() {
        live?.stop()
        live = nil
        liveAccount = nil
    }

    /// Retour au premier plan : pastille relue ; plages renvoyées si cet iPhone partage déjà ses dispos.
    func appBecameActive() async {
        await refreshBadge()
        if prefs.synced { _ = await syncBusy() }
    }

    private func rpc(_ token: String, _ fn: String, _ args: [String: Any] = [:]) async throws -> Any? {
        try await api.agendaRPC(token: token, fn: fn, args: args)["result"]
    }
}

import EventKit
import UIKit
import WebKit

/// Sondage de dates → calendrier de l'iPhone (avis 9ddbdea7fe8f, 10.11.2026 ; « quelque chose de fluide »).
/// Un toucher sur « Mettre les N dates dans mon agenda » : toutes les dates proposées entrent dans le calendrier par
/// défaut, titrées « À confirmer · <événement> » et marquées provisoires. L'app retient ce qu'elle a ajouté (sur
/// l'iPhone seulement) : quand la date est fixée, la page le lui dit (`settle`), la bonne entrée reste sous le vrai titre
/// et les autres partent toutes seules ; un événement annulé les retire toutes. Rien ne quitte l'iPhone.
enum PollCalendar {
    static let maxDates = 20
    static let prefix = "À confirmer · "
    static let defaultDuration: TimeInterval = 3 * 3600
    /// Même date « à la minute près » : les fuseaux et arrondis ne font jamais garder la mauvaise entrée.
    static let sameStartTolerance: TimeInterval = 60
    static let tentativeNote = "Date proposée : rien n’est encore fixé. Party retirera les autres dates quand celle-ci sera choisie."
    static let fixedNote = "Date fixée par l’organisateur."

    static func tentativeTitle(_ title: String) -> String { prefix + title }

    /// Date fixée : l'entrée qui commence au même moment reste, toutes les autres partent.
    static func settle(stored: [String: Date], fixedStart: Date) -> (keep: String?, remove: [String]) {
        let keep = stored.first { abs($0.value.timeIntervalSince(fixedStart)) <= sameStartTolerance }?.key
        return (keep, stored.keys.filter { $0 != keep }.sorted())
    }

    static func date(_ value: Any?) -> Date? {
        guard let text = value as? String, !text.isEmpty else { return nil }
        let precise = ISO8601DateFormatter()
        precise.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return precise.date(from: text) ?? ISO8601DateFormatter().date(from: text)
    }
}

/// Ce que la page envoie pour « ajouter toutes les dates » (validé ici : la page est une source extérieure).
struct PollCalendarRequest {
    struct Slot { let id: String; let start: Date; let end: Date }

    let eventId: String
    let title: String
    let location: String
    let notes: String
    let url: URL?
    let dates: [Slot]

    init?(_ body: [String: Any]) {
        guard let event = body["eventId"] as? String, UUID(uuidString: event) != nil,
              let title = (body["title"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines), !title.isEmpty,
              let raw = body["dates"] as? [[String: Any]], !raw.isEmpty, raw.count <= PollCalendar.maxDates else { return nil }
        var slots: [Slot] = []
        for item in raw {
            guard let id = item["id"] as? String, UUID(uuidString: id) != nil,
                  let start = PollCalendar.date(item["start"]) else { return nil }
            let end = PollCalendar.date(item["end"]).flatMap { $0 > start ? $0 : nil } ?? start.addingTimeInterval(PollCalendar.defaultDuration)
            slots.append(Slot(id: id.lowercased(), start: start, end: end))
        }
        eventId = event.lowercased()
        self.title = String(title.prefix(200))
        location = String(((body["location"] as? String) ?? "").prefix(300))
        notes = String(((body["notes"] as? String) ?? "").prefix(2000))
        url = (body["url"] as? String).flatMap(URL.init(string:)).flatMap { AppConfig.isInternal($0) ? $0 : nil }
        dates = slots
    }
}

/// Entrées ajoutées par l'app, par événement : { date proposée : identifiant de l'entrée du calendrier }.
/// Sur l'iPhone seulement (UserDefaults), jamais envoyé au serveur.
struct PollCalendarMemory {
    private static let key = "party.pollCalendar.v1"
    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) { self.defaults = defaults }

    func entries(_ event: String) -> [String: String] { all()[event] ?? [:] }
    func events() -> [String] { all().keys.sorted() }

    func save(_ event: String, _ entries: [String: String]) {
        var everything = all()
        everything[event] = entries.isEmpty ? nil : entries
        defaults.set(everything, forKey: Self.key)
    }

    private func all() -> [String: [String: String]] {
        defaults.dictionary(forKey: Self.key) as? [String: [String: String]] ?? [:]
    }
}

/// Écrit dans le calendrier et fait le ménage (testé pour de vrai sur simulateur : PollCalendarTests).
struct PollCalendarWriter {
    let store: EKEventStore
    let memory: PollCalendarMemory

    /// Entrées encore présentes (l'utilisateur a pu en supprimer à la main).
    func present(_ event: String) -> [String: EKEvent] {
        memory.entries(event).compactMapValues { store.event(withIdentifier: $0) }
    }

    func add(_ request: PollCalendarRequest) -> [String: Any] {
        var entries: [String: String] = present(request.eventId).compactMapValues(\.eventIdentifier)
        var added = 0
        for slot in request.dates where entries[slot.id] == nil {
            let entry = EKEvent(eventStore: store)
            entry.calendar = store.defaultCalendarForNewEvents
            entry.title = PollCalendar.tentativeTitle(request.title)
            entry.startDate = slot.start
            entry.endDate = slot.end
            entry.availability = .tentative
            entry.location = request.location.isEmpty ? nil : request.location
            entry.notes = [PollCalendar.tentativeNote, request.notes].filter { !$0.isEmpty }.joined(separator: "\n\n")
            entry.url = request.url
            guard (try? store.save(entry, span: .thisEvent)) != nil, let id = entry.eventIdentifier else { continue }
            entries[slot.id] = id
            added += 1
        }
        memory.save(request.eventId, entries)
        return ["added": added, "total": entries.count]
    }

    /// Date fixée : la bonne entrée prend le vrai titre, les autres partent. Annulé (ou sans date) : toutes partent.
    @discardableResult
    func settle(_ event: String, start: Date?, end: Date?, title: String?, cancelled: Bool) -> Bool {
        let live = present(event)
        guard !cancelled, let start else {
            live.values.forEach { try? store.remove($0, span: .thisEvent) }
            memory.save(event, [:])
            return !live.isEmpty
        }
        let plan = PollCalendar.settle(stored: live.mapValues(\.startDate), fixedStart: start)
        plan.remove.compactMap { live[$0] }.forEach { try? store.remove($0, span: .thisEvent) }
        if let keep = plan.keep.flatMap({ live[$0] }) {
            if let title = title?.trimmingCharacters(in: .whitespacesAndNewlines), !title.isEmpty { keep.title = String(title.prefix(200)) }
            if let end, end > keep.startDate { keep.endDate = end }
            keep.availability = .busy
            keep.notes = keep.notes?.replacingOccurrences(of: PollCalendar.tentativeNote, with: PollCalendar.fixedNote)
            try? store.save(keep, span: .thisEvent)
        }
        memory.save(event, [:])
        return true
    }
}

/// `PartyNative.calendar.*` : add (toutes les dates), status (combien sont déjà dans le calendrier), settle (date fixée
/// ou événement annulé), pending (événements dont des dates « à confirmer » attendent).
final class NativeCalendarBridge: NSObject, WKScriptMessageHandlerWithReply {
    static let handler = "partyCalendar"
    private let store = EKEventStore()
    private let memory = PollCalendarMemory()
    private var writer: PollCalendarWriter { PollCalendarWriter(store: store, memory: memory) }

    @MainActor
    func userContentController(_ controller: WKUserContentController,
                               didReceive message: WKScriptMessage) async -> (Any?, String?) {
        guard AppConfig.isInternal(message.frameInfo.securityOrigin.url),
              let body = message.body as? [String: Any], let action = body["action"] as? String else { return (nil, "Action inconnue") }
        switch action {
        case "add":
            guard let request = PollCalendarRequest(body) else { return (nil, "Demande invalide") }
            guard await authorize() else { return (["denied": true], nil) }
            return (writer.add(request), nil)
        case "status":
            guard let event = (body["eventId"] as? String)?.lowercased() else { return (nil, "Demande invalide") }
            return (["added": authorized ? writer.present(event).count : 0], nil)
        case "settle":
            guard let event = (body["eventId"] as? String)?.lowercased() else { return (nil, "Demande invalide") }
            guard authorized, !memory.entries(event).isEmpty else { return (["changed": false], nil) }
            let changed = writer.settle(event, start: PollCalendar.date(body["start"]), end: PollCalendar.date(body["end"]),
                                        title: body["title"] as? String, cancelled: body["cancelled"] as? Bool == true)
            return (["changed": changed], nil)
        case "pending":
            return (authorized ? memory.events() : [], nil)
        default:
            return (nil, "Action inconnue")
        }
    }

    private var authorized: Bool {
        let status = EKEventStore.authorizationStatus(for: .event)
        if #available(iOS 17.0, *) { return status == .fullAccess }
        return status == .authorized
    }

    /// Accès complet : il faut pouvoir retrouver puis retirer les dates non retenues (l'accès « ajout seul » ne le permet pas).
    private func authorize() async -> Bool {
        if authorized { return true }
        if #available(iOS 17.0, *) { return (try? await store.requestFullAccessToEvents()) ?? false }
        return (try? await store.requestAccess(to: .event)) ?? false
    }
}

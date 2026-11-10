import EventKit
import Foundation
import Testing
@testable import Party

/// Sondage de dates → toutes les dates dans le calendrier de l'iPhone en un toucher (avis 9ddbdea7fe8f), puis, une fois
/// la date fixée, la bonne reste (titre sans « À confirmer ») et les autres partent toutes seules.
struct PollCalendarTests {
    private let event = "64d0880c-5379-42f8-8166-e259d25c7e7b"
    private let d1 = "11111111-2222-4333-8444-555555555551"
    private let d2 = "11111111-2222-4333-8444-555555555552"

    private func body(dates: [[String: Any]], title: String = "Paintball") -> [String: Any] {
        ["action": "add", "eventId": event, "title": title, "location": "Cobalt Project", "notes": "", "url": "", "dates": dates]
    }

    @Test("La demande de la page est lue : chaque date avec son début et sa fin (3 h sans fin)")
    func parsesRequest() throws {
        let request = try #require(PollCalendarRequest(body(dates: [
            ["id": d1, "start": "2030-12-04T19:00:00Z", "end": ""],
            ["id": d2, "start": "2030-12-11T19:00:00Z", "end": "2030-12-11T23:00:00Z"],
        ])))
        #expect(request.eventId == event && request.dates.count == 2)
        #expect(request.dates[0].end.timeIntervalSince(request.dates[0].start) == 3 * 3600)
        #expect(request.dates[1].end.timeIntervalSince(request.dates[1].start) == 4 * 3600)
        #expect(PollCalendar.tentativeTitle("Paintball") == "À confirmer · Paintball")
    }

    @Test("Demande refusée : sans titre, sans date, date illisible, identifiant faux ou trop de dates")
    func refusesBadRequests() {
        #expect(PollCalendarRequest(body(dates: [["id": d1, "start": "2030-12-04T19:00:00Z", "end": ""]], title: " ")) == nil)
        #expect(PollCalendarRequest(body(dates: [])) == nil)
        #expect(PollCalendarRequest(body(dates: [["id": d1, "start": "demain", "end": ""]])) == nil)
        #expect(PollCalendarRequest(body(dates: [["id": "pas-un-id", "start": "2030-12-04T19:00:00Z", "end": ""]])) == nil)
        let many = (0...PollCalendar.maxDates).map { _ in ["id": UUID().uuidString, "start": "2030-12-04T19:00:00Z", "end": ""] }
        #expect(PollCalendarRequest(body(dates: many)) == nil)
    }

    @Test("Date fixée : on garde l'entrée du même début (à la minute près) et on retire les autres")
    func settleKeepsTheFixedDate() {
        let start1 = Date(timeIntervalSince1970: 1_922_000_000)
        let start2 = start1.addingTimeInterval(7 * 86_400)
        let plan = PollCalendar.settle(stored: [d1: start1, d2: start2], fixedStart: start2.addingTimeInterval(20))
        #expect(plan.keep == d2 && plan.remove == [d1])
        let none = PollCalendar.settle(stored: [d1: start1, d2: start2], fixedStart: start2.addingTimeInterval(86_400))
        #expect(none.keep == nil && Set(none.remove) == [d1, d2])
    }

    /// Vrai calendrier du simulateur (accès accordé par `xcrun simctl privacy booted grant calendar ch.bobycharbon.party`).
    @Test("Pour de vrai : les dates entrent « À confirmer », puis la date fixée reste sous son titre et l'autre part",
          .enabled(if: Self.calendarAllowed))
    func writesAndSettlesInTheRealCalendar() throws {
        let store = EKEventStore()
        let memory = PollCalendarMemory(defaults: try #require(UserDefaults(suiteName: "poll-calendar-tests-\(UUID().uuidString)")))
        let writer = PollCalendarWriter(store: store, memory: memory)
        let start1 = Date().addingTimeInterval(40 * 86_400).rounded()
        let start2 = start1.addingTimeInterval(7 * 86_400)
        let iso = ISO8601DateFormatter()
        let request = try #require(PollCalendarRequest(body(dates: [
            ["id": d1, "start": iso.string(from: start1), "end": ""],
            ["id": d2, "start": iso.string(from: start2), "end": ""],
        ])))
        defer { writer.settle(event, start: nil, end: nil, title: nil, cancelled: true) }

        #expect(writer.add(request)["total"] as? Int == 2)
        #expect(writer.add(request)["added"] as? Int == 0)  // un second toucher n'ajoute rien en double
        let added = writer.present(event)
        #expect(added.count == 2)
        #expect(added.values.allSatisfy { $0.title == "À confirmer · Paintball" })
        // « Provisoire » seulement si le calendrier sait le dire (le calendrier local du simulateur ne le sait pas).
        let supportsTentative = store.defaultCalendarForNewEvents?.supportedEventAvailabilities.contains(.tentative) == true
        #expect(!supportsTentative || added.values.allSatisfy { $0.availability == .tentative })

        let gone = try #require(added[d1]?.eventIdentifier)
        let keptId = try #require(added[d2]?.eventIdentifier)
        #expect(writer.settle(event, start: start2, end: nil, title: "Paintball", cancelled: false))
        #expect(store.event(withIdentifier: gone) == nil)
        let final = try #require(store.event(withIdentifier: keptId))
        #expect(final.title == "Paintball")
        #expect(memory.entries(event).isEmpty)
        try store.remove(final, span: .thisEvent)
    }

    /// Vrai iPhone (calendrier iCloud) : l'identifiant d'une entrée change après synchronisation. Essai de l'admin du
    /// 10.11 : les 4 dates restaient après « Fixer cette date ». L'app retrouve ses entrées par leur lien.
    @Test("Identifiants changés par la synchronisation : l'app retrouve ses dates et fait quand même le ménage",
          .enabled(if: Self.calendarAllowed))
    func settlesEvenWhenTheCalendarChangedTheIdentifiers() throws {
        let store = EKEventStore()
        let memory = PollCalendarMemory(defaults: try #require(UserDefaults(suiteName: "poll-calendar-tests-\(UUID().uuidString)")))
        let writer = PollCalendarWriter(store: store, memory: memory)
        let start1 = Date().addingTimeInterval(50 * 86_400).rounded()
        let start2 = start1.addingTimeInterval(7 * 86_400)
        let iso = ISO8601DateFormatter()
        let request = try #require(PollCalendarRequest(body(dates: [
            ["id": d1, "start": iso.string(from: start1), "end": ""],
            ["id": d2, "start": iso.string(from: start2), "end": ""],
        ])))
        defer { writer.settle(event, start: nil, end: nil, title: nil, cancelled: true) }
        #expect(writer.add(request)["total"] as? Int == 2)
        let written = writer.present(event)
        #expect(written.values.allSatisfy { $0.url == PollCalendar.link(event) })

        // Ce que fait iCloud : les identifiants retenus par l'app ne mènent plus nulle part.
        memory.save(event, [d1: "perime-1", d2: "perime-2"])
        #expect(writer.present(event).count == 2)
        #expect(writer.add(request)["added"] as? Int == 0)  // toujours pas de doublon

        #expect(writer.settle(event, start: start1, end: nil, title: "Paintball", cancelled: false))
        let left = store.events(matching: store.predicateForEvents(withStart: start1.addingTimeInterval(-60),
                                                                  end: start2.addingTimeInterval(4 * 3600), calendars: nil))
            .filter { $0.url == PollCalendar.link(event) }
        #expect(left.count == 1)
        #expect(left.first?.title == "Paintball" && left.first?.startDate == start1)
        try left.forEach { try store.remove($0, span: .thisEvent) }
    }

    static var calendarAllowed: Bool {
        let status = EKEventStore.authorizationStatus(for: .event)
        if #available(iOS 17.0, *) { return status == .fullAccess }
        return status == .authorized
    }
}

private extension Date {
    func rounded() -> Date { Date(timeIntervalSince1970: (timeIntervalSince1970 / 60).rounded() * 60) }
}


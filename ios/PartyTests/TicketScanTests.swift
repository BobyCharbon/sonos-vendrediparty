import Foundation
import Testing
@testable import Party

/// « Scanner les billets » (module Événements) : la page demande un scan, le lecteur natif rend le texte lu.
@MainActor
struct TicketScanTests {
    private let base = URL(string: "https://partytest.bobycharbon.ch")!

    /// Laisse la demande de scan démarrer (la feuille s'ouvre).
    private func waitOpen(_ model: WebModel) async {
        while !model.ticketScanOpen { await Task.yield() }
    }

    @Test("Le QR lu revient à la page et la feuille se ferme")
    func scannedTextGoesBackToThePage() async {
        let model = WebModel(start: base)
        let scan = Task { await model.scanTicket() }
        await waitOpen(model)
        model.finishTicketScan("https://partytest.bobycharbon.ch/?tab=events&ticket=abc")
        #expect(await scan.value == "https://partytest.bobycharbon.ch/?tab=events&ticket=abc")
        #expect(!model.ticketScanOpen)
    }

    @Test("Fermer sans scanner rend nil, une seule fois (la fermeture de la feuille suit le QR lu)")
    func closingAnswersOnce() async {
        let model = WebModel(start: base)
        let scan = Task { await model.scanTicket() }
        await waitOpen(model)
        model.finishTicketScan("QR")
        model.finishTicketScan(nil)  // onDismiss de la feuille, après le QR lu : sans effet
        #expect(await scan.value == "QR")

        let cancelled = Task { await model.scanTicket() }
        await waitOpen(model)
        model.finishTicketScan(nil)
        #expect(await cancelled.value == nil)
    }

    @Test("Une nouvelle demande clôt la précédente au lieu de la laisser en attente")
    func aNewRequestEndsThePreviousOne() async {
        let model = WebModel(start: base)
        let first = Task { await model.scanTicket() }
        await waitOpen(model)
        let second = Task { await model.scanTicket() }
        #expect(await first.value == nil)  // rendue dès que la seconde demande arrive
        #expect(model.ticketScanOpen)
        model.finishTicketScan("B")
        #expect(await second.value == "B")
    }
}

/// Billets payants : chaque nouvelle notification a son interrupteur dans Réglages › Notifications.
struct TicketPaymentNotificationTests {
    @Test("« Quelqu'un dit avoir payé » et « Paiement confirmé » : décodés, allumés par défaut, chacun son interrupteur")
    @MainActor
    func ticketPaymentSwitches() throws {
        let base = #"{"push_enabled": true, "new_event": "all", "event_changed": true, "poll_new": true, "date_fixed": true,"#
            + #""poll_nudge": true, "waitlist": true, "reminders": [], "chat": "all", "rsvp_mine": true, "proposals": false"#
        let before = try JSONDecoder().decode(EventNotificationPrefs.self, from: Data((base + "}").utf8))
        #expect(before.ticketPayDeclared == nil && before.ticketPayConfirmed == nil)  // avant la migration : reçues
        let p = try JSONDecoder().decode(EventNotificationPrefs.self, from: Data(
            (base + #", "ticket_pay_declared": true, "ticket_pay_confirmed": false}"#).utf8))
        #expect(p.ticketPayDeclared == true && p.ticketPayConfirmed == false)
        #expect(SettingsStore.applying("ticket_pay_declared", false, to: p).ticketPayDeclared == false)
        #expect(SettingsStore.applying("ticket_pay_confirmed", true, to: p).ticketPayConfirmed == true)
    }
}

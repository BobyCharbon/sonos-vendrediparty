import EventKit
import EventKitUI
import UIKit
import WebKit

/// `window.PartyNative.agenda` (contrat commun page ↔ app, 17.11) : calendriers de l'iPhone pour l'Agenda de Party.
/// status / requestAccess / calendars / setCalendar / events (affichage local, rien ne part) / syncBusy (plages « pris »
/// calculées ici, envoyées par l'app elle-même) / addToPhone (feuille d'iOS, sans autorisation) / openSettings.
final class AgendaBridge: NSObject, WKScriptMessageHandlerWithReply {
    static let handler = "partyAgenda"
    private weak var model: WebModel?

    init(model: WebModel) {
        self.model = model
    }

    /// Ajouté à window.PartyNative (NativeBridge.swift) : chaque méthode renvoie une promesse.
    static let script = """
    (function () {
      function call(body) { return window.webkit.messageHandlers.\(handler).postMessage(body); }
      return {
        status: function () { return call({ action: "status" }); },
        requestAccess: function () { return call({ action: "requestAccess" }); },
        calendars: function () { return call({ action: "calendars" }); },
        setCalendar: function (id, prefs) { return call(Object.assign({ action: "setCalendar", id: String(id) }, prefs || {})); },
        events: function (from, to) { return call({ action: "events", from: String(from), to: String(to) }); },
        syncBusy: function () { return call({ action: "syncBusy" }); },
        addToPhone: function (item) { return call(Object.assign({ action: "addToPhone" }, item || {})); },
        openSettings: function () { return call({ action: "openSettings" }); }
      };
    })()
    """

    @MainActor
    func userContentController(_ controller: WKUserContentController,
                               didReceive message: WKScriptMessage) async -> (Any?, String?) {
        guard AppConfig.isInternal(message.frameInfo.securityOrigin.url),
              let body = message.body as? [String: Any], let action = body["action"] as? String else { return (nil, "Action inconnue") }
        guard let agenda = model?.settings?.agenda else { return (nil, "App pas encore prête") }
        switch action {
        case "status":
            return (["access": agenda.access], nil)
        case "requestAccess":
            return (["access": await agenda.requestAccess()], nil)
        case "calendars":
            return (agenda.calendars(), nil)
        case "setCalendar":
            guard let id = body["id"] as? String else { return (nil, "Demande invalide") }
            return (["ok": agenda.setCalendar(id, shown: body["shown"] as? Bool, countsBusy: body["countsBusy"] as? Bool)], nil)
        case "events":
            guard let from = PollCalendar.date(body["from"]), let to = PollCalendar.date(body["to"]) else { return (nil, "Demande invalide") }
            return (agenda.events(from: from, to: to), nil)
        case "syncBusy":
            return (await agenda.syncBusy(), nil)
        case "addToPhone":
            guard let item = AgendaPhoneItem(body) else { return (nil, "Demande invalide") }
            return (["saved": await AgendaPhoneSheet.present(item, store: agenda.store)], nil)
        case "openSettings":
            if let url = URL(string: UIApplication.openSettingsURLString) { await UIApplication.shared.open(url) }
            return (["ok": true], nil)
        default:
            return (nil, "Action inconnue")
        }
    }
}

/// « Ajouter à mon iPhone » : ce que la page propose (validé ici, la page est une source extérieure).
struct AgendaPhoneItem: Equatable {
    let title: String
    let start: Date
    let end: Date
    let location: String?

    init?(_ body: [String: Any]) {
        guard let title = (body["title"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines), !title.isEmpty,
              let start = PollCalendar.date(body["start"]) else { return nil }
        self.title = String(title.prefix(200))
        self.start = start
        end = PollCalendar.date(body["end"]).flatMap { $0 > start ? $0 : nil } ?? start.addingTimeInterval(3600)
        let place = (body["location"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        location = place.isEmpty ? nil : String(place.prefix(300))
    }
}

/// Feuille d'ajout d'iOS (EKEventEditViewController) : la personne choisit le calendrier et enregistre elle-même ;
/// depuis iOS 17, aucune autorisation n'est demandée. Renvoie true si elle a enregistré.
@MainActor
enum AgendaPhoneSheet {
    static func present(_ item: AgendaPhoneItem, store: EKEventStore) async -> Bool {
        let scenes = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
        guard var top = scenes.flatMap(\.windows).first(where: \.isKeyWindow)?.rootViewController else { return false }
        while let next = top.presentedViewController { top = next }
        let event = EKEvent(eventStore: store)
        event.title = item.title
        event.startDate = item.start
        event.endDate = item.end
        event.location = item.location
        let sheet = EKEventEditViewController()
        sheet.eventStore = store
        sheet.event = event
        let delegate = Delegate()
        sheet.editViewDelegate = delegate
        objc_setAssociatedObject(sheet, &Delegate.key, delegate, .OBJC_ASSOCIATION_RETAIN)  // délégué faible : gardé par la feuille
        return await withCheckedContinuation { done in
            delegate.done = { saved in
                sheet.dismiss(animated: true)
                done.resume(returning: saved)
            }
            top.present(sheet, animated: true)
        }
    }

    private final class Delegate: NSObject, EKEventEditViewDelegate {
        var done: ((Bool) -> Void)?

        func eventEditViewController(_ controller: EKEventEditViewController, didCompleteWith action: EKEventEditViewAction) {
            let finish = done
            done = nil
            finish?(action == .saved)
            objc_setAssociatedObject(controller, &Delegate.key, nil, .OBJC_ASSOCIATION_RETAIN)
        }

        static var key = 0
    }
}

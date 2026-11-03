import UIKit
import WebKit

/// Ce que la page voit en plus dans l'app :
/// - `navigator.standalone === true` : la page se comporte comme l'app installée (pas d'invitation « Ajouter à
///   l'écran d'accueil », ios-app.js actif — voir CLAUDE.md, barre d'onglets iOS) ;
/// - `navigator.vibrate()` : rendu en retour haptique (Safari iOS l'ignore, l'app le rend enfin réel) ;
/// - `window.PartyNative.push.register()` : jeton APNs, puisque Web Push n'existe pas dans un WKWebView.
enum NativeBridge {
    static let hapticHandler = "partyHaptic"
    static let pushHandler = "partyPush"
    static let tabsHandler = "partyTabs"
    static let aiHandler = "partyAI"
    static let scanHandler = "partyScan"

    private static let script = """
    (function () {
      try { Object.defineProperty(navigator, "standalone", { get: function () { return true; }, configurable: true }); } catch (e) {}
      navigator.vibrate = function (pattern) {
        try { window.webkit.messageHandlers.\(hapticHandler).postMessage([].concat(pattern || 0)); } catch (e) {}
        return true;
      };
      window.PartyNative = {
        platform: "ios",
        version: "\(AppConfig.userAgentSuffix)",
        push: {
          // Promesse : { token, environment, bundleId } ; rejetée si l'utilisateur refuse les notifications.
          register: function () { return window.webkit.messageHandlers.\(pushHandler).postMessage({ action: "register" }); },
          status: function () { return window.webkit.messageHandlers.\(pushHandler).postMessage({ action: "status" }); }
        },
        // Barre d'onglets native : la page la décrit (app/static/native-tabs.js), l'app la dessine.
        tabs: {
          update: function (state) {
            try { window.webkit.messageHandlers.\(tabsHandler).postMessage(state); } catch (e) {}
          }
        },
        // Assistant IA : « ✨ Avec l'IA » (Événements) ouvre l'écran natif où l'on décrit l'événement à voix haute.
        ai: {
          createEvent: function () {
            try { window.webkit.messageHandlers.\(aiHandler).postMessage("event"); } catch (e) {}
          },
          editEvent: function (id) {
            try { window.webkit.messageHandlers.\(aiHandler).postMessage("edit:" + id); } catch (e) {}
          }
        },
        // « Scanner les billets » (Événements) : lecteur QR d'Apple ; promesse du texte lu, ou null si l'on ferme.
        scan: {
          qr: function () { return window.webkit.messageHandlers.\(scanHandler).postMessage("qr"); }
        },
        // Noms des contacts (avis f780431defe7) : promesse de { user_id: "Nom du contact" } pour « Nom · pseudo »
        // dans le module Événements ; noms lus sur cet iPhone, donnés seulement aux pages de Party.
        contacts: {
          names: function () { return window.webkit.messageHandlers.\(ContactNamesBridge.handler).postMessage("names"); },
          // « Ajouter aux contacts » (fiche d'un membre) : fiche Contacts d'Apple préremplie ; promesse à sa fermeture.
          add: function (person) {
            return window.webkit.messageHandlers.\(ContactNamesBridge.handler).postMessage(Object.assign({ action: "add" }, person || {}));
          }
        },
        // « Ajouter à l'app Cartes Apple » (billet) : feuille d'ajout PassKit ; promesse résolue à sa fermeture.
        wallet: {
          available: \(NativeWallet.available ? "true" : "false"),
          add: function (url) { return window.webkit.messageHandlers.\(NativeWallet.handler).postMessage(String(url)); }
        }
      };
    })();
    """

    @MainActor
    static func install(in controller: WKUserContentController, model: WebModel) {
        // Toutes les frames : le module Événements tourne dans une iframe de la page Party.
        controller.addUserScript(WKUserScript(source: script, injectionTime: .atDocumentStart, forMainFrameOnly: false))
        #if DEBUG
        // Captures d'écran sur simulateur : SIMCTL_CHILD_PARTY_DEBUG_JS="localStorage.setItem('vp_tab','games')".
        if let debugJS = ProcessInfo.processInfo.environment["PARTY_DEBUG_JS"] {
            controller.addUserScript(WKUserScript(source: debugJS, injectionTime: .atDocumentStart, forMainFrameOnly: true))
        }
        #endif
        controller.add(HapticHandler(), name: hapticHandler)
        controller.addScriptMessageHandler(PushHandler(), contentWorld: .page, name: pushHandler)
        controller.add(TabsHandler(model: model), name: tabsHandler)
        controller.add(AIHandler(model: model), name: aiHandler)
        controller.addScriptMessageHandler(ScanHandler(model: model), contentWorld: .page, name: scanHandler)
        controller.addScriptMessageHandler(WalletHandler(), contentWorld: .page, name: NativeWallet.handler)
        controller.addScriptMessageHandler(ContactNamesBridge(), contentWorld: .page, name: ContactNamesBridge.handler)
    }
}

/// Onglets décrits par la page principale → barre d'onglets native (les iframes ne comptent pas).
private final class TabsHandler: NSObject, WKScriptMessageHandler {
    private weak var model: WebModel?

    init(model: WebModel) {
        self.model = model
    }

    @MainActor
    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.frameInfo.isMainFrame, AppConfig.isInternal(message.frameInfo.securityOrigin.url),
              let state = TabBarState(message: message.body) else { return }
        model?.showTabs(state)
    }
}

/// « ✨ Avec l'IA » dans Événements (cadre du module compris) → écran natif de création d'événement.
private final class AIHandler: NSObject, WKScriptMessageHandler {
    private weak var model: WebModel?

    init(model: WebModel) {
        self.model = model
    }

    @MainActor
    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        guard AppConfig.isInternal(message.frameInfo.securityOrigin.url), let body = message.body as? String else { return }
        if body == "event" {
            model?.aiEditEventId = nil
        } else if body.hasPrefix("edit:"), let id = UUID(uuidString: String(body.dropFirst(5))) {
            model?.aiEditEventId = id.uuidString.lowercased()  // le serveur vérifie que la personne peut le modifier
        } else {
            return
        }
        model?.aiEventOpen = true
    }
}

/// « Scanner les billets » dans Événements (cadre du module compris) → lecteur QR natif ; le texte lu revient à la page.
private final class ScanHandler: NSObject, WKScriptMessageHandlerWithReply {
    private weak var model: WebModel?

    init(model: WebModel) {
        self.model = model
    }

    @MainActor
    func userContentController(_ controller: WKUserContentController,
                               didReceive message: WKScriptMessage) async -> (Any?, String?) {
        guard AppConfig.isInternal(message.frameInfo.securityOrigin.url) else { return (nil, "Origine refusée") }
        guard message.body as? String == "qr", let model else { return (nil, "Action inconnue") }
        return (await model.scanTicket() as Any?, nil)
    }
}

/// `navigator.vibrate([durée, pause, durée…])` → un choc haptique par vibration, au même rythme.
private final class HapticHandler: NSObject, WKScriptMessageHandler {
    private static let lightMaxMs = 20
    private static let mediumMaxMs = 60

    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let pattern = message.body as? [NSNumber], AppConfig.isInternal(message.frameInfo.securityOrigin.url) else { return }
        var delayMs = 0
        for (index, value) in pattern.map(\.intValue).enumerated() where value > 0 {
            if index % 2 == 0 {
                let style = Self.style(forDurationMs: value)
                DispatchQueue.main.asyncAfter(deadline: .now() + .milliseconds(delayMs)) {
                    UIImpactFeedbackGenerator(style: style).impactOccurred()
                }
            }
            delayMs += value
        }
    }

    private static func style(forDurationMs ms: Int) -> UIImpactFeedbackGenerator.FeedbackStyle {
        if ms <= lightMaxMs { return .light }
        return ms <= mediumMaxMs ? .medium : .heavy
    }
}

/// Inscription aux notifications natives, appelée par la page (bouton « Activer les notifications »).
private final class PushHandler: NSObject, WKScriptMessageHandlerWithReply {
    @MainActor
    func userContentController(_ controller: WKUserContentController,
                               didReceive message: WKScriptMessage) async -> (Any?, String?) {
        guard AppConfig.isInternal(message.frameInfo.securityOrigin.url) else { return (nil, "Origine refusée") }
        let action = (message.body as? [String: Any])?["action"] as? String
        do {
            switch action {
            case "register":
                let token = try await PushRegistrar.shared.register()
                return (["token": token, "environment": PushRegistrar.environment, "bundleId": Bundle.main.bundleIdentifier ?? ""], nil)
            case "status":
                return (["status": await PushRegistrar.shared.status()], nil)
            default:
                return (nil, "Action inconnue")
            }
        } catch {
            return (nil, error.localizedDescription)
        }
    }
}

/// `PartyNative.contacts.names()` → { identifiant de compte : nom du contact } (vide sans accès aux contacts).
final class ContactNamesBridge: NSObject, WKScriptMessageHandlerWithReply {
    static let handler = "partyContacts"

    @MainActor
    func userContentController(_ controller: WKUserContentController,
                               didReceive message: WKScriptMessage) async -> (Any?, String?) {
        guard AppConfig.isInternal(message.frameInfo.securityOrigin.url) else { return (nil, "Origine refusée") }
        if message.body as? String == "names" { return (ContactNames.shared.names, nil) }
        guard let body = message.body as? [String: Any], body["action"] as? String == "add",
              let phone = body["phone"] as? String, PhoneNumbers.e164(phone) != nil else { return (nil, "Action inconnue") }
        let contact = ContactCardSheet.newContact(phone: phone, firstName: body["firstName"] as? String,
                                                  lastName: body["lastName"] as? String, pseudo: body["nickname"] as? String ?? "")
        await ContactCardSheet.present(.new(contact))
        return (true, nil)
    }
}

private extension WKSecurityOrigin {
    var url: URL {
        URL(string: "\(`protocol`)://\(host)") ?? URL(string: "about:blank")!
    }
}

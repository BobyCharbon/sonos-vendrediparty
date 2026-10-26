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
        }
      };
    })();
    """

    @MainActor
    static func install(in controller: WKUserContentController) {
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

private extension WKSecurityOrigin {
    var url: URL {
        URL(string: "\(`protocol`)://\(host)") ?? URL(string: "about:blank")!
    }
}

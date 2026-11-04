import WebKit
import WidgetKit

/// Zicou vu par la page → widgets et Live Activity de l'éclosion. La page parle au serveur (/api/pet/me, act, coll) ;
/// l'app lit au passage la réponse (copie, jamais modifiée) et en garde l'essentiel. Aucun appel en plus au serveur :
/// pas d'ouverture comptée, aucune nouvelle (cadeau d'ami, éclosion) consommée à la place du panneau.
/// Compagnon fermé sur ce site (bêta, éteint en production : /api/pet/* → 404) : rien n'est gardé ni proposé.
enum PetWidgetBridge {
    static let handler = "partyPet"

    /// Champs gardés (le reste de la réponse ne quitte pas la page).
    static let script = """
    (function () {
      if (window.__partyPetWatch || typeof window.fetch !== "function") return;
      window.__partyPetWatch = true;
      var send = function (p) {
        var d = p.daily || {};
        window.webkit.messageHandlers.\(handler).postMessage({
          name: p.name, stage: p.stage, variant: p.variant, emotion: p.emotion, asleep: !!p.asleep, sick: !!p.sick,
          gauges: p.gauges || {}, streak: p.streak || 0, next_stage_in: p.next_stage_in, dies_at: p.dies_at || null,
          daily: { chest: { state: (d.chest || {}).state || null }, streak: { count: (d.streak || {}).count || 0 } }
        });
      };
      var original = window.fetch;
      window.fetch = function (input) {
        var answer = original.apply(this, arguments);
        try {
          var url = typeof input === "string" ? input : (input && input.url) || "";
          if (/\\/api\\/pet\\/(me|status|act|coll|collection)(\\?|$)/.test(url)) {
            answer.then(function (r) {
              if (r.status === 404) { window.webkit.messageHandlers.\(handler).postMessage({ off: true }); return; }
              if (!r.ok) return;
              r.clone().json().then(function (data) {
                if (data && data.pet && typeof data.pet.stage === "string") send(data.pet);
              }).catch(function () {});
            }).catch(function () {});
          }
        } catch (e) {}
        return answer;
      };
    })();
    """

    @MainActor
    static func install(in controller: WKUserContentController) {
        controller.addUserScript(WKUserScript(source: script, injectionTime: .atDocumentStart, forMainFrameOnly: true))
        controller.add(PetMessageHandler(), name: handler)
        watchLiveActivitySetting()
    }

    /// Interrupteur Live Activity des Réglages coupé : l'éclosion en cours s'arrête aussitôt.
    @MainActor
    private static func watchLiveActivitySetting() {
        settingObserver = settingObserver ?? NotificationCenter.default.addObserver(
            forName: UserDefaults.didChangeNotification, object: nil, queue: .main) { _ in
            Task { @MainActor in
                if !LiveActivitySetting.isEnabled { HatchActivities.endAll() }
            }
        }
    }

    @MainActor private static var settingObserver: NSObjectProtocol?

    /// Nouvel état reçu : enregistré pour les widgets (rechargés s'il a changé) et l'éclosion suivie.
    @MainActor
    static func received(_ state: PetWidgetState) {
        let before = PetWidgetStore.load()
        PetWidgetStore.save(state)
        if before.map({ !sameLook($0, state) }) ?? true {
            WidgetCenter.shared.reloadTimelines(ofKind: PetWidgetStore.widgetKind)
        }
        HatchActivities.sync(state)
        QuickAction.showCompanion(true)
    }

    /// Déconnexion, ou Compagnon fermé (404) : les widgets oublient Zicou, l'éclosion s'arrête, les actions rapides
    /// Zicou et Cadeau du jour disparaissent.
    @MainActor
    static func forget() {
        PetWidgetStore.clear()
        WidgetCenter.shared.reloadTimelines(ofKind: PetWidgetStore.widgetKind)
        HatchActivities.endAll()
        QuickAction.showCompanion(false)
    }

    /// App rouverte : l'éclosion terminée pendant que l'app était fermée est conclue.
    @MainActor
    static func appBecameActive() {
        // Rien de gardé : on ne touche à rien (la déconnexion passe par forget()).
        guard let state = PetWidgetStore.load() else { return }
        HatchActivities.sync(state)
    }

    /// Même dessin à l'écran (on ne recharge pas les widgets pour une simple relecture identique).
    static func sameLook(_ a: PetWidgetState, _ b: PetWidgetState) -> Bool {
        var a2 = a, b2 = b
        a2.at = .distantPast
        b2.at = .distantPast
        a2.hatchAt = nil
        b2.hatchAt = nil
        let gaugesClose = zip(a.gauges.all, b.gauges.all).allSatisfy { abs($0 - $1) < 3 }
        a2.gauges = b2.gauges
        return a2 == b2 && gaugesClose && abs(b.at.timeIntervalSince(a.at)) < 15 * 60
    }
}

/// Message de la page principale (origine Party seulement).
private final class PetMessageHandler: NSObject, WKScriptMessageHandler {
    @MainActor
    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.frameInfo.isMainFrame, AppConfig.isInternal(message.frameInfo.securityOrigin.url) else { return }
        if (message.body as? [String: Any])?["off"] as? Bool == true {
            PetWidgetBridge.forget()   // Compagnon fermé sur ce site : widgets neutres, ni éclosion ni actions Zicou
            return
        }
        guard JSONSerialization.isValidJSONObject(message.body),
              let data = try? JSONSerialization.data(withJSONObject: message.body),
              let state = PetWidgetState.decode(data, receivedAt: Date()) else { return }
        PetWidgetBridge.received(state)
    }
}

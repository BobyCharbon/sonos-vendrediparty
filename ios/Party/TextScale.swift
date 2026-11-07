import SwiftUI
import UIKit
import WebKit

/// Taille du texte choisie dans Réglages iOS (Dynamic Type, « Texte plus grand ») — campagne 2 : l'app l'ignorait.
///
/// - Vue web : les pages (Party, module Événements en react-native-web) sont écrites en px fixes. Un script injecté
///   dans chaque cadre (iframe du module comprise) pose `-webkit-text-size-adjust` sur la racine : seul le TEXTE
///   grandit, du même facteur que le style « Corps » d'iOS (17 pt par défaut) ; la mise en page garde sa largeur.
///   (`WKWebView.pageZoom` a été essayé : la page débordait à droite dans l'app.) Le facteur est borné à `maxScale`
///   pour que les boutons et les cartes tiennent encore.
/// - Écrans natifs : les styles .body, .headline… suivent déjà la préférence ; les tailles fixes d'un chiffre ou
///   d'un texte passent par `scaledFont`.
enum TextScale {
    static let bodyPoints: CGFloat = 17
    static let maxScale: CGFloat = 1.5
    static let minScale: CGFloat = 0.85
    /// Fonction posée dans chaque cadre par le script : la page la rappelle à chaque changement de taille.
    static let applyFunction = "__partyTextScale"

    /// Facteur du texte pour une taille iOS ; 1 à la taille par défaut (« Grand »).
    static func factor(for category: UIContentSizeCategory) -> CGFloat {
        let traits = UITraitCollection(preferredContentSizeCategory: category)
        let body = UIFontMetrics(forTextStyle: .body).scaledValue(for: bodyPoints, compatibleWith: traits)
        let factor = (body / bodyPoints * 100).rounded() / 100
        return min(max(factor, minScale), maxScale)
    }

    static func percent(for category: UIContentSizeCategory) -> Int {
        Int((factor(for: category) * 100).rounded())
    }

    /// Script de chaque cadre : la règle CSS, puis la même pour les iframes du même site déjà ouvertes.
    static func source(percent: Int) -> String {
        """
        (function () {
          window.\(applyFunction) = function (p) {
            var css = 'html { -webkit-text-size-adjust: ' + p + '% !important; text-size-adjust: ' + p + '% !important; }';
            var put = function () {
              var s = document.getElementById('party-text-scale');
              if (!s) { s = document.createElement('style'); s.id = 'party-text-scale'; (document.head || document.documentElement).appendChild(s); }
              s.textContent = css;
            };
            if (document.documentElement) put(); else document.addEventListener('DOMContentLoaded', put);
            var frames = document.querySelectorAll ? document.querySelectorAll('iframe') : [];
            for (var i = 0; i < frames.length; i++) {
              try { var w = frames[i].contentWindow; if (w && w.\(applyFunction)) w.\(applyFunction)(p); } catch (e) {}
            }
          };
          // Après le chargement : posée dès le début, la règle laissait la page blanche au lancement (vu en
          // simulateur, taille XXXL) ; appliquée ensuite, le texte grandit et la page se remet en place.
          var start = function () { window.\(applyFunction)(\(percent)); };
          if (document.readyState === 'complete') start(); else window.addEventListener('load', start);
        })();
        """
    }

    static func userScript(percent: Int) -> WKUserScript {
        WKUserScript(source: source(percent: percent), injectionTime: .atDocumentStart, forMainFrameOnly: false)
    }

    /// Au lancement : le script avec la taille actuelle du téléphone.
    static func install(in controller: WKUserContentController,
                        category: UIContentSizeCategory = UIApplication.shared.preferredContentSizeCategory) {
        controller.addUserScript(userScript(percent: percent(for: category)))
    }

    /// Taille changée app ouverte : les pages déjà là suivent tout de suite, les prochaines aussi (nouveau script,
    /// lancé après l'ancien).
    @MainActor
    static func update(_ webView: WKWebView, category: UIContentSizeCategory) {
        let p = percent(for: category)
        webView.configuration.userContentController.addUserScript(userScript(percent: p))
        webView.evaluateJavaScript("window.\(applyFunction) && window.\(applyFunction)(\(p))")
    }
}

/// Police à taille fixe qui suit malgré tout la taille du texte d'iOS (relative au style donné).
private struct ScaledFont: ViewModifier {
    @ScaledMetric private var size: CGFloat
    let weight: Font.Weight
    let design: Font.Design

    init(size: CGFloat, weight: Font.Weight, design: Font.Design, relativeTo style: Font.TextStyle) {
        _size = ScaledMetric(wrappedValue: size, relativeTo: style)
        self.weight = weight
        self.design = design
    }

    func body(content: Content) -> some View {
        content.font(.system(size: size, weight: weight, design: design))
    }
}

extension View {
    /// `.font(.system(size:…))` qui grandit avec la taille du texte d'iOS (même rendu à la taille par défaut).
    func scaledFont(size: CGFloat, weight: Font.Weight = .regular, design: Font.Design = .default,
                    relativeTo style: Font.TextStyle = .body) -> some View {
        modifier(ScaledFont(size: size, weight: weight, design: design, relativeTo: style))
    }
}

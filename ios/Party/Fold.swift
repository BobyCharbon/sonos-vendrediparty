import UIKit
import WebKit

/// iPhone Duo (iOS 27.1) : posture de l'appareil et pli de l'écran, vus par la vue web et transmis à la page.
/// La vue web ne voit pas le pli (WebKit n'a ni `devicePosture` ni segments d'écran) : l'app le lui dit.
///
/// Contrat pour la page (page principale seulement, jamais sur un autre iPhone : rien n'est posé ni envoyé) :
/// - `<html data-posture="closed|flat|book|laptop|half">` : fermé (écran extérieur), ouvert à plat, entrouvert en livre
///   (pli vertical), entrouvert posé comme un portable (pli horizontal), entrouvert sans pli dans la page ;
/// - variables CSS sur `<html>`, en px de la page, seulement quand un pli traverse la page :
///   `--fold-x`, `--fold-y`, `--fold-width`, `--fold-height` (marges du système comprises) ;
/// - `window.PartyFold` = `{ posture, fold: {x, y, width, height} | null }` et l'événement
///   `window` « party-fold » (`event.detail` = le même objet) à chaque changement et à chaque chargement de page.
/// Aucune règle de style.css ne s'en sert encore : l'apparence des pages ne change pas.
/// La charnière sert à savoir fermé / ouvert ; l'angle n'est pas transmis (Apple : jamais pour la mise en page).
struct FoldState: Equatable {
    enum Posture: String {
        case closed, flat, book, laptop, half
    }

    /// État de la charnière, sans dépendre d'iOS 27.1 (tests, cible iOS 16).
    enum Hinge {
        case closed, partiallyOpen, fullyOpen
    }

    let posture: Posture
    /// Pli actif, dans les coordonnées de la vue web (= px de la page, sans zoom) ; nil quand l'écran est d'un seul tenant.
    let fold: CGRect?

    /// nil : appareil sans charnière (tous les autres iPhone) ou état inconnu.
    init?(hinge: Hinge?, fold: CGRect?) {
        guard let hinge else { return nil }
        let fold = fold.flatMap { $0.isEmpty || $0.isNull ? nil : $0.integral }
        self.fold = fold
        switch (hinge, fold) {
        case (.closed, _): posture = .closed
        case (.fullyOpen, nil): posture = .flat
        case (_, let fold?): posture = fold.height >= fold.width ? .book : .laptop
        case (.partiallyOpen, nil): posture = .half
        }
    }

    /// Script qui pose l'état dans la page (attribut, variables CSS, `window.PartyFold`, événement « party-fold »).
    var script: String {
        let box = fold.map { "{\"x\":\(Int($0.minX)),\"y\":\(Int($0.minY)),\"width\":\(Int($0.width)),\"height\":\(Int($0.height))}" } ?? "null"
        return """
        (function (d) {
          var r = document.documentElement; if (!r) return;
          r.setAttribute('data-posture', d.posture);
          ['x', 'y', 'width', 'height'].forEach(function (k) {
            if (d.fold) r.style.setProperty('--fold-' + k, d.fold[k] + 'px'); else r.style.removeProperty('--fold-' + k);
          });
          window.PartyFold = d;
          window.dispatchEvent(new CustomEvent('party-fold', { detail: d }));
        })({"posture":"\(posture.rawValue)","fold":\(box)});
        """
    }
}

/// Vue web de Party : relit la posture quand la charnière bouge ou que la mise en page change (pliage, dépliage, Split View).
final class PartyWKWebView: WKWebView {
    /// Appelé avec le nouvel état (nil hors iPhone Duo) quand il change.
    var foldChanged: ((FoldState?) -> Void)?
    private var hinge: FoldState.Hinge?
    private var last: FoldState??

    /// iOS 27.1 : suivi de la charnière (appelé avec l'état de départ, puis à chaque changement).
    func followHinge() {
        guard #available(iOS 27.1, *) else { return }
        addInteraction(UIHingeInteraction { [weak self] _, update in
            guard let self else { return }
            self.hinge = update.hinge.flatMap { hinge in
                switch hinge.status {
                case .closed: .closed
                case .partiallyOpen: .partiallyOpen
                case .fullyOpen: .fullyOpen
                default: nil
                }
            }
            self.refreshFold()
            // Le pli devient actif juste après la charnière : relu à la mise en page suivante.
            DispatchQueue.main.async { [weak self] in self?.refreshFold() }
        })
    }

    override func layoutSubviews() {
        super.layoutSubviews()
        refreshFold()
    }

    // UIKit relance updateConstraints quand les régions réservées lues ici changent.
    override func updateConstraints() {
        super.updateConstraints()
        refreshFold()
    }

    private func refreshFold() {
        guard #available(iOS 27.1, *), hinge != nil else { return }
        let division = reservedRegions(kind: .division).first(where: \.isActive)?.frame
        let state = FoldState(hinge: hinge, fold: division)
        guard last != .some(state) else { return }
        last = .some(state)
        foldChanged?(state)
    }
}

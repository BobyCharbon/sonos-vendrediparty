import SwiftUI
import UIKit

/// Barre d'onglets iOS (UITabBar) décrite par la page. Un toucher est renvoyé à la page, qui décide :
/// l'onglet choisi ne reste sélectionné que si la page l'affiche vraiment (Événements « Bientôt » refuse).
struct NativeTabBar: UIViewRepresentable {
    let state: TabBarState
    let select: (String) -> Void

    /// Hauteur d'une barre d'onglets iOS, barre d'accueil en plus.
    static let height: CGFloat = 49

    private static let symbols = [
        "music": "music.note",
        "games": "gamecontroller",
        // Zicou (onglet du 4.11) : une boule à facettes ; pleine quand l'onglet est choisi.
        "pet": "circle.hexagongrid",
        "events": "calendar",
        "chats": "bubble.left.and.bubble.right",
        "feedback": "bubble.left",
        "account": "person.crop.circle",
    ]
    /// Symbole de l'onglet choisi, quand il diffère (sinon le même, teinté).
    private static let selectedSymbols = ["pet": "circle.hexagongrid.fill"]
    private static let fallbackSymbol = "circle"
    private static let soonBadge = "Bientôt"
    /// Délai laissé à la page pour confirmer l'onglet touché avant de revenir à l'onglet affiché.
    private static let confirmDelay: TimeInterval = 0.4

    static func item(for tab: TabBarState.Tab, tag: Int) -> UITabBarItem {
        let item = UITabBarItem(title: tab.label, image: UIImage(systemName: symbols[tab.id] ?? fallbackSymbol), tag: tag)
        if let selected = selectedSymbols[tab.id] { item.selectedImage = UIImage(systemName: selected) }
        return item
    }

    /// Libellés et pastilles à jour (barre du bas et barre verticale de l'iPhone Duo).
    static func refresh(_ items: [UITabBarItem], with tabs: [TabBarState.Tab]) {
        for (item, tab) in zip(items, tabs) {
            item.title = tab.label
            item.badgeValue = tab.soon ? soonBadge : tab.badge
            item.badgeColor = tab.soon ? .systemGray : nil
        }
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(select: select)
    }

    func makeUIView(context: Context) -> UITabBar {
        let bar = UITabBar()
        bar.delegate = context.coordinator
        bar.tintColor = AppConfig.uiAccent
        return bar
    }

    func updateUIView(_ bar: UITabBar, context: Context) {
        let coordinator = context.coordinator
        coordinator.select = select
        let ids = state.tabs.map(\.id)
        if coordinator.ids != ids {
            coordinator.ids = ids
            let items = state.tabs.enumerated().map { index, tab in
                Self.item(for: tab, tag: index)
            }
            bar.setItems(items, animated: false)
        }
        Self.refresh(bar.items ?? [], with: state.tabs)
        coordinator.activeIndex = state.activeIndex
        coordinator.showActive(in: bar)
    }

    @MainActor
    final class Coordinator: NSObject, UITabBarDelegate {
        var select: (String) -> Void
        var ids: [String] = []
        var activeIndex: Int?
        private let feedback = UISelectionFeedbackGenerator()

        init(select: @escaping (String) -> Void) {
            self.select = select
        }

        func showActive(in bar: UITabBar) {
            bar.selectedItem = activeIndex.flatMap { index in bar.items?.first { $0.tag == index } }
        }

        func tabBar(_ tabBar: UITabBar, didSelect item: UITabBarItem) {
            guard ids.indices.contains(item.tag) else { return }
            if item.tag != activeIndex { feedback.selectionChanged() }
            select(ids[item.tag])
            // La page confirme d'ordinaire dans la même image ; si elle refuse, on revient à l'onglet affiché.
            DispatchQueue.main.asyncAfter(deadline: .now() + NativeTabBar.confirmDelay) { [weak self, weak tabBar] in
                guard let self, let tabBar else { return }
                self.showActive(in: tabBar)
            }
        }
    }
}

/// iPhone Duo (iOS 27.1) : la barre d'onglets suit le système, qui la pose à la verticale sur le côté (écran extérieur,
/// écran intérieur en paysage). Seule une barre d'un vrai `UITabBarController` y passe (une `UITabBar` posée à la main
/// reste en bas) : celui-ci n'a que des écrans vides et transparents, la page et les écrans natifs restent dessous,
/// intacts. Comme `NativeTabBar`, un toucher est renvoyé à la page, qui décide de l'onglet affiché.
@available(iOS 27.1, *)
struct SystemTabBar: UIViewControllerRepresentable {
    let state: TabBarState
    let select: (String) -> Void
    /// Largeur que la barre verticale ajoute à la zone sûre de son côté (0 si elle tient dans la colonne de la barre d'état).
    let extraInset: (CGFloat) -> Void

    func makeUIViewController(context: Context) -> Host { Host() }

    func updateUIViewController(_ host: Host, context: Context) {
        host.select = select
        host.extraInset = extraInset
        host.show(state)
    }

    final class Host: UIViewController, UITabBarControllerDelegate {
        let tabs = UITabBarController()
        var select: (String) -> Void = { _ in }
        var extraInset: (CGFloat) -> Void = { _ in }
        private var ids: [String] = []
        private var reported: CGFloat = -1
        private let feedback = UISelectionFeedbackGenerator()

        override func loadView() {
            view = PassThroughView()
        }

        override func viewDidLoad() {
            super.viewDidLoad()
            (view as? PassThroughView)?.owner = self
            tabs.delegate = self
            tabs.view.tintColor = AppConfig.uiAccent
            tabs.view.backgroundColor = .clear
            addChild(tabs)
            tabs.view.frame = view.bounds
            tabs.view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
            view.addSubview(tabs.view)
            tabs.didMove(toParent: self)
        }

        func show(_ state: TabBarState) {
            let ids = state.tabs.map(\.id)
            if self.ids != ids {
                self.ids = ids
                tabs.setViewControllers(state.tabs.enumerated().map { index, tab in
                    let page = UIViewController()
                    page.view.backgroundColor = .clear
                    page.view.isUserInteractionEnabled = false
                    page.tabBarItem = NativeTabBar.item(for: tab, tag: index)
                    return page
                }, animated: false)
            }
            NativeTabBar.refresh(tabs.viewControllers?.map(\.tabBarItem) ?? [], with: state.tabs)
            if let active = state.activeIndex, tabs.selectedIndex != active { tabs.selectedIndex = active }
        }

        /// La page décide : le toucher lui est envoyé, l'onglet ne change qu'à sa réponse (`show`).
        func tabBarController(_ controller: UITabBarController, shouldSelect page: UIViewController) -> Bool {
            if let index = controller.viewControllers?.firstIndex(of: page), ids.indices.contains(index) {
                if index != controller.selectedIndex { feedback.selectionChanged() }
                select(ids[index])
            }
            return false
        }

        override func viewDidLayoutSubviews() {
            super.viewDidLayoutSubviews()
            guard let page = tabs.selectedViewController else { return }
            let edge = view.traitCollection.verticalBarEdge
            let extra = max(0, Self.side(of: page.view, edge: edge) - Self.side(of: view, edge: edge))
            // Hors de la passe de mise en page (l'état SwiftUI change ensuite).
            if extra != reported { reported = extra; DispatchQueue.main.async { [extraInset] in extraInset(extra) } }
        }

        /// Zone sûre du côté de la barre verticale.
        static func side(of view: UIView, edge: UIVerticalBarEdge) -> CGFloat {
            let onRight = (edge == .trailing) != (view.effectiveUserInterfaceLayoutDirection == .rightToLeft)
            return onRight ? view.safeAreaInsets.right : view.safeAreaInsets.left
        }

        /// Seule la bande de la barre (côté `verticalBarEdge`, hors zone sûre des écrans vides) reçoit les touchers.
        func takesTouch(at point: CGPoint) -> Bool {
            guard let page = tabs.selectedViewController else { return false }
            let edge = view.traitCollection.verticalBarEdge
            let onRight = (edge == .trailing) != (view.effectiveUserInterfaceLayoutDirection == .rightToLeft)
            let inset = Self.side(of: page.view, edge: edge)
            return onRight ? point.x >= view.bounds.width - inset : point.x <= inset
        }
    }

    final class PassThroughView: UIView {
        weak var owner: Host?
        override func hitTest(_ point: CGPoint, with event: UIEvent?) -> UIView? {
            guard owner?.takesTouch(at: point) == true else { return nil }  // le reste va à la page dessous
            return super.hitTest(point, with: event)
        }
    }
}

/// Côté où le système pose sa barre verticale (iPhone Duo, iOS 27.1) ; nil partout ailleurs (autres iPhone, écran
/// intérieur en portrait…). Vue vide, sans taille, relue à chaque changement d'écran, de taille ou d'orientation.
struct VerticalBarEdgeReader: UIViewRepresentable {
    let changed: (HorizontalEdge?) -> Void

    func makeUIView(context: Context) -> Reader {
        let reader = Reader()
        reader.isUserInteractionEnabled = false
        reader.changed = changed
        return reader
    }

    func updateUIView(_ reader: Reader, context: Context) {
        reader.changed = changed
    }

    final class Reader: UIView {
        var changed: (HorizontalEdge?) -> Void = { _ in }
        private var last: HorizontalEdge??
        private var registered = false

        override func didMoveToWindow() {
            super.didMoveToWindow()
            guard #available(iOS 27.1, *), window != nil else { return }
            if !registered {
                registered = true
                registerForTraitChanges(UITraitCollection.systemTraitsAffectingVerticalBarEdge) { (reader: Reader, _: UITraitCollection) in
                    reader.report()
                }
            }
            report()
        }

        @available(iOS 27.1, *)
        private func report() {
            let edge: HorizontalEdge? = switch traitCollection.verticalBarEdge {
            case .leading: .leading
            case .trailing: .trailing
            default: nil
            }
            guard last != .some(edge) else { return }
            last = .some(edge)
            // Hors de la mise à jour de SwiftUI en cours.
            DispatchQueue.main.async { [changed] in changed(edge) }
        }
    }
}

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
        label(item, tab.label)
        return item
    }

    /// VoiceOver lit le libellé français de l'onglet, jamais le nom anglais du symbole (« Game controller », 26.11).
    private static func label(_ item: UITabBarItem, _ text: String) {
        item.accessibilityLabel = text
        item.image?.accessibilityLabel = text
        item.selectedImage?.accessibilityLabel = text
    }

    /// Libellés et pastilles à jour (barre du bas et barre verticale de l'iPhone Duo).
    static func refresh(_ items: [UITabBarItem], with tabs: [TabBarState.Tab]) {
        for (item, tab) in zip(items, tabs) {
            item.title = tab.label
            label(item, tab.label)
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
            ChatTiming.mark("tab." + ids[item.tag])
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
    /// « Retour » en haut de la barre verticale (comme Safari) quand la page a un écran derrière ; nil sinon.
    var back: (() -> Void)?
    /// Largeur que la barre verticale ajoute à la zone sûre de son côté (0 si elle tient dans la colonne de la barre d'état).
    let extraInset: (CGFloat) -> Void

    func makeUIViewController(context: Context) -> Host { Host() }

    func updateUIViewController(_ host: Host, context: Context) {
        host.select = select
        host.extraInset = extraInset
        host.show(state)
        host.showBack(back)
    }

    final class Host: UIViewController, UITabBarControllerDelegate {
        let tabs = UITabBarController()
        var select: (String) -> Void = { _ in }
        var extraInset: (CGFloat) -> Void = { _ in }
        private var back: (() -> Void)?
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
                // Chaque écran vide est dans une pile de navigation : son bouton de gauche (Retour) monte en haut de
                // la barre verticale, au-dessus des onglets (seuls les conteneurs du système y passent).
                tabs.setViewControllers(state.tabs.enumerated().map { index, tab in
                    let page = UIViewController()
                    page.view.backgroundColor = .clear
                    page.view.isUserInteractionEnabled = false
                    let stack = UINavigationController(rootViewController: page)
                    stack.view.backgroundColor = .clear
                    let look = UINavigationBarAppearance()
                    look.configureWithTransparentBackground()
                    stack.navigationBar.standardAppearance = look
                    stack.navigationBar.scrollEdgeAppearance = look
                    stack.tabBarItem = NativeTabBar.item(for: tab, tag: index)
                    return stack
                }, animated: false)
                showBack(back, force: true)
            }
            NativeTabBar.refresh(tabs.viewControllers?.map(\.tabBarItem) ?? [], with: state.tabs)
            if let active = state.activeIndex, tabs.selectedIndex != active { tabs.selectedIndex = active }
        }

        /// Retour présent seulement quand la page a un écran derrière (icône et titre : exigé pour la barre verticale).
        func showBack(_ action: (() -> Void)?, force: Bool = false) {
            let had = back != nil
            back = action
            guard force || had != (action != nil) else { return }
            for case let stack as UINavigationController in tabs.viewControllers ?? [] {
                var item: UIBarButtonItem?
                if action != nil {
                    item = UIBarButtonItem(title: "Retour", image: UIImage(systemName: "chevron.backward"),
                                           primaryAction: UIAction { [weak self] _ in self?.back?() })
                    item?.accessibilityIdentifier = "duo-back"
                }
                stack.topViewController?.navigationItem.leftBarButtonItem = item
            }
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
            guard let page = Self.page(of: tabs) else { return }
            let edge = view.traitCollection.verticalBarEdge
            let extra = max(0, Self.side(of: page, edge: edge) - Self.side(of: view, edge: edge))
            // Hors de la passe de mise en page (l'état SwiftUI change ensuite).
            if extra != reported { reported = extra; DispatchQueue.main.async { [extraInset] in extraInset(extra) } }
        }

        /// Écran vide affiché (dans sa pile de navigation).
        static func page(of tabs: UITabBarController) -> UIView? {
            let selected = tabs.selectedViewController
            return ((selected as? UINavigationController)?.topViewController ?? selected)?.view
        }

        /// Zone sûre du côté de la barre verticale.
        static func side(of view: UIView, edge: UIVerticalBarEdge) -> CGFloat {
            let onRight = (edge == .trailing) != (view.effectiveUserInterfaceLayoutDirection == .rightToLeft)
            return onRight ? view.safeAreaInsets.right : view.safeAreaInsets.left
        }

        /// Seule la bande de la barre (côté `verticalBarEdge`, hors zone sûre des écrans vides) reçoit les touchers.
        func takesTouch(at point: CGPoint) -> Bool {
            guard let page = Self.page(of: tabs) else { return false }
            let edge = view.traitCollection.verticalBarEdge
            let onRight = (edge == .trailing) != (view.effectiveUserInterfaceLayoutDirection == .rightToLeft)
            let inset = Self.side(of: page, edge: edge)
            return onRight ? point.x >= view.bounds.width - inset : point.x <= inset
        }

        /// Fond vide de la barre (écran vide ou un de ses conteneurs) : le toucher n'est pas pour elle. Dans la colonne,
        /// iOS pose aussi le « ‹ » des piles de navigation natives dessous (Réglages › Notifications, Discussions…) :
        /// avalé ici, il ne faisait rien sur l'iPhone Duo (retour de l'admin, 19.11).
        func isBackdrop(_ hit: UIView) -> Bool {
            hit === view || hit === tabs.view || Self.page(of: tabs)?.isDescendant(of: hit) == true
        }
    }

    final class PassThroughView: UIView {
        weak var owner: Host?
        override func hitTest(_ point: CGPoint, with event: UIEvent?) -> UIView? {
            guard owner?.takesTouch(at: point) == true else { return nil }  // le reste va à la page dessous
            guard let hit = super.hitTest(point, with: event), owner?.isBackdrop(hit) == false else { return nil }
            return hit
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

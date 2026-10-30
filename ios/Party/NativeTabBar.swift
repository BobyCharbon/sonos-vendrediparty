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
        "events": "calendar",
        "chats": "bubble.left.and.bubble.right",
        "feedback": "bubble.left",
        "account": "person.crop.circle",
    ]
    private static let fallbackSymbol = "circle"
    private static let soonBadge = "Bientôt"
    /// Délai laissé à la page pour confirmer l'onglet touché avant de revenir à l'onglet affiché.
    private static let confirmDelay: TimeInterval = 0.4

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
                UITabBarItem(title: tab.label,
                             image: UIImage(systemName: Self.symbols[tab.id] ?? Self.fallbackSymbol),
                             tag: index)
            }
            bar.setItems(items, animated: false)
        }
        for (item, tab) in zip(bar.items ?? [], state.tabs) {
            item.title = tab.label
            item.badgeValue = tab.soon ? Self.soonBadge : tab.badge
            item.badgeColor = tab.soon ? .systemGray : nil
        }
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

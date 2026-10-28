import Combine
import Foundation

/// Onglet « Ton avis » natif : envoyer une idée ou un bug, suivre ses retours et les réponses de l'hôte.
/// Mêmes règles et mêmes appels que la page web (index.html, section data-view="feedback").
@MainActor
final class FeedbackStore: ObservableObject {
    struct Notice: Equatable {
        let text: String
        let isError: Bool
    }

    @Published private(set) var items: [FeedbackItem] = []
    @Published private(set) var loaded = false
    @Published private(set) var sending = false
    @Published var kind: FeedbackKind = .idea
    @Published var text = ""
    @Published var notice: Notice?
    /// Retours terminés depuis la dernière visite : mis en avant pendant cette visite, puis marqués « vus ».
    @Published private(set) var highlighted: Set<String> = []

    private let api: PartyAPI
    private weak var web: WebStorage?
    /// Onglet d'où vient l'idée (Musique, Jeux…) : l'hôte sait de quoi on parle.
    private let fromTab: () -> String?

    init(api: PartyAPI, web: WebStorage, fromTab: @escaping () -> String?) {
        self.api = api
        self.web = web
        self.fromTab = fromTab
    }

    var trimmedText: String { text.trimmingCharacters(in: .whitespacesAndNewlines) }

    var canSend: Bool {
        !sending && (FeedbackRules.minimumLength...FeedbackRules.maximumLength).contains(trimmedText.count)
    }

    /// L'onglet s'affiche : ses retours, et les terminés passent « vus » (la pastille s'éteint aussi sur la page).
    func appear() async {
        guard let me = await web?.guestIdentity() else { return }
        do {
            items = try await api.feedback(guestID: me.id)
            loaded = true
            let unseen = Set(items.filter(\.unseen).map(\.id))
            guard !unseen.isEmpty else { return }
            highlighted.formUnion(unseen)
            try await api.markFeedbackSeen(guestID: me.id)
            web?.refreshFeedbackBadge()
        } catch {
            loaded = true  // le formulaire reste utilisable, comme sur la page
        }
    }

    func send() async {
        guard canSend, let me = await web?.guestIdentity() else { return }
        sending = true
        defer { sending = false }
        do {
            items = try await api.sendFeedback(guestID: me.id, name: me.name, kind: kind.rawValue,
                                               text: trimmedText, fromTab: fromTab())
            text = ""
            notice = Notice(text: "Merci ! Ton message est bien arrivé 🙏", isError: false)
            web?.refreshFeedbackBadge()
        } catch {
            notice = Notice(text: error.localizedDescription, isError: true)
        }
    }
}

import Combine
import WebKit

/// État partagé de la vue web : la page à ouvrir et l'écran « hors ligne ».
@MainActor
final class WebModel: ObservableObject {
    @Published var failed = false
    /// Onglets de la page affichée ; nil sur une page sans barre d'onglets (admin, TV…).
    @Published private(set) var tabs: TabBarState?
    /// Écrans que l'hôte gère dans la page (« Gérer la soirée », « Gérer les retours ») plutôt qu'en vue invité
    /// native ; retenu écran par écran, d'une ouverture à l'autre. Sans effet pour un invité.
    @Published private(set) var hostManagedScreens = WebModel.savedManagedScreens() {
        didSet { UserDefaults.standard.set(hostManagedScreens.sorted(), forKey: Self.hostScreensKey) }
    }
    private static let hostScreensKey = "hostManagedScreens"
    /// Réglage de la version précédente (Musique seulement), repris une fois.
    private static let legacyMusicKey = "musicHostManages"
    /// Dernier onglet de contenu (Musique, Jeux…) : contexte d'une idée envoyée depuis « Ton avis ».
    private(set) var lastContentTab: String?
    private static let settingsTabs: Set<String> = ["feedback", "account", "host", "stats"]
    let start: URL
    weak var webView: WKWebView?
    /// Adresse demandée avant que la vue web existe (app lancée par un lien ou une notification).
    private var pending: URL?
    /// Page en cours de chargement qui n'a pas encore décrit ses onglets.
    private var awaitingTabs = false

    init(start: URL) {
        self.start = start
    }

    /// Onglets natifs (Musique, Ton avis), avec la même session que la page.
    private(set) var music: MusicStore?
    private(set) var feedback: FeedbackStore?
    private var cookieWatcher: CookieWatcher?

    func attach(_ webView: WKWebView) {
        self.webView = webView
        let cookieStore = webView.configuration.websiteDataStore.httpCookieStore
        let api = PartyAPI(base: start, jar: WebCookieJar(cookieStore))
        // Session d'hôte (vp_admin) ou code saisi après le chargement de la page : l'extension « Partager »
        // reçoit la session à jour à chaque changement de cookie.
        cookieWatcher = CookieWatcher(store: cookieStore) { [weak self] in
            Task { await self?.shareSession() }
        }
        music = MusicStore(api: api, web: self)
        feedback = FeedbackStore(api: api, web: self) { [weak self] in self?.lastContentTab }
        webView.load(URLRequest(url: pending ?? start))
        pending = nil
    }

    func open(_ url: URL) {
        let target = AppConfig.isInternal(url) ? url : start
        guard let webView else {
            pending = target
            return
        }
        failed = false
        webView.load(URLRequest(url: target))
    }

    func showTabs(_ state: TabBarState) {
        awaitingTabs = false
        guard state != tabs else { return }
        if let active = state.activeIndex.map({ state.tabs[$0].id }), !Self.settingsTabs.contains(active) {
            lastContentTab = active
        }
        tabs = state
    }

    var isHost: Bool { tabs?.host == true }

    /// Onglet natif affiché (nil : la page). L'hôte qui gère cet écran garde la page.
    var nativeScreen: String? {
        guard let screen = tabs?.nativeScreen else { return nil }
        return isHost && hostManagedScreens.contains(screen) ? nil : screen
    }

    /// Écran natif que l'hôte gère en ce moment dans la page (bouton « Vue invité » pour revenir).
    var hostManagedScreen: String? {
        guard isHost, let screen = tabs?.nativeScreen, hostManagedScreens.contains(screen) else { return nil }
        return screen
    }

    func hostManages(_ screen: String) -> Bool {
        hostManagedScreens.contains(screen)
    }

    /// L'hôte passe de la vue invité (natif) à la gestion dans la page pour cet écran, et inversement.
    func setHostManages(_ manages: Bool, screen: String) {
        if manages { hostManagedScreens.insert(screen) } else { hostManagedScreens.remove(screen) }
    }

    private static func savedManagedScreens() -> Set<String> {
        let defaults = UserDefaults.standard
        if let saved = defaults.stringArray(forKey: hostScreensKey) { return Set(saved) }
        return defaults.bool(forKey: legacyMusicKey) ? ["music"] : []
    }

    /// Nouvelle page : la barre actuelle reste jusqu'à ce que la page décrive la sienne (pas de clignement
    /// au rechargement) ; une page sans barre d'onglets (admin, TV…) la retire à la fin du chargement.
    func pageStarted() {
        awaitingTabs = true
    }

    func pageLoaded() {
        Task { await shareSession() }
        guard awaitingTabs else { return }
        awaitingTabs = false
        tabs = nil
    }

    /// Toucher d'un onglet natif : la page l'applique comme un toucher dans sa propre barre.
    func selectTab(_ id: String) {
        guard id.allSatisfy({ $0.isLetter }) else { return }  // identifiants de la page : music, games…
        webView?.evaluateJavaScript("window.PartyTabs && PartyTabs.select('\(id)')")
    }

    func reload() {
        failed = false
        guard let webView else { return }
        if webView.url == nil {
            webView.load(URLRequest(url: start))
        } else {
            webView.reload()
        }
    }
}

extension WebModel: WebStorage {
    /// Copie la session (identité + cookies du site) dans le trousseau partagé avec l'extension « Partager ».
    func shareSession() async {
        guard let webView, var me = await guestIdentity() else { return }
        // Prénom saisi dans l'extension « Partager » alors que la page n'en avait pas : la page le reprend.
        if me.name.isEmpty, let shared = SharedSession.load(), shared.guestID == me.id, !shared.name.isEmpty {
            me.name = shared.name
            writeLocal("vp_name", shared.name)
        }
        let cookies = await webView.configuration.websiteDataStore.httpCookieStore.allCookies()
            .filter { PartyAPI.cookie($0, appliesTo: start) }
        SharedSession.save(SessionSnapshot(base: start, guestID: me.id, name: me.name, cookies: cookies.map(StoredCookie.init)))
    }

    func guestIdentity() async -> GuestIdentity? {
        guard let id = await readLocal("vp_guest"), !id.isEmpty else { return nil }
        return GuestIdentity(id: id, name: await readLocal("vp_name") ?? "")
    }

    func readLocal(_ key: String) async -> String? {
        guard let webView, let script = Self.call("localStorage.getItem", key) else { return nil }
        return try? await webView.evaluateJavaScript(script) as? String
    }

    func refreshFeedbackBadge() {
        webView?.evaluateJavaScript("typeof loadFeedback === 'function' && loadFeedback(false)")
    }

    func writeLocal(_ key: String, _ value: String?) {
        let script = value.flatMap { Self.call("localStorage.setItem", key, $0) } ?? Self.call("localStorage.removeItem", key)
        guard let script else { return }
        webView?.evaluateJavaScript(script)
    }

    /// Appel JavaScript aux arguments encodés en JSON (aucune injection possible).
    private static func call(_ function: String, _ arguments: String...) -> String? {
        guard let data = try? JSONSerialization.data(withJSONObject: arguments),
              let list = String(data: data, encoding: .utf8) else { return nil }
        return "\(function)(...\(list))"
    }
}

/// Cookies de la vue web : la Musique native partage la session du site.
@MainActor
final class WebCookieJar: CookieJar {
    private let store: WKHTTPCookieStore

    init(_ store: WKHTTPCookieStore) {
        self.store = store
    }

    func allCookies() async -> [HTTPCookie] {
        await store.allCookies()
    }

    func keep(_ cookies: [HTTPCookie]) async {
        for cookie in cookies { await store.setCookie(cookie) }
    }
}

/// Prévient à chaque changement de cookie de la vue web (WKHTTPCookieStoreObserver), regroupé sur 0,5 s.
@MainActor
final class CookieWatcher: NSObject, WKHTTPCookieStoreObserver {
    private let store: WKHTTPCookieStore
    private let changed: () -> Void
    private var pending: Task<Void, Never>?
    private static let settleDelay: Duration = .milliseconds(500)

    init(store: WKHTTPCookieStore, changed: @escaping () -> Void) {
        self.store = store
        self.changed = changed
        super.init()
        store.add(self)
    }

    nonisolated func cookiesDidChange(in cookieStore: WKHTTPCookieStore) {
        Task { @MainActor in self.schedule() }
    }

    private func schedule() {
        pending?.cancel()
        pending = Task { [weak self] in
            try? await Task.sleep(for: Self.settleDelay)
            guard !Task.isCancelled else { return }
            self?.changed()
        }
    }
}


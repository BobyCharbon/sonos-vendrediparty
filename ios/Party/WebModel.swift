import Combine
import WebKit

/// État partagé de la vue web : la page à ouvrir et l'écran « hors ligne ».
@MainActor
final class WebModel: ObservableObject {
    @Published var failed = false
    /// Onglets de la page affichée ; nil sur une page sans barre d'onglets (admin, TV…).
    @Published private(set) var tabs: TabBarState?
    /// Mode de l'hôte pour la Musique, retenu d'une ouverture à l'autre : « Gérer la soirée » (page web et ses
    /// réglages) ou « Vue invité » (écran natif). Sans effet pour un invité.
    @Published private(set) var hostManages = UserDefaults.standard.bool(forKey: WebModel.hostModeKey) {
        didSet { UserDefaults.standard.set(hostManages, forKey: Self.hostModeKey) }
    }
    private static let hostModeKey = "musicHostManages"
    let start: URL
    weak var webView: WKWebView?
    /// Adresse demandée avant que la vue web existe (app lancée par un lien ou une notification).
    private var pending: URL?
    /// Page en cours de chargement qui n'a pas encore décrit ses onglets.
    private var awaitingTabs = false

    init(start: URL) {
        self.start = start
    }

    /// Onglet Musique natif, avec la même session que la page.
    private(set) var music: MusicStore?
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
        tabs = state
    }

    var isHost: Bool { tabs?.host == true }

    /// Onglet natif affiché (nil : la page). L'hôte en mode « Gérer la soirée » garde la page.
    var nativeScreen: String? {
        isHost && hostManages ? nil : tabs?.nativeScreen
    }

    /// L'hôte passe de « Vue invité » (natif) à « Gérer la soirée » (page) et inversement ; le choix est retenu.
    func setHostManages(_ manages: Bool) {
        hostManages = manages
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


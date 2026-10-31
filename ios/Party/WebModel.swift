import Combine
import WebKit

/// État partagé de la vue web : la page à ouvrir et l'écran « hors ligne ».
@MainActor
final class WebModel: ObservableObject {
    @Published var failed = false
    /// Écran « Créer un événement avec l'IA », demandé par le module Événements.
    @Published var aiEventOpen = false
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
    /// Écrans de la page rangés sous Réglages (index.html, SUB_SCREENS) : ouverts depuis les Réglages natifs.
    private static let settingsSubScreens: Set<String> = ["host", "stats"]
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
    private(set) var settings: SettingsStore?
    private(set) var hostMusic: HostMusicStore?
    /// Retours reçus (hôte), dans l'onglet « Retours » natif.
    private(set) var feedbackAdmin: FeedbackAdminStore?
    /// Discussions de groupe (avis n°10), onglet natif.
    private(set) var chats: ChatsStore?

    /// L'hôte gère la soirée dans l'écran natif (« Gérer la soirée ») plutôt qu'en vue invité ; retenu.
    @Published var hostNativeMusic = UserDefaults.standard.bool(forKey: "hostNativeMusic") {
        didSet { UserDefaults.standard.set(hostNativeMusic, forKey: "hostNativeMusic") }
    }
    private var cookieWatcher: CookieWatcher?

    /// Page du compte ouverte depuis les Réglages natifs (Mon profil, Confidentialité…) : la page s'affiche à la
    /// place de l'écran natif ; « Réglages » (ou l'onglet) y revient.
    @Published private(set) var pageDetail: String?

    /// Ce que les Réglages natifs ouvrent dans la page, en attendant leur version native.
    enum PagePlace: Equatable {
        /// Écran du module Événements (/settings/profile…), dans l'onglet Réglages.
        case account(String)
        /// Onglet de la page (host : Invités et messages, stats : Mes stats de jeu).
        case tab(String)
        /// Page /admin de la soirée.
        case admin
    }

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
        music?.start()  // suivi de la file dès le lancement (PartyApp le relance au retour au premier plan)
        feedback = FeedbackStore(api: api, web: self) { [weak self] in self?.lastContentTab }
        hostMusic = HostMusicStore(api: api, web: self)
        feedbackAdmin = FeedbackAdminStore(api: api, web: self)
        chats = ChatsStore(api: api, web: self)
        settings = SettingsStore(api: api, web: self, isHost: { [weak self] in self?.isHost ?? false },
                                 trackChanged: { [weak self] on, subscribed in
                                     self?.music?.trackPreferenceChanged(on, subscribed: subscribed)
                                 })
        webView.load(URLRequest(url: pending ?? start))
        pending = nil
    }

    func open(_ url: URL) {
        // Lien d'un pot commun (/pot/<lien>, ancien /tricount/<lien>) : Réglages › Pot commun ouvre « Rejoindre », la page ne change pas.
        if AppConfig.isInternal(url), let link = Self.tricountLink(in: url) {
            settings?.tricount.pendingJoin = link
            selectTab("account")
            return
        }
        let target = AppConfig.isInternal(url) ? url : start
        // Notification de discussion (?tab=chats&chat=<groupe>) : l'écran natif ouvre la conversation.
        chats?.requested = Self.chatRequested(in: target) ?? chats?.requested
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
        let active = state.activeIndex.map { state.tabs[$0].id }
        if let active, !Self.settingsTabs.contains(active) {
            lastContentTab = active
        }
        if active != pageDetail { pageDetail = nil }
        tabs = state
    }

    var isHost: Bool { tabs?.host == true }

    nonisolated static func tricountLink(in url: URL) -> String? {
        let parts = url.pathComponents
        guard parts.count == 3, ["pot", "tricount"].contains(parts[1]),
              parts[2].range(of: "^[0-9a-fA-F-]{36}$", options: .regularExpression) != nil else { return nil }
        return parts[2].lowercased()
    }

    nonisolated static func chatRequested(in url: URL) -> String? {
        let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []
        guard items.first(where: { $0.name == "tab" })?.value == "chats",
              let chat = items.first(where: { $0.name == "chat" })?.value,
              chat.range(of: "^[0-9a-fA-F-]{36}$", options: .regularExpression) != nil else { return nil }
        return chat.lowercased()
    }

    /// Onglet natif affiché (nil : la page). L'hôte qui gère cet écran garde la page.
    var nativeScreen: String? {
        guard let screen = tabs?.nativeScreen, screen != pageDetail else { return nil }
        return isHost && hostManagedScreens.contains(screen) ? nil : screen
    }

    func show(_ place: PagePlace) {
        switch place {
        case .account(let path):
            guard let script = Self.call("frameRoute", path) else { return }
            pageDetail = "account"
            webView?.evaluateJavaScript(script)
        case .tab(let id) where Self.settingsSubScreens.contains(id):
            // Sous-écran de Réglages dans la page (Invités et messages, Mes stats) : pas de bouton dans la barre
            // d'onglets, on l'ouvre directement ; la page s'affiche à la place des Réglages natifs (« ‹ Réglages »).
            guard let script = Self.call("showTab", id) else { return }
            pageDetail = "account"
            webView?.evaluateJavaScript(script)
        case .tab(let id):
            selectTab(id)
        case .admin:
            open(start.appendingPathComponent("admin"))
        }
    }

    /// Retour aux Réglages natifs ; le module revient à sa page d'accueil pour la prochaine fois.
    func closePageDetail() {
        pageDetail = nil
        webView?.evaluateJavaScript("typeof frameRoute === 'function' && frameRoute('/account')")
        Task { await settings?.refreshAccount() }
    }

    /// Écran natif que l'hôte gère en ce moment dans la page (bouton « Vue invité » pour revenir).
    var hostManagedScreen: String? {
        guard isHost, let screen = tabs?.nativeScreen, hostManagedScreens.contains(screen) else { return nil }
        return screen
    }

    func hostManages(_ screen: String) -> Bool {
        hostManagedScreens.contains(screen)
    }

    /// « Ancienne version » : la gestion de la soirée dans la page, en secours.
    func manageMusicInPage() {
        hostNativeMusic = false
        setHostManages(true, screen: "music")
    }

    /// L'hôte passe de la vue invité (natif) à la gestion dans la page pour cet écran, et inversement.
    func setHostManages(_ manages: Bool, screen: String) {
        if manages { hostManagedScreens.insert(screen) } else { hostManagedScreens.remove(screen) }
    }

    private static func savedManagedScreens() -> Set<String> {
        let defaults = UserDefaults.standard
        // « Retours » se gère désormais en natif : un ancien choix « dans la page » est oublié.
        if let saved = defaults.stringArray(forKey: hostScreensKey) { return Set(saved).subtracting(["feedback"]) }
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

    /// Événement créé par l'assistant IA : l'onglet Événements l'ouvre.
    func openEvent(_ id: String) {
        guard id.range(of: "^[0-9a-fA-F-]{36}$", options: .regularExpression) != nil else { return }
        selectTab("events")
        webView?.evaluateJavaScript("window.PartyEvents && PartyEvents.open('/events/event/\(id)')")
    }

    /// Toucher d'un onglet natif : la page l'applique comme un toucher dans sa propre barre.
    func selectTab(_ id: String) {
        guard id.allSatisfy({ $0.isLetter }) else { return }  // identifiants de la page : music, games…
        if id == pageDetail { closePageDetail() }
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

    func openInPage(_ url: URL) {
        open(url)
    }

    /// linkAccount (index.html) : relit le compte (vp_account) et l'identité de joueur ; le module Événements
    /// rechargé reprend le nouveau profil.
    func accountChanged() async {
        guard let webView else { return }
        let script = "if (typeof linkAccount === 'function') await linkAccount(); "
            + "const f = document.getElementById('eventsFrame'); if (f && f.contentWindow) f.contentWindow.location.reload();"
        _ = try? await webView.callAsyncJavaScript(script, arguments: [:], contentWorld: .page)
    }

    func storeSession(key: String, json: String) async {
        guard let webView else { return }
        _ = try? await webView.callAsyncJavaScript("localStorage.setItem(key, value)", arguments: ["key": key, "value": json],
                                                   contentWorld: .page)
        await accountChanged()
    }

    func clearSession() async {
        guard let webView else { return }
        // Le module Événements est rechargé avant de relier le compte : il ne peut plus réécrire l'ancienne session.
        let script = """
            const forget = () => Object.keys(localStorage).filter((k) => /^sb-.+-auth-token$/.test(k)).forEach((k) => localStorage.removeItem(k));
            forget();
            const f = document.getElementById('eventsFrame');
            if (f && f.contentWindow) f.contentWindow.location.reload();
            await new Promise((done) => setTimeout(done, 400));
            forget();
            if (typeof linkAccount === 'function') await linkAccount();
            """
        _ = try? await webView.callAsyncJavaScript(script, arguments: [:], contentWorld: .page)
    }

    /// freshToken (index.html) : jeton du compte, renouvelé au besoin par le serveur et réécrit pour le module.
    func accountToken() async -> String? {
        guard let webView else { return nil }
        let script = "return typeof freshToken === 'function' ? await freshToken() : null"
        let value = try? await webView.callAsyncJavaScript(script, arguments: [:], contentWorld: .page)
        return (value as? String).flatMap { $0.isEmpty ? nil : $0 }
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


import Combine
import WebKit

/// État partagé de la vue web : la page à ouvrir et l'écran « hors ligne ».
@MainActor
final class WebModel: ObservableObject {
    @Published var failed = false
    /// Écran « Créer un événement avec l'IA », demandé par le module Événements.
    @Published var aiEventOpen = false
    /// « ✨ Modifier avec l'IA » sur un événement : son id (nil : l'écran IA crée un événement).
    @Published var aiEditEventId: String?
    /// « Scanner les billets » (module Événements) : lecteur QR natif ouvert, le texte lu revient à la page.
    @Published var ticketScanOpen = false
    private var ticketScanReply: CheckedContinuation<String?, Never>?
    private var chatsPreloaded = false
    /// « Ajouter un titre » choisi avant que la page ait décrit ses onglets (lancement à froid).
    private var musicSearchWanted = false
    /// Onglets de la page affichée ; nil sur une page sans barre d'onglets (admin, TV…).
    @Published private(set) var tabs: TabBarState?
    /// Bulle de Zicou décrite par la page (pet/zicou-home.js) ; nil tant que la page n'en a rien dit (Zicou éteint).
    @Published private(set) var zicouBubble: ZicouBubbleState?
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
    /// Discussions ouvertes sur ce site (/api/features.discussions ; absent ou hors ligne : fermées). Fermées : ni
    /// onglet, ni « Écrire », ni conversation ouverte par un lien ou une notification.
    @Published private(set) var discussions = false
    private var api: PartyAPI?

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
        self.api = api
        refreshFeatures()
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
        // Noms des contacts (« Nom · pseudo ») : reconnaissance au lancement, puis à chaque changement du répertoire.
        ContactNames.shared.configure(api: api, web: self)
        settings = SettingsStore(api: api, web: self, isHost: { [weak self] in self?.isHost ?? false },
                                 trackChanged: { [weak self] on, subscribed in
                                     self?.music?.trackPreferenceChanged(on, subscribed: subscribed)
                                 })
        webView.load(URLRequest(url: pending ?? start))
        pending = nil
    }

    /// Crée un événement avec l'IA à partir d'un lien (partagé depuis Safari, Instagram…).
    func startAIEvent(link: String) {
        guard let store = settings?.aiEvent else {
            SharedSession.savePendingEvent(link)  // l'app n'est pas prête : on réessaiera à la prochaine ouverture
            return
        }
        aiEditEventId = nil
        aiEventOpen = true
        Task { await store.start(link: link) }
    }

    /// Ouvre le lecteur QR natif pour un billet ; rend le texte lu, ou nil si l'on ferme (une demande à la fois).
    func scanTicket() async -> String? {
        finishTicketScan(nil)
        return await withCheckedContinuation { reply in
            ticketScanReply = reply
            ticketScanOpen = true
        }
    }

    /// Fin du scan (QR lu, ou feuille fermée) : la page reçoit la réponse une seule fois.
    func finishTicketScan(_ text: String?) {
        let reply = ticketScanReply
        ticketScanReply = nil
        ticketScanOpen = false
        reply?.resume(returning: text)
    }

    func open(_ url: URL) {
        // Lien d'un pot commun (/pot/<lien>, ancien /tricount/<lien>) : Réglages › Pot commun ouvre « Rejoindre », la page ne change pas.
        if AppConfig.isInternal(url), let link = Self.tricountLink(in: url) {
            settings?.tricount.pendingJoin = link
            selectTab("account")
            return
        }
        // Lien d'invitation dans Party (/events/join/<lien>) : la feuille native « X t'invite sur Party » (Réglages).
        if AppConfig.isInternal(url), let invite = Self.appInviteLink(in: url) {
            settings?.friends.received(invite)
            selectTab("account")
            return
        }
        let target = AppConfig.isInternal(url) ? url : start
        // Notification de discussion (?tab=chats&chat=<groupe>) : l'écran natif ouvre la conversation.
        if discussions { chats?.requested = Self.chatRequested(in: target) ?? chats?.requested }
        guard let webView else {
            pending = target
            return
        }
        failed = false
        webView.load(URLRequest(url: target))
    }

    func showTabs(_ state: TabBarState) {
        awaitingTabs = false
        if musicSearchWanted {
            musicSearchWanted = false
            selectTab("music")
        }
        if discussions && !chatsPreloaded {  // page chargée (session lisible) : la liste est prête avant l'onglet
            chatsPreloaded = true
            Task { [weak self] in await self?.chats?.preload() }
        }
        guard state != tabs else { return }
        let active = state.activeIndex.map { state.tabs[$0].id }
        if let active, !Self.settingsTabs.contains(active) {
            lastContentTab = active
        }
        if active != pageDetail { pageDetail = nil }
        tabs = state
    }

    var isHost: Bool { tabs?.host == true }

    /// Barre d'onglets dessinée par l'app (Discussions retirées quand le site les a fermées).
    var visibleTabs: TabBarState? { tabs?.visible(discussions: discussions) }

    /// Fonctions ouvertes sur ce site (au lancement et au retour au premier plan). Une erreur réseau garde l'état connu.
    func refreshFeatures() {
        guard let api else { return }
        Task { [weak self] in
            guard let features = try? await api.features() else { return }
            self?.featuresChanged(features)
        }
    }

    func featuresChanged(_ features: PartyFeatures) {
        guard features.discussions != discussions else { return }
        discussions = features.discussions
        if discussions, tabs != nil, !chatsPreloaded {
            chatsPreloaded = true
            Task { [weak self] in await self?.chats?.preload() }
        }
    }

    nonisolated static func tricountLink(in url: URL) -> String? {
        let parts = url.pathComponents
        guard parts.count == 3, ["pot", "tricount"].contains(parts[1]),
              parts[2].range(of: "^[0-9a-fA-F-]{36}$", options: .regularExpression) != nil else { return nil }
        return parts[2].lowercased()
    }

    nonisolated static func appInviteLink(in url: URL) -> String? {
        let parts = url.pathComponents
        guard parts.count == 4, parts[1] == "events", parts[2] == "join",
              parts[3].range(of: "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", options: .regularExpression) != nil
        else { return nil }
        return parts[3].lowercased()
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
        guard let screen = visibleTabs?.nativeScreen, screen != pageDetail else { return nil }
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

    /// « Créer avec l'IA », étape 2 : le brouillon vient d'être enregistré, la page « Qui est invité » s'ouvre dans
    /// Événements (pré-réglage de qui voit, personnes citées cochées d'avance) ; on y choisit soi-même puis on publie.
    func openInvite(_ created: AIEvent.Created) {
        guard let path = AIEvent.invitePath(created.id, suggested: created.suggested.map(\.id), preset: created.preset) else { return }
        selectTab("events")
        webView?.evaluateJavaScript("window.PartyEvents && PartyEvents.open('\(path)')")
    }

    /// Messages directs : Discussions présentes et ouvertes (pas « Bientôt », réservé aux bêta-testeurs en production).
    var canWriteDirect: Bool {
        discussions && chats != nil && tabs?.tabs.contains { $0.id == "chats" && !$0.soon } == true
    }

    /// « Écrire » : LA conversation privée avec ce membre (créée au besoin), ouverte dans l'onglet Discussions.
    /// Le numéro de la personne dans mes contacts (empreinte) prouve qu'on se connaît, sans groupe ni événement commun.
    func writeDirect(to user: String) async -> Bool {
        guard let chats, await chats.write(to: user, contactHash: ContactNames.shared.contactHash(for: user)) else { return false }
        selectTab("chats")
        return true
    }

    /// Fiche d'un membre › son Zicou : l'onglet Zicou de la page, sur sa visite (ami) ou sur le mien (« Adopter le mien »).
    func openZicou(visit: String?) {
        selectTab("pet")
        if let visit, visit.range(of: "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", options: .regularExpression) != nil {
            webView?.evaluateJavaScript("window.Pet && Pet.visit('\(visit)')")
        }
    }

    /// Lien interne « ?tab=chats&chat=<id> » suivi dans la page déjà chargée (fiche d'un joueur › Écrire, toucher
    /// d'une notification) : l'écran natif ouvre la conversation, la page ne se recharge pas.
    func openNativeChat(_ url: URL) -> Bool {
        guard discussions, tabs != nil, let chats, let chat = Self.chatRequested(in: url) else { return false }
        chats.requested = chat
        selectTab("chats")
        return true
    }

    /// Toucher d'un onglet natif : la page l'applique comme un toucher dans sa propre barre.
    /// Action rapide de l'icône : le Compagnon (adresse de la page) ou Musique avec la recherche prête.
    func perform(_ action: QuickAction) {
        switch action.target() {
        case .page(let url):
            open(url)
        case .addTrack:
            if tabs == nil { musicSearchWanted = true } else { selectTab("music") }
            QuickAction.requestMusicSearch()
        }
    }

    func showZicouBubble(_ state: ZicouBubbleState) {
        guard state != zicouBubble else { return }
        zicouBubble = state
    }

    /// Toucher de la bulle native : la page ouvre Zicou (onglet, ou l'accueil de l'œuf).
    func openZicouBubble() {
        webView?.evaluateJavaScript("window.ZicouHome && ZicouHome.openFromApp && ZicouHome.openFromApp()")
    }

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
        PetWidgetBridge.forget()  // widgets Zicou : plus de compte, plus de Zicou
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


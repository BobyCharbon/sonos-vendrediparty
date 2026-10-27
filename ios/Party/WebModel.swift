import Combine
import WebKit

/// État partagé de la vue web : la page à ouvrir et l'écran « hors ligne ».
@MainActor
final class WebModel: ObservableObject {
    @Published var failed = false
    /// Onglets de la page affichée ; nil sur une page sans barre d'onglets (admin, TV…).
    @Published private(set) var tabs: TabBarState?
    /// L'hôte a ouvert « Gérer la soirée » : l'onglet natif laisse la place à la page jusqu'au prochain toucher.
    @Published private(set) var showsWebScreen = false
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

    func attach(_ webView: WKWebView) {
        self.webView = webView
        let api = PartyAPI(base: start, cookieStore: webView.configuration.websiteDataStore.httpCookieStore)
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
        if state.nativeScreen == nil || !state.host { showsWebScreen = false }  // autre onglet, ou plus hôte
        tabs = state
    }

    /// Onglet natif affiché (nil : la page).
    var nativeScreen: String? {
        showsWebScreen ? nil : tabs?.nativeScreen
    }

    /// « Gérer la soirée » : l'onglet de la page, avec les réglages de l'hôte.
    func manageInPage() {
        showsWebScreen = true
    }

    /// Nouvelle page : la barre actuelle reste jusqu'à ce que la page décrive la sienne (pas de clignement
    /// au rechargement) ; une page sans barre d'onglets (admin, TV…) la retire à la fin du chargement.
    func pageStarted() {
        awaitingTabs = true
    }

    func pageLoaded() {
        guard awaitingTabs else { return }
        awaitingTabs = false
        tabs = nil
    }

    /// Toucher d'un onglet natif : la page l'applique comme un toucher dans sa propre barre.
    func selectTab(_ id: String) {
        guard id.allSatisfy({ $0.isLetter }) else { return }  // identifiants de la page : music, games…
        // Nouveau toucher sur l'onglet affiché dans la page : retour à l'écran natif.
        if showsWebScreen, tabs?.nativeScreen == id { showsWebScreen = false }
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


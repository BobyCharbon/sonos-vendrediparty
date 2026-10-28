import SafariServices
import SwiftUI
import WebKit

/// La webapp dans un WKWebView réglé pour se comporter comme l'app installée depuis Safari.
struct PartyWebView: UIViewRepresentable {
    @ObservedObject var model: WebModel

    func makeCoordinator() -> Coordinator {
        Coordinator(model: model)
    }

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        // Cookies et localStorage gardés d'un lancement à l'autre (session, prénom, compte).
        config.websiteDataStore = .default()
        // Sons des jeux et vidéos sans plein écran forcé ni toucher préalable.
        config.allowsInlineMediaPlayback = true
        config.mediaTypesRequiringUserActionForPlayback = []
        config.applicationNameForUserAgent = AppConfig.userAgentSuffix
        NativeBridge.install(in: config.userContentController, model: model)

        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = context.coordinator
        webView.uiDelegate = context.coordinator
        webView.isOpaque = false
        webView.backgroundColor = AppConfig.uiBackground
        webView.scrollView.backgroundColor = AppConfig.uiBackground
        // La page place elle-même sa barre d'onglets au-dessus de la barre d'accueil (safe-area-inset-bottom).
        webView.scrollView.contentInsetAdjustmentBehavior = .never
        // Comme la PWA : pas de geste « retour » natif (le module Événements a son propre balayage depuis le bord).
        webView.allowsBackForwardNavigationGestures = false
        // Pas de zoom : l'app doit se sentir native (le viewport des pages l'interdit aussi).
        webView.scrollView.minimumZoomScale = 1
        webView.scrollView.maximumZoomScale = 1
        webView.scrollView.bouncesZoom = false
        webView.scrollView.delegate = context.coordinator
        #if DEBUG
        if #available(iOS 16.4, *) { webView.isInspectable = true }  // Safari > Développement sur le Mac
        #endif
        context.coordinator.webView = webView
        model.attach(webView)
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {}

    @MainActor
    final class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate {
        let model: WebModel
        weak var webView: WKWebView?

        init(model: WebModel) {
            self.model = model
        }

        // MARK: Navigation : le site dans l'app, le reste dehors

        func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            guard let url = action.request.url else { return decisionHandler(.cancel) }
            let scheme = url.scheme?.lowercased() ?? ""
            if ["about", "blob", "data"].contains(scheme) { return decisionHandler(.allow) }
            if url.pathExtension.lowercased() == "ics" {
                showCalendar(url)
                return decisionHandler(.cancel)
            }
            if (scheme == "https" || scheme == "http") && AppConfig.isInternal(url) {
                // target="_blank" vers le site lui-même : on reste dans la même vue.
                if action.targetFrame == nil { webView.load(action.request); return decisionHandler(.cancel) }
                return decisionHandler(.allow)
            }
            // Iframes tierces (lecteur intégré…) : chargées sur place, jamais renvoyées vers Safari.
            if let frame = action.targetFrame, !frame.isMainFrame { return decisionHandler(.allow) }
            // open.spotify.com, tel:, sms:, mailto:, webcal:, Google Agenda… : Safari ou l'app concernée.
            UIApplication.shared.open(url)
            decisionHandler(.cancel)
        }

        func webView(_ webView: WKWebView, decidePolicyFor response: WKNavigationResponse,
                     decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
            // Fichier agenda servi sans extension .ics : Safari affiche « Ajouter à Calendrier ».
            if response.response.mimeType == "text/calendar", let url = response.response.url {
                showCalendar(url)
                return decisionHandler(.cancel)
            }
            decisionHandler(.allow)
        }

        func webView(_ webView: WKWebView, didCommit navigation: WKNavigation!) {
            model.pageStarted()
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            model.pageLoaded()
            model.failed = false
        }

        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            handle(error)
        }

        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            handle(error)
        }

        /// Processus web tué par iOS (mémoire) : on recharge plutôt que d'afficher une page blanche.
        func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
            webView.reload()
        }

        private func handle(_ error: Error) {
            let code = (error as NSError).code
            // Navigation annulée par nous-mêmes (lien externe, .ics) : pas une panne réseau.
            if code == NSURLErrorCancelled || code == 102 /* WebKitErrorFrameLoadInterruptedByPolicyChange */ { return }
            model.failed = true
        }

        private func showCalendar(_ url: URL) {
            guard url.scheme?.hasPrefix("http") == true else { return UIApplication.shared.open(url) }
            present(SFSafariViewController(url: url))
        }

        // MARK: Fenêtres et boîtes de dialogue (WKWebView n'affiche rien sans ça)

        func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                     for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
            // window.open(…, "_blank") : même règle qu'un lien.
            if let url = action.request.url {
                if AppConfig.isInternal(url) { webView.load(action.request) } else { UIApplication.shared.open(url) }
            }
            return nil
        }

        func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String,
                     initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
            let alert = UIAlertController(title: nil, message: message, preferredStyle: .alert)
            alert.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler() })
            present(alert, orElse: completionHandler)
        }

        func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String,
                     initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
            let alert = UIAlertController(title: nil, message: message, preferredStyle: .alert)
            alert.addAction(UIAlertAction(title: "Annuler", style: .cancel) { _ in completionHandler(false) })
            alert.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler(true) })
            present(alert, orElse: { completionHandler(false) })
        }

        func webView(_ webView: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String, defaultText: String?,
                     initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (String?) -> Void) {
            let alert = UIAlertController(title: nil, message: prompt, preferredStyle: .alert)
            alert.addTextField { $0.text = defaultText }
            alert.addAction(UIAlertAction(title: "Annuler", style: .cancel) { _ in completionHandler(nil) })
            alert.addAction(UIAlertAction(title: "OK", style: .default) { _ in
                completionHandler(alert.textFields?.first?.text)
            })
            present(alert, orElse: { completionHandler(nil) })
        }

        /// Micro / caméra demandés par la page : la permission iOS suffit, pas de seconde question du site.
        func webView(_ webView: WKWebView, requestMediaCapturePermissionFor origin: WKSecurityOrigin,
                     initiatedByFrame frame: WKFrameInfo, type: WKMediaCaptureType,
                     decisionHandler: @escaping (WKPermissionDecision) -> Void) {
            let host = origin.host.lowercased()
            decisionHandler(AppConfig.internalHosts.contains(host) ? .grant : .prompt)
        }

        private func present(_ controller: UIViewController, orElse fallback: @escaping () -> Void = {}) {
            guard var top = webView?.window?.rootViewController else { return fallback() }
            while let next = top.presentedViewController { top = next }
            top.present(controller, animated: true)
        }
    }
}

// Pas de zoom au pincement ni au double-tap : aucune vue n'est zoomable.
extension PartyWebView.Coordinator: UIScrollViewDelegate {
    func viewForZooming(in scrollView: UIScrollView) -> UIView? { nil }
}

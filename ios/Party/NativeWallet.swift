import PassKit
import UIKit
import WebKit

/// « Ajouter à l'app Cartes Apple » sous le billet d'un événement. Une WKWebView n'ouvre pas les .pkpass :
/// la page prépare le billet (/api/wallet/ticket), puis passe son lien à l'app, qui le télécharge et montre la
/// feuille d'ajout d'Apple (PKAddPassesViewController). Réponse à la page : true une fois la feuille fermée.
enum NativeWallet {
    static let handler = "partyWallet"
    static let passPath = "/api/wallet/pass/"

    /// Le Wallet existe sur cet appareil (pas sur certains iPad gérés, ni si un profil le bloque).
    static var available: Bool { PKAddPassesViewController.canAddPasses() }

    /// Seuls les billets préparés par Party : serveur Party en https, chemin des billets, extension .pkpass.
    static func isPassURL(_ url: URL) -> Bool {
        guard url.scheme?.lowercased() == "https", AppConfig.isInternal(url),
              url.host?.lowercased().hasSuffix(".bobycharbon.ch") == true else { return false }
        return url.path.hasPrefix(passPath) && url.pathExtension == "pkpass" && url.query == nil
    }

    enum Failure: LocalizedError {
        case refused, download, invalid, unavailable

        var errorDescription: String? {
            switch self {
            case .refused: "Adresse de billet refusée"
            case .download: "Le billet n’a pas pu être téléchargé. Réessaie."
            case .invalid: "Ce billet n’est pas valable pour Cartes Apple."
            case .unavailable: "L’app Cartes n’est pas disponible sur cet appareil."
            }
        }
    }

    static func pass(at url: URL, session: URLSession = .shared) async throws -> PKPass {
        guard isPassURL(url) else { throw Failure.refused }
        let (data, response) = try await session.data(from: url)
        guard (response as? HTTPURLResponse)?.statusCode == 200 else { throw Failure.download }
        do {
            return try PKPass(data: data)
        } catch {
            throw Failure.invalid
        }
    }

    @MainActor
    static func present(_ pass: PKPass) async throws {
        guard available, let controller = PKAddPassesViewController(pass: pass), let top = topController() else {
            throw Failure.unavailable
        }
        await withCheckedContinuation { (done: CheckedContinuation<Void, Never>) in
            let delegate = Delegate { done.resume() }
            controller.delegate = delegate
            objc_setAssociatedObject(controller, &Delegate.key, delegate, .OBJC_ASSOCIATION_RETAIN_NONATOMIC)
            top.present(controller, animated: true)
        }
    }

    @MainActor
    private static func topController() -> UIViewController? {
        let scenes = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
        var top = scenes.flatMap(\.windows).first(where: \.isKeyWindow)?.rootViewController
        while let next = top?.presentedViewController { top = next }
        return top
    }

    private final class Delegate: NSObject, PKAddPassesViewControllerDelegate {
        nonisolated(unsafe) static var key: UInt8 = 0
        private var finish: (() -> Void)?

        init(finish: @escaping () -> Void) {
            self.finish = finish
        }

        func addPassesViewControllerDidFinish(_ controller: PKAddPassesViewController) {
            controller.dismiss(animated: true)
            finish?()
            finish = nil
        }
    }
}

/// `window.PartyNative.wallet.add(url)` (cadre du module Événements compris).
final class WalletHandler: NSObject, WKScriptMessageHandlerWithReply {
    @MainActor
    func userContentController(_ controller: WKUserContentController,
                               didReceive message: WKScriptMessage) async -> (Any?, String?) {
        let origin = message.frameInfo.securityOrigin
        guard let page = URL(string: "\(origin.protocol)://\(origin.host)"), AppConfig.isInternal(page) else {
            return (nil, "Origine refusée")
        }
        guard let link = message.body as? String, let url = URL(string: link) else { return (nil, "Adresse invalide") }
        do {
            try await NativeWallet.present(try await NativeWallet.pass(at: url))
            return (true, nil)
        } catch {
            return (nil, error.localizedDescription)
        }
    }
}

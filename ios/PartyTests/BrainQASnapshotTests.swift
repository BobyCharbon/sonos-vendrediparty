import Foundation
import SwiftUI
import Testing
import UIKit
@testable import Party

/// QA Méninges : captures de l'écran « Mes stats de jeu › Méninges » et de la fiche membre, chargés depuis un faux
/// serveur local (réponses simulées), en sombre, avec le plus grand texte (Dynamic Type) et le texte normal.
/// Ne tourne que si on le demande : TEST_RUNNER_BRAIN_QA_URL=http://127.0.0.1:<port> et
/// TEST_RUNNER_BRAIN_QA_SHOTS=<dossier> (voir le rapport QA). Sinon le test est ignoré.
@MainActor
struct BrainQASnapshotTests {
    nonisolated static let env = ProcessInfo.processInfo.environment
    nonisolated static let enabled = env["BRAIN_QA_URL"] != nil && env["BRAIN_QA_SHOTS"] != nil

    private final class FakeWeb: WebStorage {
        func guestIdentity() async -> GuestIdentity? { nil }
        func readLocal(_ key: String) async -> String? { nil }
        func writeLocal(_ key: String, _ value: String?) {}
        func shareSession() async {}
        func refreshFeedbackBadge() {}
        func openInPage(_ url: URL) {}
        func accountToken() async -> String? { "jeton-qa" }
        func accountChanged() async {}
        func storeSession(key: String, json: String) async {}
        func clearSession() async {}
    }

    private final class NoCookies: CookieJar {
        func allCookies() async -> [HTTPCookie] { [] }
        func keep(_ cookies: [HTTPCookie]) async {}
    }

    /// Fenêtre de la taille de l'écran (une fenêtre plus haute ne se rend pas) ; la liste défile page par page,
    /// une capture par page : ios_<nom>_<n>.png.
    private func render<V: View>(_ view: V, name: String, size: DynamicTypeSize) async throws {
        let root = view.environment(\.dynamicTypeSize, size).preferredColorScheme(.dark)
        let host = UIHostingController(rootView: root)
        let scene = try #require(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first)
        let window = UIWindow(windowScene: scene)
        window.frame = scene.coordinateSpace.bounds
        window.overrideUserInterfaceStyle = .dark
        window.rootViewController = host
        window.makeKeyAndVisible()
        try await Task.sleep(for: .seconds(2))
        let dir = URL(fileURLWithPath: Self.env["BRAIN_QA_SHOTS"]!)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let list = Self.scrollView(in: window)
        for page in 0..<Self.maxPages {
            let image = UIGraphicsImageRenderer(bounds: window.bounds).image { _ in
                window.drawHierarchy(in: window.bounds, afterScreenUpdates: true)
            }
            try #require(image.pngData()).write(to: dir.appendingPathComponent("ios_\(name)_\(page).png"))
            guard let list else { break }
            let bottom = list.contentSize.height + list.adjustedContentInset.bottom - list.bounds.height
            if list.contentOffset.y >= bottom - 1 { break }
            let step = list.bounds.height * 0.8
            list.setContentOffset(CGPoint(x: 0, y: min(list.contentOffset.y + step, bottom)), animated: false)
            try await Task.sleep(for: .milliseconds(600))
        }
        window.isHidden = true
    }

    static let maxPages = 30

    private static func scrollView(in view: UIView) -> UIScrollView? {
        if let s = view as? UIScrollView, s.contentSize.height > 0 { return s }
        for sub in view.subviews { if let s = scrollView(in: sub) { return s } }
        return nil
    }

    @Test("Captures : Méninges (profil extrême) et fiche membre, sombre, Dynamic Type le plus grand et normal",
          .enabled(if: BrainQASnapshotTests.enabled))
    func snapshots() async throws {
        let api = PartyAPI(base: URL(string: Self.env["BRAIN_QA_URL"]!)!, jar: NoCookies())
        let web = FakeWeb()  // AccountStore ne la garde qu'en référence faible
        let store = AccountStore(api: api, web: web, settings: nil)
        await store.loadBrain()
        #expect(store.brainError == nil, "\(store.brainError ?? "")")
        #expect(store.brain?.plays ?? 0 > 0)
        let compare = try #require(try await api.brainCompare(token: "jeton-qa", target: "u-bob"))
        for (size, label) in [(DynamicTypeSize.accessibility5, "ax5"), (.large, "normal")] {
            let stats = NavigationStack {
                List { BrainStatsSections(store: store, openGames: {}) }.listStyle(.insetGrouped)
                    .navigationTitle("Mes stats de jeu").navigationBarTitleDisplayMode(.inline)
            }
            try await render(stats, name: "brain_stats_\(label)", size: size)
            let card = NavigationStack { List { BrainCompareSection(compare: compare) }.listStyle(.insetGrouped) }
            try await render(card, name: "brain_compare_\(label)", size: size)
        }
        withExtendedLifetime(web) {}
    }
}

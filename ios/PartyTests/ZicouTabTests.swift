import Foundation
import Testing
import UIKit
@testable import Party

/// Onglet « Zicou » (4.11) : « Ton avis » sort de la barre et devient une page des Réglages, sans rien perdre.
struct ZicouTabTests {
    private func tab(_ id: String, active: Bool = false, badge: Any = NSNull()) -> [String: Any] {
        ["id": id, "label": id, "active": active, "badge": badge, "soon": false]
    }

    private func state(screen: String?, feedback: [String: Any]? = nil) -> TabBarState? {
        var body: [String: Any] = [
            "hidden": false, "host": false, "native": ["music", "feedback", "chats", "account"],
            "tabs": [tab("music"), tab("games"), tab("pet"), tab("events"), tab("account", active: screen == "feedback" || screen == "account")],
        ]
        if let screen { body["screen"] = screen }
        if let feedback { body["feedback"] = feedback }
        return TabBarState(message: body)
    }

    @Test("Réglages › Ton avis : l'écran natif de « Ton avis » s'affiche, Réglages reste allumé dans la barre")
    func feedbackIsASettingsPage() throws {
        let s = try #require(state(screen: "feedback"))
        #expect(s.isSubScreen && s.nativeScreen == "feedback")
        #expect(s.activeIndex.map { s.tabs[$0].id } == "account")
        let settings = try #require(state(screen: "account"))
        #expect(!settings.isSubScreen && settings.nativeScreen == "account")
    }

    @Test("Page plus ancienne (sans « screen ») : comme avant, l'onglet actif décide")
    func olderPageStillWorks() throws {
        let s = try #require(state(screen: nil))
        #expect(!s.isSubScreen && s.nativeScreen == nil && s.feedback == nil)
    }

    @Test("Ligne « Ton avis » / « Retours » : libellé et pastille décrits par la page")
    func feedbackEntryIsDecoded() throws {
        let s = try #require(state(screen: "account", feedback: ["allowed": true, "label": "Retours", "badge": "3"]))
        #expect(s.feedback == TabBarState.FeedbackEntry(allowed: true, label: "Retours", badge: "3"))
        #expect(SettingsView.feedbackTitle(isHost: true, entry: s.feedback) == "Retours")
        #expect(SettingsView.feedbackTitle(isHost: false, entry: nil) == "Ton avis")
        #expect(SettingsView.showsFeedback(isHost: false, account: false, entry: s.feedback))
        #expect(!SettingsView.showsFeedback(isHost: false, account: false, entry: nil))
        let none = try #require(state(screen: "account", feedback: ["allowed": false, "label": "Ton avis", "badge": NSNull()]))
        #expect(none.feedback?.badge == nil)
        // Une description illisible ne casse pas la barre : la ligne garde ses règles d'avant.
        let odd = try #require(state(screen: "account", feedback: ["label": 3]))
        #expect(odd.feedback == nil && odd.tabs.count == 5)
    }

    @Test("Symbole SF de l'onglet Zicou : une boule à facettes, pleine une fois choisie")
    func zicouSymbol() throws {
        let item = NativeTabBar.item(for: try #require(state(screen: nil)).tabs[2], tag: 2)
        #expect(item.image != nil && item.selectedImage != nil)
        #expect(UIImage(systemName: "circle.hexagongrid") != nil && UIImage(systemName: "circle.hexagongrid.fill") != nil)
    }
}

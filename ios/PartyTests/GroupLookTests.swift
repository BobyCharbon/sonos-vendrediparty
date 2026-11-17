import Foundation
import Testing
@testable import Party

/// Groupes : nouveau graphisme (17.11) — emoji et couleur sur les lignes de Discussions ; « Gérer le groupe », ✎ et
/// Réglages › Groupes ouvrent les pages du module Événements.
struct GroupLookTests {
    @Test("Liste : un groupe garde son emoji et sa couleur (cache compris) ; un serveur plus ancien n'en donne pas")
    func decodesGroupLook() throws {
        let row = try JSONDecoder().decode(ChatSummary.self, from: Data(#"""
        {"id":"g1","name":"Les potes du foot","kind":"group","emoji":"⚽","color":"mint","notify":"mentions","unread":3}
        """#.utf8))
        #expect(row.emoji == "⚽" && row.color == "mint" && !row.direct && row.unread == 3)
        let again = try JSONDecoder().decode(ChatSummary.self, from: JSONEncoder().encode(row))
        #expect(again == row)
        let old = try JSONDecoder().decode(ChatSummary.self, from: Data(#"{"id":"g2","name":"Rando","kind":"group"}"#.utf8))
        #expect(old.emoji == nil && old.color == nil)  // la ligne garde alors ses initiales
    }

    @Test("Pages du module Événements : liste, création, page d'un groupe ; rien d'autre n'est envoyé à la page")
    func pagePaths() {
        #expect(GroupLook.pagePath(nil) == "/events/groups")
        #expect(GroupLook.pagePath("new") == "/events/group/new")
        #expect(GroupLook.pagePath("5E0D6A51-8F1C-4C51-9A6B-2B8F1E4C0A02") == "/events/group/5e0d6a51-8f1c-4c51-9a6b-2b8f1e4c0a02")
        #expect(GroupLook.pagePath("'); alert(1); ('") == nil)
        #expect(GroupLook.pagePath("../admin") == nil)
    }

    @Test("Couleurs : les 6 de Party, rose pour une couleur inconnue")
    func gradients() {
        let pink = GroupLook.gradient("pink")
        let unknown = GroupLook.gradient("turquoise")
        #expect(unknown.from == pink.from && unknown.to == pink.to)
        let keys = ["pink", "coral", "mint", "sky", "lavender", "lemon"]
        #expect(Set(keys.map { "\(GroupLook.gradient($0).to)" }).count == keys.count)
    }
}

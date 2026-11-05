import Foundation
import SwiftUI
import Testing
@testable import Party

/// Fiche profil › son Zicou (POST /api/pet/profile) : vedette avec ce qu'il porte, œuf terne sans Zicou, adoption
/// proposée seulement sur ma fiche ou quand je n'en ai pas, visite seulement chez un ami.
struct MemberZicouTests {
    private func decode(_ json: String) throws -> MemberZicou {
        try JSONDecoder().decode(MemberZicou.self, from: Data(json.utf8))
    }

    @Test("Avec un Zicou : nom, génération, âge, pièces et plus belle pièce")
    func decodesTheSpotlight() throws {
        let z = try decode(#"""
        {"member": "m1", "me": false, "friend": true, "mine": true,
         "zicou": {"name": "Paillette", "stage": "adult", "variant": "star", "emotion": "party", "outfit": null,
                   "acc": {"head": "couronne"}, "shiny": true, "gen": 2, "age_days": 5,
                   "best": {"id": "couronne", "slot": "head", "label": "Couronne", "emoji": "👑", "rarity": "epic", "rarity_label": "Épique", "color": "#a565ff"},
                   "acc_items": [{"id": "couronne", "slot": "head", "label": "Couronne", "emoji": "👑", "rarity": "epic", "rarity_label": "Épique", "color": "#a565ff"}]}}
        """#)
        let look = try #require(z.zicou)
        #expect(look.title == "Paillette" && look.subtitle == "Génération 2 · 5 jours" && look.shiny)
        #expect(look.pieces.count == 1 && look.highlight?.label == "Couronne")
        #expect(z.canVisit && !z.offersAdoption)
    }

    @Test("Nom refusé par le filtre : « Son Zicou » ; né aujourd'hui ; œuf ; pièce commune pas mise en avant")
    func fallbacks() throws {
        let z = try decode(#"""
        {"member": "m1", "me": false, "friend": false, "mine": false,
         "zicou": {"name": null, "stage": "baby", "emotion": "happy", "shiny": false, "gen": 1, "age_days": 0, "acc": {},
                   "best": {"id": "lunettes", "label": "Lunettes", "emoji": "🕶️", "rarity": "common", "color": "#9aa3b5"}, "acc_items": []}}
        """#)
        let look = try #require(z.zicou)
        #expect(look.title == "Son Zicou" && look.age == "né aujourd'hui" && look.highlight == nil && !z.canVisit)
        let egg = try decode(#"{"member": "m1", "me": true, "friend": false, "mine": true, "zicou": {"stage": "egg", "emotion": "egg", "gen": 1, "age_days": 0}}"#)
        #expect(egg.zicou?.subtitle == "Génération 1 · dans son œuf")
    }

    @Test("Sans Zicou : adopter le mien sur ma fiche ou si je n'en ai pas ; jamais si j'en ai déjà un")
    func adoption() throws {
        #expect(try decode(#"{"member": "m", "me": true, "friend": false, "mine": false, "zicou": null}"#).offersAdoption)
        #expect(try decode(#"{"member": "m", "me": false, "friend": false, "mine": false, "zicou": null}"#).offersAdoption)
        #expect(!(try decode(#"{"member": "m", "me": false, "friend": false, "mine": true, "zicou": null}"#).offersAdoption))
    }

    @Test("Couleur de rareté : hexadécimale ou arc-en-ciel (Mythique)")
    func rarityTint() throws {
        let piece = try JSONDecoder().decode(MemberZicou.Piece.self, from: Data(#"{"id": "m-1", "label": "Mythe", "emoji": "🌈", "rarity": "mythic", "color": "rainbow"}"#.utf8))
        _ = piece.tint   // ne plante pas
        #expect(piece.rarityLabel == nil)
    }
}

/// Captures du bloc (vedette, œuf terne) : écrites seulement si ZICOU_SHOTS est donné
/// (xcodebuild … TEST_RUNNER_ZICOU_SHOTS=/chemin), pour comparer avec le web.
@MainActor
struct MemberZicouShots {
    @Test("Captures du bloc Zicou de la fiche")
    func shots() throws {
        guard let dir = ProcessInfo.processInfo.environment["ZICOU_SHOTS"], !dir.isEmpty else { return }
        let with = try JSONDecoder().decode(MemberZicou.self, from: Data(#"""
        {"member": "m1", "me": false, "friend": true, "mine": true,
         "zicou": {"name": "Paillette", "stage": "adult", "emotion": "happy", "shiny": true, "gen": 1, "age_days": 3,
                   "best": {"id": "couronne", "label": "Couronne", "emoji": "👑", "rarity": "epic", "rarity_label": "Épique", "color": "#a565ff"},
                   "acc_items": [{"id": "couronne", "label": "Couronne", "emoji": "👑", "rarity": "epic", "rarity_label": "Épique", "color": "#a565ff"},
                                 {"id": "noeud", "label": "Nœud papillon", "emoji": "🎀", "rarity": "common", "color": "#9aa3b5"}]}}
        """#.utf8))
        let without = try JSONDecoder().decode(MemberZicou.self, from: Data(#"{"member": "m2", "me": false, "friend": false, "mine": false, "zicou": null}"#.utf8))
        for (name, data) in [("ios_with", with), ("ios_without", without)] {
            let view = MemberZicouView(data: data) { _ in }
                .padding(16).frame(width: 390).background(Color(hex: 0x15102A)).environment(\.colorScheme, .dark)
            let renderer = ImageRenderer(content: view)
            renderer.scale = 3
            let png = try #require(renderer.uiImage?.pngData())
            try png.write(to: URL(fileURLWithPath: dir).appendingPathComponent("zicou_profile_\(name).png"))
        }
    }
}

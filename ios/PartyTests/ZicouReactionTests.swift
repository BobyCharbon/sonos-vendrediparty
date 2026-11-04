import Foundation
import Testing
@testable import Party

/// Réactions de Zicou (app/pet_reactions.py) : bandeau après un titre ajouté, réglage « Réactions de Zicou ».
struct ZicouReactionTests {
    private func decode<T: Decodable>(_ json: String) throws -> T {
        try JSONDecoder().decode(T.self, from: Data(json.utf8))
    }

    @Test("Ajout d'un titre : la réaction de Zicou suit le bandeau habituel")
    func addedTextCarriesTheReaction() throws {
        let added: EnqueueResult = try decode("""
        {"ok": true, "track": {"id": "a"}, "source": "sonos",
         "zicou": [{"kind": "reward", "source": "music", "coins": 5, "text": "🪩 Paillette danse sur ton son ! +5 🪙"}]}
        """)
        #expect(MusicStore.addedText("Physical", zicou: added.zicou ?? []) == "« Physical » ajouté 🎶\n🪩 Paillette danse sur ton son ! +5 🪙")
    }

    @Test("Ancien serveur, invité sans compte ou plafond atteint : le bandeau habituel seul")
    func addedTextWithoutReaction() throws {
        let old: EnqueueResult = try decode(#"{"ok": true, "source": "sonos"}"#)
        #expect(old.zicou == nil)
        #expect(MusicStore.addedText("Physical", zicou: []) == "« Physical » ajouté 🎶")
    }

    @Test("Réglage lu et changé par le serveur Party")
    func decodesThePreference() throws {
        let prefs: ZicouReactionsPrefs = try decode(#"{"enabled": false}"#)
        #expect(prefs.enabled == false)
    }

    @Test("Compagnon en bêta : réglages affichés seulement si le serveur l'a allumé (absent = éteint)")
    func decodesTheCompanionFlag() throws {
        let on: PartyFeatures = try decode(#"{"compagnon": true}"#)
        let off: PartyFeatures = try decode(#"{"compagnon": false}"#)
        let old: PartyFeatures = try decode("{}")
        #expect(on.compagnon && !off.compagnon && !old.compagnon)
    }
}

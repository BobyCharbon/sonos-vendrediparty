import SwiftUI
import Testing
@testable import Party

/// Animations natives : Réduire les animations respecté, bandeaux qui se relancent, états qui ne rejouent rien.
struct MotionTests {
    @Test("Réduire les animations : toujours le fondu court, quelle que soit l'animation demandée")
    func reducedMotionFallsBackToFade() {
        #expect(Motion.pick(Motion.snappy, reduced: true) == Motion.fade)
        #expect(Motion.pick(Motion.bouncy, reduced: true) == Motion.fade)
        #expect(Motion.pick(Motion.smooth, reduced: false) == Motion.smooth)
    }

    @Test("Bandeau : un succès vibre « réussi », une erreur « échec », un texte seul ne vibre pas")
    func noticeTones() {
        #expect(NoticeBanner.Notice(text: "Ajouté", isError: false).tone == .success)
        #expect(NoticeBanner.Notice(text: "Raté", isError: true).tone == .error)
        #expect(NoticeBanner.Notice(text: "Info").tone == .info)
    }

    @Test("Bandeau : même texte publié deux fois avec deux identités = deux apparitions (le délai repart)")
    func noticeKeyUsesIdentity() {
        let first = NoticeBanner.Notice(text: "Titre retiré", isError: false, id: UUID())
        let second = NoticeBanner.Notice(text: "Titre retiré", isError: false, id: UUID())
        #expect(first.key != second.key)
        #expect(NoticeBanner.Notice(text: "Enregistré").key == NoticeBanner.Notice(text: "Enregistré").key)
    }

    @Test("Musique : l'état animé ne dépend pas du contenu (un rafraîchissement ne rejoue pas le fondu)")
    @MainActor
    func phaseKindIgnoresContent() throws {
        let one = try JSONDecoder().decode(PartyState.self, from: Data(#"{"active": true, "upcoming": []}"#.utf8))
        let two = try JSONDecoder().decode(PartyState.self, from: Data(#"{"active": true, "room": "Salon", "upcoming": []}"#.utf8))
        #expect(MusicStore.Phase.ready(one).kind == MusicStore.Phase.ready(two).kind)
        #expect(MusicStore.Phase.loading.kind != MusicStore.Phase.ready(one).kind)
        #expect(MusicStore.Phase.offline("a").kind == MusicStore.Phase.offline("b").kind)
    }
}

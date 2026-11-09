import Foundation
import Testing
@testable import Party

/// App envoyée à Apple (audit du 04.11.2026) : Discussions masquées quand le site les ferme, accord avant l'IA des
/// événements, « Créer mon compte » à la limite invité, version IA des retours reçus, Zicou réservé à la BETA.
@MainActor
struct AppStoreReadinessTests {
    private final class NoCookies: CookieJar {
        func allCookies() async -> [HTTPCookie] { [] }
        func keep(_ cookies: [HTTPCookie]) async {}
    }

    private func decode<T: Decodable>(_ json: String) throws -> T {
        try JSONDecoder().decode(T.self, from: Data(json.utf8))
    }

    // ── Discussions ──

    @Test("features.discussions : vrai seulement si le serveur le dit ; absent (ancien serveur) = fermé")
    func discussionsFeature() throws {
        let open: PartyFeatures = try decode(#"{"compagnon": false, "discussions": true}"#)
        let closed: PartyFeatures = try decode(#"{"compagnon": true, "discussions": false}"#)
        let old: PartyFeatures = try decode(#"{"compagnon": true}"#)
        #expect(open.discussions && !closed.discussions && !old.discussions)
        #expect(closed.compagnon && old.compagnon)
        #expect(PartyFeatures(compagnon: false).discussions == false)
    }

    private func tabs(active: String) -> TabBarState? {
        let ids = ["music", "games", "chats", "account"]
        let body: [String: Any] = [
            "hidden": false, "host": false, "screen": active, "native": ["music", "chats", "account"],
            "tabs": ids.map { ["id": $0, "label": $0, "active": $0 == active, "soon": $0 == "chats"] as [String: Any] },
        ]
        return TabBarState(message: body)
    }

    @Test("Discussions fermées : ni bouton dans la barre native ni écran natif, le reste ne bouge pas")
    func closedDiscussionsLeaveTheTabBar() throws {
        let state = try #require(tabs(active: "chats"))
        let closed = state.visible(discussions: false)
        #expect(closed.tabs.map(\.id) == ["music", "games", "account"])
        #expect(!closed.native.contains("chats") && closed.nativeScreen == nil)
        let onMusic = try #require(tabs(active: "music")).visible(discussions: false)
        #expect(onMusic.nativeScreen == "music" && onMusic.activeIndex == 0)
        #expect(state.visible(discussions: true) == state)
    }

    // ── Assistant IA des événements : accord ──

    @Test("403 « accord requis » reconnu ; une autre erreur ne rouvre pas la feuille")
    func consentRequiredError() {
        #expect(AIEvent.needsConsent(PartyAPIError.server("Accord requis")))
        #expect(AIEvent.needsConsent(PartyAPIError.server("Ton accord est requis pour utiliser l'IA")))
        #expect(!AIEvent.needsConsent(PartyAPIError.server("Description trop longue")))
        #expect(!AIEvent.needsConsent(PartyAPIError.offline))
    }

    @Test("Feuille d'accord : même composant que « Ton avis », dit ce qui part chez Anthropic")
    func consentCopy() {
        #expect(AIConsentSheet.Copy.feedback.text == FeedbackAI.consentText)
        #expect(AIConsentSheet.Copy.event.text.contains("Anthropic (Claude)"))
        #expect(AIConsentSheet.Copy.event.text.contains("captures d'écran"))
        #expect(AIConsentSheet.Copy.event.acceptID != AIConsentSheet.Copy.feedback.acceptID)
        // Accord version 2 : un seul texte (avis, voix, captures, photos, liens, tickets), le même que la feuille web.
        #expect(FeedbackAI.consentVersion == 2)
        for copy in [AIConsentSheet.Copy.feedback, .event, .receipt] {
            #expect(copy.title == "✨ Utiliser l'IA de Party ?" && copy.text == FeedbackAI.consentText)
        }
        for part in ["transcription de ta voix", "tes photos", "liens", "ticket du pot commun"] {
            #expect(FeedbackAI.consentText.contains(part))
        }
    }

    @Test("CGU : même texte que le web, sans Zicou ; contact support@vendrediparty.ch par défaut")
    func termsMatchTheWeb() {
        let all = TermsView.sections.flatMap { [$0.0] + $0.1 }.joined(separator: " ")
        #expect(!all.contains("Zicou"))
        #expect(all.contains("réponse de jeu montrée à la table"))
        #expect(TermsView.supportEmail == "support@vendrediparty.ch")
    }

    @Test("Sans accord connu : la feuille s'ouvre ; « Pas maintenant » ou fermée d'un geste = rien n'est envoyé")
    func consentSheetBlocksTheFirstRequest() async {
        let store = AIEventStore(api: PartyAPI(base: URL(string: "https://party.invalid")!, jar: NoCookies()), web: nil)
        let asking = Task { await store.ensureConsent(token: "t") }
        while !store.askingConsent { await Task.yield() }
        store.answerConsent(false)
        #expect(await asking.value == false)
        #expect(!store.askingConsent && !store.consentAccepted)

        let dismissed = Task { await store.ensureConsent(token: "t") }
        while !store.askingConsent { await Task.yield() }
        store.consentDismissed()
        #expect(await dismissed.value == false)
    }

    @Test("Pot commun › Scanner un ticket : feuille d'accord avant l'envoi ; refus = rien n'est envoyé")
    func receiptScanAsksConsentFirst() async {
        let store = TricountStore(api: PartyAPI(base: URL(string: "https://party.invalid")!, jar: NoCookies()), web: nil)
        let asking = Task { await store.ensureAIConsent(token: "t") }
        while !store.askingAIConsent { await Task.yield() }
        store.answerAIConsent(false)
        #expect(await asking.value == false)
        #expect(!store.askingAIConsent && !store.aiConsentAccepted)
        #expect(AIConsentSheet.Copy.receipt.text.contains("Anthropic (Claude)"))
    }

    @Test("Manifeste de Party : infos financières déclarées, aucun suivi")
    func privacyManifestDeclaresFinancialInfo() throws {
        let url = try #require(Bundle(for: TricountStore.self).url(forResource: "PrivacyInfo", withExtension: "xcprivacy"))
        let plist = try #require(NSDictionary(contentsOf: url))
        #expect(plist["NSPrivacyTracking"] as? Bool == false)
        let types = (plist["NSPrivacyCollectedDataTypes"] as? [[String: Any]] ?? []).compactMap { $0["NSPrivacyCollectedDataType"] as? String }
        #expect(types.contains("NSPrivacyCollectedDataTypeOtherFinancialInfo"))
        #expect(types.contains("NSPrivacyCollectedDataTypePhoneNumber"))
        // Exigence Apple du 09.11 : identifiant de l'appareil déclaré ; plus d'audio (dictée faite par Apple).
        #expect(types.contains("NSPrivacyCollectedDataTypeDeviceID"))
        #expect(types.contains("NSPrivacyCollectedDataTypeGameplayContent"))
        #expect(!types.contains("NSPrivacyCollectedDataTypeAudioData"))
    }

    // ── Réglages › Confidentialité : accord IA pour tous les comptes ──

    @Test("Accord IA : date en français, « Pas d'accord » sans accord ; ancien serveur sans date")
    func aiConsentLabel() throws {
        let given: AIConsentState = try decode(#"{"consent": "accepted", "consent_at": 1794225600}"#)
        #expect(given.accepted && given.label.hasPrefix("Accord donné le ") && given.label.contains("2026"))
        let declined: AIConsentState = try decode(#"{"consent": "declined", "consent_at": null}"#)
        #expect(!declined.accepted && declined.label.hasPrefix("Pas d'accord"))
        let old: AIConsentState = try decode(#"{"consent": "accepted"}"#)
        #expect(old.label == "Accord donné.")
        #expect(AIConsentSheet.Copy.settings.text == FeedbackAI.consentText)
        #expect(FeedbackAI.consentFootnote.contains("Réglages › Confidentialité"))
    }

    @Test("CGU : aucune tolérance, signalements traités sous 24 heures")
    func termsZeroTolerance() {
        let all = TermsView.sections.flatMap { $0.1 }.joined(separator: " ")
        #expect(all.contains("Aucune tolérance pour les contenus choquants ou les utilisateurs abusifs"))
        #expect(all.contains("traités sous 24 heures"))
    }

    // ── Musique : limite invité ──

    @Test("Limite invité atteinte (ou compte requis ce soir) : bouton « Créer mon compte » ; avant, la recherche")
    func guestLimitAsksForAnAccount() throws {
        let some: GuestTracks = try decode(#"{"used": 1, "limit": 3, "left": 2}"#)
        let none: GuestTracks = try decode(#"{"used": 3, "limit": 3, "left": 0}"#)
        let zero: GuestTracks = try decode(#"{"used": 0, "limit": 0, "left": 0}"#)
        #expect(!some.needsAccount && none.needsAccount && zero.needsAccount)
        #expect(none.text.contains("Crée ton compte") && !none.text.contains("dans Réglages"))
    }

    // ── Retours reçus : version de l'IA ──

    @Test("Retour reçu : titre ✨, type et zone de la version IA ; sans titre ou ancien avis = rien")
    func receivedFeedbackShowsTheAIVersion() throws {
        let json = """
        {"id": "a1", "text": "le quiz bug", "context": {"tab": "games", "ai": {"kind": "bug", "area": "games",
         "title": "Le Quiz se fige", "description": "Il se fige.", "steps": ["Lancer"], "actual": "Figé"}}}
        """
        let item: AdminFeedback.Item = try decode(json)
        let ai = try #require(item.ai)
        #expect(ai.title == "Le Quiz se fige" && ai.kindAndArea == "🐞 Bug · 🎲 Jeux")
        #expect(ai.rows.map(\.label) == ["Étapes", "Ce qui se passe"])
        let plain: AdminFeedback.Item = try decode(#"{"id": "a2", "text": "x", "context": {"ai": {"kind": "idea"}}}"#)
        #expect(plain.ai == nil)
        let old: AdminFeedback.Item = try decode(#"{"id": "a3", "text": "x"}"#)
        #expect(old.ai == nil)
    }

    // ── Zicou : BETA seulement ──

    @Test("Tests (configuration Debug = BETA) : Zicou compilé ; l'App Store (Release) ne le compile pas")
    func zicouIsABetaBuild() {
        #expect(AppConfig.zicouBuild)
    }
}

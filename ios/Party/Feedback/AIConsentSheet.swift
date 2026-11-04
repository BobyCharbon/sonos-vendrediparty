import SwiftUI

/// Feuille d'accord avant d'envoyer quoi que ce soit à l'IA (Apple 5.1.2(i)) : « Ton avis » et l'assistant des
/// événements. « J'accepte » est enregistré par le serveur, par compte (POST /api/feedback/ai/consent) ; fermer la
/// feuille d'un geste ne vaut pas accord.
struct AIConsentSheet: View {
    struct Copy: Equatable {
        let title: String
        let text: String
        let footnote: String
        let decline: String
        let acceptID: String
    }

    let copy: Copy
    let answer: (Bool) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(copy.title).font(.title2.weight(.bold))
            Text(copy.text)
            Text(copy.footnote).font(.subheadline).foregroundStyle(.secondary)
            Button { answer(true) } label: {
                Text("J'accepte").bold().frame(maxWidth: .infinity, minHeight: 44)
            }
            .buttonStyle(.borderedProminent).tint(Palette.accent).accessibilityIdentifier(copy.acceptID)
            Button { answer(false) } label: {
                Text(copy.decline).frame(maxWidth: .infinity, minHeight: 44)
            }
            .buttonStyle(.bordered)
        }
        .padding(24)
        .presentationDetents([.medium])
    }
}

/// Même feuille partout (texte de l'accord version 2, identique au web) ; seuls le bouton de refus et l'identifiant
/// d'accessibilité changent selon l'endroit.
extension AIConsentSheet.Copy {
    private static func shared(decline: String, acceptID: String) -> AIConsentSheet.Copy {
        AIConsentSheet.Copy(title: FeedbackAI.consentTitle, text: FeedbackAI.consentText,
                            footnote: FeedbackAI.consentFootnote, decline: decline, acceptID: acceptID)
    }

    /// « Ton avis ».
    static let feedback = shared(decline: "Écrire sans l'IA", acceptID: "feedback-ai-accept")
    /// Assistant des événements.
    static let event = shared(decline: "Pas maintenant", acceptID: "event-ai-accept")
    /// Pot commun › Scanner un ticket.
    static let receipt = shared(decline: "Saisir à la main", acceptID: "receipt-ai-accept")
}

/// Accord IA d'un compte, gardé par le serveur (même accord pour « Ton avis », les événements et les tickets).
extension PartyAPI {
    func aiConsentAccepted(web: WebStorage?, token: String) async -> Bool {
        guard let me = await web?.guestIdentity() else { return false }
        return (try? await feedbackAIStatus(guestID: me.id, token: token))?.accepted == true
    }

    func acceptAIConsent(web: WebStorage?, token: String) async throws -> Bool {
        guard let me = await web?.guestIdentity() else { return false }
        return try await feedbackAIConsent(guestID: me.id, token: token, accept: true).accepted
    }
}

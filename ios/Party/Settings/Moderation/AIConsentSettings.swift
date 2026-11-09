import SwiftUI

/// Accord « IA de Party » d'un compte (un seul pour « Ton avis », l'assistant des événements et les tickets), lu et
/// changé par POST /api/account/ai/status et /api/account/ai/consent. Réglages › Confidentialité le montre à TOUS les
/// comptes, même sans « Écrire un avis » (Apple 5.1.2(i), nLPD) : on le voit, on le retire, on le redonne.
struct AIConsentState: Decodable, Equatable {
    /// "accepted" · "declined" · "" (jamais demandé, ou texte d'accord changé)
    let consent: String
    /// Date de l'accord en cours (secondes depuis 1970) ; nil sans accord.
    let consentAt: Double?

    enum CodingKeys: String, CodingKey { case consent, consentAt = "consent_at" }

    init(consent: String, consentAt: Double?) {
        (self.consent, self.consentAt) = (consent, consentAt)
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        consent = (try? c.decode(String.self, forKey: .consent)) ?? ""
        consentAt = try? c.decode(Double.self, forKey: .consentAt)
    }

    var accepted: Bool { consent == "accepted" }

    /// « Accord donné le 9 novembre 2026 » ou « Pas d'accord ».
    var label: String {
        guard accepted else { return "Pas d'accord : l'IA n'est jamais utilisée pour toi." }
        guard let consentAt else { return "Accord donné." }
        let day = Date(timeIntervalSince1970: consentAt)
            .formatted(.dateTime.day().month(.wide).year().locale(Locale(identifier: "fr_CH")))
        return "Accord donné le \(day)."
    }
}

extension PartyAPI {
    func accountAIConsent(token: String) async throws -> AIConsentState {
        try await postDecoding("/api/account/ai/status", body: ["token": token])
    }

    func setAccountAIConsent(token: String, accept: Bool) async throws -> AIConsentState {
        try await postDecoding("/api/account/ai/consent", body: ["token": token, "accept": accept])
    }
}

extension AIConsentSheet.Copy {
    /// Réglages › Confidentialité › IA de Party : redonner son accord.
    static let settings = AIConsentSheet.Copy(title: FeedbackAI.consentTitle, text: FeedbackAI.consentText,
                                              footnote: FeedbackAI.consentFootnote, decline: "Pas maintenant",
                                              acceptID: "settings-ai-accept")
}

/// Section « IA de Party » de Réglages › Confidentialité : état de l'accord, « Retirer mon accord » ou « Donner mon
/// accord » (même feuille qu'ailleurs ; la fermer d'un geste ne vaut pas accord).
struct AIConsentSection: View {
    @ObservedObject var store: ModerationStore
    @State private var asking = false

    var body: some View {
        Section {
            if let state = store.aiConsent {
                Text(state.label).font(.subheadline).accessibilityIdentifier("ai-consent-state")
                if state.accepted {
                    Button("Retirer mon accord", role: .destructive) { Task { await store.setAIConsent(false) } }
                        .disabled(store.busy.contains("ai"))
                        .accessibilityIdentifier("ai-consent-withdraw")
                } else {
                    Button("Donner mon accord") { asking = true }
                        .disabled(store.busy.contains("ai"))
                        .accessibilityIdentifier("ai-consent-give")
                }
            } else if store.error == nil {
                ProgressView()
            }
        } header: {
            Text("IA de Party")
        } footer: {
            Text("Un seul accord pour toute l'IA de Party (Ton avis, assistant des événements, tickets). Sans accord, tout marche sans l'IA.")
        }
        .task { await store.loadAIConsent() }
        .sheet(isPresented: $asking) {
            AIConsentSheet(copy: .settings) { accept in
                asking = false
                if accept { Task { await store.setAIConsent(true) } }
            }
        }
    }
}
